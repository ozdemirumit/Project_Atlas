from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    _assert_no_step_up_language,
    _AuditSink,
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
)
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.modules.workflows.adapters import (
    DenyAllWorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier,
    UnavailableWorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor,
)
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy,
)

code_owned_handoff_policy = (
    code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy
)

ENDPOINT = (
    "/api/v1/workflows/physical-transport-target-context-capsule-handoff-authorization-leases"
)
SCOPE = WorkflowScope(
    "organization.development",
    "environment.development",
    "site.local",
)
NOW = datetime(2026, 8, 16, 18, 0, tzinfo=UTC)


def _lease(
    *,
    lease_id: str = "workflow-target-context-capsule-handoff-authorization-lease.api01",
    scope: WorkflowScope = SCOPE,
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease:
    policy = code_owned_handoff_policy()
    authority = WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority()
    values: dict[str, Any] = {
        "authorization_lease_id": lease_id,
        "consumer_binding_id": "target-context-capsule-consumer-binding.api01",
        "consumer_binding_digest": "1" * 64,
        "opening_result_id": "target-context-artifact-opening.api01",
        "opening_result_digest": "2" * 64,
        "sealed_capsule_id": "sealed-target-context-capsule.api01",
        "sealed_capsule_digest": "3" * 64,
        "capsule_schema_id": "schema.workflow-protected-target-context-capsule",
        "capsule_schema_version": "1.0",
        "lifecycle_attestation_id": "target-context-capsule-lifecycle-attestation.api01",
        "lifecycle_attestation_digest": "4" * 64,
        "lifecycle_attestation_valid_until": NOW + timedelta(minutes=1),
        "scope": scope,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "issued_at": NOW,
        "valid_until": NOW + timedelta(seconds=1),
        "effective_until": NOW + timedelta(minutes=1),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "authority": authority,
    }
    payload = {
        name: value.canonical_value()
        if isinstance(
            value,
            (WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority, WorkflowScope),
        )
        else value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if isinstance(
            value,
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState,
        )
        else value
        for name, value in values.items()
    }
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease(
        **values,
        canonical_digest=canonical_digest(payload),
    )


class _Service:
    durable = True

    def __init__(
        self,
        leases: tuple[
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease, ...
        ] = (),
        *,
        failure: (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError | None
        ) = None,
        ignore_scope: bool = False,
    ) -> None:
        self.repository = self
        self.leases = list(leases)
        self.failure = failure
        self.ignore_scope = ignore_scope
        self.authorize_calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return NOW + timedelta(milliseconds=500)

    async def list_leases(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease, ...]:
        if self.ignore_scope:
            return tuple(self.leases)[:limit]
        return tuple(lease for lease in self.leases if lease.scope == scope)[:limit]

    async def authorize(
        self, **kwargs: Any
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease:
        self.authorize_calls.append(kwargs)
        if self.failure is not None:
            raise self.failure
        lease = _lease()
        if not self.leases:
            self.leases.append(lease)
        return self.leases[0]


def _payload() -> dict[str, str]:
    policy = code_owned_handoff_policy()
    return {
        "consumer_binding_id": "target-context-capsule-consumer-binding.api01",
        "consumer_binding_digest": "1" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "target-context-capsule-handoff-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def _assert_minimized(item: dict[str, Any]) -> None:
    assert set(item) == {
        "authorization_lease_id",
        "scope",
        "consumer_contract_id",
        "consumer_contract_version",
        "purpose_id",
        "state",
        "effective_state",
        "issued_at",
        "valid_until",
        "single_use",
        "renewable",
        "transferable",
        "lease_is_bearer_capability",
        "policy",
        "authority",
        "integrity_reference",
    }
    assert item["state"] == "authorized_unconsumed"
    assert item["effective_state"] == "active"
    assert item["single_use"] is True
    assert item["renewable"] is False
    assert item["transferable"] is False
    assert item["lease_is_bearer_capability"] is False
    assert set(item["policy"]) == {"policy_id", "policy_version"}
    assert len(item["authority"]) == 18
    assert item["authority"]["target_context_capsule_handoff_authorized"] is True
    assert sum(value is True for value in item["authority"].values()) == 1
    assert datetime.fromisoformat(item["valid_until"]) - datetime.fromisoformat(
        item["issued_at"]
    ) == timedelta(seconds=1)
    forbidden = {
        "consumer_binding_id",
        "consumer_binding_digest",
        "consumer_subject_id",
        "consumer_audience",
        "opening_result_id",
        "opening_result_digest",
        "sealed_capsule_id",
        "sealed_capsule_digest",
        "lifecycle_attestation_id",
        "lifecycle_attestation_digest",
        "outbox_entry_id",
        "event_artifact_id",
        "route_binding_id",
        "credential_assignment_binding_id",
        "fencing_token",
        "idempotency_key",
        "request_fingerprint",
        "policy_digest",
        "canonical_digest",
    }
    assert not forbidden.intersection(item)


def test_exact_consumer_post_and_password_session_get_minimized_inventory() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_transport_target_context_capsule_handoff_authorization_lease_service=cast(
            Any, service
        ),
    )

    with TestClient(app) as client:
        anonymous = client.get(ENDPOINT)
        csrf = _login(client)
        human_post = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            ),
        )
        inventory = client.get(ENDPOINT)

    assert anonymous.status_code == 403
    assert human_post.status_code == 401
    assert created.status_code == 201
    _assert_minimized(dict(created.json()["data"]))
    assert inventory.status_code == 200
    items = inventory.json()["data"][
        "physical_transport_target_context_capsule_handoff_authorization_leases"
    ]
    assert len(items) == 1
    _assert_minimized(dict(items[0]))
    assert inventory.json()["data"]["durable"] is True
    for response in (anonymous, human_post, created, inventory):
        _assert_no_store(response)
    _assert_no_step_up_language(human_post.text + inventory.text)
    assert "authorized browser session" not in inventory.text.casefold()
    context = service.authorize_calls[0]["context"]
    assert context.subject_id == WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
    assert context.credential_audience == (
        WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
    )


