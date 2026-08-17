from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WorkflowProtectedRuntimeReadinessAttempt,
    WorkflowProtectedRuntimeReadinessConsumptionAttemptState,
    WorkflowProtectedRuntimeReadinessConsumptionAuthority,
    WorkflowProtectedRuntimeReadinessConsumptionClaim,
    WorkflowProtectedRuntimeReadinessConsumptionFailureClass,
    WorkflowProtectedRuntimeReadinessConsumptionPolicy,
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    WorkflowProtectedRuntimeReadinessInstruction,
    WorkflowProtectedRuntimeReadinessInvocation,
    WorkflowProtectedRuntimeReadinessReceipt,
    WorkflowProtectedRuntimeReadinessResult,
    WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
    code_owned_workflow_protected_runtime_readiness_consumption_policy_values,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    if hasattr(value, "digest_payload") and hasattr(value, "canonical_digest"):
        return value.digest_payload() | {"canonical_digest": value.canonical_digest}
    return value


def _digest(values: dict[str, object]) -> str:
    return canonical_digest({name: _canonical_value(value) for name, value in values.items()})


def _without_digest(instance: object) -> dict[str, Any]:
    return {
        field.name: getattr(instance, field.name)
        for field in fields(cast(Any, instance))
        if field.name != "canonical_digest"
    }


def _claim() -> WorkflowProtectedRuntimeReadinessConsumptionClaim:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    values: dict[str, object] = {
        "claim_id": "runtime-readiness-consumption-claim.imp-226",
        "consumption_id": "runtime-readiness-consumption.imp-226",
        "attempt_id": "runtime-readiness-attempt.imp-226",
        "authorization_lease_id": "runtime-readiness-lease.imp-225",
        "authorization_lease_digest": "1" * 64,
        "authorization_claim_id": "runtime-readiness-authorization-claim.imp-225",
        "authorization_claim_digest": "2" * 64,
        "start_result_id": "runtime-start-result.imp-224",
        "start_result_digest": "3" * 64,
        "start_consumption_id": "runtime-start-consumption.imp-224",
        "start_attempt_id": "runtime-start-attempt.imp-224",
        "start_attempt_digest": "4" * 64,
        "start_claim_id": "runtime-start-claim.imp-224",
        "start_claim_digest": "5" * 64,
        "destination_deployment_id": "deployment.imp-226",
        "destination_generation": 7,
        "destination_fencing_token_digest": "6" * 64,
        "protected_slot_commitment": "7" * 64,
        "protected_slot_generation": 11,
        "runtime_envelope_id": "runtime-envelope.imp-226",
        "runtime_envelope_commitment": "8" * 64,
        "runtime_envelope_generation": 11,
        "readiness_profile_id": policy.readiness_profile_id,
        "readiness_profile_version": policy.readiness_profile_version,
        "readiness_profile_digest": policy.readiness_profile_digest,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "idempotency_digest": "9" * 64,
        "request_fingerprint": "a" * 64,
        "irreversible_consumption_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "claimed_at": NOW,
        "authority": WorkflowProtectedRuntimeReadinessConsumptionAuthority(),
    }
    return WorkflowProtectedRuntimeReadinessConsumptionClaim(
        **cast(Any, values), canonical_digest=_digest(values)
    )


def _attempt() -> WorkflowProtectedRuntimeReadinessAttempt:
    claim = _claim()
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    values: dict[str, object] = {
        name: getattr(claim, name)
        for name in (
            "attempt_id",
            "consumption_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "authorization_claim_id",
            "authorization_claim_digest",
            "start_result_id",
            "start_result_digest",
            "start_consumption_id",
            "start_attempt_id",
            "start_attempt_digest",
            "start_claim_id",
            "start_claim_digest",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "protected_slot_commitment",
            "protected_slot_generation",
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "readiness_profile_id",
            "readiness_profile_version",
            "readiness_profile_digest",
            "scope",
            "consumer_subject_id",
            "consumer_audience",
            "consumer_contract_id",
            "consumer_contract_version",
            "purpose_id",
            "policy_id",
            "policy_version",
            "policy_digest",
        )
    }
    values.update(
        {
            "claim_id": claim.claim_id,
            "claim_digest": claim.canonical_digest,
            "protected_operation_reference": "protected-runtime-readiness.imp-226",
            "expected_assessment_count_pre": 0,
            "expected_assessment_count_post": 1,
            "assessor_contract_id": policy.required_assessor_contract_id,
            "assessor_contract_version": policy.required_assessor_contract_version,
            "assessor_id": policy.approved_assessor_id,
            "assessor_version": policy.approved_assessor_version,
            "receipt_verification_signing_key_id": (policy.receipt_verification_signing_key_id),
            "request_nonce_digest": "b" * 64,
            "started_at": NOW,
            "invocation_deadline": NOW + timedelta(milliseconds=700),
            "state": (
                WorkflowProtectedRuntimeReadinessConsumptionAttemptState
            ).RUNTIME_READINESS_ATTEMPT_STARTED,
            "authority": WorkflowProtectedRuntimeReadinessConsumptionAuthority(),
        }
    )
    return WorkflowProtectedRuntimeReadinessAttempt(
        **cast(Any, values), canonical_digest=_digest(values)
    )


