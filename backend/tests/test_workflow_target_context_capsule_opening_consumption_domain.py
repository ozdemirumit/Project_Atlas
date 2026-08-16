from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority,
    WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim,
    WorkflowProtectedTransportTargetContextCapsuleOpeningFailureClass,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResult,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultState,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
OPENING_DEADLINE = NOW + timedelta(milliseconds=500)
RESULT_STATES = WorkflowProtectedTransportTargetContextCapsuleOpeningResultState
FAILURE_CLASSES = WorkflowProtectedTransportTargetContextCapsuleOpeningFailureClass
SUCCESS_STATE = RESULT_STATES.OPENED_IN_PROTECTED_CONSUMER_BOUNDARY
FAILURE_STATE = RESULT_STATES.OPENING_FAILED
UNCERTAIN_STATE = RESULT_STATES.OPENING_OUTCOME_UNCERTAIN
OPENER_REJECTED = FAILURE_CLASSES.TRUSTED_OPENER_REJECTED
UNCERTAIN_FAILURE = FAILURE_CLASSES.OPENING_OUTCOME_UNCERTAIN


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


def _claim() -> WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    values: dict[str, object] = {
        "claim_id": "target-context-capsule-opening-claim.imp-215",
        "opening_id": "target-context-capsule-opening.imp-215",
        "attempt_id": "target-context-capsule-opening-attempt.imp-215",
        "authorization_lease_id": "target-context-capsule-opening-lease.imp-214",
        "authorization_lease_digest": "1" * 64,
        "handoff_id": "target-context-capsule-handoff.imp-213",
        "handoff_result_digest": "2" * 64,
        "handoff_attempt_id": "target-context-capsule-handoff-attempt.imp-213",
        "handoff_attempt_digest": "3" * 64,
        "handoff_consumption_claim_id": "target-context-capsule-handoff-claim.imp-213",
        "handoff_consumption_claim_digest": "4" * 64,
        "consumer_binding_id": "target-context-capsule-consumer-binding.imp-212",
        "consumer_binding_digest": "5" * 64,
        "sealed_capsule_id": "sealed-target-context-capsule.imp-211",
        "sealed_capsule_digest": "6" * 64,
        "consumer_receipt_id": "target-context-capsule-consumer-receipt.imp-213",
        "consumer_receipt_digest": "7" * 64,
        "sealed_capsule_is_bearer_capability": False,
        "consumer_receipt_is_bearer_capability": False,
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
        "request_fingerprint": "8" * 64,
        "idempotency_digest": "9" * 64,
        "consumption_authorization_audit_digest": "a" * 64,
        "claimed_at": NOW,
        "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority(),
    }
    return WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _attempt() -> WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    claim = _claim()
    values: dict[str, object] = {
        "attempt_id": claim.attempt_id,
        "opening_id": claim.opening_id,
        "consumption_claim_id": claim.claim_id,
        "consumption_claim_digest": claim.canonical_digest,
        "authorization_lease_id": claim.authorization_lease_id,
        "authorization_lease_digest": claim.authorization_lease_digest,
        "consumer_binding_id": claim.consumer_binding_id,
        "consumer_binding_digest": claim.consumer_binding_digest,
        "sealed_capsule_id": claim.sealed_capsule_id,
        "sealed_capsule_digest": claim.sealed_capsule_digest,
        "consumer_receipt_id": claim.consumer_receipt_id,
        "consumer_receipt_digest": claim.consumer_receipt_digest,
        "sealed_capsule_is_bearer_capability": False,
        "consumer_receipt_is_bearer_capability": False,
        "scope": claim.scope,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "required_opener_contract_id": policy.required_opener_contract_id,
        "required_opener_contract_version": policy.required_opener_contract_version,
        "approved_opener_id": policy.approved_opener_id,
        "approved_opener_version": policy.approved_opener_version,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "custody_contract_id": policy.custody_contract_id,
        "custody_contract_version": policy.custody_contract_version,
        "verification_signing_key_id": policy.verification_signing_key_id,
        "trusted_opener_profile_digest": policy.trusted_opener_profile_digest,
        "custody_attestation_id": "target-context-capsule-custody.imp-215",
        "custody_attestation_digest": "b" * 64,
        "openability_attestation_id": "target-context-capsule-openability.imp-215",
        "openability_attestation_digest": "c" * 64,
        "request_nonce_digest": "d" * 64,
        "started_at": NOW,
        "opening_deadline": OPENING_DEADLINE,
        "lease_valid_until": NOW + timedelta(seconds=1),
        "custody_attestation_valid_until": NOW + timedelta(seconds=1),
        "openability_attestation_valid_until": NOW + timedelta(seconds=1),
        "state": WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptState.STARTED,
        "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority(),
    }
    return WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _instruction() -> WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction:
    attempt = _attempt()
    values: dict[str, object] = {
        name: getattr(attempt, name)
        for name in (
            "opening_id",
            "attempt_id",
            "consumption_claim_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "sealed_capsule_id",
            "sealed_capsule_digest",
            "consumer_receipt_id",
            "consumer_receipt_digest",
            "sealed_capsule_is_bearer_capability",
            "consumer_receipt_is_bearer_capability",
            "consumer_subject_id",
            "consumer_audience",
            "consumer_contract_id",
            "consumer_contract_version",
            "purpose_id",
            "policy_id",
            "policy_version",
            "policy_digest",
            "required_opener_contract_id",
            "required_opener_contract_version",
            "approved_opener_id",
            "approved_opener_version",
            "destination_boundary_id",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "custody_contract_id",
            "custody_contract_version",
            "trusted_opener_profile_digest",
            "custody_attestation_digest",
            "openability_attestation_digest",
            "started_at",
            "opening_deadline",
        )
    }
    return WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _receipt(
    state: WorkflowProtectedTransportTargetContextCapsuleOpeningResultState = SUCCESS_STATE,
) -> WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    instruction = _instruction()
    succeeded = state is SUCCESS_STATE
    values: dict[str, object] = {
        "opening_id": instruction.opening_id,
        "attempt_id": instruction.attempt_id,
        "consumption_claim_id": instruction.consumption_claim_id,
        "instruction_digest": instruction.canonical_digest,
        "authorization_lease_id": instruction.authorization_lease_id,
        "authorization_lease_digest": instruction.authorization_lease_digest,
        "sealed_capsule_id": instruction.sealed_capsule_id,
        "sealed_capsule_digest": instruction.sealed_capsule_digest,
        "consumer_receipt_id": instruction.consumer_receipt_id,
        "consumer_receipt_digest": instruction.consumer_receipt_digest,
        "opener_contract_id": policy.required_opener_contract_id,
        "opener_contract_version": policy.required_opener_contract_version,
        "opener_id": policy.approved_opener_id,
        "opener_version": policy.approved_opener_version,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "custody_contract_id": policy.custody_contract_id,
        "custody_contract_version": policy.custody_contract_version,
        "trusted_opener_profile_digest": policy.trusted_opener_profile_digest,
        "state": state,
        "failure_class": (None if succeeded else OPENER_REJECTED),
        "protected_resident_context_id": (
            "protected-resident-target-context.imp-215" if succeeded else None
        ),
        "protected_resident_context_digest": "e" * 64 if succeeded else None,
        "protected_resident_context_is_bearer_capability": False,
        "capsule_opened_in_protected_boundary": succeeded,
        "target_context_pair_verified": succeeded,
        "raw_target_context_returned": False,
        "runtime_handle_created": False,
        "network_activity_performed": False,
        "delivery_performed": False,
        "execution_performed": False,
        "protected_source_closed": True,
        "source_capsule_zeroized": True,
        "completed_at": NOW + timedelta(milliseconds=250),
        "opening_deadline": OPENING_DEADLINE,
        "attested_by": "attestor.workflow-protected-target-context-capsule-opener",
        "signing_key_id": policy.verification_signing_key_id,
        "signature_algorithm": "test-sha256-v1",
        "integrity_signature": "signature.imp-215",
    }
    return WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _result(
    state: WorkflowProtectedTransportTargetContextCapsuleOpeningResultState,
) -> WorkflowProtectedTransportTargetContextCapsuleOpeningResult:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    attempt = _attempt()
    success = state is SUCCESS_STATE
    failure = state is FAILURE_STATE
    receipt = _receipt(state) if success or failure else None
    values: dict[str, object] = {
        "opening_id": attempt.opening_id,
        "attempt_id": attempt.attempt_id,
        "attempt_digest": attempt.canonical_digest,
        "consumption_claim_id": attempt.consumption_claim_id,
        "consumption_claim_digest": attempt.consumption_claim_digest,
        "authorization_lease_id": attempt.authorization_lease_id,
        "authorization_lease_digest": attempt.authorization_lease_digest,
        "consumer_binding_id": attempt.consumer_binding_id,
        "consumer_binding_digest": attempt.consumer_binding_digest,
        "sealed_capsule_id": attempt.sealed_capsule_id,
        "sealed_capsule_digest": attempt.sealed_capsule_digest,
        "consumer_receipt_id": attempt.consumer_receipt_id,
        "consumer_receipt_digest": attempt.consumer_receipt_digest,
        "scope": attempt.scope,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "opener_id": policy.approved_opener_id,
        "opener_version": policy.approved_opener_version,
        "opening_receipt_digest": receipt.canonical_digest if receipt else None,
        "state": state,
        "failure_class": (None if success else OPENER_REJECTED if failure else UNCERTAIN_FAILURE),
        "protected_resident_context_id": (
            "protected-resident-target-context.imp-215" if success else None
        ),
        "protected_resident_context_digest": "e" * 64 if success else None,
        "protected_resident_context_is_bearer_capability": False,
        "capsule_opened_in_protected_boundary": success,
        "target_context_pair_verified": success,
        "outcome_known": success or failure,
        "protected_source_closed": success or failure,
        "source_capsule_zeroized": success or failure,
        "completed_at": NOW + timedelta(milliseconds=250) if success or failure else None,
        "recorded_at": (
            NOW + timedelta(milliseconds=300)
            if success or failure
            else OPENING_DEADLINE + timedelta(milliseconds=1)
        ),
        "opening_deadline": OPENING_DEADLINE,
        "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority(),
    }
    return WorkflowProtectedTransportTargetContextCapsuleOpeningResult(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def test_code_owned_opening_consumption_policy_is_closed_and_digest_bound() -> None:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )

    assert policy.consumer_subject_id == (
        "service.workflow-protected-transport-target-context-capsule-consumer"
    )
    assert policy.consumer_audience == (
        "audience.workflow-protected-transport-target-context-capsule-consumer"
    )
    assert policy.automatic_retry_allowed is False
    assert policy.raw_material_return_forbidden is True
    assert policy.runtime_handle_creation_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.delivery_forbidden is True
    assert policy.execution_forbidden is True

    with pytest.raises(ValueError, match="not code-owned"):
        replace(policy, approved_opener_version="2.0")
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(policy, canonical_digest="f" * 64)


