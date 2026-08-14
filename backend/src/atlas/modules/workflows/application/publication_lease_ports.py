from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowDispatchOutboxEntry,
    WorkflowOutboxPublicationLease,
    WorkflowScope,
)


class WorkflowOutboxPublicationLeaseError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowOutboxPublicationLeaseAcquireStatus(StrEnum):
    ACQUIRED = "acquired"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    CONTENDED = "contended"
    EVIDENCE_CONFLICT = "evidence_conflict"


class WorkflowOutboxPublicationLeaseMutationStatus(StrEnum):
    UPDATED = "updated"
    NOT_FOUND = "not_found"
    EVIDENCE_CONFLICT = "evidence_conflict"
    LEASE_CONFLICT = "lease_conflict"


@dataclass(frozen=True, slots=True)
class WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord:
    request_fingerprint: str
    lease: WorkflowOutboxPublicationLease


@dataclass(frozen=True, slots=True)
class WorkflowOutboxPublicationLeaseAcquireRequest:
    expected_outbox_entry_digest: str
    expected_orchestration_lease_id: str
    expected_orchestration_lease_digest: str
    expected_orchestration_fencing_token: int
    candidate: WorkflowOutboxPublicationLease
    requested_at: datetime
    idempotency_key: str
    request_fingerprint: str
    expected_current_lease_digest: str | None
    expected_current_publication_fencing_token: int | None


@dataclass(frozen=True, slots=True)
class WorkflowOutboxPublicationLeaseAcquireResult:
    status: WorkflowOutboxPublicationLeaseAcquireStatus
    lease: WorkflowOutboxPublicationLease | None


@dataclass(frozen=True, slots=True)
class WorkflowOutboxPublicationLeaseMutationRequest:
    expected_outbox_entry_digest: str
    expected_orchestration_lease_id: str
    expected_orchestration_lease_digest: str
    expected_orchestration_fencing_token: int
    expected_publication_lease_id: str
    expected_publication_lease_digest: str
    expected_publication_fencing_token: int
    publisher_subject_id: str
    requested_at: datetime
    updated_lease: WorkflowOutboxPublicationLease


@dataclass(frozen=True, slots=True)
class WorkflowOutboxPublicationLeaseMutationResult:
    status: WorkflowOutboxPublicationLeaseMutationStatus
    lease: WorkflowOutboxPublicationLease | None


class WorkflowOutboxPublicationLeaseRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None: ...

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None: ...

    async def get_publication_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord | None: ...

    async def acquire_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseAcquireRequest
    ) -> WorkflowOutboxPublicationLeaseAcquireResult: ...

    async def heartbeat_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult: ...

    async def release_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult: ...


__all__ = [
    "WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord",
    "WorkflowOutboxPublicationLeaseAcquireRequest",
    "WorkflowOutboxPublicationLeaseAcquireResult",
    "WorkflowOutboxPublicationLeaseAcquireStatus",
    "WorkflowOutboxPublicationLeaseError",
    "WorkflowOutboxPublicationLeaseMutationRequest",
    "WorkflowOutboxPublicationLeaseMutationResult",
    "WorkflowOutboxPublicationLeaseMutationStatus",
    "WorkflowOutboxPublicationLeaseRepository",
]
