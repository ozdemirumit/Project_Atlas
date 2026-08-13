from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import WorkflowOrchestrationLease, WorkflowScope


class WorkflowOrchestrationLeaseError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowLeaseAcquireStatus(StrEnum):
    ACQUIRED = "acquired"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    CONTENDED = "contended"
    PLAN_CONFLICT = "plan_conflict"


class WorkflowLeaseMutationStatus(StrEnum):
    UPDATED = "updated"
    NOT_FOUND = "not_found"
    PLAN_CONFLICT = "plan_conflict"
    LEASE_CONFLICT = "lease_conflict"


@dataclass(frozen=True, slots=True)
class WorkflowLeaseAcquireIdempotencyRecord:
    request_fingerprint: str
    lease: WorkflowOrchestrationLease


@dataclass(frozen=True, slots=True)
class WorkflowLeaseAcquireRequest:
    expected_plan_digest: str
    candidate: WorkflowOrchestrationLease
    requested_at: datetime
    idempotency_key: str
    request_fingerprint: str
    expected_current_lease_digest: str | None
    expected_current_fencing_token: int | None


@dataclass(frozen=True, slots=True)
class WorkflowLeaseAcquireResult:
    status: WorkflowLeaseAcquireStatus
    lease: WorkflowOrchestrationLease | None


@dataclass(frozen=True, slots=True)
class WorkflowLeaseMutationRequest:
    expected_plan_digest: str
    expected_lease_id: str
    expected_lease_digest: str
    expected_fencing_token: int
    worker_subject_id: str
    requested_at: datetime
    updated_lease: WorkflowOrchestrationLease


@dataclass(frozen=True, slots=True)
class WorkflowLeaseMutationResult:
    status: WorkflowLeaseMutationStatus
    lease: WorkflowOrchestrationLease | None


class WorkflowOrchestrationLeaseRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_lease_by_plan_id(self, *, plan_id: str) -> WorkflowOrchestrationLease | None: ...

    async def get_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowLeaseAcquireIdempotencyRecord | None: ...

    async def acquire_lease(
        self, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseAcquireResult: ...

    async def heartbeat_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult: ...

    async def release_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult: ...


__all__ = [
    "WorkflowLeaseAcquireIdempotencyRecord",
    "WorkflowLeaseAcquireRequest",
    "WorkflowLeaseAcquireResult",
    "WorkflowLeaseAcquireStatus",
    "WorkflowLeaseMutationRequest",
    "WorkflowLeaseMutationResult",
    "WorkflowLeaseMutationStatus",
    "WorkflowOrchestrationLeaseError",
    "WorkflowOrchestrationLeaseRepository",
]
