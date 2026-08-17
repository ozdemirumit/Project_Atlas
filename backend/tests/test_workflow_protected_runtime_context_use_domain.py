from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    build_workflow_protected_runtime_context_use_instruction,
    build_workflow_protected_runtime_context_use_invocation,
    build_workflow_protected_runtime_context_use_signed_instruction_envelope,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID,
    WorkflowProtectedRuntimeContextUseAttempt,
    WorkflowProtectedRuntimeContextUseAttemptState,
    WorkflowProtectedRuntimeContextUseAuthority,
    WorkflowProtectedRuntimeContextUseClaim,
    WorkflowProtectedRuntimeContextUseFailureClass,
    WorkflowProtectedRuntimeContextUseReceipt,
    WorkflowProtectedRuntimeContextUseResult,
    WorkflowProtectedRuntimeContextUseResultState,
    code_owned_workflow_protected_runtime_context_use_policy,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


class _InstructionSigner:
    @property
    def available(self) -> bool:
        return True

    @property
    def signing_key_id(self) -> str:
        return WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID

    @property
    def signature_algorithm(self) -> str:
        return WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        return canonical_digest({"payload_digest": payload_digest, "test_key": "imp-222"})


def _canonical_mapping(values: dict[str, object]) -> dict[str, object]:
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


