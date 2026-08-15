from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowScope,
)


class WorkflowTransportCredentialAssignmentFreshnessAdmissionError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus(StrEnum):
    ADMITTED_CURRENT = "admitted_current"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentFreshnessAdmissionIdempotencyRecord:
    request_fingerprint: str
    admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest:
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
    scope: WorkflowScope
    admitter_subject_id: str
    requested_at: datetime
    candidate: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission
    idempotency_key: str
    request_fingerprint: str
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentFreshnessAdmissionResult:
    status: WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus
    admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission | None


class WorkflowTransportCredentialAssignmentFreshnessAdmissionRepository(Protocol):
    """Owns immutable source locks, assignment fencing and atomic persistence."""

    @property
    def durable(self) -> bool: ...

    async def get_credential_assignment_binding_by_id(
        self,
        *,
        binding_id: str,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding | None: ...

    async def get_credential_assignment_snapshot_by_id(
        self,
        *,
        snapshot_id: str,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot | None: ...

    async def get_current_credential_assignment_head(
        self,
        *,
        assignment_id: str,
    ) -> DeploymentPhysicalTransportCredentialAssignment | None: ...

    async def list_credential_assignment_freshness_admissions(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission, ...]: ...

    async def get_credential_assignment_freshness_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportCredentialAssignmentFreshnessAdmissionIdempotencyRecord | None: ...

    async def admit_credential_assignment_freshness(
        self,
        request: WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
    ) -> WorkflowTransportCredentialAssignmentFreshnessAdmissionResult: ...


def validate_workflow_transport_credential_assignment_freshness_request(
    request: WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
) -> None:
    candidate = request.candidate
    if (
        candidate.physical_transport_credential_assignment_binding_id
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
        or candidate.scope != request.scope
        or candidate.admitter_subject_id != request.admitter_subject_id
        or candidate.evaluated_at != request.requested_at
        or any(candidate.authority.canonical_value().values())
    ):
        raise ValueError("credential-assignment freshness payload is unsafe")
    if not 8 <= len(request.idempotency_key) <= 128:
        raise ValueError("credential-assignment freshness idempotency key is invalid")
    if len(request.request_fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in request.request_fingerprint
    ):
        raise ValueError("credential-assignment freshness request fingerprint is invalid")
    if request.requested_at.tzinfo is None:
        raise ValueError("credential-assignment freshness request time must be aware")


__all__ = [
    "WorkflowTransportCredentialAssignmentFreshnessAdmissionError",
    "WorkflowTransportCredentialAssignmentFreshnessAdmissionIdempotencyRecord",
    "WorkflowTransportCredentialAssignmentFreshnessAdmissionRepository",
    "WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest",
    "WorkflowTransportCredentialAssignmentFreshnessAdmissionResult",
    "WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus",
    "validate_workflow_transport_credential_assignment_freshness_request",
]