def test_post_rejects_pat_wrong_workload_and_caller_owned_fields() -> None:
    workload_service, exact_token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    wrong_service, wrong_token = _workload_service_and_token(
        identity_id="service.workflow-protected-transport-target-context-capsule-binder",
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_transport_target_context_capsule_handoff_authorization_lease_service=cast(
            Any, service
        ),
    )
    wrong_app = create_app(
        _settings(),
        workload_identity_service=wrong_service,
        workflow_protected_transport_target_context_capsule_handoff_authorization_lease_service=cast(
            Any, service
        ),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        pat = client.post(
            ENDPOINT,
            json=_payload(),
            headers={"Authorization": f"Bearer {personal_token}"},
        )
        wrong_audience = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(exact_token, "audience.workflow.publisher"),
        )
        unsafe_payload = client.post(
            ENDPOINT,
            json={
                **_payload(),
                "sealed_capsule_id": "sealed-capsule.caller-controlled",
                "consumer_subject_id": "service.caller-controlled",
                "lifecycle_attestation": {"usable": True},
                "ttl_seconds": 60,
                "delivery_authorized": True,
            },
            headers=_workload_headers(
                exact_token,
                WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            ),
        )
    with TestClient(wrong_app) as client:
        wrong_subject = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                wrong_token,
                WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            ),
        )

    for denied in (pat, wrong_audience, wrong_subject):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_store(denied)
        _assert_no_step_up_language(denied.text)
    assert unsafe_payload.status_code == 422
    assert unsafe_payload.json()["code"] == "validation_failed"
    _assert_no_store(unsafe_payload)
    assert personal_token not in pat.text
    assert service.authorize_calls == []


def test_human_read_is_default_deny_and_scope_escape_is_non_oracle() -> None:
    denied_app = create_app(
        Settings(
            environment="development",
            development_identity_enabled=True,
            development_role_ids=("role.unassigned",),
        ),
        workflow_protected_transport_target_context_capsule_handoff_authorization_lease_service=cast(
            Any, _Service((_lease(),))
        ),
    )
    escaped = _lease(
        lease_id="workflow-target-context-capsule-handoff-authorization-lease.wrongscope",
        scope=WorkflowScope("organization.other", "environment.development", "site.local"),
    )
    escaped_app = create_app(
        _settings(),
        workflow_protected_transport_target_context_capsule_handoff_authorization_lease_service=cast(
            Any, _Service((escaped,), ignore_scope=True)
        ),
    )

    with TestClient(denied_app) as client:
        _login(client)
        denied = client.get(ENDPOINT)
    with TestClient(escaped_app) as client:
        _login(client)
        scope_escape = client.get(ENDPOINT)

    assert denied.status_code == 403
    assert denied.json()["code"] == "authorization_denied"
    assert scope_escape.status_code == 503
    assert scope_escape.json()["code"].endswith("_service_unavailable")
    assert "scope" not in scope_escape.json()["detail"].casefold()
    for response in (denied, scope_escape):
        _assert_no_store(response)
        _assert_no_step_up_language(response.text)


def test_conflicts_are_non_oracle_and_default_composition_fails_closed() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    failure = WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
        "workflow_target_context_capsule_handoff_evidence_conflict",
        "Protected-store locator, capsule digest and fencing token must remain internal.",
    )
    conflict_app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_transport_target_context_capsule_handoff_authorization_lease_service=cast(
            Any, _Service(failure=failure)
        ),
    )
    default_app = create_app(_settings(), audit_sink=_AuditSink())

    with TestClient(conflict_app) as client:
        conflict = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            ),
        )
    with TestClient(default_app) as client:
        service = (
            default_app.state.workflow_target_context_capsule_handoff_authorization_lease_service
        )
        _login(client)
        unavailable = client.get(ENDPOINT)

    assert conflict.status_code == 409
    assert conflict.json()["code"] == (
        "workflow_target_context_capsule_handoff_authorization_unavailable"
    )
    assert "locator" not in conflict.text.casefold()
    assert "evidence_conflict" not in conflict.text
    assert unavailable.status_code == 503
    assert service.durable is False
    assert isinstance(
        service._lifecycle_status_attestor,
        UnavailableWorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor,
    )
    assert isinstance(
        service._lifecycle_signature_verifier,
        DenyAllWorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier,
    )
    for response in (conflict, unavailable):
        _assert_no_store(response)
        _assert_no_step_up_language(response.text)
