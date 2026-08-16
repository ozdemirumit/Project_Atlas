from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessConsumptionAttempt,
    WorkflowProtectedResidentContextAccessConsumptionAttemptState,
    WorkflowProtectedResidentContextAccessConsumptionAuthority,
    WorkflowProtectedResidentContextAccessConsumptionClaim,
    WorkflowProtectedResidentContextAccessConsumptionFailureClass,
    WorkflowProtectedResidentContextAccessConsumptionResult,
    WorkflowProtectedResidentContextAccessConsumptionResultState,
    WorkflowProtectedResidentContextTrustedAccessorInstruction,
    WorkflowProtectedResidentContextTrustedAccessorReceipt,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_resident_context_access_consumption_policy,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
ACCESS_DEADLINE = NOW + timedelta(milliseconds=500)
LEASE_VALID_UNTIL = NOW + timedelta(milliseconds=800)
RESIDENT_USABLE_UNTIL = NOW + timedelta(seconds=2)
STATES = WorkflowProtectedResidentContextAccessConsumptionResultState
FAILURES = WorkflowProtectedResidentContextAccessConsumptionFailureClass
SUCCESS = STATES.HANDLE_ESTABLISHED_IN_PROTECTED_BOUNDARY
FAILED = STATES.RESIDENT_CONTEXT_ACCESS_FAILED
UNCERTAIN = STATES.ACCESS_OUTCOME_UNCERTAIN


def _payload(values: dict[str, object]) -> dict[str, object]:
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


