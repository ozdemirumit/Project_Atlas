from __future__ import annotations

from typing import NoReturn

from atlas.modules.workflows.application.target_context_access_authorization_lease_ports import (
    WorkflowProtectedArtifactStatusAttestationRequest,
    WorkflowTargetContextAccessAuthorizationLeaseError,
)
from atlas.modules.workflows.domain import WorkflowProtectedArtifactStatusAttestation


class UnavailableWorkflowProtectedEndpointStatusAttestor:
    """Fail closed until a trusted endpoint protected-store attestor is configured."""

    async def attest_endpoint_artifact_status(
        self, request: WorkflowProtectedArtifactStatusAttestationRequest
    ) -> WorkflowProtectedArtifactStatusAttestation:
        del request
        self._raise_unavailable()

    @staticmethod
    def _raise_unavailable() -> NoReturn:
        raise WorkflowTargetContextAccessAuthorizationLeaseError(
            "workflow_target_context_access_endpoint_status_attestor_unavailable",
            "The protected endpoint status attestor is unavailable.",
        )


class UnavailableWorkflowProtectedCredentialStatusAttestor:
    """Fail closed until a trusted credential protected-store attestor is configured."""

    async def attest_credential_artifact_status(
        self, request: WorkflowProtectedArtifactStatusAttestationRequest
    ) -> WorkflowProtectedArtifactStatusAttestation:
        del request
        self._raise_unavailable()

    @staticmethod
    def _raise_unavailable() -> NoReturn:
        raise WorkflowTargetContextAccessAuthorizationLeaseError(
            "workflow_target_context_access_credential_status_attestor_unavailable",
            "The protected credential status attestor is unavailable.",
        )


class DenyAllWorkflowProtectedArtifactStatusSignatureVerifier:
    """Reject every attestation until trusted verification keys are configured."""

    def verify_status_attestation(
        self, attestation: WorkflowProtectedArtifactStatusAttestation
    ) -> bool:
        del attestation
        return False


__all__ = [
    "DenyAllWorkflowProtectedArtifactStatusSignatureVerifier",
    "UnavailableWorkflowProtectedCredentialStatusAttestor",
    "UnavailableWorkflowProtectedEndpointStatusAttestor",
]
