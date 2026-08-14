from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    DeploymentEventTransportProfile,
    EventPhysicalTransportProfileSnapshot,
    WorkflowScope,
)


class WorkflowTransportProfileSnapshotError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowTransportProfileSnapshotStatus(StrEnum):
    SNAPSHOTTED = "snapshotted"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    SOURCE_CONFLICT = "source_conflict"
    ALREADY_SNAPSHOTTED = "already_snapshotted"


@dataclass(frozen=True, slots=True)
class WorkflowTransportProfileSnapshotIdempotencyRecord:
    request_fingerprint: str
    snapshot: EventPhysicalTransportProfileSnapshot


@dataclass(frozen=True, slots=True)
class WorkflowTransportProfileSnapshotRequest:
    expected_source_profile_id: str
    expected_source_profile_revision: str
    expected_source_profile_digest: str
    scope: WorkflowScope
    snapshotter_subject_id: str
    requested_at: datetime
    candidate: EventPhysicalTransportProfileSnapshot
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowTransportProfileSnapshotResult:
    status: WorkflowTransportProfileSnapshotStatus
    snapshot: EventPhysicalTransportProfileSnapshot | None


class DeploymentEventTransportProfileRegistry(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_active_transport_profile(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
    ) -> DeploymentEventTransportProfile | None: ...


class WorkflowTransportProfileSnapshotRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_transport_profile_snapshot(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
    ) -> EventPhysicalTransportProfileSnapshot | None: ...

    async def get_transport_profile_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportProfileSnapshotIdempotencyRecord | None: ...

    async def snapshot_transport_profile(
        self, request: WorkflowTransportProfileSnapshotRequest
    ) -> WorkflowTransportProfileSnapshotResult: ...


__all__ = [
    "DeploymentEventTransportProfileRegistry",
    "WorkflowTransportProfileSnapshotError",
    "WorkflowTransportProfileSnapshotIdempotencyRecord",
    "WorkflowTransportProfileSnapshotRepository",
    "WorkflowTransportProfileSnapshotRequest",
    "WorkflowTransportProfileSnapshotResult",
    "WorkflowTransportProfileSnapshotStatus",
]
