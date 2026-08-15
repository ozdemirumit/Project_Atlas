from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowProtectedArtifactKind,
    WorkflowProtectedArtifactStatusAttestation,
    WorkflowScope,
    canonical_digest,
)


class WorkflowTargetContextAccessAuthorizationLeaseError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowTargetContextAccessAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedArtifactStatusAttestationRequest:
    artifact_kind: WorkflowProtectedArtifactKind
    materialization_id: str
    materialization_digest: str
    target_context_binding_id: str
    target_context_binding_digest: str
    target_context_commitment: str
    scope: WorkflowScope
    accessor_subject_id: str
    request_nonce_digest: str
    requested_at: datetime


class WorkflowProtectedEndpointStatusAttestor(Protocol):
    async def attest_endpoint_artifact_status(
        self, request: WorkflowProtectedArtifactStatusAttestationRequest
    ) -> WorkflowProtectedArtifactStatusAttestation: ...


class WorkflowProtectedCredentialStatusAttestor(Protocol):
    async def attest_credential_artifact_status(
        self, request: WorkflowProtectedArtifactStatusAttestationRequest
    ) -> WorkflowProtectedArtifactStatusAttestation: ...


class WorkflowProtectedArtifactStatusSignatureVerifier(Protocol):
    """Deterministically verifies status signatures without performing I/O."""

    def verify_status_attestation(
        self, attestation: WorkflowProtectedArtifactStatusAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextAccessAuthorizationLeaseIdempotencyRecord:
    request_fingerprint: str
    lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextAccessAuthorizationLeaseRequest:
    """Offline evidence for one locked, database-timed authorization transaction."""

    expected_target_context_binding_id: str
    expected_target_context_binding_digest: str
    expected_target_context_commitment: str
    expected_endpoint_materialization_id: str
    expected_endpoint_materialization_digest: str
    expected_credential_materialization_id: str
    expected_credential_materialization_digest: str
    endpoint_status_attestation: WorkflowProtectedArtifactStatusAttestation
    credential_status_attestation: WorkflowProtectedArtifactStatusAttestation
    expected_request_nonce_digest: str
    expected_endpoint_status_attestor_id: str
    expected_endpoint_status_attestor_version: str
    expected_credential_status_attestor_id: str
    expected_credential_status_attestor_version: str
    offline_signature_verifier: WorkflowProtectedArtifactStatusSignatureVerifier
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    accessor_subject_id: str
    requested_at: datetime
    candidate: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease
    idempotency_key: str
    request_fingerprint: str
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowTargetContextAccessAuthorizationLeaseResult:
    status: WorkflowTargetContextAccessAuthorizationLeaseStatus
    lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease | None


class WorkflowTargetContextAccessAuthorizationLeaseRepository(Protocol):
    """Owns liveness locks, current-head fencing, DB time and atomic persistence."""

    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def get_target_context_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportTargetContextBinding | None: ...

    async def authorize_target_context_access(
        self, request: WorkflowTargetContextAccessAuthorizationLeaseRequest
    ) -> WorkflowTargetContextAccessAuthorizationLeaseResult:
        """Lock, re-time, revalidate, audit and atomically persist lease plus claim."""
        ...

    async def list_target_context_access_authorization_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease, ...]: ...


