from dataclasses import replace

import pytest
from workflow_process_creation_consumption_support import NOW, instruction

from atlas.modules.workflows.adapters.protected_runtime_process_creators import (
    DenyAllWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier,
    DenyAllWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier,
    DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator,
    DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome,
    UnavailableWorkflowProtectedRuntimeProcessCreationInstructionSigner,
    UnavailableWorkflowProtectedRuntimeProcessCreator,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessCreationConsumptionError,
    build_workflow_protected_runtime_process_creation_invocation,
    build_workflow_protected_runtime_process_creation_signed_instruction_envelope,
)
from atlas.modules.workflows.domain.models import canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    WorkflowProtectedRuntimeProcessCreationConsumptionResultState,
    WorkflowProtectedRuntimeProcessCreationInvocation,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
)


def _invocation() -> WorkflowProtectedRuntimeProcessCreationInvocation:
    signer = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner(
        development_enabled=True
    )
    envelope = build_workflow_protected_runtime_process_creation_signed_instruction_envelope(
        instruction(), signer
    )
    return build_workflow_protected_runtime_process_creation_invocation(envelope)


def test_production_components_fail_closed() -> None:
    assert UnavailableWorkflowProtectedRuntimeProcessCreationInstructionSigner().available is False
    assert UnavailableWorkflowProtectedRuntimeProcessCreator().available is False
    assert (
        DenyAllWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier().available
        is False
    )
    assert (
        DenyAllWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier().available is False
    )


@pytest.mark.asyncio
async def test_creator_creates_only_one_sealed_suspended_process_and_exactly_replays() -> None:
    creator = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator(
        development_enabled=True, clock=lambda: NOW
    )
    invocation = _invocation()

    first = await creator.create_sealed_suspended_process(invocation)
    replay = await creator.create_sealed_suspended_process(invocation)

    assert replay == first
    assert len(creator.calls) == 1
    assert (
        first.result_state
        is (
            WorkflowProtectedRuntimeProcessCreationConsumptionResultState
        ).PROCESS_CREATED_SUSPENDED_IN_PROTECTED_BOUNDARY
    )
    assert first.process_created is first.process_sealed is first.process_suspended is True
    assert not any(
        (
            first.process_scheduled,
            first.process_resumed,
            first.process_dispatched,
            first.process_executed,
            first.caller_material_used,
            first.runtime_locator_returned,
            first.process_identifier_returned,
            first.network_activity_performed,
            first.model_activity_performed,
            first.mcp_activity_performed,
            first.connector_activity_performed,
            first.provider_activity_performed,
            first.infrastructure_mutation_performed,
        )
    )
    verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationReceiptSignatureVerifier(
            development_enabled=True
        )
    )
    assert verifier.verify_receipt(first) is True


@pytest.mark.parametrize(
    ("outcome", "expected_state"),
    [
        (
            DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome.REJECTED_WITHOUT_CREATION,
            "process_creation_rejected_without_creation",
        ),
        (
            DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome.FAILED_WITHOUT_CREATION,
            "process_creation_failed_without_creation",
        ),
    ],
)
@pytest.mark.asyncio
async def test_creator_known_no_creation_outcomes_are_terminal(
    outcome: DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome,
    expected_state: str,
) -> None:
    creator = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator(
        development_enabled=True,
        clock=lambda: NOW,
        outcome=outcome,
    )

    receipt = await creator.create_sealed_suspended_process(_invocation())

    assert receipt.result_state.value == expected_state
    assert receipt.process_created is False
    assert receipt.process_sealed is False
    assert receipt.process_suspended is False


@pytest.mark.asyncio
async def test_ambiguous_post_commit_outcome_is_permanent_and_never_retried() -> None:
    creator = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreator(
        development_enabled=True,
        clock=lambda: NOW,
        outcome=(DevelopmentWorkflowProtectedRuntimeProcessCreationOutcome).OUTCOME_UNCERTAIN,
    )
    invocation = _invocation()

    with pytest.raises(WorkflowProtectedRuntimeProcessCreationConsumptionError):
        await creator.create_sealed_suspended_process(invocation)
    with pytest.raises(
        WorkflowProtectedRuntimeProcessCreationConsumptionError,
        match="permanently_uncertain",
    ):
        await creator.create_sealed_suspended_process(invocation)
    assert len(creator.calls) == 1


def test_instruction_and_receipt_keys_are_distinct() -> None:
    signer = DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSigner(
        development_enabled=True
    )
    instruction_verifier = (
        DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationInstructionSignatureVerifier(
            development_enabled=True
        )
    )
    envelope = build_workflow_protected_runtime_process_creation_signed_instruction_envelope(
        instruction(), signer
    )

    assert instruction_verifier.verify_instruction_envelope(envelope) is True
    policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
    assert signer.signing_key_id != policy.receipt_verification_signing_key_id
    forged_values = envelope.digest_payload() | {"integrity_signature": "f" * 64}
    forged = replace(
        envelope,
        integrity_signature="f" * 64,
        canonical_digest=canonical_digest(forged_values),
    )
    assert instruction_verifier.verify_instruction_envelope(forged) is False
