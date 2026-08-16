from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
)
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)

from atlas.api.app import create_app
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
)
from atlas.modules.workflows.application.protected_resident_context_access_authorization_ports import (  # noqa: E501
    WorkflowProtectedResidentContextAccessAuthorizationPresentation,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessAuthorizationLease,
    WorkflowProtectedResidentContextAccessAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_resident_context_access_authorization_policy,
)

ENDPOINT = "/api/v1/workflows/protected-resident-context-access-authorizations"
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")
OPERATIONAL_AUTHORITY_FIELDS = (
    "endpoint_resolution_authorized",
    "route_selection_authorized",
    "route_binding_authorized",
    "credential_selection_authorized",
    "credential_assignment_binding_authorized",
    "credential_access_authorized",
    "credential_brokerage_authorized",
    "credential_resolution_authorized",
    "protected_artifact_access_authorized",
    "credential_delivery_authorized",
    "network_access_authorized",
    "readiness_probe_authorized",
    "publication_authorized",
    "delivery_authorized",
    "dispatch_authorized",
    "execution_authorized",
    "infrastructure_mutation_authorized",
    "target_context_capsule_handoff_authorized",
    "target_context_capsule_opening_authorized",
)


def _canonical_payload(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in values.items()
    }


def _lease() -> WorkflowProtectedResidentContextAccessAuthorizationLease:
    policy = code_owned_workflow_protected_resident_context_access_authorization_policy()
    values: dict[str, object] = {
        "authorization_lease_id": (
            "workflow-protected-resident-context-access-lease.0123456789abcdef01234567"
        ),
        "claim_id": "claim.resident-context-access.api-imp-216",
        "claim_digest": "1" * 64,
        "opening_id": "opening.api-imp-215",
        "opening_result_digest": "a" * 64,
        "opening_attempt_id": "attempt.opening.api-imp-215",
        "opening_attempt_digest": "2" * 64,
        "opening_consumption_claim_id": "claim.opening.api-imp-215",
        "opening_consumption_claim_digest": "3" * 64,
        "opening_authorization_lease_id": "lease.opening.api-imp-214",
        "opening_authorization_lease_digest": "4" * 64,
        "opening_receipt_digest": "5" * 64,
        "opening_result_state": (
            WorkflowProtectedTransportTargetContextCapsuleOpeningResultState.OPENED_IN_PROTECTED_CONSUMER_BOUNDARY
        ),
        "opening_completed_at": NOW - timedelta(seconds=1),
        "opening_deadline": NOW,
        "protected_resident_context_id": "resident-context.api-imp-215",
        "protected_resident_context_digest": "6" * 64,
        "protected_resident_context_created_at": NOW - timedelta(seconds=1),
        "protected_resident_context_usable_until": NOW + timedelta(seconds=10),
        "protected_resident_context_is_bearer_capability": False,
        "capsule_opened_in_protected_boundary": True,
        "target_context_pair_verified": True,
        "opening_outcome_known": True,
        "protected_source_closed": True,
        "source_capsule_zeroized": True,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "lifecycle_attestation_id": "attestation.resident-context.api-imp-216",
        "lifecycle_attestation_digest": "7" * 64,
        "lifecycle_attestation_valid_until": NOW + timedelta(seconds=2),
        "issued_at": NOW,
        "valid_until": NOW + timedelta(seconds=1),
        "effective_until": NOW + timedelta(seconds=1),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedResidentContextAccessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        **{name: False for name in OPERATIONAL_AUTHORITY_FIELDS},
        "protected_resident_context_access_authority_granted": True,
    }
    return WorkflowProtectedResidentContextAccessAuthorizationLease(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_payload(values))
    )


class _Service:
    durable = True

    def __init__(self) -> None:
        self.repository = self
        self.lease: WorkflowProtectedResidentContextAccessAuthorizationLease | None = None
        self.consumed_lease_ids: set[str] = set()
        self.calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return NOW + timedelta(milliseconds=500)

    async def authorize(
        self, **kwargs: Any
    ) -> WorkflowProtectedResidentContextAccessAuthorizationLease:
        self.calls.append(kwargs)
        self.lease = _lease()
        return self.lease

    def _presentation(
        self, lease: WorkflowProtectedResidentContextAccessAuthorizationLease
    ) -> WorkflowProtectedResidentContextAccessAuthorizationPresentation:
        return WorkflowProtectedResidentContextAccessAuthorizationPresentation(
            lease=lease,
            consumed=lease.authorization_lease_id in self.consumed_lease_ids,
            evaluated_at=NOW + timedelta(milliseconds=500),
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedResidentContextAccessAuthorizationPresentation, ...]:
        del limit
        return (
            ()
            if self.lease is None or self.lease.scope != scope
            else (self._presentation(self.lease),)
        )

    async def get_presentation(
        self, *, scope: WorkflowScope, authorization_lease_id: str
    ) -> WorkflowProtectedResidentContextAccessAuthorizationPresentation:
        assert self.lease is not None
        assert self.lease.scope == scope
        assert self.lease.authorization_lease_id == authorization_lease_id
        return self._presentation(self.lease)


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def authorize(
        self, **kwargs: Any
    ) -> WorkflowProtectedResidentContextAccessAuthorizationLease:
        del kwargs
        raise RuntimeError("database unavailable")

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedResidentContextAccessAuthorizationPresentation, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")

    async def get_presentation(
        self, *, scope: WorkflowScope, authorization_lease_id: str
    ) -> WorkflowProtectedResidentContextAccessAuthorizationPresentation:
        del scope, authorization_lease_id
        raise RuntimeError("database unavailable")


