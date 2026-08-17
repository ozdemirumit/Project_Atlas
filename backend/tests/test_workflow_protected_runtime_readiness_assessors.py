from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters.protected_runtime_readiness_assessors import (
    DenyAllWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier,
    DenyAllWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor,
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier,
    DevelopmentWorkflowProtectedRuntimeReadinessOutcome,
    UnavailableWorkflowProtectedRuntimeReadinessAssessor,
    UnavailableWorkflowProtectedRuntimeReadinessInstructionSigner,
)
from atlas.modules.workflows.application.protected_runtime_readiness_consumption_ports import (
    WorkflowProtectedRuntimeReadinessConsumptionError,
    build_workflow_protected_runtime_readiness_invocation,
    build_workflow_protected_runtime_readiness_signed_instruction_envelope,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    WorkflowProtectedRuntimeReadinessInstruction,
    WorkflowProtectedRuntimeReadinessReceipt,
    WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
_FORBIDDEN_RECEIPT_FLAGS = (
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
)


def _instruction(
    *,
    attempt_id: str = "runtime-readiness-attempt.test",
    claim_digest: str = "2" * 64,
) -> WorkflowProtectedRuntimeReadinessInstruction:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    values: dict[str, object] = {
        "consumption_id": "runtime-readiness-consumption.test",
        "attempt_id": attempt_id,
        "attempt_digest": "1" * 64,
        "claim_id": "runtime-readiness-consumption-claim.test",
        "claim_digest": claim_digest,
        "authorization_lease_id": "runtime-readiness-authorization-lease.test",
        "authorization_lease_digest": "3" * 64,
        "start_result_id": "runtime-start-result.test",
        "start_result_digest": "4" * 64,
        "protected_operation_reference": "protected-operation.test",
        "destination_deployment_id": "deployment.test",
        "destination_generation": 3,
        "destination_fencing_token_digest": "5" * 64,
        "protected_slot_commitment": "6" * 64,
        "protected_slot_generation": 7,
        "runtime_envelope_id": "runtime-envelope.test",
        "runtime_envelope_commitment": "7" * 64,
        "runtime_envelope_generation": 7,
        "readiness_profile_id": policy.readiness_profile_id,
        "readiness_profile_version": policy.readiness_profile_version,
        "readiness_profile_digest": policy.readiness_profile_digest,
        "expected_assessment_count_pre": 0,
        "expected_assessment_count_post": 1,
        "assessor_contract_id": policy.required_assessor_contract_id,
        "assessor_contract_version": policy.required_assessor_contract_version,
        "assessor_id": policy.approved_assessor_id,
        "assessor_version": policy.approved_assessor_version,
        "request_nonce_digest": "8" * 64,
        "scope": WorkflowScope(
            organization_id="organization.test",
            environment_id="environment.test",
            site_id="site.test",
        ),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "started_at": NOW - timedelta(milliseconds=100),
        "invocation_deadline": NOW + timedelta(milliseconds=900),
    }
    return WorkflowProtectedRuntimeReadinessInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def _invocation(
    *,
    attempt_id: str = "runtime-readiness-attempt.test",
    claim_digest: str = "2" * 64,
) -> Any:
    instruction = _instruction(attempt_id=attempt_id, claim_digest=claim_digest)
    signer = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSigner(
        development_enabled=True
    )
    envelope = build_workflow_protected_runtime_readiness_signed_instruction_envelope(
        instruction, signer
    )
    return build_workflow_protected_runtime_readiness_invocation(envelope)


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


def _forged_invocation_signature(valid: Any) -> Any:
    instruction = valid.signed_instruction_envelope.instruction
    envelope_values: dict[str, object] = {
        "instruction": instruction.digest_payload()
        | {"canonical_digest": instruction.canonical_digest},
        "signing_key_id": valid.signed_instruction_envelope.signing_key_id,
        "signature_algorithm": valid.signed_instruction_envelope.signature_algorithm,
        "integrity_signature": "f" * 64,
    }
    forged = WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope(
        instruction=instruction,
        signing_key_id=cast(str, envelope_values["signing_key_id"]),
        signature_algorithm=cast(str, envelope_values["signature_algorithm"]),
        integrity_signature=cast(str, envelope_values["integrity_signature"]),
        canonical_digest=canonical_digest(envelope_values),
    )
    return build_workflow_protected_runtime_readiness_invocation(forged)


def _receipt_with_signature(
    receipt: WorkflowProtectedRuntimeReadinessReceipt, signature: str
) -> WorkflowProtectedRuntimeReadinessReceipt:
    values = {
        field.name: getattr(receipt, field.name)
        for field in fields(WorkflowProtectedRuntimeReadinessReceipt)
        if field.name != "canonical_digest"
    }
    values["integrity_signature"] = signature
    return WorkflowProtectedRuntimeReadinessReceipt(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def test_production_defaults_are_unavailable_and_deny_all() -> None:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    signer = UnavailableWorkflowProtectedRuntimeReadinessInstructionSigner()
    assessor = UnavailableWorkflowProtectedRuntimeReadinessAssessor()
    instruction_verifier = DenyAllWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier()
    receipt_verifier = DenyAllWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier()

    assert signer.available is False
    assert assessor.available is False
    assert instruction_verifier.available is False
    assert receipt_verifier.available is False
    assert assessor.assessor_contract_id == policy.required_assessor_contract_id
    assert assessor.assessor_contract_version == policy.required_assessor_contract_version
    assert assessor.assessor_id == policy.approved_assessor_id
    assert assessor.assessor_version == policy.approved_assessor_version
    assert assessor.readiness_profile_digest == policy.readiness_profile_digest
    assert instruction_verifier.verify_instruction_envelope(cast(Any, object())) is False
    assert receipt_verifier.verify_receipt(cast(Any, object())) is False


@pytest.mark.asyncio
async def test_unavailable_production_components_fail_closed() -> None:
    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_instruction_signer_unavailable",
    ):
        UnavailableWorkflowProtectedRuntimeReadinessInstructionSigner().sign_instruction_envelope_digest(
            "a" * 64
        )

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_assessor_unavailable",
    ):
        await UnavailableWorkflowProtectedRuntimeReadinessAssessor().assess_runtime_readiness(
            cast(Any, object())
        )


