from atlas.modules.workflows.application.target_context_artifact_opening_ports import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt,
    code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy,
)


class UnavailableWorkflowPhysicalTransportTargetContextArtifactOpener:
    """Production fail-closed placeholder until a protected opener is configured."""

    @property
    def available(self) -> bool:
        return False

    @property
    def opener_contract_id(self) -> str:
        policy = (
            code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy()
        )
        return policy.required_opener_contract_id

    async def open_paired_artifacts(
        self, instruction: WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction
    ) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt:
        del instruction
        raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(
            "target_context_artifact_opening_trusted_opener_unavailable"
        )

    def verify_receipt(
        self, receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt
    ) -> bool:
        del receipt
        return False

    async def destroy_capsule(
        self, receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt
    ) -> bool:
        del receipt
        raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(
            "target_context_artifact_opening_trusted_opener_unavailable"
        )


__all__ = ["UnavailableWorkflowPhysicalTransportTargetContextArtifactOpener"]
