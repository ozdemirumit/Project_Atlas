from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.target_context_capsule_handoff_ports import (
    WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest,
    WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest,
    WorkflowProtectedTransportTargetContextCapsuleHandoffError,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation,
    WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation,
    WorkflowProtectedTransportTargetContextCapsuleHandoffFailureClass,
    WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction,
    WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResultState,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy,
)


class UnavailableWorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestor:
    async def attest_capsule_handoff_lifecycle(
        self, request: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation:
        del request
        self._raise("target_context_capsule_handoff_lifecycle_attestor_unavailable")

    @staticmethod
    def _raise(code: str) -> NoReturn:
        raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(code)


class UnavailableWorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestor:
    async def attest_consumer_boundary_acceptance(
        self,
        request: WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest,
    ) -> WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation:
        del request
        raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(
            "target_context_capsule_handoff_acceptance_attestor_unavailable"
        )


class DenyAllWorkflowProtectedTargetContextCapsuleHandoffAttestationSignatureVerifier:
    def verify_capsule_handoff_lifecycle_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation
    ) -> bool:
        del attestation
        return False

    def verify_consumer_boundary_acceptance_attestation(
        self, attestation: WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation
    ) -> bool:
        del attestation
        return False


class UnavailableWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter:
    @property
    def available(self) -> bool:
        return False

    @property
    def adapter_id(self) -> str:
        return "adapter.workflow-protected-target-context-capsule-sealed-handoff"

    @property
    def adapter_version(self) -> str:
        return "1.0"

    @property
    def adapter_contract_id(self) -> str:
        return "contract.workflow-protected-target-context-capsule-sealed-handoff"

    @property
    def adapter_contract_version(self) -> str:
        return "1.0"

    async def handoff_sealed_capsule(
        self, instruction: WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt:
        del instruction
        raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(
            "target_context_capsule_handoff_trusted_adapter_unavailable"
        )

    def verify_receipt(
        self, receipt: WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt
    ) -> bool:
        del receipt
        return False


class DeterministicSyntheticWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter:
    """No-I/O development adapter that emits signed metadata without moving a capsule."""

    def __init__(
        self,
        *,
        allow_synthetic_handoff: bool = False,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._allow_synthetic_handoff = allow_synthetic_handoff
        self._clock = clock or (lambda: datetime.now(UTC))
        self._policy = code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()  # noqa: E501

    @property
    def available(self) -> bool:
        return self._allow_synthetic_handoff

    @property
    def adapter_id(self) -> str:
        return self._policy.approved_adapter_id

    @property
    def adapter_version(self) -> str:
        return self._policy.approved_adapter_version

    @property
    def adapter_contract_id(self) -> str:
        return self._policy.required_adapter_contract_id

    @property
    def adapter_contract_version(self) -> str:
        return self._policy.required_adapter_contract_version

    async def handoff_sealed_capsule(
        self, instruction: WorkflowProtectedTransportTargetContextCapsuleHandoffInstruction
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt:
        if not self._allow_synthetic_handoff:
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(
                "target_context_capsule_handoff_synthetic_adapter_disabled"
            )
        protected_boundary_now = self._clock()
        if protected_boundary_now.tzinfo is None:
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(
                "target_context_capsule_handoff_protected_boundary_time_invalid"
            )
        timely = protected_boundary_now < instruction.handoff_deadline
        base: dict[str, object] = {
            "handoff_id": instruction.handoff_id,
            "attempt_id": instruction.attempt_id,
            "consumption_claim_id": instruction.consumption_claim_id,
            "instruction_digest": instruction.canonical_digest,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "adapter_contract_id": self.adapter_contract_id,
            "adapter_contract_version": self.adapter_contract_version,
            "destination_boundary_id": instruction.destination_boundary_id,
            "destination_deployment_id": instruction.destination_deployment_id,
            "destination_generation": instruction.destination_generation,
            "destination_fencing_token_digest": (instruction.destination_fencing_token_digest),
            "custody_contract_id": instruction.custody_contract_id,
            "custody_contract_version": instruction.custody_contract_version,
            "trusted_profile_digest": instruction.trusted_profile_digest,
            "state": (
                WorkflowProtectedTransportTargetContextCapsuleHandoffResultState.HANDED_OFF_SEALED
                if timely
                else WorkflowProtectedTransportTargetContextCapsuleHandoffResultState.HANDOFF_FAILED
            ),
            "failure_class": (
                None
                if timely
                else (
                    WorkflowProtectedTransportTargetContextCapsuleHandoffFailureClass
                ).DEADLINE_EXPIRED
            ),
            "consumer_receipt_id": (
                f"workflow-target-context-capsule-consumer-receipt."
                f"{canonical_digest({'attempt_id': instruction.attempt_id})[:24]}"
                if timely
                else None
            ),
            "consumer_receipt_is_bearer_capability": False,
            "sealed_capsule_handed_off": timely,
            "capsule_remained_sealed": True,
            "source_cleanup_confirmed": True,
            "runtime_use_performed": False,
            "network_activity_performed": False,
            "completed_at": protected_boundary_now,
            "usable_until": instruction.handoff_deadline if timely else None,
            "attested_by": "attestor.workflow-protected-target-context-capsule-sealed-handoff",
            "signing_key_id": self._policy.verification_signing_key_id,
            "signature_algorithm": "synthetic-sha256-v1",
        }
        signature_payload = self._canonical_payload(base)
        integrity_signature = canonical_digest(signature_payload)
        digest_payload = {**signature_payload, "integrity_signature": integrity_signature}
        return WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt(
            **cast(Any, base),
            integrity_signature=integrity_signature,
            canonical_digest=canonical_digest(digest_payload),
        )

    def verify_receipt(
        self, receipt: WorkflowProtectedTransportTargetContextCapsuleHandoffReceipt
    ) -> bool:
        expected = canonical_digest(receipt.signature_payload())
        return bool(
            receipt.adapter_id == self.adapter_id
            and receipt.adapter_version == self.adapter_version
            and receipt.adapter_contract_id == self.adapter_contract_id
            and receipt.adapter_contract_version == self.adapter_contract_version
            and receipt.destination_boundary_id == self._policy.destination_boundary_id
            and receipt.destination_deployment_id == self._policy.destination_deployment_id
            and receipt.destination_generation == self._policy.destination_generation
            and receipt.destination_fencing_token_digest
            == self._policy.destination_fencing_token_digest
            and receipt.custody_contract_id == self._policy.custody_contract_id
            and receipt.custody_contract_version == self._policy.custody_contract_version
            and receipt.signing_key_id == self._policy.verification_signing_key_id
            and receipt.trusted_profile_digest == self._policy.trusted_profile_digest
            and receipt.integrity_signature == expected
        )

    @staticmethod
    def _canonical_payload(values: dict[str, object]) -> dict[str, object]:
        return {
            name: (
                value.isoformat()
                if isinstance(value, datetime)
                else value.value
                if hasattr(value, "value")
                else value
            )
            for name, value in values.items()
        }


__all__ = [
    "DenyAllWorkflowProtectedTargetContextCapsuleHandoffAttestationSignatureVerifier",
    "UnavailableWorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestor",
    "UnavailableWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter",
    "UnavailableWorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestor",
]
