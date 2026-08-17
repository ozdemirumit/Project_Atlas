from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_authorization_domain import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority,
    WorkflowProtectedRuntimeProcessCreationAuthorizationClaim,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLease,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_creation_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)


def _digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    return value


def _canonical_record_digest(values: dict[str, object]) -> str:
    return canonical_digest({name: _canonical_value(value) for name, value in values.items()})


def _source_values() -> dict[str, object]:
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    source_policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    completed_at = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
    return {
        "readiness_result_id": "readiness-result-1",
        "readiness_result_digest": _digest("readiness-result"),
        "readiness_consumption_id": "readiness-consumption-1",
        "readiness_attempt_id": "readiness-attempt-1",
        "readiness_attempt_digest": _digest("readiness-attempt"),
        "readiness_claim_id": "readiness-claim-1",
        "readiness_claim_digest": _digest("readiness-claim"),
        "readiness_authorization_lease_id": "readiness-lease-1",
        "readiness_authorization_lease_digest": _digest("readiness-lease"),
        "start_result_id": "start-result-1",
        "start_result_digest": _digest("start-result"),
        "assessor_receipt_digest": _digest("assessor-receipt"),
        "readiness_result_state": (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY,
        "readiness_failure_class": None,
        "readiness_outcome_known": True,
        "readiness_assessment_performed": True,
        "runtime_ready": True,
        "readiness_completed_at": completed_at,
        "readiness_result_recorded_at": completed_at + timedelta(milliseconds=25),
        "readiness_profile_id": source_policy.readiness_profile_id,
        "readiness_profile_version": source_policy.readiness_profile_version,
        "readiness_profile_digest": source_policy.readiness_profile_digest,
        "destination_deployment_id": "deployment-1",
        "destination_generation": 11,
        "destination_fencing_token_digest": _digest("destination-fence"),
        "protected_slot_commitment": _digest("protected-slot"),
        "protected_slot_generation": 7,
        "runtime_envelope_id": "runtime-envelope-1",
        "runtime_envelope_commitment": _digest("runtime-envelope"),
        "runtime_envelope_generation": 7,
        "scope": WorkflowScope(
            organization_id="organization-1",
            environment_id="environment-1",
            site_id="site-1",
        ),
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
    }


def _claim(**changes: object) -> WorkflowProtectedRuntimeProcessCreationAuthorizationClaim:
    source = _source_values()
    values = {
        "claim_id": "process-creation-claim-1",
        **source,
        "request_fingerprint": _digest("request"),
        "idempotency_digest": _digest("idempotency"),
        "authorization_audit_digest": _digest("audit"),
        "claimed_at": cast(datetime, source["readiness_result_recorded_at"])
        + timedelta(milliseconds=25),
        "authority": WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority(),
    }
    values.update(changes)
    return WorkflowProtectedRuntimeProcessCreationAuthorizationClaim(
        **cast(Any, values),
        canonical_digest=_canonical_record_digest(values),
    )


def _lease(**changes: object) -> WorkflowProtectedRuntimeProcessCreationAuthorizationLease:
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    claim = _claim()
    source = _source_values()
    issued_at = cast(datetime, source["readiness_result_recorded_at"]) + timedelta(milliseconds=50)
    values = {
        "authorization_lease_id": "process-creation-lease-1",
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        **source,
        "lifecycle_attestation_id": "lifecycle-attestation-1",
        "lifecycle_attestation_digest": _digest("lifecycle-attestation"),
        "lifecycle_attestation_valid_until": issued_at + timedelta(seconds=1),
        "runtime_envelope_eligible_until": issued_at + timedelta(seconds=1),
        "attestation_metadata_only": True,
        "runtime_started": True,
        "process_created": False,
        "process_scheduled": False,
        "process_creation_profile_id": policy.process_creation_profile_id,
        "process_creation_profile_version": policy.process_creation_profile_version,
        "process_creation_profile_digest": policy.process_creation_profile_digest,
        "issued_at": issued_at,
        "valid_until": issued_at + timedelta(seconds=1),
        "effective_until": issued_at + timedelta(seconds=1),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState
        ).AUTHORIZED_UNCONSUMED,
        "authority": WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority(
            protected_runtime_process_creation_authority_granted=True
        ),
    }
    values.update(changes)
    return WorkflowProtectedRuntimeProcessCreationAuthorizationLease(
        **cast(Any, values),
        canonical_digest=_canonical_record_digest(values),
    )


def test_policy_is_code_owned_bounded_single_use_and_non_bearer() -> None:
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()

    assert policy.required_source_state == "runtime_ready_in_protected_boundary"
    assert policy.maximum_lifetime_seconds == 1
    assert policy.maximum_attestation_freshness_seconds == 1
    assert policy.single_use_required is True
    assert policy.renewable_allowed is False
    assert policy.transferable_allowed is False
    assert policy.bearer_capability_allowed is False
    assert policy.durable_replay_required is True
    assert policy.fresh_attestation_required is True
    assert policy.metadata_only_attestation_required is True
    assert policy.process_created_required is False
    assert policy.process_scheduled_required is False


