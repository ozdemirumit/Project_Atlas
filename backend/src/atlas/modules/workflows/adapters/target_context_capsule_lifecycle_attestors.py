from __future__ import annotations

from typing import NoReturn

from atlas.modules.workflows.application import (
    WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleLifecycleAttestation,
)


class UnavailableWorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor:
    """Fail closed until a trusted capsule lifecycle attestor is configured."""

    async def attest_capsule_lifecycle(
        self, request: WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleLifecycleAttestation:
        del request
        self._raise_unavailable()

    @staticmethod
    def _raise_unavailable() -> NoReturn:
        raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
            "workflow_target_context_capsule_lifecycle_status_attestor_unavailable",
            "The protected target-context capsule lifecycle status attestor is unavailable.",
        )


class DenyAllWorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier:
    """Reject every capsule lifecycle attestation until keys are configured."""

    def verify_capsule_lifecycle_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleLifecycleAttestation
    ) -> bool:
        del attestation
        return False


__all__ = [
    "DenyAllWorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier",
    "UnavailableWorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor",
]
