from __future__ import annotations

from atlas.modules.workflows.application.target_context_capsule_opening_authorization_lease_ports import (  # noqa: E501
    WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation,
)


class UnavailableWorkflowProtectedTargetContextCapsuleDestinationCustodyAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_destination_custody(
        self,
        request: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest,
    ) -> WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation:
        del request
        raise RuntimeError("trusted destination custody attestor is unavailable")


class DenyAllWorkflowProtectedTargetContextCapsuleDestinationCustodySignatureVerifier:
    def verify_destination_custody_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation
    ) -> bool:
        del attestation
        return False


__all__ = [
    "DenyAllWorkflowProtectedTargetContextCapsuleDestinationCustodySignatureVerifier",
    "UnavailableWorkflowProtectedTargetContextCapsuleDestinationCustodyAttestor",
]
