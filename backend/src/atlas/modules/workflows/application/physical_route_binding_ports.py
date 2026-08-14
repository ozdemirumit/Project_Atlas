from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportRouteSnapshot,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowScope,
)


class WorkflowEventPhysicalTransportRouteBindingError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowEventPhysicalTransportRouteBindingStatus(StrEnum):
    BOUND = "bound"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_BOUND = "already_bound"


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord:
    request_fingerprint: str
    binding: WorkflowEventPhysicalTransportRouteBinding


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteBindingRequest:
    expected_logical_channel_binding_id: str
    expected_logical_channel_binding_digest: str
    expected_transport_compatibility_admission_id: str
    expected_transport_compatibility_admission_digest: str
    expected_transport_profile_snapshot_id: str
    expected_transport_profile_snapshot_digest: str
    expected_transport_route_snapshot_id: str
    expected_transport_route_snapshot_digest: str
    expected_policy_digest: str
    scope: WorkflowScope
    binder_subject_id: str
    requested_at: datetime
    candidate: WorkflowEventPhysicalTransportRouteBinding
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowEventPhysicalTransportRouteBindingResult:
    status: WorkflowEventPhysicalTransportRouteBindingStatus
    binding: WorkflowEventPhysicalTransportRouteBinding | None


class WorkflowEventPhysicalTransportRouteBindingRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_event_logical_channel_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventLogicalChannelBinding | None: ...

    async def get_transport_compatibility_admission_by_id(
        self, *, admission_id: str
    ) -> WorkflowEventTransportCompatibilityAdmission | None: ...

    async def get_transport_profile_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportProfileSnapshot | None: ...

    async def get_transport_route_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportRouteSnapshot | None: ...

    async def get_physical_transport_route_binding(
        self, *, logical_channel_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None: ...

    async def list_physical_transport_route_bindings(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportRouteBinding, ...]: ...

    async def get_physical_transport_route_binding_request(
        self,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord | None: ...

    async def bind_physical_transport_route(
        self, request: WorkflowEventPhysicalTransportRouteBindingRequest
    ) -> WorkflowEventPhysicalTransportRouteBindingResult: ...


__all__ = [
    "WorkflowEventPhysicalTransportRouteBindingError",
    "WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord",
    "WorkflowEventPhysicalTransportRouteBindingRepository",
    "WorkflowEventPhysicalTransportRouteBindingRequest",
    "WorkflowEventPhysicalTransportRouteBindingResult",
    "WorkflowEventPhysicalTransportRouteBindingStatus",
]