def _instruction() -> WorkflowProtectedRuntimeReadinessInstruction:
    attempt = _attempt()
    values: dict[str, object] = {
        name: getattr(attempt, name)
        for name in (
            "consumption_id",
            "attempt_id",
            "claim_id",
            "claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "start_result_id",
            "start_result_digest",
            "protected_operation_reference",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "protected_slot_commitment",
            "protected_slot_generation",
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "readiness_profile_id",
            "readiness_profile_version",
            "readiness_profile_digest",
            "expected_assessment_count_pre",
            "expected_assessment_count_post",
            "assessor_contract_id",
            "assessor_contract_version",
            "assessor_id",
            "assessor_version",
            "request_nonce_digest",
            "scope",
            "policy_id",
            "policy_version",
            "policy_digest",
            "started_at",
            "invocation_deadline",
        )
    }
    values["attempt_digest"] = attempt.canonical_digest
    return WorkflowProtectedRuntimeReadinessInstruction(
        **cast(Any, values), canonical_digest=_digest(values)
    )


def _signed_envelope() -> WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope:
    instruction = _instruction()
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    values: dict[str, object] = {
        "instruction": instruction,
        "signing_key_id": policy.instruction_signing_key_id,
        "signature_algorithm": policy.instruction_signature_algorithm,
        "integrity_signature": "c" * 64,
    }
    return WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope(
        **cast(Any, values), canonical_digest=_digest(values)
    )


def _receipt(
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState,
) -> WorkflowProtectedRuntimeReadinessReceipt:
    attempt = _attempt()
    instruction = _instruction()
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    values: dict[str, object] = {
        name: getattr(attempt, name)
        for name in (
            "consumption_id",
            "attempt_id",
            "claim_id",
            "claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "start_result_id",
            "start_result_digest",
            "protected_operation_reference",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "protected_slot_commitment",
            "protected_slot_generation",
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "readiness_profile_id",
            "readiness_profile_version",
            "readiness_profile_digest",
            "assessor_contract_id",
            "assessor_contract_version",
            "assessor_id",
            "assessor_version",
            "request_nonce_digest",
            "started_at",
            "invocation_deadline",
        )
    }
    ready = (
        state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
    )
    failed = (
        state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
    )
    values.update(
        {
            "attempt_digest": attempt.canonical_digest,
            "instruction_digest": instruction.canonical_digest,
            "assessment_count_pre": 0,
            "assessment_count_post": 0 if failed else 1,
            "result_state": state,
            "runtime_ready": None if failed else ready,
            "readiness_assessment_performed": not failed,
            "runtime_locator_returned": False,
            "process_identifier_returned": False,
            "runtime_context_returned": False,
            "endpoint_material_returned": False,
            "credential_material_returned": False,
            "secret_material_returned": False,
            "command_constructed": False,
            "prompt_constructed": False,
            "model_inference_performed": False,
            "network_activity_performed": False,
            "connector_activity_performed": False,
            "mcp_activity_performed": False,
            "publication_performed": False,
            "delivery_performed": False,
            "dispatch_performed": False,
            "execution_performed": False,
            "infrastructure_mutation_performed": False,
            "completed_at": NOW + timedelta(milliseconds=500),
            "signing_key_id": policy.receipt_verification_signing_key_id,
            "signature_algorithm": policy.receipt_signature_algorithm,
            "integrity_signature": "d" * 64,
        }
    )
    return WorkflowProtectedRuntimeReadinessReceipt(
        **cast(Any, values), canonical_digest=_digest(values)
    )


