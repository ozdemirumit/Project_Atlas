from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    DeploymentEventTransportRoute,
    EventPhysicalTransportRouteSnapshot,
    WorkflowScope,
)


class WorkflowTransportRouteSnapshotError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowTransportRouteSnapshotStatus(StrEnum):
    SNAPSHOTTED = "snapshotted"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    SOURCE_CONFLICT = "source_conflict"
    ALREADY_SNAPSHOTTED = "already_snapshotted"


@dataclass(frozen=True, slots=True)
class WorkflowTransportRouteSnapshotIdempotencyRecord:
    request_fingerprint: str
    snapshot: EventPhysicalTransportRouteSnapshot


@dataclass(frozen=True, slots=True)
class WorkflowTransportRouteSnapshotRequest:
    expected_source_route_id: str
    expected_source_route_revision: str
    expected_source_route_digest: str
    scope: WorkflowScope
    snapshotter_subject_id: str
    requested_at: datetime
    candidate: EventPhysicalTransportRouteSnapshot
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowTransportRouteSnapshotResult:
    status: WorkflowTransportRouteSnapshotStatus
    snapshot: EventPhysicalTransportRouteSnapshot | None


class DeploymentEventTransportRouteRegistry(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_active_transport_route(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> DeploymentEventTransportRoute | None: ...


class WorkflowTransportRouteSnapshotRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_transport_route_snapshot(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> EventPhysicalTransportRouteSnapshot | None: ...

    async def get_transport_route_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportRouteSnapshotIdempotencyRecord | None: ...

    async def snapshot_transport_route(
        self, request: WorkflowTransportRouteSnapshotRequest
    ) -> WorkflowTransportRouteSnapshotResult: ...


__all__ = [
    "DeploymentEventTransportRouteRegistry",
    "WorkflowTransportRouteSnapshotError",
    "WorkflowTransportRouteSnapshotIdempotencyRecord",
    "WorkflowTransportRouteSnapshotRepository",
    "WorkflowTransportRouteSnapshotRequest",
    "WorkflowTransportRouteSnapshotResult",
    "WorkflowTransportRouteSnapshotStatus",
]
