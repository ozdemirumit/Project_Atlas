from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters.protected_runtime_starters import (
    DenyAllWorkflowProtectedRuntimeStartInstructionSignatureVerifier,
    DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeStarter,
    DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeStartReceiptSignatureVerifier,
    DevelopmentWorkflowProtectedRuntimeStartOutcome,
    UnavailableWorkflowProtectedRuntimeStarter,
    UnavailableWorkflowProtectedRuntimeStartInstructionSigner,
)
from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartConsumptionError,
    build_workflow_protected_runtime_start_invocation,
    build_workflow_protected_runtime_start_signed_instruction_envelope,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionResultState,
    WorkflowProtectedRuntimeStartInstruction,
    WorkflowProtectedRuntimeStartSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _instruction(
    *,
    attempt_id: str = "runtime-start-attempt.test",
    claim_digest: str = "2" * 64,
) -> WorkflowProtectedRuntimeStartInstruction:
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    values: dict[str, object] = {
        "attempt_id": attempt_id,
        "attempt_digest": "1" * 64,
        "consumption_id": "runtime-start-consumption.test",
        "claim_id": "runtime-start-consumption-claim.test",
        "claim_digest": claim_digest,
        "authorization_lease_id": "runtime-start-authorization-lease.test",
        "authorization_lease_digest": "3" * 64,
        "protected_operation_reference": "protected-operation.test",
        "destination_deployment_id": "deployment.test",
        "destination_generation": 3,
        "destination_fencing_token_digest": "5" * 64,
        "runtime_slot_commitment": "6" * 64,
        "runtime_slot_generation": 7,
        "runtime_envelope_id": "runtime-envelope.test",
        "runtime_envelope_commitment": "7" * 64,
        "runtime_envelope_generation": 7,
        "expected_start_count_pre": 0,
        "expected_start_count_post": 1,
        "runtime_start_profile_id": policy.runtime_start_profile_id,
        "runtime_start_profile_version": policy.runtime_start_profile_version,
        "runtime_start_profile_digest": policy.runtime_start_profile_digest,
        "starter_contract_id": policy.required_starter_contract_id,
        "starter_contract_version": policy.required_starter_contract_version,
        "starter_id": policy.approved_starter_id,
        "starter_version": policy.approved_starter_version,
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
    return WorkflowProtectedRuntimeStartInstruction(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_mapping(values))
    )


def _invocation(
    *,
    attempt_id: str = "runtime-start-attempt.test",
    claim_digest: str = "2" * 64,
) -> Any:
    instruction = _instruction(attempt_id=attempt_id, claim_digest=claim_digest)
    signer = DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSigner(
        development_enabled=True
    )
    envelope = build_workflow_protected_runtime_start_signed_instruction_envelope(
        instruction, signer
    )
    return build_workflow_protected_runtime_start_invocation(envelope)


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


def _forge_invocation_signature(valid: Any) -> Any:
    instruction = valid.signed_instruction_envelope.instruction
    signature_payload = {
        "instruction": instruction.digest_payload()
        | {"canonical_digest": instruction.canonical_digest},
        "signing_key_id": valid.signed_instruction_envelope.signing_key_id,
        "signature_algorithm": valid.signed_instruction_envelope.signature_algorithm,
    }
    envelope_values = signature_payload | {"integrity_signature": "f" * 64}
    forged_envelope = WorkflowProtectedRuntimeStartSignedInstructionEnvelope(
        instruction=instruction,
        signing_key_id=valid.signed_instruction_envelope.signing_key_id,
        signature_algorithm=valid.signed_instruction_envelope.signature_algorithm,
        integrity_signature="f" * 64,
        canonical_digest=canonical_digest(envelope_values),
    )
    return build_workflow_protected_runtime_start_invocation(forged_envelope)


def test_production_defaults_are_unavailable_and_deny_all() -> None:
    signer = UnavailableWorkflowProtectedRuntimeStartInstructionSigner()
    starter = UnavailableWorkflowProtectedRuntimeStarter()
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()

    assert signer.available is False
    assert starter.available is False
    instruction_verifier = DenyAllWorkflowProtectedRuntimeStartInstructionSignatureVerifier()
    receipt_verifier = DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier()
    assert instruction_verifier.available is False
    assert receipt_verifier.available is False
    assert starter.starter_contract_id == policy.required_starter_contract_id
    assert starter.starter_contract_version == policy.required_starter_contract_version
    assert starter.starter_id == policy.approved_starter_id
    assert starter.starter_version == policy.approved_starter_version
    assert instruction_verifier.verify_instruction_envelope(cast(Any, object())) is False
    assert receipt_verifier.verify_receipt(cast(Any, object())) is False


@pytest.mark.asyncio
async def test_unavailable_production_components_fail_closed() -> None:
    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_instruction_signer_unavailable",
    ):
        UnavailableWorkflowProtectedRuntimeStartInstructionSigner().sign_instruction_envelope_digest(
            "a" * 64
        )

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_starter_unavailable",
    ):
        await UnavailableWorkflowProtectedRuntimeStarter().start_runtime(cast(Any, object()))


