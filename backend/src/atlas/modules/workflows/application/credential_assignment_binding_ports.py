from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportRouteSnapshot,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowScope,
)


class WorkflowTransportCredentialAssignmentBindingError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowTransportCredentialAssignmentBindingStatus(StrEnum):
    BOUND = "bound"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_BOUND = "already_bound"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentBindingIdempotencyRecord:
    request_fingerprint: str
    binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentBindingRequest:
    expected_physical_transport_route_binding_id: str
    expected_physical_transport_route_binding_digest: str
    expected_transport_route_snapshot_id: str
    expected_transport_route_snapshot_digest: str
    expected_credential_assignment_snapshot_id: str
    expected_credential_assignment_snapshot_digest: str
    expected_policy_digest: str
    scope: WorkflowScope
    binder_subject_id: str
    requested_at: datetime
    candidate: WorkflowEventPhysicalTransportCredentialAssignmentBinding
    idempotency_key: str
    request_fingerprint: str
    required_precommit_audit: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkflowTransportCredentialAssignmentBindingResult:
    status: WorkflowTransportCredentialAssignmentBindingStatus
    binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding | None


class WorkflowTransportCredentialAssignmentBindingRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_physical_transport_route_binding_by_id(
        self,
        *,
        binding_id: str,
    ) -> WorkflowEventPhysicalTransportRouteBinding | None: ...

    async def get_transport_route_snapshot_by_id(
        self,
        *,
        snapshot_id: str,
    ) -> EventPhysicalTransportRouteSnapshot | None: ...

    async def get_credential_assignment_snapshot_by_id(
        self,
        *,
        snapshot_id: str,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot | None: ...

    async def get_credential_assignment_binding(
        self,
        *,
        physical_transport_route_binding_id: str,
        credential_assignment_snapshot_id: str,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding | None: ...

    async def list_credential_assignment_bindings(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAssignmentBinding, ...]: ...

    async def get_credential_assignment_binding_request(
        self,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportCredentialAssignmentBindingIdempotencyRecord | None: ...

    async def bind_credential_assignment(
        self,
        request: WorkflowTransportCredentialAssignmentBindingRequest,
    ) -> WorkflowTransportCredentialAssignmentBindingResult: ...


__all__ = [
    "WorkflowTransportCredentialAssignmentBindingError",
    "WorkflowTransportCredentialAssignmentBindingIdempotencyRecord",
    "WorkflowTransportCredentialAssignmentBindingRepository",
    "WorkflowTransportCredentialAssignmentBindingRequest",
    "WorkflowTransportCredentialAssignmentBindingResult",
    "WorkflowTransportCredentialAssignmentBindingStatus",
]
