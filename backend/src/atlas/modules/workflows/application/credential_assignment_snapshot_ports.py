from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Protocol

from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportCredentialAssignmentSnapshotState,
    EventPhysicalTransportRouteSnapshot,
    WorkflowScope,
    canonical_digest,
)


class WorkflowTransportCredentialAssignmentSnapshotError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowTransportCredentialAssignmentSnapshotStatus(StrEnum):
    SNAPSHOTTED = "snapshotted"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    SOURCE_CONFLICT = "source_conflict"
    ALREADY_SNAPSHOTTED = "already_snapshotted"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord:
    request_fingerprint: str
    snapshot: EventPhysicalTransportCredentialAssignmentSnapshot


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentSnapshotRequest:
    expected_source_assignment_id: str
    expected_source_assignment_revision: str
    expected_source_assignment_digest: str
    scope: WorkflowScope
    snapshotter_subject_id: str
    requested_at: datetime
    candidate: EventPhysicalTransportCredentialAssignmentSnapshot
    idempotency_key: str
    request_fingerprint: str
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentSnapshotResult:
    status: WorkflowTransportCredentialAssignmentSnapshotStatus
    snapshot: EventPhysicalTransportCredentialAssignmentSnapshot | None


class DeploymentPhysicalTransportCredentialAssignmentRegistry(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_active_credential_assignment(
        self,
        *,
        assignment_id: str,
        assignment_revision: str,
    ) -> DeploymentPhysicalTransportCredentialAssignment | None: ...


class DeploymentPhysicalTransportCredentialAssignmentSynchronizer(Protocol):
    async def synchronize_credential_assignments(
        self,
        assignments: tuple[DeploymentPhysicalTransportCredentialAssignment, ...],
    ) -> None: ...


class WorkflowTransportRouteSnapshotReader(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_transport_route_snapshot(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> EventPhysicalTransportRouteSnapshot | None: ...


class WorkflowTransportCredentialAssignmentSnapshotRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_credential_assignment_snapshot(
        self,
        *,
        assignment_id: str,
        assignment_revision: str,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot | None: ...

    async def list_credential_assignment_snapshots(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[EventPhysicalTransportCredentialAssignmentSnapshot, ...]: ...

    async def get_credential_assignment_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord | None: ...

    async def snapshot_credential_assignment(
        self,
        request: WorkflowTransportCredentialAssignmentSnapshotRequest,
    ) -> WorkflowTransportCredentialAssignmentSnapshotResult: ...


def validate_workflow_transport_credential_assignment_snapshot_request(
    request: WorkflowTransportCredentialAssignmentSnapshotRequest,
) -> None:
    candidate = request.candidate
    if (
        candidate.assignment_id != request.expected_source_assignment_id
        or candidate.assignment_revision != request.expected_source_assignment_revision
        or candidate.source_assignment_digest != request.expected_source_assignment_digest
        or candidate.scope != request.scope
        or candidate.snapshotter_subject_id != request.snapshotter_subject_id
        or candidate.captured_at != request.requested_at
        or any(candidate.authority.canonical_value().values())
    ):
        raise ValueError("credential-assignment snapshot payload is unsafe")
    if not 8 <= len(request.idempotency_key) <= 128:
        raise ValueError("credential-assignment snapshot idempotency key is invalid")
    if len(request.request_fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in request.request_fingerprint
    ):
        raise ValueError("credential-assignment snapshot request fingerprint is invalid")
    if request.requested_at.tzinfo is None:
        raise ValueError("credential-assignment snapshot time must be aware")


def validate_workflow_transport_credential_assignment_snapshot(
    snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
    *,
    scope: WorkflowScope,
) -> None:
    expected_snapshot_id = (
        "event-physical-transport-credential-assignment-snapshot."
        + sha256(
            (
                f"{snapshot.assignment_id}:{snapshot.assignment_revision}:"
                f"{snapshot.source_assignment_digest}"
            ).encode()
        ).hexdigest()[:24]
    )
    if (
        snapshot.snapshot_id != expected_snapshot_id
        or snapshot.scope != scope
        or not snapshot.activated_at <= snapshot.captured_at < snapshot.expires_at
        or snapshot.source_non_revoked is not True
        or snapshot.state is not EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED
        or canonical_digest(snapshot.digest_payload()) != snapshot.canonical_digest
        or any(snapshot.authority.canonical_value().values())
        or snapshot.grants_endpoint_resolution_authority
        or snapshot.grants_credential_access_authority
        or snapshot.grants_network_access_authority
        or snapshot.grants_readiness_probe_authority
        or snapshot.grants_publication_authority
        or snapshot.grants_delivery_authority
        or snapshot.grants_dispatch_authority
        or snapshot.grants_execution_authority
    ):
        raise WorkflowTransportCredentialAssignmentSnapshotError(
            "workflow_transport_credential_assignment_snapshot_repository_scope_violation",
            "Stored credential assignment snapshot metadata is invalid.",
        )


__all__ = [
    "DeploymentPhysicalTransportCredentialAssignmentRegistry",
    "DeploymentPhysicalTransportCredentialAssignmentSynchronizer",
    "WorkflowTransportCredentialAssignmentSnapshotError",
    "WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord",
    "WorkflowTransportCredentialAssignmentSnapshotRepository",
    "WorkflowTransportCredentialAssignmentSnapshotRequest",
    "WorkflowTransportCredentialAssignmentSnapshotResult",
    "WorkflowTransportCredentialAssignmentSnapshotStatus",
    "WorkflowTransportRouteSnapshotReader",
    "validate_workflow_transport_credential_assignment_snapshot",
    "validate_workflow_transport_credential_assignment_snapshot_request",
]