@pytest.mark.asyncio
async def test_development_starter_validates_instruction_and_deduplicates_exact_call() -> None:
    invocation = _invocation()
    starter = DeterministicDevelopmentWorkflowProtectedRuntimeStarter(
        development_enabled=True, clock=lambda: NOW
    )
    receipt_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeStartReceiptSignatureVerifier(
            development_enabled=True
        )
    )

    first = await starter.start_runtime(invocation)
    replay = await starter.start_runtime(invocation)

    assert replay is first
    assert starter.calls == [invocation]
    assert receipt_verifier.verify_receipt(first) is True
    assert (
        first.result_state
        is WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
    )
    assert first.runtime_started is True
    assert first.runtime_start_count_pre == 0
    assert first.runtime_start_count_post == 1
    assert first.readiness_probe_performed is False
    assert first.publication_performed is False
    assert first.delivery_performed is False
    assert not any(
        hasattr(first, name)
        for name in (
            "runtime_locator",
            "endpoint",
            "credential",
            "protected_material",
        )
    )


@pytest.mark.asyncio
async def test_development_starter_rejects_invalid_instruction_signature() -> None:
    valid = _invocation()
    forged = _forge_invocation_signature(valid)
    starter = DeterministicDevelopmentWorkflowProtectedRuntimeStarter(
        development_enabled=True, clock=lambda: NOW
    )

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_instruction_envelope_invalid",
    ):
        await starter.start_runtime(forged)

    assert starter.calls == []


@pytest.mark.asyncio
async def test_exact_receipt_replay_revalidates_signature_but_bypasses_deadline() -> None:
    invocation = _invocation()
    current = NOW
    starter = DeterministicDevelopmentWorkflowProtectedRuntimeStarter(
        development_enabled=True, clock=lambda: current
    )
    receipt = await starter.start_runtime(invocation)
    current = NOW + timedelta(seconds=2)

    assert await starter.start_runtime(invocation) is receipt
    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_instruction_envelope_invalid",
    ):
        await starter.start_runtime(_forge_invocation_signature(invocation))

    assert starter.calls == [invocation]


@pytest.mark.asyncio
async def test_development_starter_rejects_changed_attempt_and_envelope_reuse() -> None:
    starter = DeterministicDevelopmentWorkflowProtectedRuntimeStarter(
        development_enabled=True, clock=lambda: NOW
    )
    await starter.start_runtime(_invocation())

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_instruction_changed_for_attempt",
    ):
        await starter.start_runtime(_invocation(claim_digest="9" * 64))
    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_compare_and_swap_rejected",
    ):
        await starter.start_runtime(_invocation(attempt_id="runtime-start-attempt.competing"))

    assert len(starter.calls) == 1


@pytest.mark.asyncio
async def test_development_starter_known_failure_proves_no_effect() -> None:
    starter = DeterministicDevelopmentWorkflowProtectedRuntimeStarter(
        development_enabled=True,
        clock=lambda: NOW,
        outcome=DevelopmentWorkflowProtectedRuntimeStartOutcome.KNOWN_NO_EFFECT_FAILURE,
    )

    receipt = await starter.start_runtime(_invocation())

    assert (
        receipt.result_state
        is WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_FAILED_WITHOUT_START
    )
    assert receipt.runtime_started is False
    assert receipt.runtime_start_count_pre == receipt.runtime_start_count_post == 0
    assert receipt.residual_process_absent is True
    assert receipt.residual_task_absent is True
    assert receipt.scheduling_performed is False


@pytest.mark.asyncio
async def test_partial_transition_is_permanently_uncertain_and_never_retried() -> None:
    invocation = _invocation()
    starter = DeterministicDevelopmentWorkflowProtectedRuntimeStarter(
        development_enabled=True,
        clock=lambda: NOW,
        outcome=DevelopmentWorkflowProtectedRuntimeStartOutcome.PARTIAL_UNCERTAIN,
    )

    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_partial_transition_outcome_uncertain",
    ):
        await starter.start_runtime(invocation)
    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_outcome_permanently_uncertain",
    ):
        await starter.start_runtime(invocation)
    with pytest.raises(
        WorkflowProtectedRuntimeStartConsumptionError,
        match="protected_runtime_start_instruction_envelope_invalid",
    ):
        await starter.start_runtime(_forge_invocation_signature(invocation))

    assert starter.calls == [invocation]


def test_development_signature_boundaries_are_distinct_and_opt_in() -> None:
    signer = DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSigner()
    instruction_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier()
    )
    receipt_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeStartReceiptSignatureVerifier()
    )

    assert signer.available is False
    assert instruction_verifier.available is False
    assert receipt_verifier.available is False
    assert (
        DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier(
            development_enabled=True
        ).available
        is True
    )
    assert (
        DeterministicDevelopmentWorkflowProtectedRuntimeStartReceiptSignatureVerifier(
            development_enabled=True
        ).available
        is True
    )
    assert all(
        not hasattr(component, "key")
        and not hasattr(component, "secret")
        and not hasattr(component, "credential")
        for component in (signer, instruction_verifier, receipt_verifier)
    )