def test_development_instruction_signature_is_opt_in_and_detects_tampering() -> None:
    signer = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSigner()
    verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier()
    )
    enabled_signer = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSigner(
        development_enabled=True
    )
    enabled_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier(
            development_enabled=True
        )
    )
    instruction = _instruction()
    envelope = build_workflow_protected_runtime_readiness_signed_instruction_envelope(
        instruction, enabled_signer
    )

    assert signer.available is False
    assert verifier.verify_instruction_envelope(envelope) is False
    assert enabled_verifier.verify_instruction_envelope(envelope) is True
    assert (
        enabled_verifier.verify_instruction_envelope(
            _forged_invocation_signature(
                build_workflow_protected_runtime_readiness_invocation(envelope)
            ).signed_instruction_envelope
        )
        is False
    )


@pytest.mark.asyncio
async def test_ready_assessment_is_exactly_deduplicated_and_metadata_only() -> None:
    invocation = _invocation()
    assessor = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor(
        development_enabled=True, clock=lambda: NOW
    )
    verifier = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier(
        development_enabled=True
    )

    first = await assessor.assess_runtime_readiness(invocation)
    replay = await assessor.assess_runtime_readiness(invocation)

    assert replay is first
    assert assessor.calls == [invocation]
    assert verifier.verify_receipt(first) is True
    assert (
        first.result_state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
    )
    assert first.runtime_ready is True
    assert first.readiness_assessment_performed is True
    assert (first.assessment_count_pre, first.assessment_count_post) == (0, 1)
    assert first.attempt_digest == invocation.signed_instruction_envelope.instruction.attempt_digest
    assert first.instruction_digest == invocation.instruction_digest
    assert all(getattr(first, name) is False for name in _FORBIDDEN_RECEIPT_FLAGS)
    assert not any(
        hasattr(first, name)
        for name in (
            "runtime_locator",
            "process_id",
            "runtime_context",
            "endpoint",
            "credential",
            "secret",
            "command",
            "prompt",
            "model",
        )
    )


@pytest.mark.asyncio
async def test_exact_receipt_replay_bypasses_deadline_but_revalidates_signature() -> None:
    invocation = _invocation()
    current = NOW
    assessor = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor(
        development_enabled=True, clock=lambda: current
    )
    receipt = await assessor.assess_runtime_readiness(invocation)
    current = NOW + timedelta(seconds=2)

    assert await assessor.assess_runtime_readiness(invocation) is receipt
    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_instruction_envelope_invalid",
    ):
        await assessor.assess_runtime_readiness(_forged_invocation_signature(invocation))

    assert assessor.calls == [invocation]


