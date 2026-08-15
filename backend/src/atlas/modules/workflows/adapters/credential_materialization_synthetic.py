from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

from atlas.modules.workflows.application.credential_access_authorization_leases import (
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
)
from atlas.modules.workflows.application.credential_materialization_ports import (
    WorkflowEventPhysicalTransportCredentialMaterializationError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialMaterializationFailureClass,
    WorkflowEventPhysicalTransportCredentialMaterializationInstruction,
    WorkflowEventPhysicalTransportCredentialMaterializationReceipt,
    WorkflowEventPhysicalTransportCredentialMaterializationResultState,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_materialization_policy,
)


def _canonical_payload(values: dict[str, Any]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value
        )
        for name, value in values.items()
    }


class SyntheticWorkflowPhysicalTransportCredentialMaterializer:
    """Deterministic credential-free development materializer with no external I/O."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        failure_class: (
            WorkflowEventPhysicalTransportCredentialMaterializationFailureClass | None
        ) = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._failure_class = failure_class
        self.calls: list[WorkflowEventPhysicalTransportCredentialMaterializationInstruction] = []
        self.revoked_receipt_digests: list[str] = []

    @property
    def available(self) -> bool:
        return True

    @property
    def materializer_contract_id(self) -> str:
        policy = code_owned_workflow_event_physical_transport_credential_materialization_policy()
        return policy.required_materializer_contract_id

    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportCredentialMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationReceipt:
        self.calls.append(instruction)
        policy = code_owned_workflow_event_physical_transport_credential_materialization_policy()
        if (
            instruction.canonical_digest != canonical_digest(instruction.digest_payload())
            or instruction.accessor_subject_id
            != WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT
            or instruction.materializer_contract_id != policy.required_materializer_contract_id
            or instruction.materializer_attestor_id != policy.required_materializer_attestor_id
            or instruction.protected_artifact_schema_id != policy.protected_artifact_schema_id
            or instruction.protected_artifact_schema_version
            != policy.protected_artifact_schema_version
            or instruction.protected_artifact_profile_digest
            != policy.protected_artifact_profile_digest
        ):
            raise WorkflowEventPhysicalTransportCredentialMaterializationError(
                "credential_materialization_instruction_commitment_mismatch"
            )

        completed_at = self._clock()
        if completed_at.tzinfo is None:
            raise WorkflowEventPhysicalTransportCredentialMaterializationError(
                "credential_materialization_clock_must_be_aware"
            )
        failure_class = self._failure_class
        if completed_at >= instruction.lease_valid_until:
            failure_class = (
                WorkflowEventPhysicalTransportCredentialMaterializationFailureClass
            ).DEADLINE_EXPIRED
        failed = failure_class is not None
        state = (
            WorkflowEventPhysicalTransportCredentialMaterializationResultState.MATERIALIZATION_FAILED
            if failed
            else (
                WorkflowEventPhysicalTransportCredentialMaterializationResultState
            ).MATERIALIZED_PROTECTED
        )
        artifact_digest = canonical_digest(
            {
                "assignment_id": instruction.assignment_id,
                "assignment_revision": instruction.assignment_revision,
                "broker_policy_digest": instruction.broker_policy_digest,
                "credential_assignment_snapshot_digest": (
                    instruction.credential_assignment_snapshot_digest
                ),
                "credential_generation": instruction.credential_generation,
                "credential_profile_digest": instruction.credential_profile_digest,
                "credential_requirement_profile_digest": (
                    instruction.credential_requirement_profile_digest
                ),
                "instruction_digest": instruction.canonical_digest,
                "materializer": "synthetic-workflow-credential-materializer.v1",
                "rotation_epoch": instruction.rotation_epoch,
                "source_assignment_digest": instruction.source_assignment_digest,
                "target_scope_commitment": instruction.target_scope_commitment,
            }
        )
        usable_until = min(
            instruction.lease_valid_until,
            completed_at + timedelta(seconds=policy.maximum_artifact_lifetime_seconds),
        )
        values: dict[str, Any] = {
            "materialization_id": instruction.materialization_id,
            "attempt_id": instruction.attempt_id,
            "consumption_claim_id": instruction.consumption_claim_id,
            "instruction_digest": instruction.canonical_digest,
            "materializer_contract_id": instruction.materializer_contract_id,
            "materializer_id": "materializer.synthetic-workflow-protected-credential",
            "materializer_version": "1.0",
            "attested_by": instruction.materializer_attestor_id,
            "accessor_subject_id": instruction.accessor_subject_id,
            "state": state,
            "failure_class": failure_class,
            "protected_artifact_id": (
                None if failed else f"protected-credential-artifact.{artifact_digest[:24]}"
            ),
            "protected_artifact_digest": None if failed else artifact_digest,
            "protected_artifact_schema_id": instruction.protected_artifact_schema_id,
            "protected_artifact_schema_version": instruction.protected_artifact_schema_version,
            "protected_artifact_profile_digest": instruction.protected_artifact_profile_digest,
            "source_assignment_digest": instruction.source_assignment_digest,
            "credential_generation": instruction.credential_generation,
            "rotation_epoch": instruction.rotation_epoch,
            "materialized_at": None if failed else completed_at,
            "completed_at": completed_at,
            "usable_until": None if failed else usable_until,
            "source_commitment_verified": not failed,
            "encrypted_at_rest": not failed,
            "accessor_bound": not failed,
            "lineage_bound": not failed,
            "raw_credential_returned": False,
            "secret_locator_returned": False,
            "provider_payload_returned": False,
            "network_activity_performed": False,
            "process_activity_performed": False,
            "protected_artifact_revoked": failed,
            "cleanup_confirmed": True,
            "signature_verified": True,
        }
        return WorkflowEventPhysicalTransportCredentialMaterializationReceipt(
            **cast(Any, values),
            canonical_digest=canonical_digest(_canonical_payload(values)),
        )

    async def revoke_or_destroy(
        self, receipt: WorkflowEventPhysicalTransportCredentialMaterializationReceipt
    ) -> bool:
        policy = code_owned_workflow_event_physical_transport_credential_materialization_policy()
        if (
            receipt.materializer_contract_id != policy.required_materializer_contract_id
            or receipt.materializer_id != "materializer.synthetic-workflow-protected-credential"
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
        ):
            return False
        self.revoked_receipt_digests.append(receipt.canonical_digest)
        return True


__all__ = ["SyntheticWorkflowPhysicalTransportCredentialMaterializer"]