def _payload() -> dict[str, str]:
    policy = code_owned_workflow_protected_resident_context_access_authorization_policy()
    return {
        "opening_result_id": "opening.imp-215",
        "opening_result_digest": "a" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "resident-access-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_workload_only_post_and_password_session_get_are_minimized() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_resident_context_access_authorization_service=cast(Any, service),
    )
    with TestClient(app) as client:
        anonymous = client.get(ENDPOINT)
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        human_post = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
        assert service.lease is not None
        service.consumed_lease_ids.add(service.lease.authorization_lease_id)
        replayed = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
        inventory = client.get(ENDPOINT)
        client.cookies.clear()
        personal_inventory = client.get(
            ENDPOINT, headers={"Authorization": f"Bearer {personal_token}"}
        )
        workload_inventory = client.get(
            ENDPOINT,
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )

    assert anonymous.status_code == 403
    assert human_post.status_code == 401
    assert created.status_code == 201
    assert replayed.status_code == 201
    assert inventory.status_code == 200
    assert personal_inventory.status_code == 403
    assert workload_inventory.status_code == 401
    item = dict(created.json()["data"])
    assert set(item) == {
        "authorization_lease_id",
        "state",
        "effective_state",
        "issued_at",
        "valid_until",
        "effective_until",
        "consumer_contract_id",
        "consumer_contract_version",
        "purpose_id",
        "policy_id",
        "policy_version",
        "destination_profile_reference",
        "authority",
        "integrity_reference",
    }
    assert item["state"] == "authorized_unconsumed"
    assert item["effective_state"] == "active"
    assert item["authority"]["protected_access_authority_granted"] is True
    assert sum(value is True for value in item["authority"].values()) == 1
    assert item["destination_profile_reference"].startswith("integrity.")
    assert item["integrity_reference"].startswith("integrity.")
    forbidden_top_level_fragments = {
        "opening",
        "capsule",
        "receipt",
        "resident_context",
        "attestation",
        "nonce",
        "target",
        "idempotency",
        "fingerprint",
        "fence",
    }
    assert not any(fragment in key for key in item for fragment in forbidden_top_level_fragments)
    consumed_item = inventory.json()["data"]["authorizations"][0]
    assert consumed_item["state"] == "consumed"
    assert consumed_item["effective_state"] == "consumed"
    assert consumed_item["authority"]["protected_access_authority_granted"] is False
    assert set(consumed_item["authority"].values()) == {False}
    replayed_item = replayed.json()["data"]
    assert replayed_item["state"] == "consumed"
    assert replayed_item["effective_state"] == "consumed"
    assert set(replayed_item["authority"].values()) == {False}
    for response in (
        anonymous,
        human_post,
        created,
        replayed,
        inventory,
        personal_inventory,
        workload_inventory,
    ):
        _assert_no_store(response)


def test_post_forbids_caller_owned_lifetime_authority_and_internal_fields() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_resident_context_access_authorization_service=cast(Any, service),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    with TestClient(app) as client:
        for field, value in (
            ("ttl_seconds", 300),
            ("authority", {"execution_authorized": True}),
            ("lifecycle_attestation_id", "attestation.untrusted"),
            ("protected_resident_context_id", "resident-context.untrusted"),
        ):
            response = client.post(ENDPOINT, json={**_payload(), field: value}, headers=headers)
            assert response.status_code == 422
            _assert_no_store(response)
    assert service.calls == []


def test_repository_outages_fail_closed_as_non_oracle_no_store_503() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_resident_context_access_authorization_service=cast(
            Any, _FailingService()
        ),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        _login(client)
        inventory = client.get(ENDPOINT)
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
    for response in (inventory, created):
        assert response.status_code == 503
        assert response.json()["code"] == (
            "workflow_protected_access_authorization_service_unavailable"
        )
        assert "evidence" not in response.json()["detail"].lower()
        _assert_no_store(response)


def test_wrong_workload_identity_cannot_issue_authorization() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id="service.workflow-unrelated",
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_resident_context_access_authorization_service=cast(Any, service),
    )
    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
    assert response.status_code == 401
    _assert_no_store(response)
    assert service.calls == []
