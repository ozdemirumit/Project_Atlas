from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportEndpointMaterializationFailureClass,
    WorkflowEventPhysicalTransportEndpointMaterializationInstruction,
    WorkflowEventPhysicalTransportEndpointMaterializationReceipt,
    WorkflowEventPhysicalTransportEndpointMaterializationResultState,
    canonical_digest,
    code_owned_workflow_event_physical_transport_endpoint_materialization_policy,
)


class SyntheticWorkflowPhysicalTransportEndpointMaterializer:
    """Deterministic metadata-only development materializer with no external I/O."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        failure_class: (
            WorkflowEventPhysicalTransportEndpointMaterializationFailureClass | None
        ) = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._failure_class = failure_class
        self.calls: list[WorkflowEventPhysicalTransportEndpointMaterializationInstruction] = []

    @property
    def available(self) -> bool:
        return True

    @property
    def materializer_contract_id(self) -> str:
        policy = code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
        return policy.required_materializer_contract_id

    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportEndpointMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationReceipt:
        self.calls.append(instruction)
        completed_at = self._clock()
        failed = self._failure_class is not None
        seed = canonical_digest(
            {
                "instruction_digest": instruction.canonical_digest,
                "materializer": "synthetic-workflow-endpoint-materializer.v1",
            }
        )
        state = (
            (
                WorkflowEventPhysicalTransportEndpointMaterializationResultState
            ).MATERIALIZATION_FAILED
            if failed
            else (
                WorkflowEventPhysicalTransportEndpointMaterializationResultState
            ).MATERIALIZED_PROTECTED
        )
        values: dict[str, Any] = {
            "materialization_id": instruction.materialization_id,
            "attempt_id": instruction.attempt_id,
            "consumption_claim_id": instruction.consumption_claim_id,
            "instruction_digest": instruction.canonical_digest,
            "materializer_contract_id": instruction.materializer_contract_id,
            "materializer_id": "materializer.synthetic-workflow-protected-endpoint",
            "materializer_version": "1.0",
            "attested_by": instruction.materializer_attestor_id,
            "resolver_subject_id": instruction.resolver_subject_id,
            "state": state,
            "failure_class": self._failure_class,
            "protected_artifact_id": (
                None if failed else f"protected-endpoint-artifact.{seed[:24]}"
            ),
            "protected_artifact_digest": None if failed else seed,
            "normalized_endpoint_set_digest": (
                None
                if failed
                else canonical_digest(
                    {
                        "endpoint_set_id": instruction.endpoint_set_id,
                        "endpoint_set_revision": instruction.endpoint_set_revision,
                        "sealed_commitment": instruction.private_route_descriptor_commitment,
                    }
                )
            ),
            "endpoint_count": 0 if failed else 2,
            "protected_artifact_schema_id": instruction.protected_artifact_schema_id,
            "protected_artifact_schema_version": (instruction.protected_artifact_schema_version),
            "protected_artifact_profile_digest": (instruction.protected_artifact_profile_digest),
            "source_route_digest": instruction.source_route_digest,
            "private_route_descriptor_commitment": (
                instruction.private_route_descriptor_commitment
            ),
            "materialized_at": None if failed else completed_at,
            "completed_at": completed_at,
            "usable_until": None if failed else instruction.lease_valid_until,
            "commitment_verified": not failed,
            "encrypted_at_rest": not failed,
            "resolver_bound": not failed,
            "lineage_bound": not failed,
            "raw_endpoint_returned": False,
            "dns_activity_performed": False,
            "network_activity_performed": False,
            "credential_access_performed": False,
            "process_activity_performed": False,
            "provider_activity_performed": False,
            "protected_artifact_revoked": failed,
            "cleanup_confirmed": True,
            "signature_verified": True,
        }
        payload = {
            "attempt_id": values["attempt_id"],
            "attested_by": values["attested_by"],
            "cleanup_confirmed": values["cleanup_confirmed"],
            "commitment_verified": values["commitment_verified"],
            "completed_at": completed_at.isoformat(),
            "consumption_claim_id": values["consumption_claim_id"],
            "credential_access_performed": False,
            "dns_activity_performed": False,
            "encrypted_at_rest": values["encrypted_at_rest"],
            "endpoint_count": values["endpoint_count"],
            "failure_class": (None if self._failure_class is None else self._failure_class.value),
            "instruction_digest": values["instruction_digest"],
            "lineage_bound": values["lineage_bound"],
            "materialization_id": values["materialization_id"],
            "materialized_at": None if failed else completed_at.isoformat(),
            "materializer_contract_id": values["materializer_contract_id"],
            "materializer_id": values["materializer_id"],
            "materializer_version": values["materializer_version"],
            "network_activity_performed": False,
            "normalized_endpoint_set_digest": values["normalized_endpoint_set_digest"],
            "private_route_descriptor_commitment": values["private_route_descriptor_commitment"],
            "process_activity_performed": False,
            "protected_artifact_digest": values["protected_artifact_digest"],
            "protected_artifact_id": values["protected_artifact_id"],
            "protected_artifact_profile_digest": values["protected_artifact_profile_digest"],
            "protected_artifact_revoked": values["protected_artifact_revoked"],
            "protected_artifact_schema_id": values["protected_artifact_schema_id"],
            "protected_artifact_schema_version": values["protected_artifact_schema_version"],
            "provider_activity_performed": False,
            "raw_endpoint_returned": False,
            "resolver_bound": values["resolver_bound"],
            "resolver_subject_id": values["resolver_subject_id"],
            "signature_verified": True,
            "source_route_digest": values["source_route_digest"],
            "state": state.value,
            "usable_until": (None if failed else instruction.lease_valid_until.isoformat()),
        }
        return WorkflowEventPhysicalTransportEndpointMaterializationReceipt(
            **cast(Any, values), canonical_digest=canonical_digest(payload)
        )


__all__ = ["SyntheticWorkflowPhysicalTransportEndpointMaterializer"]