def _result(
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState,
) -> WorkflowProtectedRuntimeReadinessResult:
    attempt = _attempt()
    known_assessment = state in (
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY,
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY,
    )
    failed = (
        state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
    )
    uncertain = (
        state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
    )
    values: dict[str, object] = {
        name: getattr(attempt, name)
        for name in (
            "consumption_id",
            "attempt_id",
            "claim_id",
            "claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "start_result_id",
            "start_result_digest",
            "readiness_profile_id",
            "readiness_profile_version",
            "readiness_profile_digest",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "protected_slot_commitment",
            "protected_slot_generation",
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "scope",
            "policy_id",
            "policy_version",
            "policy_digest",
        )
    }
    values.update(
        {
            "result_id": "runtime-readiness-result.imp-226",
            "attempt_digest": attempt.canonical_digest,
            "state": state,
            "failure_class": (
                WorkflowProtectedRuntimeReadinessConsumptionFailureClass.PROTECTED_ASSESSMENT_FAILED_WITHOUT_ASSESSMENT
                if failed
                else (
                    WorkflowProtectedRuntimeReadinessConsumptionFailureClass.RUNTIME_READINESS_OUTCOME_UNCERTAIN
                    if uncertain
                    else None
                )
            ),
            "outcome_known": not uncertain,
            "assessment_performed": True if known_assessment else (False if failed else None),
            "runtime_ready": (
                state
                is (
                    WorkflowProtectedRuntimeReadinessConsumptionResultState
                ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
                if known_assessment
                else None
            ),
            "assessor_receipt_digest": "e" * 64 if not uncertain else None,
            "completed_at": NOW + timedelta(milliseconds=500) if not uncertain else None,
            "recorded_at": NOW + timedelta(milliseconds=600),
            "authority": WorkflowProtectedRuntimeReadinessConsumptionAuthority(),
        }
    )
    return WorkflowProtectedRuntimeReadinessResult(
        **cast(Any, values), canonical_digest=_digest(values)
    )


def test_policy_is_cached_code_owned_single_attempt_and_non_retrying() -> None:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()

    assert policy is code_owned_workflow_protected_runtime_readiness_consumption_policy()
    assert policy.policy_id == "policy.workflow-protected-runtime-readiness-consumption"
    assert policy.required_source_state == "authorized_unconsumed"
    assert policy.claim_and_attempt_atomic_required is True
    assert policy.commit_before_assessor_io_required is True
    assert policy.at_most_one_assessor_call_required is True
    assert policy.automatic_retry_allowed is False
    assert policy.protected_boundary_only_required is True
    assert policy.metadata_only_instruction_required is True
    assert policy.instruction_signing_key_id != policy.receipt_verification_signing_key_id


def test_policy_rejects_non_code_owned_value() -> None:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()

    with pytest.raises(ValueError, match="not code-owned"):
        replace(policy, automatic_retry_allowed=True)


def test_policy_values_rebuild_to_same_digest_without_changing_cached_object() -> None:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    values = code_owned_workflow_protected_runtime_readiness_consumption_policy_values()

    assert canonical_digest(values) == policy.canonical_digest
    assert (
        WorkflowProtectedRuntimeReadinessConsumptionPolicy(
            **cast(Any, values), canonical_digest=canonical_digest(values)
        )
        == policy
    )


def test_authority_has_exactly_twenty_eight_false_declarations_and_is_frozen() -> None:
    authority = WorkflowProtectedRuntimeReadinessConsumptionAuthority()

    assert len(authority.canonical_value()) == 28
    assert not any(authority.canonical_value().values())
    with pytest.raises(FrozenInstanceError):
        authority.protected_runtime_readiness_authority_granted = True  # type: ignore[misc]


@pytest.mark.parametrize(
    "field_name",
    [field.name for field in fields(WorkflowProtectedRuntimeReadinessConsumptionAuthority)],
)
def test_authority_rejects_every_true_declaration(field_name: str) -> None:
    values = {
        field.name: False for field in fields(WorkflowProtectedRuntimeReadinessConsumptionAuthority)
    }
    values[field_name] = True

    with pytest.raises(ValueError, match="grants no authority"):
        WorkflowProtectedRuntimeReadinessConsumptionAuthority(**values)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("irreversible_consumption_acknowledged", False),
        ("uncertainty_no_retry_acknowledged", False),
        ("protected_slot_generation", 0),
        ("runtime_envelope_generation", 12),
    ],
)
def test_claim_rejects_invalid_atomic_consumption_invariants(
    field_name: str, invalid_value: object
) -> None:
    claim = _claim()

    with pytest.raises(ValueError, match="claim is invalid"):
        replace(claim, **cast(Any, {field_name: invalid_value}))


