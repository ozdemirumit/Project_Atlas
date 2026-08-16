from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import _login, _settings, _workload_headers
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)

from atlas.api.app import create_app
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy,
)

ENDPOINT = (
    "/api/v1/workflows/physical-transport-target-context-capsule-opening-authorization-leases"
)
NOW = datetime(2026, 8, 16, 20, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _lease() -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease:
    policy = code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy()  # noqa: E501
    values: dict[str, Any] = {
        "authorization_lease_id": (
            "workflow-target-context-capsule-opening-authorization-lease.api01"
        ),
        "handoff_id": "workflow-target-context-capsule-handoff.api01",
        "handoff_result_digest": "1" * 64,
        "attempt_id": "workflow-target-context-capsule-handoff-attempt.api01",
        "attempt_digest": "2" * 64,
        "consumption_claim_id": "workflow-target-context-capsule-handoff-claim.api01",
        "consumption_claim_digest": "3" * 64,
        "upstream_authorization_lease_id": "workflow-target-context-capsule-handoff-lease.api01",
        "upstream_authorization_lease_digest": "4" * 64,
        "consumer_binding_id": "target-context-capsule-consumer-binding.api01",
        "consumer_binding_digest": "5" * 64,
        "sealed_capsule_id": "sealed-target-context-capsule.api01",
        "sealed_capsule_digest": "6" * 64,
        "consumer_receipt_id": "consumer-receipt.api01",
        "receipt_digest": "7" * 64,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "custody_contract_id": policy.custody_contract_id,
        "custody_contract_version": policy.custody_contract_version,
        "approved_adapter_id": policy.approved_adapter_id,
        "approved_adapter_version": policy.approved_adapter_version,
        "verification_signing_key_id": policy.verification_signing_key_id,
        "trusted_profile_digest": policy.trusted_profile_digest,
        "custody_attestation_id": "destination-custody-attestation.api01",
        "custody_attestation_digest": "8" * 64,
        "custody_attestation_valid_until": NOW + timedelta(seconds=5),
        "scope": SCOPE,
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
        "effective_until": NOW + timedelta(seconds=5),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority(),
    }
    payload = {
        name: value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if hasattr(value, "value")
        else value.canonical_value()
        if hasattr(value, "canonical_value")
        else value
        for name, value in values.items()
    }
    return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease(
        **values, canonical_digest=canonical_digest(payload)
    )


class _Service:
    durable = True

    def __init__(self) -> None:
        self.repository = self
        self.lease: (
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease | None
        ) = None
        self.calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return NOW + timedelta(milliseconds=500)

    async def authorize(
        self, **kwargs: Any
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease:
        self.calls.append(kwargs)
        self.lease = _lease()
        return self.lease

    async def list_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease, ...]:
        del limit
        return () if self.lease is None or self.lease.scope != scope else (self.lease,)


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def authorize(
        self, **kwargs: Any
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease:
        del kwargs
        raise RuntimeError("database unavailable")

    async def list_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")


def _payload() -> dict[str, str]:
    policy = code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy()  # noqa: E501
    return {
        "handoff_result_id": "workflow-target-context-capsule-handoff.api01",
        "handoff_result_digest": "1" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "opening-authorization-api-0001",
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
        workflow_protected_transport_target_context_capsule_opening_authorization_lease_service=cast(
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
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
        inventory = client.get(ENDPOINT)
    assert anonymous.status_code == 403
    assert human_post.status_code == 401
    assert created.status_code == 201
    assert inventory.status_code == 200
    item = dict(created.json()["data"])
    assert set(item) == {
        "authorization_lease_id",
        "scope",
        "state",
        "effective_state",
        "issued_at",
        "valid_until",
        "single_use",
        "renewable",
        "transferable",
        "lease_is_bearer_capability",
        "consumer_contract_id",
        "consumer_contract_version",
        "purpose_id",
        "destination_custody_profile_reference",
        "policy_id",
        "policy_version",
        "authority",
        "integrity_reference",
    }
    assert item["authority"]["target_context_capsule_opening_authorized"] is True
    assert item["consumer_contract_id"] == (
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    )
    assert item["purpose_id"] == (
        "purpose.workflow-protected-transport-target-context-capsule-opening-evaluation"
    )
    assert item["destination_custody_profile_reference"].startswith("integrity.")
    assert sum(value is True for value in item["authority"].values()) == 1
    forbidden = {
        "handoff_id",
        "handoff_result_digest",
        "sealed_capsule_id",
        "consumer_receipt_id",
        "custody_attestation_digest",
        "destination_fencing_token_digest",
        "trusted_profile_digest",
        "canonical_digest",
    }
    assert not forbidden.intersection(item)
    for response in (anonymous, human_post, created, inventory):
        _assert_no_store(response)


def test_post_forbids_caller_owned_ttl_authority_and_opener_fields() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_transport_target_context_capsule_opening_authorization_lease_service=cast(
            Any, service
        ),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    with TestClient(app) as client:
        for field, value in (
            ("ttl_seconds", 300),
            ("authority", {"protected_artifact_access_authorized": True}),
            ("opener_id", "opener.untrusted"),
            ("sealed_capsule_id", "sealed-target-context-capsule.api01"),
        ):
            response = client.post(ENDPOINT, json={**_payload(), field: value}, headers=headers)
            assert response.status_code == 422
            _assert_no_store(response)
    assert service.calls == []


def test_repository_outages_fail_closed_as_no_store_503_for_get_and_post() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_transport_target_context_capsule_opening_authorization_lease_service=cast(
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
            "workflow_target_context_capsule_opening_authorization_service_unavailable"
        )
        _assert_no_store(response)


def test_wrong_workload_identity_cannot_issue_opening_authorization() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id="service.workflow-unrelated",
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_transport_target_context_capsule_opening_authorization_lease_service=cast(
            Any, service
        ),
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
