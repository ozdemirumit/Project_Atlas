from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    WorkflowProtectedRuntimeProcessCreationConsumptionResultState,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
)
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_authorization_domain import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_scheduling_authorization_policy,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope(
    organization_id="organization.test",
    environment_id="environment.test",
    site_id="site.test",
)


def _digest(value: str) -> str:
    return canonical_digest({"value": value})


def _canonical_values(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if hasattr(value, "value")
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in values.items()
    }


def _claim_and_lease() -> tuple[
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease,
]:
    policy = code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()
    source_policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
    source_values: dict[str, object] = {
        "process_creation_result_id": "process-creation-result.test",
        "process_creation_result_digest": _digest("process-creation-result"),
        "process_creation_consumption_id": "process-creation-consumption.test",
        "process_creation_attempt_id": "process-creation-attempt.test",
        "process_creation_attempt_digest": _digest("process-creation-attempt"),
        "process_creation_claim_id": "process-creation-claim.test",
        "process_creation_claim_digest": _digest("process-creation-claim"),
        "process_creation_authorization_lease_id": "process-creation-auth-lease.test",
        "process_creation_authorization_lease_digest": _digest("process-creation-auth-lease"),
        "process_creation_authorization_claim_id": "process-creation-auth-claim.test",
        "process_creation_authorization_claim_digest": _digest("process-creation-auth-claim"),
        "process_creation_receipt_digest": _digest("process-creation-receipt"),
        "process_creation_result_state": (
            WorkflowProtectedRuntimeProcessCreationConsumptionResultState
        ).PROCESS_CREATED_SUSPENDED_IN_PROTECTED_BOUNDARY,
        "process_creation_failure_class": None,
        "process_creation_outcome_known": True,
        "process_created": True,
        "process_sealed": True,
        "process_suspended": True,
        "process_scheduled": False,
        "process_resumed": False,
        "process_dispatched": False,
        "process_executed": False,
        "process_creation_completed_at": NOW - timedelta(milliseconds=300),
        "process_creation_result_recorded_at": NOW - timedelta(milliseconds=200),
        "destination_deployment_id": SCOPE.site_id,
        "destination_generation": 7,
        "destination_fencing_token_digest": _digest("runtime-envelope"),
        "protected_slot_commitment": _digest("runtime-envelope"),
        "protected_slot_generation": 7,
        "runtime_envelope_id": "runtime-envelope.test",
        "runtime_envelope_commitment": _digest("runtime-envelope"),
        "runtime_envelope_generation": 7,
        "process_creation_profile_id": source_policy.process_creation_profile_id,
        "process_creation_profile_version": source_policy.process_creation_profile_version,
        "process_creation_profile_digest": source_policy.process_creation_profile_digest,
        "primitive_id": source_policy.primitive_id,
        "primitive_version": source_policy.primitive_version,
        "primitive_digest": source_policy.primitive_digest,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
    }
    claim_values = {
        **source_values,
        "claim_id": "process-scheduling-auth-claim.test",
        "request_fingerprint": _digest("request"),
        "idempotency_digest": _digest("idempotency"),
        "authorization_audit_digest": _digest("audit"),
        "claimed_at": NOW,
        "authority": WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority(),
    }
    claim = WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim(
        **cast(Any, claim_values),
        canonical_digest=canonical_digest(_canonical_values(claim_values)),
    )
    lease_values = {
        **source_values,
        "authorization_lease_id": "process-scheduling-auth-lease.test",
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        "process_state_attestation_id": "process-state-attestation.test",
        "process_state_attestation_digest": _digest("process-state-attestation"),
        "process_state_attestation_valid_until": NOW + timedelta(milliseconds=900),
        "process_state_eligible_until": NOW + timedelta(seconds=1),
        "attestation_metadata_only": True,
        "scheduling_profile_id": policy.scheduling_profile_id,
        "scheduling_profile_version": policy.scheduling_profile_version,
        "scheduling_profile_digest": policy.scheduling_profile_digest,
        "issued_at": NOW,
        "valid_until": NOW + timedelta(milliseconds=900),
        "effective_until": NOW + timedelta(milliseconds=900),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "authority": WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority(
            protected_runtime_process_scheduling_authority_granted=True
        ),
    }
    lease = WorkflowProtectedRuntimeProcessSchedulingAuthorizationLease(
        **cast(Any, lease_values),
        canonical_digest=canonical_digest(_canonical_values(lease_values)),
    )
    return claim, lease


def test_policy_is_code_owned_bounded_and_nonoperational() -> None:
    policy = code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()

    assert policy.maximum_lifetime_seconds == 1
    assert policy.single_use_required is True
    assert policy.renewable_allowed is False
    assert policy.transferable_allowed is False
    assert policy.bearer_capability_allowed is False
    assert policy.scheduling_forbidden is True
    assert policy.resume_forbidden is True
    assert policy.dispatch_forbidden is True
    assert policy.execution_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.infrastructure_mutation_forbidden is True

    with pytest.raises(ValueError, match="code-owned"):
        replace(policy, maximum_lifetime_seconds=2)


def test_authority_rejects_every_operational_grant() -> None:
    with pytest.raises(ValueError, match="operational authority"):
        WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority(
            protected_runtime_process_scheduling_authority_granted=True,
            dispatch_authorized=True,
        )


def test_lease_exposes_only_active_future_request_authority() -> None:
    claim, lease = _claim_and_lease()

    assert claim.authority.protected_runtime_process_scheduling_authority_granted is False
    assert lease.is_active(evaluated_at=NOW)
    active = lease.presented_authority(evaluated_at=NOW)
    assert active.protected_runtime_process_scheduling_authority_granted is True
    active_values = active.canonical_value()
    active_values.pop("protected_runtime_process_scheduling_authority_granted")
    assert not any(active_values.values())

    assert not lease.is_active(evaluated_at=lease.valid_until)
    assert not lease.is_active(evaluated_at=NOW, consumed=True)
    assert not any(
        lease.presented_authority(evaluated_at=lease.valid_until).canonical_value().values()
    )


def test_source_snapshot_rejects_runtime_fence_drift() -> None:
    claim, _ = _claim_and_lease()
    values = {name: getattr(claim, name) for name in claim.__slots__ if name != "canonical_digest"}
    values["destination_fencing_token_digest"] = _digest("different-envelope")

    with pytest.raises(ValueError, match="source is ineligible"):
        WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaim(
            **values,
            canonical_digest=canonical_digest(_canonical_values(values)),
        )
