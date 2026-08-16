from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.workflows.adapters.protected_runtime_slot_lifecycle_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor,
    UnavailableWorkflowProtectedRuntimeSlotLifecycleAttestor,
)
from atlas.modules.workflows.application.protected_runtime_context_use_authorization_ports import (
    WorkflowProtectedRuntimeContextUseAuthorizationError,
    WorkflowProtectedRuntimeSlotLifecycleAttestationRequest,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _request(
    *, injected_context_usable_until: datetime | None = None
) -> WorkflowProtectedRuntimeSlotLifecycleAttestationRequest:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()
    return WorkflowProtectedRuntimeSlotLifecycleAttestationRequest(
        injection_result_id="injection-result.imp-220",
        injection_result_digest="1" * 64,
        injection_id="injection.imp-220",
        injection_attempt_id="injection-attempt.imp-220",
        injection_attempt_digest="2" * 64,
        injection_consumption_claim_id="injection-claim.imp-220",
        injection_consumption_claim_digest="3" * 64,
        injection_authorization_lease_id="injection-lease.imp-220",
        injection_authorization_lease_digest="4" * 64,
        injector_receipt_digest="5" * 64,
        destination_boundary_id="boundary.test",
        destination_deployment_id="deployment.test",
        destination_generation=3,
        destination_fencing_token_digest="6" * 64,
        runtime_slot_profile_id=policy.runtime_slot_profile_id,
        runtime_slot_profile_version=policy.runtime_slot_profile_version,
        runtime_slot_profile_digest=policy.runtime_slot_profile_digest,
        runtime_slot_commitment="7" * 64,
        runtime_slot_post_generation=8,
        injected_context_usable_until=(injected_context_usable_until or NOW + timedelta(seconds=1)),
        use_profile_id=policy.use_profile_id,
        use_profile_version=policy.use_profile_version,
        use_profile_digest=policy.use_profile_digest,
        scope=WorkflowScope("organization.test", "environment.test", "site.test"),
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        purpose_id=policy.purpose_id,
        request_nonce_digest="8" * 64,
        requested_at=NOW,
    )


@pytest.mark.asyncio
async def test_development_attestor_returns_signed_nonce_bound_passive_evidence() -> None:
    attestor = DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW,
    )

    attestation = await attestor.attest_runtime_slot_lifecycle(_request())

    assert len(attestor.calls) == 1
    assert attestation.request_nonce_digest == "8" * 64
    assert attestation.injected_context_usable_until == NOW + timedelta(seconds=1)
    assert attestation.valid_until == attestation.injected_context_usable_until
    assert attestation.exact_runtime_slot_confirmed is True
    assert attestation.inert_context_present is True
    assert attestation.runtime_slot_inert is True
    assert attestation.runtime_slot_unused is True
    assert attestation.runtime_use_authorized is False
    assert attestation.runtime_start_authorized is False
    assert attestation.runtime_resume_authorized is False
    assert attestation.network_activity_authorized is False
    assert attestation.connector_activity_authorized is False
    assert attestation.execution_authorized is False
    assert attestation.infrastructure_mutation_authorized is False
    assert attestor.verify_runtime_slot_lifecycle_attestation(attestation) is True
    assert (
        attestor.verify_runtime_slot_lifecycle_attestation(
            replace(attestation, request_nonce_digest="9" * 64)
        )
        is False
    )
    assert (
        attestor.verify_runtime_slot_lifecycle_attestation(
            replace(
                attestation,
                injected_context_usable_until=(
                    attestation.injected_context_usable_until + timedelta(microseconds=1)
                ),
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_development_attestor_rejects_non_positive_injected_context_ceiling() -> None:
    attestor = DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW,
    )

    with pytest.raises(WorkflowProtectedRuntimeContextUseAuthorizationError) as exc_info:
        await attestor.attest_runtime_slot_lifecycle(_request(injected_context_usable_until=NOW))

    assert exc_info.value.code == "workflow_protected_runtime_slot_lifecycle_ceiling_expired"


@pytest.mark.asyncio
async def test_development_attestor_fails_closed_when_not_explicitly_enabled() -> None:
    attestor = DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor()

    assert attestor.available is False
    with pytest.raises(WorkflowProtectedRuntimeContextUseAuthorizationError):
        await attestor.attest_runtime_slot_lifecycle(_request())


@pytest.mark.asyncio
async def test_production_default_is_unavailable_and_never_attests() -> None:
    attestor = UnavailableWorkflowProtectedRuntimeSlotLifecycleAttestor()

    assert attestor.available is False
    with pytest.raises(WorkflowProtectedRuntimeContextUseAuthorizationError):
        await attestor.attest_runtime_slot_lifecycle(_request())
