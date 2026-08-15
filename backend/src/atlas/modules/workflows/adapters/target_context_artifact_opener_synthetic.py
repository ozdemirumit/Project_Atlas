from __future__ import annotations

import hmac
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Any, cast

from atlas.modules.workflows.application.target_context_access_authorization_leases import (
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
)
from atlas.modules.workflows.application.target_context_artifact_opening_ports import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState,
    WorkflowScope,
    canonical_digest,
    canonical_json_bytes,
    code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy,
)

_SYNTHETIC_RECEIPT_SIGNING_KEY = b"atlas-synthetic-target-context-opener-receipt-v1"


def _payload(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if isinstance(value, WorkflowScope)
            else value
        )
        for name, value in values.items()
    }


class SyntheticWorkflowPhysicalTransportTargetContextArtifactOpener:
    """Credential-free paired opener that emits only sealed lineage metadata."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        failure_class: (
            WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass | None
        ) = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._failure_class = failure_class
        self.calls: list[WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction] = []
        self.destroyed_capsule_digests: list[str] = []

    @property
    def available(self) -> bool:
        return True

    @property
    def opener_contract_id(self) -> str:
        policy = (
            code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy()
        )
        return policy.required_opener_contract_id

    async def open_paired_artifacts(
        self, instruction: WorkflowEventPhysicalTransportTargetContextArtifactOpeningInstruction
    ) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt:
        self.calls.append(instruction)
        policy = (
            code_owned_workflow_event_physical_transport_target_context_artifact_opening_policy()
        )
        if (
            instruction.canonical_digest != canonical_digest(instruction.digest_payload())
            or instruction.accessor_subject_id
            != WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT
            or instruction.opener_contract_id != policy.required_opener_contract_id
            or instruction.opener_attestor_id != policy.required_opener_attestor_id
            or instruction.capsule_schema_id != policy.capsule_schema_id
            or instruction.capsule_schema_version != policy.capsule_schema_version
        ):
            raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(
                "target_context_artifact_opening_instruction_commitment_mismatch"
            )

        completed_at = self._clock()
        if completed_at.tzinfo is None:
            raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(
                "target_context_artifact_opening_clock_must_be_aware"
            )
        deadline = min(
            instruction.lease_valid_until,
            instruction.joint_usable_until,
            instruction.evidence_valid_until,
        )
        failure_class = self._failure_class
        if completed_at >= deadline:
            failure_class = (
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningFailureClass
            ).DEADLINE_EXPIRED
        failed = failure_class is not None
        state = (
            WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState.OPENING_FAILED
            if failed
            else (
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultState
            ).OPENED_PROTECTED
        )
        capsule_digest = canonical_digest(
            {
                "accessor_subject_id": instruction.accessor_subject_id,
                "credential_protected_artifact_digest": (
                    instruction.credential_protected_artifact_digest
                ),
                "endpoint_protected_artifact_digest": (
                    instruction.endpoint_protected_artifact_digest
                ),
                "instruction_digest": instruction.canonical_digest,
                "opener": "synthetic-workflow-protected-target-context-opener.v1",
                "target_context_commitment": instruction.target_context_commitment,
            }
        )
        usable_until = min(
            deadline,
            completed_at + timedelta(seconds=policy.maximum_capsule_lifetime_seconds),
        )
        values: dict[str, object] = {
            "opening_id": instruction.opening_id,
            "attempt_id": instruction.attempt_id,
            "consumption_claim_id": instruction.consumption_claim_id,
            "instruction_digest": instruction.canonical_digest,
            "opener_contract_id": instruction.opener_contract_id,
            "opener_id": "opener.synthetic-workflow-protected-target-context",
            "opener_version": "1.0",
            "attested_by": instruction.opener_attestor_id,
            "accessor_subject_id": instruction.accessor_subject_id,
            "state": state,
            "failure_class": failure_class,
            "sealed_capsule_id": (
                None if failed else f"sealed-target-context-capsule.{capsule_digest[:24]}"
            ),
            "sealed_capsule_digest": None if failed else capsule_digest,
            "capsule_is_bearer_capability": False,
            "capsule_schema_id": instruction.capsule_schema_id,
            "capsule_schema_version": instruction.capsule_schema_version,
            "endpoint_opened": not failed,
            "credential_opened": not failed,
            "pair_commitment_verified": not failed,
            "raw_endpoint_returned": False,
            "raw_credential_returned": False,
            "network_activity_performed": False,
            "delivery_performed": False,
            "runtime_use_performed": False,
            "protected_sources_closed": True,
            "cleanup_confirmed": True,
            "completed_at": completed_at,
            "usable_until": None if failed else usable_until,
            "signing_key_id": "signing-key.synthetic-target-context-opener.v1",
            "signature_algorithm": "hmac-sha256",
        }
        signature = hmac.new(
            _SYNTHETIC_RECEIPT_SIGNING_KEY,
            canonical_json_bytes(_payload(values)),
            sha256,
        ).hexdigest()
        values["integrity_signature"] = signature
        return WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def verify_receipt(
        self, receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt
    ) -> bool:
        if (
            receipt.opener_contract_id != self.opener_contract_id
            or receipt.opener_id != "opener.synthetic-workflow-protected-target-context"
            or receipt.opener_version != "1.0"
            or receipt.signing_key_id != "signing-key.synthetic-target-context-opener.v1"
            or receipt.signature_algorithm != "hmac-sha256"
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
        ):
            return False
        expected = hmac.new(
            _SYNTHETIC_RECEIPT_SIGNING_KEY,
            canonical_json_bytes(receipt.signature_payload()),
            sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, receipt.integrity_signature)

    async def destroy_capsule(
        self, receipt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningReceipt
    ) -> bool:
        if receipt.sealed_capsule_digest is None or not self.verify_receipt(receipt):
            return False
        self.destroyed_capsule_digests.append(receipt.sealed_capsule_digest)
        return True


__all__ = ["SyntheticWorkflowPhysicalTransportTargetContextArtifactOpener"]