def validate_workflow_target_context_access_authorization_request(
    request: WorkflowTargetContextAccessAuthorizationLeaseRequest,
) -> None:
    candidate = request.candidate
    endpoint = request.endpoint_status_attestation
    credential = request.credential_status_attestation
    if (
        request.expected_endpoint_status_attestor_id
        != "attestor.workflow-protected-endpoint-store-status"
        or request.expected_endpoint_status_attestor_version != "1.0"
        or request.expected_credential_status_attestor_id
        != "attestor.workflow-protected-credential-store-status"
        or request.expected_credential_status_attestor_version != "1.0"
        or candidate.target_context_binding_id != request.expected_target_context_binding_id
        or candidate.target_context_binding_digest != request.expected_target_context_binding_digest
        or candidate.target_context_commitment != request.expected_target_context_commitment
        or endpoint.artifact_kind is not WorkflowProtectedArtifactKind.ENDPOINT
        or endpoint.materialization_id != request.expected_endpoint_materialization_id
        or endpoint.materialization_digest != request.expected_endpoint_materialization_digest
        or endpoint.target_context_binding_id != request.expected_target_context_binding_id
        or endpoint.target_context_binding_digest != request.expected_target_context_binding_digest
        or endpoint.target_context_commitment != request.expected_target_context_commitment
        or endpoint.protected_store_attestor_id != request.expected_endpoint_status_attestor_id
        or endpoint.protected_store_attestor_version
        != request.expected_endpoint_status_attestor_version
        or credential.artifact_kind is not WorkflowProtectedArtifactKind.CREDENTIAL
        or credential.materialization_id != request.expected_credential_materialization_id
        or credential.materialization_digest != request.expected_credential_materialization_digest
        or credential.target_context_binding_id != request.expected_target_context_binding_id
        or credential.target_context_binding_digest
        != request.expected_target_context_binding_digest
        or credential.target_context_commitment != request.expected_target_context_commitment
        or credential.protected_store_attestor_id != request.expected_credential_status_attestor_id
        or credential.protected_store_attestor_version
        != request.expected_credential_status_attestor_version
        or endpoint.request_nonce_digest != request.expected_request_nonce_digest
        or credential.request_nonce_digest != request.expected_request_nonce_digest
        or endpoint.request_nonce_digest != credential.request_nonce_digest
        or canonical_digest(endpoint.digest_payload()) != endpoint.canonical_digest
        or canonical_digest(credential.digest_payload()) != credential.canonical_digest
        or endpoint.usable is not True
        or endpoint.revoked is not False
        or endpoint.destroyed is not False
        or credential.usable is not True
        or credential.revoked is not False
        or credential.destroyed is not False
        or candidate.endpoint_status_attestation_id != endpoint.attestation_id
        or candidate.endpoint_status_attestation_digest != endpoint.canonical_digest
        or candidate.endpoint_status_attestation_valid_until != endpoint.valid_until
        or candidate.credential_status_attestation_id != credential.attestation_id
        or candidate.credential_status_attestation_digest != credential.canonical_digest
        or candidate.credential_status_attestation_valid_until != credential.valid_until
        or candidate.policy_digest != request.expected_policy_digest
        or candidate.valid_until - candidate.issued_at
        != timedelta(seconds=request.expected_validity_window_seconds)
        or candidate.scope != request.scope
        or candidate.accessor_subject_id != request.accessor_subject_id
        or candidate.issued_at != request.requested_at
        or candidate.valid_until > endpoint.valid_until
        or candidate.valid_until > credential.valid_until
        or candidate.authority.protected_artifact_access_authorized is not True
        or any(
            value is not False
            for name, value in candidate.authority.canonical_value().items()
            if name != "protected_artifact_access_authorized"
        )
    ):
        raise ValueError("target context access authorization payload is unsafe")
    try:
        endpoint_signature_valid = request.offline_signature_verifier.verify_status_attestation(
            endpoint
        )
        credential_signature_valid = request.offline_signature_verifier.verify_status_attestation(
            credential
        )
    except Exception as exc:
        raise ValueError("target context access authorization signature is invalid") from exc
    if endpoint_signature_valid is not True or credential_signature_valid is not True:
        raise ValueError("target context access authorization signature is invalid")
    if not 8 <= len(request.idempotency_key) <= 128:
        raise ValueError("target context access authorization idempotency key is invalid")
    if len(request.request_fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in request.request_fingerprint
    ):
        raise ValueError("target context access authorization request fingerprint is invalid")
    if request.requested_at.tzinfo is None:
        raise ValueError("target context access authorization request time must be aware")
    if len(request.expected_request_nonce_digest) != 64 or any(
        character not in "0123456789abcdef" for character in request.expected_request_nonce_digest
    ):
        raise ValueError("target context access authorization request nonce is invalid")


__all__ = [
    "WorkflowProtectedArtifactStatusAttestationRequest",
    "WorkflowProtectedArtifactStatusSignatureVerifier",
    "WorkflowProtectedCredentialStatusAttestor",
    "WorkflowProtectedEndpointStatusAttestor",
    "WorkflowTargetContextAccessAuthorizationLeaseError",
    "WorkflowTargetContextAccessAuthorizationLeaseIdempotencyRecord",
    "WorkflowTargetContextAccessAuthorizationLeaseRepository",
    "WorkflowTargetContextAccessAuthorizationLeaseRequest",
    "WorkflowTargetContextAccessAuthorizationLeaseResult",
    "WorkflowTargetContextAccessAuthorizationLeaseStatus",
    "validate_workflow_target_context_access_authorization_request",
]