def test_claim_rejects_tampered_canonical_digest() -> None:
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(_claim(), canonical_digest="f" * 64)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("expected_assessment_count_pre", 1),
        ("expected_assessment_count_post", 2),
        ("invocation_deadline", NOW),
        ("assessor_id", "assessor.changed"),
        ("receipt_verification_signing_key_id", "key.changed"),
    ],
)
def test_attempt_rejects_non_single_or_unbound_assessment(
    field_name: str, invalid_value: object
) -> None:
    attempt = _attempt()

    with pytest.raises(ValueError, match="attempt is invalid"):
        replace(attempt, **cast(Any, {field_name: invalid_value}))


def test_instruction_binds_exact_attempt_lineage_and_policy() -> None:
    instruction = _instruction()
    attempt = _attempt()

    assert instruction.attempt_digest == attempt.canonical_digest
    assert instruction.authorization_lease_digest == attempt.authorization_lease_digest
    assert instruction.start_result_digest == attempt.start_result_digest
    assert instruction.runtime_envelope_commitment == attempt.runtime_envelope_commitment
    assert instruction.destination_fencing_token_digest == (
        attempt.destination_fencing_token_digest
    )
    assert instruction.protected_slot_commitment == attempt.protected_slot_commitment
    assert instruction.request_nonce_digest == attempt.request_nonce_digest


def test_instruction_rejects_changed_assessor_or_profile_binding() -> None:
    instruction = _instruction()

    with pytest.raises(ValueError, match="instruction is invalid"):
        replace(instruction, assessor_version="2.0")
    with pytest.raises(ValueError, match="instruction is invalid"):
        replace(instruction, readiness_profile_digest="f" * 64)


def test_signed_envelope_and_invocation_bind_exact_instruction() -> None:
    envelope = _signed_envelope()
    instruction = envelope.instruction
    invocation = WorkflowProtectedRuntimeReadinessInvocation(
        protected_operation_reference=instruction.protected_operation_reference,
        instruction_digest=instruction.canonical_digest,
        invocation_deadline=instruction.invocation_deadline,
        signed_instruction_envelope=envelope,
    )

    assert invocation.instruction_digest == instruction.canonical_digest
    with pytest.raises(ValueError, match="invocation is invalid"):
        replace(invocation, instruction_digest="f" * 64)


def test_signed_envelope_rejects_receipt_key_confusion() -> None:
    envelope = _signed_envelope()
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()

    with pytest.raises(ValueError, match="envelope is invalid"):
        replace(envelope, signing_key_id=policy.receipt_verification_signing_key_id)


@pytest.mark.parametrize(
    ("state", "expected_ready", "assessment_performed", "count_post"),
    [
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY,
            True,
            True,
            1,
        ),
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY,
            False,
            True,
            1,
        ),
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT,
            None,
            False,
            0,
        ),
    ],
)
def test_receipt_accepts_known_metadata_only_terminal_evidence(
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState,
    expected_ready: bool | None,
    assessment_performed: bool,
    count_post: int,
) -> None:
    receipt = _receipt(state)

    assert receipt.result_state is state
    assert receipt.attempt_digest == _attempt().canonical_digest
    assert receipt.runtime_ready is expected_ready
    assert receipt.assessment_count_pre == 0
    assert receipt.assessment_count_post == count_post
    assert receipt.readiness_assessment_performed is assessment_performed


