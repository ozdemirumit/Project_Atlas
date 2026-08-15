from atlas.modules.workflows.application.credential_materialization_ports import (
    WorkflowEventPhysicalTransportCredentialMaterializationError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialMaterializationInstruction,
    WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
    code_owned_workflow_event_physical_transport_credential_materialization_policy,
)


class UnavailableWorkflowPhysicalTransportCredentialMaterializer:
    """Production fail-closed placeholder until a protected boundary is configured."""

    @property
    def available(self) -> bool:
        return False

    @property
    def materializer_contract_id(self) -> str:
        policy = code_owned_workflow_event_physical_transport_credential_materialization_policy()
        return policy.required_materializer_contract_id

    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportCredentialMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationReceipt:
        del instruction
        raise WorkflowEventPhysicalTransportCredentialMaterializationError(
            "credential_materialization_trusted_materializer_unavailable"
        )

    async def revoke_or_destroy(
        self, receipt: WorkflowEventPhysicalTransportCredentialMaterializationReceipt
    ) -> bool:
        del receipt
        raise WorkflowEventPhysicalTransportCredentialMaterializationError(
            "credential_materialization_trusted_materializer_unavailable"
        )


__all__ = ["UnavailableWorkflowPhysicalTransportCredentialMaterializer"]