@pytest.mark.parametrize(
    "authority_field",
    list(WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority().canonical_value()),
)
def test_opening_consumption_authority_has_nineteen_all_false_fields(
    authority_field: str,
) -> None:
    authority = WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority()

    assert len(authority.canonical_value()) == 19
    assert set(authority.canonical_value().values()) == {False}
    with pytest.raises(ValueError, match="grants no authority"):
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority(
            **cast(Any, {authority_field: True})
        )


@pytest.mark.parametrize(
    ("field_name", "unsafe_value"),
    [
        ("consumer_subject_id", "service.wrong-consumer"),
        ("consumer_audience", "audience.wrong-consumer"),
        ("irreversible_consumption_acknowledged", False),
        ("uncertain_outcome_requires_new_authorization_acknowledged", False),
        ("sealed_capsule_is_bearer_capability", True),
        ("consumer_receipt_is_bearer_capability", True),
    ],
)
def test_claim_requires_exact_identity_acknowledgements_and_non_bearer_lineage(
    field_name: str, unsafe_value: object
) -> None:
    claim = _claim()

    with pytest.raises(ValueError, match="claim is invalid"):
        replace(claim, **cast(Any, {field_name: unsafe_value}))


def test_claim_and_attempt_are_immutable_and_digest_bound() -> None:
    claim = _claim()
    attempt = _attempt()

    with pytest.raises(FrozenInstanceError):
        claim.claim_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        attempt.opening_deadline = NOW + timedelta(seconds=1)  # type: ignore[misc]
    with pytest.raises(ValueError, match="attempt is invalid"):
        replace(attempt, opening_deadline=attempt.lease_valid_until + timedelta(microseconds=1))