@pytest.mark.parametrize(
    "field_name",
    [
        "process_creation_forbidden",
        "process_control_forbidden",
        "scheduling_forbidden",
        "command_material_forbidden",
        "executable_material_forbidden",
        "argument_material_forbidden",
        "environment_material_forbidden",
        "prompt_material_forbidden",
        "model_material_forbidden",
        "runtime_material_forbidden",
        "runtime_locator_forbidden",
        "network_activity_forbidden",
        "connector_activity_forbidden",
        "mcp_activity_forbidden",
        "provider_activity_forbidden",
        "publication_forbidden",
        "delivery_forbidden",
        "dispatch_forbidden",
        "execution_forbidden",
        "infrastructure_mutation_forbidden",
    ],
)
def test_policy_explicitly_forbids_operational_material_and_activity(
    field_name: str,
) -> None:
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()

    assert getattr(policy, field_name) is True


def test_authority_grants_only_future_process_creation_request_submission() -> None:
    authority = WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority(
        protected_runtime_process_creation_authority_granted=True
    )
    values = authority.canonical_value()

    assert len(values) == 29
    assert values.pop("protected_runtime_process_creation_authority_granted") is True
    assert not any(values.values())
    assert authority.network_access_authorized is False
    assert authority.connector_activity_authorized is False
    assert authority.publication_authorized is False
    assert authority.dispatch_authorized is False
    assert authority.execution_authorized is False
    assert authority.infrastructure_mutation_authorized is False


@pytest.mark.parametrize(
    "field_name",
    [
        field.name
        for field in fields(WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority)
        if field.name != "protected_runtime_process_creation_authority_granted"
    ],
)
def test_authority_rejects_every_preexisting_authority(field_name: str) -> None:
    values = {
        field.name: False
        for field in fields(WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority)
    }
    values[field_name] = True

    with pytest.raises(ValueError):
        WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority(**values)


def test_claim_accepts_only_exact_terminal_ready_result_without_authority() -> None:
    claim = _claim()

    assert (
        claim.readiness_result_state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
    )
    assert claim.runtime_ready is True
    assert not any(claim.authority.canonical_value().values())


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        (
            "readiness_result_state",
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY,
        ),
        ("readiness_outcome_known", False),
        ("readiness_assessment_performed", False),
        ("runtime_ready", False),
        ("readiness_failure_class", "runtime_readiness_outcome_uncertain"),
        ("runtime_envelope_generation", 8),
    ],
)
def test_claim_rejects_ineligible_or_drifted_source(field_name: str, value: object) -> None:
    with pytest.raises(ValueError):
        _claim(**{field_name: value})


def test_claim_rejects_noncanonical_digest() -> None:
    claim = _claim()
    values = {
        field.name: getattr(claim, field.name)
        for field in fields(claim)
        if field.name != "canonical_digest"
    }

    with pytest.raises(ValueError, match="digest mismatch"):
        WorkflowProtectedRuntimeProcessCreationAuthorizationClaim(
            **cast(Any, values),
            canonical_digest=_digest("wrong"),
        )


def test_lease_presents_authority_only_while_active_and_unconsumed() -> None:
    lease = _lease()
    active_at = lease.issued_at + timedelta(milliseconds=500)

    assert lease.is_active(evaluated_at=active_at) is True
    assert (
        lease.presented_authority(
            evaluated_at=active_at
        ).protected_runtime_process_creation_authority_granted
        is True
    )
    assert not any(
        lease.presented_authority(evaluated_at=lease.valid_until).canonical_value().values()
    )
    assert not any(
        lease.presented_authority(evaluated_at=active_at, consumed=True).canonical_value().values()
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("process_created", True),
        ("process_scheduled", True),
        ("attestation_metadata_only", False),
        ("renewable", True),
        ("transferable", True),
        ("lease_is_bearer_capability", True),
    ],
)
def test_lease_rejects_operational_or_reusable_capability(field_name: str, value: object) -> None:
    with pytest.raises(ValueError):
        _lease(**{field_name: value})


def test_lease_rejects_lifetime_greater_than_one_second() -> None:
    baseline = _lease()
    later = baseline.issued_at + timedelta(seconds=1, microseconds=1)

    with pytest.raises(ValueError):
        _lease(
            valid_until=later,
            effective_until=later,
            lifecycle_attestation_valid_until=later,
            runtime_envelope_eligible_until=later,
        )


def test_lease_rejects_naive_presentation_time() -> None:
    lease = _lease()

    with pytest.raises(ValueError, match="must be aware"):
        lease.presented_authority(evaluated_at=datetime(2026, 8, 18, 10, 0))


def test_contract_records_are_immutable() -> None:
    lease = _lease()

    with pytest.raises(FrozenInstanceError):
        lease.process_created = True  # type: ignore[misc]


def test_claim_and_lease_are_non_transferable_and_non_renewable() -> None:
    claim = _claim()
    lease = _lease()

    assert claim.scope == lease.scope
    assert claim.readiness_result_id == lease.readiness_result_id
    assert claim.readiness_result_digest == lease.readiness_result_digest
    assert lease.single_use is True
    assert lease.renewable is False
    assert lease.transferable is False
    assert lease.lease_is_bearer_capability is False