@pytest.mark.asyncio
async def test_changed_same_attempt_invocation_fails_closed_without_second_assessment() -> None:
    assessor = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor(
        development_enabled=True, clock=lambda: NOW
    )
    await assessor.assess_runtime_readiness(_invocation())

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_instruction_changed_for_attempt",
    ):
        await assessor.assess_runtime_readiness(_invocation(claim_digest="9" * 64))

    assert len(assessor.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "state", "runtime_ready"),
    (
        (
            DevelopmentWorkflowProtectedRuntimeReadinessOutcome.NOT_READY,
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY,
            False,
        ),
        (
            DevelopmentWorkflowProtectedRuntimeReadinessOutcome.FAILED_WITHOUT_ASSESSMENT,
            WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT,
            None,
        ),
    ),
)
async def test_development_known_outcomes_are_signed_and_side_effect_free(
    outcome: DevelopmentWorkflowProtectedRuntimeReadinessOutcome,
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState,
    runtime_ready: bool | None,
) -> None:
    assessor = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor(
        development_enabled=True, clock=lambda: NOW, outcome=outcome
    )
    verifier = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier(
        development_enabled=True
    )

    receipt = await assessor.assess_runtime_readiness(_invocation())

    assert receipt.result_state is state
    assert receipt.runtime_ready is runtime_ready
    assert receipt.readiness_assessment_performed is (runtime_ready is not None)
    assert receipt.assessment_count_pre == 0
    assert receipt.assessment_count_post == (0 if runtime_ready is None else 1)
    assert verifier.verify_receipt(receipt) is True
    assert all(getattr(receipt, name) is False for name in _FORBIDDEN_RECEIPT_FLAGS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "exception_type", "match"),
    (
        (
            DevelopmentWorkflowProtectedRuntimeReadinessOutcome.TIMEOUT,
            TimeoutError,
            "timed out",
        ),
        (
            DevelopmentWorkflowProtectedRuntimeReadinessOutcome.ERROR,
            WorkflowProtectedRuntimeReadinessConsumptionError,
            "protected_runtime_readiness_assessment_failed",
        ),
    ),
)
async def test_timeout_and_error_are_permanently_single_attempt(
    outcome: DevelopmentWorkflowProtectedRuntimeReadinessOutcome,
    exception_type: type[BaseException],
    match: str,
) -> None:
    invocation = _invocation()
    assessor = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor(
        development_enabled=True, clock=lambda: NOW, outcome=outcome
    )

    with pytest.raises(exception_type, match=match):
        await assessor.assess_runtime_readiness(invocation)
    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_outcome_permanently_uncertain",
    ):
        await assessor.assess_runtime_readiness(invocation)

    assert assessor.calls == [invocation]


@pytest.mark.asyncio
async def test_assessor_rejects_expired_instruction_and_naive_clock() -> None:
    invocation = _invocation()
    expired = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor(
        development_enabled=True, clock=lambda: NOW + timedelta(seconds=1)
    )
    naive = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor(
        development_enabled=True, clock=lambda: NOW.replace(tzinfo=None)
    )

    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_deadline_expired",
    ):
        await expired.assess_runtime_readiness(invocation)
    with pytest.raises(
        WorkflowProtectedRuntimeReadinessConsumptionError,
        match="protected_runtime_readiness_development_clock_must_be_aware",
    ):
        await naive.assess_runtime_readiness(invocation)

    assert expired.calls == []
    assert naive.calls == []


@pytest.mark.asyncio
async def test_instruction_and_receipt_keys_are_not_interchangeable() -> None:
    invocation = _invocation()
    assessor = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor(
        development_enabled=True, clock=lambda: NOW
    )
    receipt = await assessor.assess_runtime_readiness(invocation)
    instruction_signer = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSigner(
        development_enabled=True
    )
    receipt_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier(
            development_enabled=True
        )
    )
    confused_signature = instruction_signer.sign_instruction_envelope_digest(
        canonical_digest(receipt.signature_payload())
    )

    assert (
        receipt_verifier.verify_receipt(_receipt_with_signature(receipt, confused_signature))
        is False
    )
    assert all(
        not hasattr(component, "key")
        and not hasattr(component, "secret")
        and not hasattr(component, "credential")
        for component in (instruction_signer, receipt_verifier, assessor)
    )
