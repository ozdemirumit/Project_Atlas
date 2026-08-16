from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleLifecycleAttestation,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowScope,
    canonical_digest,
)


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest:
    opening_result_id: str
    opening_result_digest: str
    consumer_binding_id: str
    consumer_binding_digest: str
    sealed_capsule_id: str
    sealed_capsule_digest: str
    capsule_schema_id: str
    capsule_schema_version: str
    scope: WorkflowScope
    consumer_subject_id: str
    request_nonce_digest: str
    requested_at: datetime


class WorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor(Protocol):
    async def attest_capsule_lifecycle(
        self, request: WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleLifecycleAttestation: ...


class WorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier(Protocol):
    """Verifies a captured lifecycle signature deterministically without I/O."""

    def verify_capsule_lifecycle_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleLifecycleAttestation
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseIdempotencyRecord:
    request_fingerprint: str
    lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest:
    """Captured evidence for one locked, database-timed authorization transaction."""

    expected_consumer_binding_id: str
    expected_consumer_binding_digest: str
    expected_opening_result_id: str
    expected_opening_result_digest: str
    expected_sealed_capsule_id: str
    expected_sealed_capsule_digest: str
    expected_capsule_schema_id: str
    expected_capsule_schema_version: str
    lifecycle_attestation: WorkflowProtectedTargetContextCapsuleLifecycleAttestation
    expected_request_nonce_digest: str
    expected_lifecycle_attestor_id: str
    expected_lifecycle_attestor_version: str
    offline_signature_verifier: WorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    requested_at: datetime
    candidate: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease
    idempotency_key: str
    request_fingerprint: str
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResult:
    status: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseStatus
    lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease | None
    evaluated_at: datetime | None = None


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository(Protocol):
    """Owns canonical locks, currentness, DB time and atomic append-only persistence."""

    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def get_target_context_capsule_consumer_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBinding | None: ...

    async def authorize_target_context_capsule_handoff(
        self,
        request: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResult:
        """Re-time, revalidate, audit and atomically append a lease plus its claim."""
        ...

    async def list_target_context_capsule_handoff_authorization_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease, ...]: ...


def validate_workflow_protected_transport_target_context_capsule_handoff_authorization_request(
    request: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest,
) -> None:
    candidate = request.candidate
    attestation = request.lifecycle_attestation
    if (
        request.expected_lifecycle_attestor_id
        != "attestor.workflow-protected-target-context-capsule-lifecycle"
        or request.expected_lifecycle_attestor_version != "1.0"
        or candidate.consumer_binding_id != request.expected_consumer_binding_id
        or candidate.consumer_binding_digest != request.expected_consumer_binding_digest
        or candidate.opening_result_id != request.expected_opening_result_id
        or candidate.opening_result_digest != request.expected_opening_result_digest
        or candidate.sealed_capsule_id != request.expected_sealed_capsule_id
        or candidate.sealed_capsule_digest != request.expected_sealed_capsule_digest
        or candidate.capsule_schema_id != request.expected_capsule_schema_id
        or candidate.capsule_schema_version != request.expected_capsule_schema_version
        or attestation.consumer_binding_id != request.expected_consumer_binding_id
        or attestation.consumer_binding_digest != request.expected_consumer_binding_digest
        or attestation.opening_result_id != request.expected_opening_result_id
        or attestation.opening_result_digest != request.expected_opening_result_digest
        or attestation.sealed_capsule_id != request.expected_sealed_capsule_id
        or attestation.sealed_capsule_digest != request.expected_sealed_capsule_digest
        or attestation.capsule_schema_id != request.expected_capsule_schema_id
        or attestation.capsule_schema_version != request.expected_capsule_schema_version
        or attestation.request_nonce_digest != request.expected_request_nonce_digest
        or attestation.protected_store_attestor_id != request.expected_lifecycle_attestor_id
        or attestation.protected_store_attestor_version
        != request.expected_lifecycle_attestor_version
        or canonical_digest(attestation.digest_payload()) != attestation.canonical_digest
        or attestation.usable is not True
        or attestation.revoked is not False
        or attestation.destroyed is not False
        or attestation.sealed is not True
        or attestation.capsule_is_bearer_capability is not False
        or candidate.lifecycle_attestation_id != attestation.attestation_id
        or candidate.lifecycle_attestation_digest != attestation.canonical_digest
        or candidate.lifecycle_attestation_valid_until != attestation.valid_until
        or candidate.policy_digest != request.expected_policy_digest
        or candidate.valid_until - candidate.issued_at
        != timedelta(seconds=request.expected_validity_window_seconds)
        or candidate.scope != request.scope
        or candidate.consumer_subject_id != request.consumer_subject_id
        or candidate.consumer_audience != request.consumer_audience
        or candidate.consumer_contract_id != request.consumer_contract_id
        or candidate.consumer_contract_version != request.consumer_contract_version
        or candidate.purpose_id != request.purpose_id
        or candidate.issued_at != request.requested_at
        or candidate.valid_until > attestation.valid_until
        or candidate.authority.target_context_capsule_handoff_authorized is not True
        or any(
            value is not False
            for name, value in candidate.authority.canonical_value().items()
            if name != "target_context_capsule_handoff_authorized"
        )
    ):
        raise ValueError("target context capsule handoff authorization payload is unsafe")
    try:
        signature_valid = request.offline_signature_verifier.verify_capsule_lifecycle_attestation(
            attestation
        )
    except Exception as exc:
        raise ValueError("target context capsule lifecycle signature is invalid") from exc
    if signature_valid is not True:
        raise ValueError("target context capsule lifecycle signature is invalid")
    if not 8 <= len(request.idempotency_key) <= 128:
        raise ValueError("target context capsule handoff idempotency key is invalid")
    for value, name in (
        (request.expected_request_nonce_digest, "request nonce"),
        (request.request_fingerprint, "request fingerprint"),
    ):
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError(f"target context capsule handoff {name} is invalid")
    if request.requested_at.tzinfo is None:
        raise ValueError("target context capsule handoff request time must be aware")


__all__ = [
    "WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest",
    "WorkflowProtectedTargetContextCapsuleLifecycleSignatureVerifier",
    "WorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseIdempotencyRecord",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResult",
    "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseStatus",
    "validate_workflow_protected_transport_target_context_capsule_handoff_authorization_request",
]