def _claim() -> WorkflowProtectedResidentContextAccessConsumptionClaim:
    policy = code_owned_workflow_protected_resident_context_access_consumption_policy()
    values: dict[str, object] = {
        "claim_id": "resident-context-access-consumption-claim.imp-217",
        "access_id": "resident-context-access.imp-217",
        "attempt_id": "resident-context-access-attempt.imp-217",
        "authorization_lease_id": "resident-context-access-lease.imp-216",
        "authorization_lease_digest": "1" * 64,
        "authorization_claim_id": "resident-context-access-claim.imp-216",
        "authorization_claim_digest": "2" * 64,
        "opening_id": "target-context-capsule-opening.imp-215",
        "opening_result_digest": "3" * 64,
        "protected_resident_context_id": "protected-resident-context.imp-215",
        "protected_resident_context_digest": "4" * 64,
        "scope": WorkflowScope("org-atlas", "environment-lab", "site-istanbul"),
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "request_fingerprint": "5" * 64,
        "idempotency_digest": "6" * 64,
        "consumption_authorization_audit_digest": "7" * 64,
        "claimed_at": NOW,
        "authority": WorkflowProtectedResidentContextAccessConsumptionAuthority(),
    }
    return WorkflowProtectedResidentContextAccessConsumptionClaim(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _attempt() -> WorkflowProtectedResidentContextAccessConsumptionAttempt:
    policy = code_owned_workflow_protected_resident_context_access_consumption_policy()
    claim = _claim()
    values: dict[str, object] = {
        "attempt_id": claim.attempt_id,
        "access_id": claim.access_id,
        "consumption_claim_id": claim.claim_id,
        "consumption_claim_digest": claim.canonical_digest,
        "authorization_lease_id": claim.authorization_lease_id,
        "authorization_lease_digest": claim.authorization_lease_digest,
        "protected_resident_context_id": claim.protected_resident_context_id,
        "protected_resident_context_digest": claim.protected_resident_context_digest,
        "scope": claim.scope,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "required_accessor_contract_id": policy.required_accessor_contract_id,
        "required_accessor_contract_version": policy.required_accessor_contract_version,
        "approved_accessor_id": policy.approved_accessor_id,
        "approved_accessor_version": policy.approved_accessor_version,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "runtime_handle_profile_id": policy.runtime_handle_profile_id,
        "runtime_handle_profile_version": policy.runtime_handle_profile_version,
        "runtime_handle_profile_digest": policy.runtime_handle_profile_digest,
        "verification_signing_key_id": policy.verification_signing_key_id,
        "lifecycle_attestation_id": "resident-context-lifecycle.imp-217",
        "lifecycle_attestation_digest": "8" * 64,
        "readiness_attestation_id": "resident-context-accessor-readiness.imp-217",
        "readiness_attestation_digest": "9" * 64,
        "request_nonce_digest": "a" * 64,
        "started_at": NOW,
        "access_deadline": ACCESS_DEADLINE,
        "authorization_lease_valid_until": LEASE_VALID_UNTIL,
        "protected_resident_context_usable_until": RESIDENT_USABLE_UNTIL,
        "lifecycle_attestation_valid_until": NOW + timedelta(milliseconds=900),
        "readiness_attestation_valid_until": NOW + timedelta(milliseconds=850),
        "state": WorkflowProtectedResidentContextAccessConsumptionAttemptState.STARTED,
        "authority": WorkflowProtectedResidentContextAccessConsumptionAuthority(),
    }
    return WorkflowProtectedResidentContextAccessConsumptionAttempt(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _instruction() -> WorkflowProtectedResidentContextTrustedAccessorInstruction:
    attempt = _attempt()
    values: dict[str, object] = {
        "access_id": attempt.access_id,
        "attempt_id": attempt.attempt_id,
        "consumption_claim_id": attempt.consumption_claim_id,
        "authorization_lease_id": attempt.authorization_lease_id,
        "authorization_lease_digest": attempt.authorization_lease_digest,
        "protected_resident_context_id": attempt.protected_resident_context_id,
        "protected_resident_context_digest": attempt.protected_resident_context_digest,
        "consumer_subject_id": attempt.consumer_subject_id,
        "consumer_audience": attempt.consumer_audience,
        "consumer_contract_id": attempt.consumer_contract_id,
        "consumer_contract_version": attempt.consumer_contract_version,
        "purpose_id": attempt.purpose_id,
        "policy_id": attempt.policy_id,
        "policy_version": attempt.policy_version,
        "policy_digest": attempt.policy_digest,
        "accessor_contract_id": attempt.required_accessor_contract_id,
        "accessor_contract_version": attempt.required_accessor_contract_version,
        "accessor_id": attempt.approved_accessor_id,
        "accessor_version": attempt.approved_accessor_version,
        "destination_boundary_id": attempt.destination_boundary_id,
        "destination_deployment_id": attempt.destination_deployment_id,
        "destination_generation": attempt.destination_generation,
        "destination_fencing_token_digest": attempt.destination_fencing_token_digest,
        "runtime_handle_profile_id": attempt.runtime_handle_profile_id,
        "runtime_handle_profile_version": attempt.runtime_handle_profile_version,
        "runtime_handle_profile_digest": attempt.runtime_handle_profile_digest,
        "lifecycle_attestation_digest": attempt.lifecycle_attestation_digest,
        "readiness_attestation_digest": attempt.readiness_attestation_digest,
        "request_nonce_digest": attempt.request_nonce_digest,
        "started_at": attempt.started_at,
        "access_deadline": attempt.access_deadline,
        "protected_resident_context_usable_until": (
            attempt.protected_resident_context_usable_until
        ),
    }
    return WorkflowProtectedResidentContextTrustedAccessorInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _receipt(
    state: WorkflowProtectedResidentContextAccessConsumptionResultState = SUCCESS,
) -> WorkflowProtectedResidentContextTrustedAccessorReceipt:
    policy = code_owned_workflow_protected_resident_context_access_consumption_policy()
    instruction = _instruction()
    succeeded = state is SUCCESS
    values: dict[str, object] = {
        "access_id": instruction.access_id,
        "attempt_id": instruction.attempt_id,
        "consumption_claim_id": instruction.consumption_claim_id,
        "instruction_digest": instruction.canonical_digest,
        "authorization_lease_id": instruction.authorization_lease_id,
        "authorization_lease_digest": instruction.authorization_lease_digest,
        "protected_resident_context_id": instruction.protected_resident_context_id,
        "protected_resident_context_digest": instruction.protected_resident_context_digest,
        "accessor_contract_id": policy.required_accessor_contract_id,
        "accessor_contract_version": policy.required_accessor_contract_version,
        "accessor_id": policy.approved_accessor_id,
        "accessor_version": policy.approved_accessor_version,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "runtime_handle_profile_id": policy.runtime_handle_profile_id,
        "runtime_handle_profile_version": policy.runtime_handle_profile_version,
        "runtime_handle_profile_digest": policy.runtime_handle_profile_digest,
        "state": state,
        "failure_class": None if succeeded else FAILURES.TRUSTED_ACCESSOR_REJECTED,
        "protected_runtime_handle_id": (
            "protected-runtime-context-handle.imp-217" if succeeded else None
        ),
        "protected_runtime_handle_digest": "b" * 64 if succeeded else None,
        "protected_runtime_handle_created_at": (
            NOW + timedelta(milliseconds=250) if succeeded else None
        ),
        "protected_runtime_handle_usable_until": (
            NOW + timedelta(milliseconds=1500) if succeeded else None
        ),
        "protected_runtime_handle_is_bearer_capability": False,
        "protected_resident_context_consumed": True,
        "runtime_handle_established_in_protected_boundary": succeeded,
        "runtime_handle_absence_confirmed": not succeeded,
        "raw_context_returned": False,
        "runtime_handle_locator_returned": False,
        "endpoint_returned": False,
        "credential_returned": False,
        "secret_returned": False,
        "bearer_token_returned": False,
        "provider_payload_returned": False,
        "filesystem_activity_performed": False,
        "provider_activity_performed": False,
        "connector_activity_performed": False,
        "network_activity_performed": False,
        "readiness_probe_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "completed_at": NOW + timedelta(milliseconds=250),
        "access_deadline": instruction.access_deadline,
        "protected_resident_context_usable_until": (
            instruction.protected_resident_context_usable_until
        ),
        "attested_by": "attestor.workflow-protected-resident-context-accessor",
        "signing_key_id": policy.verification_signing_key_id,
        "signature_algorithm": "test-sha256-v1",
        "integrity_signature": "signature.imp-217",
    }
    return WorkflowProtectedResidentContextTrustedAccessorReceipt(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _result(
    state: WorkflowProtectedResidentContextAccessConsumptionResultState,
) -> WorkflowProtectedResidentContextAccessConsumptionResult:
    policy = code_owned_workflow_protected_resident_context_access_consumption_policy()
    attempt = _attempt()
    success = state is SUCCESS
    failure = state is FAILED
    receipt = _receipt(state) if success or failure else None
    values: dict[str, object] = {
        "access_id": attempt.access_id,
        "attempt_id": attempt.attempt_id,
        "attempt_digest": attempt.canonical_digest,
        "consumption_claim_id": attempt.consumption_claim_id,
        "consumption_claim_digest": attempt.consumption_claim_digest,
        "authorization_lease_id": attempt.authorization_lease_id,
        "authorization_lease_digest": attempt.authorization_lease_digest,
        "protected_resident_context_id": attempt.protected_resident_context_id,
        "protected_resident_context_digest": attempt.protected_resident_context_digest,
        "scope": attempt.scope,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "accessor_id": policy.approved_accessor_id,
        "accessor_version": policy.approved_accessor_version,
        "runtime_handle_profile_id": policy.runtime_handle_profile_id,
        "runtime_handle_profile_version": policy.runtime_handle_profile_version,
        "runtime_handle_profile_digest": policy.runtime_handle_profile_digest,
        "accessor_receipt_digest": receipt.canonical_digest if receipt else None,
        "state": state,
        "failure_class": (
            None
            if success
            else FAILURES.TRUSTED_ACCESSOR_REJECTED
            if failure
            else FAILURES.ACCESS_OUTCOME_UNCERTAIN
        ),
        "protected_runtime_handle_id": (
            "protected-runtime-context-handle.imp-217" if success else None
        ),
        "protected_runtime_handle_digest": "b" * 64 if success else None,
        "protected_runtime_handle_created_at": (
            NOW + timedelta(milliseconds=250) if success else None
        ),
        "protected_runtime_handle_usable_until": (
            NOW + timedelta(milliseconds=1500) if success else None
        ),
        "protected_runtime_handle_is_bearer_capability": False,
        "protected_resident_context_consumed": True if success or failure else None,
        "runtime_handle_established_in_protected_boundary": success,
        "runtime_handle_absence_confirmed": failure,
        "outcome_known": success or failure,
        "completed_at": NOW + timedelta(milliseconds=250) if success or failure else None,
        "recorded_at": (
            NOW + timedelta(milliseconds=300)
            if success or failure
            else ACCESS_DEADLINE + timedelta(microseconds=1)
        ),
        "access_deadline": ACCESS_DEADLINE,
        "protected_resident_context_usable_until": RESIDENT_USABLE_UNTIL,
        "authority": WorkflowProtectedResidentContextAccessConsumptionAuthority(),
    }
    return WorkflowProtectedResidentContextAccessConsumptionResult(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def test_code_owned_consumption_policy_is_closed_and_digest_bound() -> None:
    policy = code_owned_workflow_protected_resident_context_access_consumption_policy()

    assert policy.consumer_subject_id == (
        "service.workflow-protected-transport-target-context-capsule-consumer"
    )
    assert policy.automatic_retry_allowed is False
    assert policy.raw_context_return_forbidden is True
    assert policy.runtime_handle_locator_return_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.delivery_forbidden is True
    assert policy.execution_forbidden is True
    assert policy.readiness_verification_signing_key_id != policy.verification_signing_key_id
    assert canonical_digest(policy.digest_payload()) == policy.canonical_digest

    with pytest.raises(ValueError, match="not code-owned"):
        replace(policy, approved_accessor_version="2.0")
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(policy, canonical_digest="f" * 64)


@pytest.mark.parametrize(
    "authority_field",
    list(WorkflowProtectedResidentContextAccessConsumptionAuthority().canonical_value()),
)
def test_consumption_authority_has_twenty_all_false_fields(authority_field: str) -> None:
    authority = WorkflowProtectedResidentContextAccessConsumptionAuthority()

    assert len(authority.canonical_value()) == 20
    assert set(authority.canonical_value().values()) == {False}
    with pytest.raises(ValueError, match="grants no authority"):
        WorkflowProtectedResidentContextAccessConsumptionAuthority(
            **cast(Any, {authority_field: True})
        )


@pytest.mark.parametrize(
    ("field_name", "unsafe_value"),
    [
        ("consumer_subject_id", "service.wrong-consumer"),
        ("consumer_audience", "audience.wrong-consumer"),
        ("irreversible_consumption_acknowledged", False),
        ("uncertain_outcome_requires_new_authorization_acknowledged", False),
    ],
)
def test_claim_requires_exact_identity_and_acknowledgements(
    field_name: str, unsafe_value: object
) -> None:
    with pytest.raises(ValueError, match="claim is invalid"):
        replace(_claim(), **cast(Any, {field_name: unsafe_value}))


def test_claim_attempt_and_result_are_immutable_and_digest_bound() -> None:
    claim = _claim()
    attempt = _attempt()
    result = _result(SUCCESS)

    with pytest.raises(FrozenInstanceError):
        claim.claim_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        attempt.access_deadline = LEASE_VALID_UNTIL  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.state = FAILED  # type: ignore[misc]
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(claim, canonical_digest="f" * 64)


def test_attempt_requires_aware_times_and_deadline_bounded_by_all_sources() -> None:
    attempt = _attempt()

    with pytest.raises(ValueError, match="attempt is invalid"):
        replace(
            attempt,
            access_deadline=attempt.authorization_lease_valid_until + timedelta(microseconds=1),
        )
    with pytest.raises(ValueError, match="attempt is invalid"):
        replace(attempt, started_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="attempt is invalid"):
        replace(
            attempt,
            protected_resident_context_usable_until=ACCESS_DEADLINE - timedelta(microseconds=1),
        )


def test_instruction_is_exact_metadata_only_and_deadline_bound() -> None:
    instruction = _instruction()

    assert instruction.access_deadline <= instruction.protected_resident_context_usable_until
    assert not hasattr(instruction, "raw_context")
    assert not hasattr(instruction, "runtime_handle_locator")
    assert not hasattr(instruction, "endpoint")
    assert not hasattr(instruction, "credential")
    with pytest.raises(ValueError, match="instruction is invalid"):
        replace(instruction, accessor_id="accessor.untrusted")


def test_signed_accessor_receipt_supports_only_known_success_or_failure() -> None:
    success = _receipt(SUCCESS)
    failure = _receipt(FAILED)

    assert success.protected_runtime_handle_id is not None
    assert success.protected_runtime_handle_is_bearer_capability is False
    assert success.runtime_handle_locator_returned is False
    assert failure.protected_runtime_handle_id is None
    assert failure.runtime_handle_absence_confirmed is True
    assert not hasattr(success, "runtime_handle_locator")
    assert not hasattr(success, "raw_context")

    with pytest.raises(ValueError, match="failed resident context accessor receipt"):
        replace(success, state=FAILED)
    with pytest.raises(ValueError, match="receipt is invalid"):
        replace(
            failure,
            state=UNCERTAIN,
            failure_class=FAILURES.ACCESS_OUTCOME_UNCERTAIN,
        )


def test_success_receipt_rejects_bearer_or_overlong_handle_metadata() -> None:
    success = _receipt(SUCCESS)

    with pytest.raises(ValueError, match="receipt is unsafe"):
        replace(success, protected_runtime_handle_is_bearer_capability=True)
    with pytest.raises(ValueError, match="successful resident context accessor receipt"):
        replace(
            success,
            protected_runtime_handle_usable_until=RESIDENT_USABLE_UNTIL + timedelta(microseconds=1),
        )
    with pytest.raises(ValueError, match="receipt is unsafe"):
        replace(success, completed_at=ACCESS_DEADLINE)


@pytest.mark.parametrize(
    "field_name",
    [
        "raw_context_returned",
        "runtime_handle_locator_returned",
        "endpoint_returned",
        "credential_returned",
        "secret_returned",
        "bearer_token_returned",
        "provider_payload_returned",
        "filesystem_activity_performed",
        "provider_activity_performed",
        "connector_activity_performed",
        "network_activity_performed",
        "readiness_probe_performed",
        "publication_performed",
        "delivery_performed",
        "dispatch_performed",
        "execution_performed",
        "infrastructure_mutation_performed",
    ],
)
def test_signed_accessor_receipt_rejects_every_forbidden_effect(field_name: str) -> None:
    with pytest.raises(ValueError, match="receipt is unsafe"):
        cast(Any, replace)(_receipt(SUCCESS), **{field_name: True})


@pytest.mark.parametrize("state", [SUCCESS, FAILED, UNCERTAIN])
def test_result_enforces_success_failure_and_uncertain_invariants(
    state: WorkflowProtectedResidentContextAccessConsumptionResultState,
) -> None:
    result = _result(state)

    assert result.state is state
    assert len(result.authority.canonical_value()) == 20
    assert set(result.authority.canonical_value().values()) == {False}
    assert result.protected_runtime_handle_is_bearer_capability is False
    if state is SUCCESS:
        assert result.protected_runtime_handle_id is not None
        assert result.outcome_known is True
    elif state is FAILED:
        assert result.protected_runtime_handle_id is None
        assert result.runtime_handle_absence_confirmed is True
        assert result.outcome_known is True
    else:
        assert result.accessor_receipt_digest is None
        assert result.completed_at is None
        assert result.recorded_at >= result.access_deadline
        assert result.protected_resident_context_consumed is None
        assert result.outcome_known is False


def test_result_rejects_cross_state_evidence_and_late_known_outcome() -> None:
    success = _result(SUCCESS)
    failure = _result(FAILED)
    uncertain = _result(UNCERTAIN)
    assert success.completed_at is not None

    with pytest.raises(ValueError, match="successful resident context access result"):
        replace(success, runtime_handle_established_in_protected_boundary=False)
    with pytest.raises(ValueError, match="failed resident context access result"):
        replace(failure, runtime_handle_absence_confirmed=False)
    with pytest.raises(ValueError, match="uncertain resident context access result"):
        replace(uncertain, accessor_receipt_digest="c" * 64)
    with pytest.raises(ValueError, match="uncertain resident context access result"):
        replace(uncertain, protected_resident_context_consumed=False)
    with pytest.raises(ValueError, match="successful resident context access result"):
        replace(
            success,
            completed_at=ACCESS_DEADLINE,
            recorded_at=ACCESS_DEADLINE + timedelta(microseconds=1),
        )
    with pytest.raises(ValueError, match="resident context access result is unsafe"):
        replace(success, recorded_at=success.completed_at - timedelta(microseconds=1))


def test_exact_result_state_values_match_adr_167() -> None:
    assert SUCCESS.value == "handle_established_in_protected_boundary"
    assert FAILED.value == "resident_context_access_failed"
    assert UNCERTAIN.value == "access_outcome_uncertain"