def _claim(**changes: object) -> WorkflowProtectedRuntimeContextUseClaim:
    policy = code_owned_workflow_protected_runtime_context_use_policy()
    values: dict[str, object] = {
        "claim_id": "runtime-context-use-claim.imp-222",
        "use_id": "runtime-context-use.imp-222",
        "attempt_id": "runtime-context-use-attempt.imp-222",
        "authorization_consumption_result_id": "use-consumption-result.imp-221",
        "authorization_consumption_result_digest": "1" * 64,
        "authorization_consumption_claim_id": "use-consumption-claim.imp-221",
        "authorization_consumption_claim_digest": "2" * 64,
        "authorization_lease_id": "use-authorization-lease.imp-220",
        "authorization_lease_digest": "3" * 64,
        "injection_result_id": "injection-result.imp-219",
        "injection_result_digest": "4" * 64,
        "destination_deployment_id": "deployment.imp-222",
        "destination_generation": 7,
        "destination_fencing_token_digest": "5" * 64,
        "runtime_slot_commitment": "6" * 64,
        "runtime_slot_pre_generation": 11,
        "injected_context_usable_until": NOW + timedelta(seconds=1),
        "use_profile_id": policy.use_profile_id,
        "use_profile_version": policy.use_profile_version,
        "use_profile_digest": policy.use_profile_digest,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "idempotency_digest": "7" * 64,
        "request_fingerprint": "8" * 64,
        "use_authorization_audit_digest": "9" * 64,
        "irreversible_use_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "claimed_at": NOW,
        "authority": WorkflowProtectedRuntimeContextUseAuthority(),
    }
    values.update(changes)
    return WorkflowProtectedRuntimeContextUseClaim(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def _attempt(**changes: object) -> WorkflowProtectedRuntimeContextUseAttempt:
    policy = code_owned_workflow_protected_runtime_context_use_policy()
    claim = _claim()
    values: dict[str, object] = {
        "attempt_id": claim.attempt_id,
        "use_id": claim.use_id,
        "claim_id": claim.claim_id,
        "claim_digest": claim.canonical_digest,
        "authorization_consumption_result_id": claim.authorization_consumption_result_id,
        "authorization_consumption_result_digest": claim.authorization_consumption_result_digest,
        "authorization_consumption_claim_id": claim.authorization_consumption_claim_id,
        "authorization_consumption_claim_digest": claim.authorization_consumption_claim_digest,
        "authorization_lease_id": claim.authorization_lease_id,
        "authorization_lease_digest": claim.authorization_lease_digest,
        "injection_result_id": claim.injection_result_id,
        "injection_result_digest": claim.injection_result_digest,
        "protected_operation_reference": "protected-operation.imp-222",
        "destination_deployment_id": claim.destination_deployment_id,
        "destination_generation": claim.destination_generation,
        "destination_fencing_token_digest": claim.destination_fencing_token_digest,
        "runtime_slot_commitment": claim.runtime_slot_commitment,
        "runtime_slot_pre_generation": claim.runtime_slot_pre_generation,
        "expected_runtime_slot_post_generation": claim.runtime_slot_pre_generation + 1,
        "expected_use_count_pre": 0,
        "expected_use_count_post": 1,
        "injected_context_usable_until": claim.injected_context_usable_until,
        "use_profile_id": policy.use_profile_id,
        "use_profile_version": policy.use_profile_version,
        "use_profile_digest": policy.use_profile_digest,
        "required_executor_contract_id": policy.required_executor_contract_id,
        "required_executor_contract_version": policy.required_executor_contract_version,
        "approved_executor_id": policy.approved_executor_id,
        "approved_executor_version": policy.approved_executor_version,
        "receipt_verification_signing_key_id": policy.receipt_verification_signing_key_id,
        "eligibility_attestation_id": "eligibility-attestation.imp-222",
        "eligibility_attestation_digest": "a" * 64,
        "request_nonce_digest": "b" * 64,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "started_at": NOW,
        "use_deadline": NOW + timedelta(milliseconds=500),
        "attestation_valid_until": NOW + timedelta(milliseconds=700),
        "state": WorkflowProtectedRuntimeContextUseAttemptState.USE_STARTED,
        "authority": WorkflowProtectedRuntimeContextUseAuthority(),
    }
    values.update(changes)
    return WorkflowProtectedRuntimeContextUseAttempt(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def _receipt(
    attempt: WorkflowProtectedRuntimeContextUseAttempt | None = None,
    **changes: object,
) -> WorkflowProtectedRuntimeContextUseReceipt:
    attempt = attempt or _attempt()
    instruction = build_workflow_protected_runtime_context_use_instruction(attempt)
    values: dict[str, object] = {
        "instruction_digest": instruction.canonical_digest,
        "protected_operation_reference": instruction.protected_operation_reference,
        "authorization_consumption_result_id": instruction.authorization_consumption_result_id,
        "authorization_consumption_result_digest": (
            instruction.authorization_consumption_result_digest
        ),
        "destination_deployment_id": instruction.destination_deployment_id,
        "destination_generation": instruction.destination_generation,
        "destination_fencing_token_digest": instruction.destination_fencing_token_digest,
        "runtime_slot_commitment": instruction.runtime_slot_commitment,
        "runtime_slot_pre_generation": instruction.runtime_slot_pre_generation,
        "runtime_slot_post_generation": instruction.expected_runtime_slot_post_generation,
        "use_count_pre": instruction.expected_use_count_pre,
        "use_count_post": instruction.expected_use_count_post,
        "use_profile_id": instruction.use_profile_id,
        "use_profile_version": instruction.use_profile_version,
        "use_profile_digest": instruction.use_profile_digest,
        "executor_contract_id": instruction.executor_contract_id,
        "executor_contract_version": instruction.executor_contract_version,
        "executor_id": instruction.executor_id,
        "executor_version": instruction.executor_version,
        "state": (
            WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY
        ),
        "failure_class": None,
        "context_adopted": True,
        "protected_runtime_context_use_performed": True,
        "context_terminal_non_reusable": True,
        "transient_material_zeroized": True,
        "context_disclosed": False,
        "runtime_started": False,
        "runtime_resumed": False,
        "process_created": False,
        "prompt_constructed": False,
        "model_inference_performed": False,
        "model_output_created": False,
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
        "completed_at": NOW + timedelta(milliseconds=200),
        "use_deadline": instruction.use_deadline,
        "attested_by": "executor.workflow-protected-runtime-context-use",
        "signing_key_id": (
            code_owned_workflow_protected_runtime_context_use_policy().receipt_verification_signing_key_id
        ),
        "signature_algorithm": "hmac-sha256",
        "integrity_signature": "c" * 64,
    }
    values.update(changes)
    return WorkflowProtectedRuntimeContextUseReceipt(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def _result(
    attempt: WorkflowProtectedRuntimeContextUseAttempt | None = None,
    receipt: WorkflowProtectedRuntimeContextUseReceipt | None = None,
    **changes: object,
) -> WorkflowProtectedRuntimeContextUseResult:
    attempt = attempt or _attempt()
    receipt = receipt or _receipt(attempt)
    values: dict[str, object] = {
        "result_id": "runtime-context-use-result.imp-222",
        "use_id": attempt.use_id,
        "attempt_id": attempt.attempt_id,
        "attempt_digest": attempt.canonical_digest,
        "claim_id": attempt.claim_id,
        "claim_digest": attempt.claim_digest,
        "authorization_consumption_result_id": attempt.authorization_consumption_result_id,
        "authorization_consumption_result_digest": (
            attempt.authorization_consumption_result_digest
        ),
        "destination_deployment_id": attempt.destination_deployment_id,
        "destination_generation": attempt.destination_generation,
        "destination_fencing_token_digest": attempt.destination_fencing_token_digest,
        "runtime_slot_commitment": attempt.runtime_slot_commitment,
        "runtime_slot_pre_generation": attempt.runtime_slot_pre_generation,
        "runtime_slot_post_generation": receipt.runtime_slot_post_generation,
        "use_count_pre": receipt.use_count_pre,
        "use_count_post": receipt.use_count_post,
        "use_profile_id": attempt.use_profile_id,
        "use_profile_version": attempt.use_profile_version,
        "use_profile_digest": attempt.use_profile_digest,
        "executor_contract_id": receipt.executor_contract_id,
        "executor_contract_version": receipt.executor_contract_version,
        "executor_id": receipt.executor_id,
        "executor_version": receipt.executor_version,
        "executor_receipt_digest": receipt.canonical_digest,
        "state": receipt.state,
        "failure_class": receipt.failure_class,
        "outcome_known": True,
        "context_adopted": receipt.context_adopted,
        "protected_runtime_context_use_performed": (
            receipt.protected_runtime_context_use_performed
        ),
        "context_terminal_non_reusable": receipt.context_terminal_non_reusable,
        "transient_material_zeroized": receipt.transient_material_zeroized,
        "completed_at": receipt.completed_at,
        "recorded_at": receipt.completed_at,
        "use_deadline": attempt.use_deadline,
        "authority": WorkflowProtectedRuntimeContextUseAuthority(),
    }
    values.update(changes)
    return WorkflowProtectedRuntimeContextUseResult(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def test_policy_is_code_owned_replay_first_and_forbids_operational_work() -> None:
    policy = code_owned_workflow_protected_runtime_context_use_policy()

    assert policy.durable_replay_required is True
    assert policy.fresh_attestation_required is True
    assert policy.claim_before_executor_io_required is True
    assert policy.at_most_one_executor_call_required is True
    assert policy.automatic_retry_allowed is False
    assert policy.runtime_start_forbidden is True
    assert policy.model_inference_forbidden is True
    assert policy.connector_activity_forbidden is True
    assert policy.infrastructure_mutation_forbidden is True

    with pytest.raises(ValueError, match="not code-owned"):
        replace(policy, automatic_retry_allowed=True)


def test_authority_has_exactly_twenty_six_false_fields() -> None:
    authority = WorkflowProtectedRuntimeContextUseAuthority()

    assert len(authority.canonical_value()) == 26
    assert not any(authority.canonical_value().values())
    with pytest.raises(ValueError, match="grants no authority"):
        WorkflowProtectedRuntimeContextUseAuthority(runtime_use_authorized=True)
    with pytest.raises(ValueError, match="grants no authority"):
        WorkflowProtectedRuntimeContextUseAuthority(
            protected_runtime_context_use_authority_granted=True
        )


def test_claim_and_attempt_require_irreversibility_zero_to_one_and_deadline() -> None:
    claim = _claim()
    attempt = _attempt()

    assert claim.irreversible_use_acknowledged is True
    assert claim.uncertainty_no_retry_acknowledged is True
    assert attempt.expected_use_count_pre == 0
    assert attempt.expected_use_count_post == 1
    assert attempt.expected_runtime_slot_post_generation == attempt.runtime_slot_pre_generation + 1

    with pytest.raises(ValueError, match="claim is invalid"):
        _claim(uncertainty_no_retry_acknowledged=False)
    with pytest.raises(ValueError, match="attempt is invalid"):
        _attempt(expected_use_count_post=2)


def test_instruction_envelope_binds_full_lineage_and_minimizes_the_call_gate() -> None:
    attempt = _attempt()
    instruction = build_workflow_protected_runtime_context_use_instruction(attempt)
    envelope = build_workflow_protected_runtime_context_use_signed_instruction_envelope(
        instruction, _InstructionSigner()
    )
    invocation = build_workflow_protected_runtime_context_use_invocation(instruction, envelope)

    assert invocation.protected_operation_reference == instruction.protected_operation_reference
    assert invocation.instruction_digest == instruction.canonical_digest
    assert invocation.signed_instruction_envelope == envelope
    assert instruction.attempt_digest == attempt.canonical_digest
    assert instruction.claim_digest == attempt.claim_digest
    assert instruction.authorization_consumption_claim_digest == (
        attempt.authorization_consumption_claim_digest
    )
    assert instruction.authorization_lease_digest == attempt.authorization_lease_digest
    assert instruction.injection_result_digest == attempt.injection_result_digest
    assert instruction.request_nonce_digest == attempt.request_nonce_digest
    assert instruction.scope == attempt.scope
    assert instruction.consumer_subject_id == attempt.consumer_subject_id
    assert instruction.policy_digest == attempt.policy_digest
    assert envelope.signing_key_id == (
        WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID
    )
    assert envelope.signature_algorithm == (
        WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM
    )
    assert set(invocation.__slots__) == {
        "protected_operation_reference",
        "instruction_digest",
        "use_deadline",
        "signed_instruction_envelope",
    }

    with pytest.raises(ValueError, match="instruction envelope is invalid"):
        replace(envelope, signing_key_id="key.unapproved")


def test_verified_success_is_use_fact_only_and_rejects_forbidden_effects() -> None:
    result = _result()

    assert result.state.value == "context_used_once_in_protected_boundary"
    assert result.protected_runtime_context_use_performed is True
    assert result.use_count_pre == 0
    assert result.use_count_post == 1
    assert not any(result.authority.canonical_value().values())

    with pytest.raises(ValueError, match="receipt is invalid"):
        _receipt(model_inference_performed=True)
    with pytest.raises(ValueError, match="receipt is invalid"):
        _receipt(context_disclosed=True)


def test_known_failure_proves_no_use_and_still_consumes_the_attempt() -> None:
    attempt = _attempt()
    receipt = _receipt(
        attempt,
        state=WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USE_FAILED_WITHOUT_USE,
        failure_class=WorkflowProtectedRuntimeContextUseFailureClass.CONTEXT_COMPARE_AND_SWAP_REJECTED,
        runtime_slot_post_generation=attempt.runtime_slot_pre_generation,
        use_count_post=0,
        context_adopted=False,
        protected_runtime_context_use_performed=False,
        context_terminal_non_reusable=False,
    )
    result = _result(attempt, receipt)

    assert result.outcome_known is True
    assert result.protected_runtime_context_use_performed is False
    assert result.runtime_slot_post_generation == result.runtime_slot_pre_generation

    with pytest.raises(ValueError, match="receipt is invalid"):
        _receipt(
            attempt,
            state=(WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USE_FAILED_WITHOUT_USE),
            failure_class=(
                WorkflowProtectedRuntimeContextUseFailureClass.CONTEXT_USE_OUTCOME_UNCERTAIN
            ),
            runtime_slot_post_generation=attempt.runtime_slot_pre_generation,
            use_count_post=0,
            context_adopted=False,
            protected_runtime_context_use_performed=False,
            context_terminal_non_reusable=False,
        )


def test_uncertain_result_is_receipt_free_permanent_non_success() -> None:
    attempt = _attempt()
    result = _result(
        attempt,
        executor_receipt_digest=None,
        runtime_slot_post_generation=None,
        use_count_post=None,
        state=WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USE_OUTCOME_UNCERTAIN,
        failure_class=WorkflowProtectedRuntimeContextUseFailureClass.CONTEXT_USE_OUTCOME_UNCERTAIN,
        outcome_known=False,
        context_adopted=False,
        protected_runtime_context_use_performed=False,
        context_terminal_non_reusable=False,
        transient_material_zeroized=False,
        completed_at=None,
        recorded_at=attempt.use_deadline,
    )

    assert result.executor_receipt_digest is None
    assert result.outcome_known is False
    assert result.protected_runtime_context_use_performed is False
