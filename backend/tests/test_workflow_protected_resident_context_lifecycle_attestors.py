from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

import atlas.modules.workflows.adapters.protected_resident_context_lifecycle_attestors as module
from atlas.modules.workflows.adapters import (
    DenyAllWorkflowProtectedResidentContextLifecycleSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedResidentContextLifecycleAttestor,
    UnavailableWorkflowProtectedResidentContextLifecycleAttestor,
)
from atlas.modules.workflows.application import (
    WorkflowProtectedResidentContextAccessAuthorizationError,
    WorkflowProtectedResidentContextLifecycleAttestationRequest,
)
from atlas.modules.workflows.domain import WorkflowScope

NOW = datetime(2026, 8, 16, 22, 0, tzinfo=UTC)


class _Policy:
    required_attestor_id = "attestor.workflow-protected-resident-context-lifecycle"
    required_attestor_version = "1.0"
    verification_signing_key_id = "key.workflow-protected-resident-context-lifecycle.v1"


def _request(
    *, nonce: str = "9" * 64
) -> WorkflowProtectedResidentContextLifecycleAttestationRequest:
    return WorkflowProtectedResidentContextLifecycleAttestationRequest(
        opening_id="workflow-target-context-capsule-opening.imp-216",
        opening_result_digest="1" * 64,
        opening_attempt_id="workflow-target-context-capsule-opening-attempt.imp-216",
        opening_attempt_digest="2" * 64,
        opening_consumption_claim_id="workflow-target-context-capsule-opening-claim.imp-216",
        opening_consumption_claim_digest="3" * 64,
        opening_authorization_lease_id="workflow-target-context-capsule-opening-lease.imp-216",
        opening_authorization_lease_digest="4" * 64,
        opening_receipt_digest="5" * 64,
        opening_receipt_signing_key_id="key.workflow-capsule-opening-receipt.v1",
        protected_resident_context_id="protected-resident-context.imp-216",
        protected_resident_context_digest="6" * 64,
        protected_resident_context_created_at=NOW - timedelta(seconds=1),
        protected_resident_context_usable_until=NOW + timedelta(seconds=10),
        destination_boundary_id="boundary.workflow-protected-consumer",
        destination_deployment_id="deployment.workflow-protected-consumer",
        destination_generation=1,
        destination_fencing_token_digest="7" * 64,
        scope=WorkflowScope("org-atlas", "environment-lab", "site-istanbul"),
        consumer_subject_id=(
            "service.workflow-protected-transport-target-context-capsule-consumer"
        ),
        consumer_audience=("audience.workflow-protected-transport-target-context-capsule-consumer"),
        consumer_contract_id=(
            "contract.workflow-protected-transport-target-context-capsule-consumer"
        ),
        consumer_contract_version="1.0",
        purpose_id="purpose.workflow-protected-resident-context-access-evaluation",
        request_nonce_digest=nonce,
        requested_at=NOW,
    )


@pytest.mark.asyncio
async def test_guarded_development_attestor_is_deterministic_signed_and_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "code_owned_workflow_protected_resident_context_access_authorization_policy",
        lambda: _Policy(),
    )
    attestor = DeterministicDevelopmentWorkflowProtectedResidentContextLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW + timedelta(milliseconds=100),
    )

    first = await attestor.attest_resident_context_lifecycle(_request())
    second = await attestor.attest_resident_context_lifecycle(_request())

    assert first == second
    assert first.request_nonce_digest == "9" * 64
    assert first.resident_context_present is True
    assert first.resident_context_unexpired is True
    assert all(
        value is False
        for value in (
            first.resident_context_is_bearer_capability,
            first.resident_context_handle_outstanding,
            first.raw_context_included,
            first.endpoint_included,
            first.credential_included,
            first.secret_included,
            first.bearer_token_included,
            first.locator_included,
            first.provider_payload_included,
            first.runtime_handle_creation_authorized,
            first.network_activity_authorized,
            first.execution_authorized,
            first.infrastructure_mutation_authorized,
        )
    )
    assert first.resident_context_unrevoked is True
    assert first.resident_context_undestroyed is True
    assert first.resident_context_unconsumed is True
    assert attestor.verify_lifecycle_attestation(first) is True
    assert (
        attestor.verify_lifecycle_attestation(replace(first, integrity_signature="0" * 64)) is False
    )
    assert {
        "raw_context",
        "runtime_handle",
        "endpoint",
        "credential",
        "secret",
        "bearer_token",
        "locator",
        "provider_payload",
    }.isdisjoint(field.name for field in fields(first))

    changed_nonce = await attestor.attest_resident_context_lifecycle(_request(nonce="8" * 64))
    assert changed_nonce.attestation_id != first.attestation_id
    assert changed_nonce.integrity_signature != first.integrity_signature


@pytest.mark.asyncio
async def test_development_attestor_is_disabled_by_default_without_request_leakage() -> None:
    request = _request()
    attestor = DeterministicDevelopmentWorkflowProtectedResidentContextLifecycleAttestor()

    with pytest.raises(WorkflowProtectedResidentContextAccessAuthorizationError) as caught:
        await attestor.attest_resident_context_lifecycle(request)

    assert caught.value.code.endswith("development_attestor_disabled")
    rendered = f"{caught.value} {caught.value.detail}"
    assert request.protected_resident_context_id not in rendered
    assert request.request_nonce_digest not in rendered
    assert attestor.calls == []


@pytest.mark.asyncio
async def test_unavailable_and_deny_all_adapters_fail_closed() -> None:
    unavailable = UnavailableWorkflowProtectedResidentContextLifecycleAttestor()
    with pytest.raises(WorkflowProtectedResidentContextAccessAuthorizationError):
        await unavailable.attest_resident_context_lifecycle(_request())

    verifier = DenyAllWorkflowProtectedResidentContextLifecycleSignatureVerifier()
    assert verifier.verify_lifecycle_attestation(cast(Any, None)) is False
