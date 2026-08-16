from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    _assert_no_step_up_language,
    _login,
    _settings,
    _workload_headers,
)
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)
from test_workflow_target_context_capsule_handoffs import make_attempt

from atlas.api.app import create_app
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffError,
    WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation,
)
from atlas.modules.workflows.domain import (
    WorkflowScope,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy,
)

ENDPOINT = "/api/v1/workflows/physical-transport-target-context-capsule-handoffs"
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")
NOW = datetime(2026, 8, 16, 20, 0, tzinfo=UTC)


class _Service:
    durable = True

    def __init__(self, *, server_time: datetime = NOW, fail_closed: bool = False) -> None:
        self.repository = self
        self.server_time = server_time
        self.fail_closed = fail_closed
        self.attempt = make_attempt(
            started_at=NOW,
            handoff_deadline=NOW + timedelta(seconds=1),
            scope=SCOPE,
        )
        self.handoff_calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return self.server_time

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation, ...]:
        if self.fail_closed:
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(
                "target_context_capsule_handoff_durable_repository_required"
            )
        if scope != self.attempt.scope:
            return ()
        return (
            WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(self.attempt, None),
        )[:limit]

    async def handoff(
        self, **kwargs: Any
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation:
        self.handoff_calls.append(kwargs)
        if self.fail_closed:
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(
                "target_context_capsule_handoff_idempotency_conflict"
            )
        return WorkflowProtectedTransportTargetContextCapsuleHandoffPresentation(self.attempt, None)


def _request_payload() -> dict[str, object]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()
    )
    return {
        "authorization_lease_id": "workflow-target-context-capsule-handoff-lease.api-213",
        "authorization_lease_digest": "a" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "target-context-capsule-handoff-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_all_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value))
    return set()


def _assert_minimized(item: dict[str, Any], *, expected_state: str) -> None:
    assert set(item) == {
        "handoff_id",
        "scope",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "consumer_contract_id",
        "consumer_contract_version",
        "purpose_id",
        "adapter_contract_id",
        "adapter_contract_version",
        "sealed_capsule_handed_off",
        "consumer_receipt_is_bearer_capability",
        "policy",
        "authority",
        "integrity_reference",
    }
    assert item["attempt_state"] == "started"
    assert item["result_state"] == expected_state
    assert item["completed_at"] is None
    assert item["sealed_capsule_handed_off"] is False
    assert item["consumer_receipt_is_bearer_capability"] is False
    authority = item["authority"]
    assert len(authority) == 18
    assert all(value is False for value in authority.values())
    forbidden = {
        "authorization_lease_id",
        "authorization_lease_digest",
        "consumer_binding_id",
        "consumer_binding_digest",
        "sealed_capsule_id",
        "sealed_capsule_digest",
        "capsule_schema_id",
        "capsule_schema_version",
        "lifecycle_attestation_id",
        "lifecycle_attestation_digest",
        "acceptance_attestation_id",
        "acceptance_attestation_digest",
        "request_nonce_digest",
        "destination_boundary_id",
        "destination_deployment_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "trusted_profile_digest",
        "consumer_receipt_id",
        "receipt_digest",
        "canonical_digest",
    }
    assert forbidden.isdisjoint(_all_keys(item))


def test_password_session_get_presents_pending_then_deadline_uncertainty_minimized() -> None:
    service = _Service(server_time=NOW + timedelta(milliseconds=500))
    app = create_app(
        _settings(),
        workflow_protected_transport_target_context_capsule_handoff_service=cast(Any, service),
    )

    with TestClient(app) as client:
        anonymous = client.get(ENDPOINT)
        _login(client)
        pending = client.get(ENDPOINT)
        service.server_time = NOW + timedelta(seconds=1)
        uncertain = client.get(ENDPOINT)

    assert anonymous.status_code == 403
    assert pending.status_code == 200
    assert uncertain.status_code == 200
    pending_data = pending.json()["data"]
    uncertain_data = uncertain.json()["data"]
    assert pending_data["durable"] is True
    assert uncertain_data["durable"] is True
    _assert_minimized(
        dict(pending_data["physical_transport_target_context_capsule_handoffs"][0]),
        expected_state="pending",
    )
    _assert_minimized(
        dict(uncertain_data["physical_transport_target_context_capsule_handoffs"][0]),
        expected_state="handoff_outcome_uncertain",
    )
    for response in (anonymous, pending, uncertain):
        _assert_no_store(response)
    _assert_no_step_up_language(pending.text + uncertain.text)
    assert "authorized browser session" not in (pending.text + uncertain.text).casefold()


def test_workload_post_is_minimized_and_human_post_is_rejected() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service(server_time=NOW + timedelta(milliseconds=500))
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_transport_target_context_capsule_handoff_service=cast(Any, service),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        human = client.post(ENDPOINT, json=_request_payload(), headers={"X-CSRF-Token": csrf})
        created = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )

    assert human.status_code == 401
    assert created.status_code == 201
    _assert_minimized(dict(created.json()["data"]), expected_state="pending")
    _assert_no_store(human)
    _assert_no_store(created)
    assert len(service.handoff_calls) == 1


def test_repository_unavailability_and_idempotency_conflict_fail_closed() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service(fail_closed=True)
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_transport_target_context_capsule_handoff_service=cast(Any, service),
    )

    with TestClient(app) as client:
        _login(client)
        inventory = client.get(ENDPOINT)
        conflict = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )

    assert inventory.status_code == 503
    assert inventory.json()["code"] == (
        "workflow_target_context_capsule_handoff_service_unavailable"
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == ("target_context_capsule_handoff_idempotency_conflict")
    _assert_no_store(inventory)
    _assert_no_store(conflict)