def test_attempt_and_instruction_bind_exact_opener_and_evidence_window() -> None:
    attempt = _attempt()
    instruction = _instruction()

    assert instruction.opening_deadline == attempt.opening_deadline
    assert instruction.custody_attestation_digest == attempt.custody_attestation_digest
    assert instruction.openability_attestation_digest == attempt.openability_attestation_digest
    assert not hasattr(instruction, "runtime_handle")
    assert not hasattr(instruction, "endpoint")

    with pytest.raises(ValueError, match="attempt is invalid"):
        replace(attempt, approved_opener_id="opener.untrusted")
    with pytest.raises(ValueError, match="instruction is invalid"):
        replace(instruction, sealed_capsule_is_bearer_capability=True)


def test_trusted_opener_receipt_supports_only_signed_success_or_known_failure() -> None:
    success = _receipt()
    failure = _receipt(FAILURE_STATE)

    assert success.protected_resident_context_id is not None
    assert success.protected_resident_context_is_bearer_capability is False
    assert success.runtime_handle_created is False
    assert success.network_activity_performed is False
    assert failure.failure_class is not None
    assert failure.protected_resident_context_id is None
    assert failure.protected_source_closed is True
    assert failure.source_capsule_zeroized is True

    with pytest.raises(ValueError, match="failed trusted capsule opener receipt"):
        replace(
            failure,
            state=UNCERTAIN_STATE,
            failure_class=UNCERTAIN_FAILURE,
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "protected_resident_context_is_bearer_capability",
        "raw_target_context_returned",
        "runtime_handle_created",
        "network_activity_performed",
        "delivery_performed",
        "execution_performed",
    ],
)
def test_trusted_opener_receipt_rejects_bearer_raw_runtime_network_and_execution(
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match="receipt is unsafe"):
        replace(_receipt(), **cast(Any, {field_name: True}))


def test_result_models_distinguish_success_failure_and_receiptless_uncertainty() -> None:
    success = _result(SUCCESS_STATE)
    failure = _result(FAILURE_STATE)
    uncertain = _result(UNCERTAIN_STATE)

    assert success.opening_receipt_digest is not None
    assert success.protected_resident_context_id is not None
    assert success.protected_resident_context_is_bearer_capability is False
    assert failure.opening_receipt_digest is not None
    assert failure.outcome_known is True
    assert uncertain.opening_receipt_digest is None
    assert uncertain.completed_at is None
    assert uncertain.outcome_known is False
    assert uncertain.recorded_at >= uncertain.opening_deadline
    assert not any(uncertain.authority.canonical_value().values())


def test_result_rejects_receipt_for_uncertainty_and_unconfirmed_known_cleanup() -> None:
    uncertain = _result(UNCERTAIN_STATE)
    failure = _result(FAILURE_STATE)

    with pytest.raises(ValueError, match="uncertain capsule opening result"):
        replace(uncertain, opening_receipt_digest="f" * 64)
    with pytest.raises(ValueError, match="failed capsule opening result"):
        replace(failure, protected_source_closed=False)
