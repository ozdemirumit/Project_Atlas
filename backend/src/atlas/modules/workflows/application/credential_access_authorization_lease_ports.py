from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowScope,
)


class WorkflowTransportCredentialAccessAuthorizationLeaseError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowTransportCredentialAccessAuthorizationLeaseStatus(StrEnum):
    AUTHORIZED = "authorized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_AUTHORIZED = "already_authorized"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAccessAuthorizationLeaseIdempotencyRecord:
    request_fingerprint: str
    lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAccessAuthorizationLeaseRequest:
    """Expected evidence for the locked, database-timed authorization transaction."""

    expected_freshness_admission_id: str
    expected_freshness_admission_digest: str
    expected_freshness_admission_valid_until: datetime
    expected_credential_assignment_binding_id: str
    expected_credential_assignment_binding_digest: str
    expected_credential_assignment_snapshot_id: str
    expected_credential_assignment_snapshot_digest: str
    expected_assignment_id: str
    expected_assignment_revision: str
    expected_source_assignment_digest: str
    expected_credential_generation: int
    expected_rotation_epoch: int
    expected_assignment_activated_at: datetime
    expected_assignment_expires_at: datetime
    expected_assignment_active: bool
    expected_assignment_revoked: bool
    expected_policy_digest: str
    expected_validity_window_seconds: int
    scope: WorkflowScope
    accessor_subject_id: str
    requested_at: datetime
    candidate: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease
    idempotency_key: str
    request_fingerprint: str
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAccessAuthorizationLeaseResult:
    status: WorkflowTransportCredentialAccessAuthorizationLeaseStatus
    lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease | None


class WorkflowTransportCredentialAccessAuthorizationLeaseRepository(Protocol):
    """Owns source locks, assignment fencing, DB time and atomic lease persistence."""

    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def get_credential_assignment_freshness_admission_by_id(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission | None: ...

    async def get_credential_assignment_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding | None: ...

    async def get_credential_assignment_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot | None: ...

    async def get_current_credential_assignment_head(
        self, *, assignment_id: str
    ) -> DeploymentPhysicalTransportCredentialAssignment | None: ...

    async def list_credential_access_authorization_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease, ...]: ...

    async def authorize_credential_access(
        self, request: WorkflowTransportCredentialAccessAuthorizationLeaseRequest
    ) -> WorkflowTransportCredentialAccessAuthorizationLeaseResult:
        """Lock, fence, audit, re-time, revalidate and persist lease plus claim."""
        ...


def validate_workflow_transport_credential_access_authorization_request(
    request: WorkflowTransportCredentialAccessAuthorizationLeaseRequest,
) -> None:
    candidate = request.candidate
    if (
        candidate.freshness_admission_id != request.expected_freshness_admission_id
        or candidate.freshness_admission_digest != request.expected_freshness_admission_digest
        or candidate.physical_transport_credential_assignment_binding_id
        != request.expected_credential_assignment_binding_id
        or candidate.physical_transport_credential_assignment_binding_digest
        != request.expected_credential_assignment_binding_digest
        or candidate.credential_assignment_snapshot_id
        != request.expected_credential_assignment_snapshot_id
        or candidate.credential_assignment_snapshot_digest
        != request.expected_credential_assignment_snapshot_digest
        or candidate.assignment_id != request.expected_assignment_id
        or candidate.assignment_revision != request.expected_assignment_revision
        or candidate.source_assignment_digest != request.expected_source_assignment_digest
        or candidate.credential_generation != request.expected_credential_generation
        or candidate.rotation_epoch != request.expected_rotation_epoch
        or candidate.assignment_activated_at != request.expected_assignment_activated_at
        or candidate.assignment_expires_at != request.expected_assignment_expires_at
        or candidate.assignment_active != request.expected_assignment_active
        or candidate.assignment_non_revoked != (not request.expected_assignment_revoked)
        or candidate.policy_digest != request.expected_policy_digest
        or candidate.valid_until - candidate.issued_at
        != timedelta(seconds=request.expected_validity_window_seconds)
        or candidate.scope != request.scope
        or candidate.accessor_subject_id != request.accessor_subject_id
        or candidate.issued_at != request.requested_at
        or candidate.authority.credential_access_authorized is not True
        or any(
            value is not False
            for name, value in candidate.authority.canonical_value().items()
            if name != "credential_access_authorized"
        )
    ):
        raise ValueError("credential-access authorization payload is unsafe")
    if not 8 <= len(request.idempotency_key) <= 128:
        raise ValueError("credential-access authorization idempotency key is invalid")
    if len(request.request_fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in request.request_fingerprint
    ):
        raise ValueError("credential-access authorization request fingerprint is invalid")
    if request.requested_at.tzinfo is None:
        raise ValueError("credential-access authorization request time must be aware")


__all__ = [
    "WorkflowTransportCredentialAccessAuthorizationLeaseError",
    "WorkflowTransportCredentialAccessAuthorizationLeaseIdempotencyRecord",
    "WorkflowTransportCredentialAccessAuthorizationLeaseRepository",
    "WorkflowTransportCredentialAccessAuthorizationLeaseRequest",
    "WorkflowTransportCredentialAccessAuthorizationLeaseResult",
    "WorkflowTransportCredentialAccessAuthorizationLeaseStatus",
    "validate_workflow_transport_credential_access_authorization_request",
]
