from atlas.modules.workflows.application.endpoint_materialization_ports import (
    WorkflowEventPhysicalTransportEndpointMaterializationError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportEndpointMaterializationInstruction,
    WorkflowEventPhysicalTransportEndpointMaterializationReceipt,
    code_owned_workflow_event_physical_transport_endpoint_materialization_policy,
)


class UnavailableWorkflowPhysicalTransportEndpointMaterializer:
    """Production fail-closed placeholder until a protected boundary is configured."""

    @property
    def available(self) -> bool:
        return False

    @property
    def materializer_contract_id(self) -> str:
        policy = code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
        return policy.required_materializer_contract_id

    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportEndpointMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationReceipt:
        del instruction
        raise WorkflowEventPhysicalTransportEndpointMaterializationError(
            "endpoint_materialization_trusted_materializer_unavailable"
        )


__all__ = ["UnavailableWorkflowPhysicalTransportEndpointMaterializer"]