def test_receipt_rejects_uncertain_state() -> None:
    receipt = _receipt(
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY
    )

    with pytest.raises(ValueError, match="receipt is invalid"):
        replace(
            receipt,
            result_state=(
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READINESS_OUTCOME_UNCERTAIN,
        )


@pytest.mark.parametrize(
    ("state", "changes"),
    [
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY,
            {"assessment_count_post": 0},
        ),
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY,
            {"runtime_ready": None},
        ),
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY,
            {"readiness_assessment_performed": False},
        ),
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT,
            {"assessment_count_post": 1},
        ),
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT,
            {"runtime_ready": False},
        ),
        (
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT,
            {"readiness_assessment_performed": True},
        ),
    ],
)
def test_receipt_rejects_contradictory_counts_values_and_performed_flags(
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState,
    changes: dict[str, object],
) -> None:
    receipt = _receipt(state)

    with pytest.raises(ValueError, match="receipt is invalid"):
        replace(receipt, **cast(Any, changes))


@pytest.mark.parametrize(
    "field_name",
    [
        "runtime_locator_returned",
        "process_identifier_returned",
        "runtime_context_returned",
        "endpoint_material_returned",
        "credential_material_returned",
        "secret_material_returned",
        "command_constructed",
        "prompt_constructed",
        "model_inference_performed",
        "network_activity_performed",
        "connector_activity_performed",
        "mcp_activity_performed",
        "publication_performed",
        "delivery_performed",
        "dispatch_performed",
        "execution_performed",
        "infrastructure_mutation_performed",
    ],
)
def test_receipt_rejects_every_prohibited_material_or_side_effect(field_name: str) -> None:
    receipt = _receipt(
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY
    )

    with pytest.raises(ValueError, match="receipt is invalid"):
        replace(receipt, **cast(Any, {field_name: True}))


def test_receipt_rejects_value_state_mismatch_and_deadline_equality() -> None:
    receipt = _receipt(
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY
    )

    with pytest.raises(ValueError, match="receipt is invalid"):
        replace(receipt, runtime_ready=False)
    with pytest.raises(ValueError, match="receipt is invalid"):
        replace(receipt, completed_at=receipt.invocation_deadline)


@pytest.mark.parametrize(
    "state",
    list(WorkflowProtectedRuntimeReadinessConsumptionResultState),
)
def test_all_four_terminal_results_are_canonical_and_zero_authority(
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState,
) -> None:
    result = _result(state)

    assert result.state is state
    assert not any(result.authority.canonical_value().values())
    assert result.canonical_digest == _digest(_without_digest(result))


def test_failed_and_uncertain_results_never_claim_runtime_readiness() -> None:
    failed = _result(
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
    )
    uncertain = _result(
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_OUTCOME_UNCERTAIN
    )

    assert failed.outcome_known is True
    assert failed.assessment_performed is False
    assert failed.runtime_ready is None
    assert failed.assessor_receipt_digest is not None
    assert failed.completed_at is not None
    assert uncertain.outcome_known is False
    assert uncertain.assessment_performed is None
    assert uncertain.runtime_ready is None
    assert uncertain.assessor_receipt_digest is None
    assert uncertain.completed_at is None


def test_failed_result_requires_signed_receipt_digest_and_completion_time() -> None:
    result = _result(
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
    )

    with pytest.raises(ValueError, match="result is invalid"):
        replace(result, assessor_receipt_digest=None)
    with pytest.raises(ValueError, match="result is invalid"):
        replace(result, completed_at=None)


def test_result_rejects_contradictory_readiness_and_receipt_state() -> None:
    result = _result(
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY
    )

    with pytest.raises(ValueError, match="result is invalid"):
        replace(result, runtime_ready=False)
    with pytest.raises(ValueError, match="result is invalid"):
        replace(result, assessor_receipt_digest=None)


def test_metadata_contract_has_no_prohibited_bearer_material_fields() -> None:
    prohibited_exact_fields = {
        "runtime_locator",
        "process_id",
        "context",
        "endpoint",
        "credential",
        "secret",
        "command",
        "prompt",
        "model",
        "network",
        "connector",
        "mcp",
    }
    contract_types = (
        WorkflowProtectedRuntimeReadinessConsumptionClaim,
        WorkflowProtectedRuntimeReadinessAttempt,
        WorkflowProtectedRuntimeReadinessInstruction,
        WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
        WorkflowProtectedRuntimeReadinessInvocation,
        WorkflowProtectedRuntimeReadinessReceipt,
        WorkflowProtectedRuntimeReadinessResult,
    )

    for contract_type in contract_types:
        assert prohibited_exact_fields.isdisjoint({field.name for field in fields(contract_type)})
