from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchOutboxEntry,
    WorkflowOutboxPublicationLease,
    WorkflowScope,
)


class WorkflowDispatchEventEnvelopeError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowDispatchEventEnvelopePrepareStatus(StrEnum):
    PREPARED = "prepared"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_PREPARED = "already_prepared"


@dataclass(frozen=True, slots=True)
class WorkflowDispatchEventEnvelopePrepareIdempotencyRecord:
    request_fingerprint: str
    envelope: WorkflowDispatchEventEnvelope


@dataclass(frozen=True, slots=True)
class WorkflowDispatchEventEnvelopePrepareRequest:
    expected_outbox_entry_digest: str
    expected_plan_digest: str
    expected_orchestration_lease_id: str
    expected_orchestration_lease_digest: str
    expected_orchestration_fencing_token: int
    expected_publication_lease_id: str
    expected_publication_lease_digest: str
    expected_publication_fencing_token: int
    publisher_subject_id: str
    requested_at: datetime
    candidate: WorkflowDispatchEventEnvelope
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowDispatchEventEnvelopePrepareResult:
    status: WorkflowDispatchEventEnvelopePrepareStatus
    envelope: WorkflowDispatchEventEnvelope | None


class WorkflowDispatchEventEnvelopeRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None: ...

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None: ...

    async def get_dispatch_event_envelope_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchEventEnvelope | None: ...

    async def get_dispatch_event_envelope_prepare_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchEventEnvelopePrepareIdempotencyRecord | None: ...

    async def prepare_dispatch_event_envelope(
        self, request: WorkflowDispatchEventEnvelopePrepareRequest
    ) -> WorkflowDispatchEventEnvelopePrepareResult: ...


__all__ = [
    "WorkflowDispatchEventEnvelopeError",
    "WorkflowDispatchEventEnvelopePrepareIdempotencyRecord",
    "WorkflowDispatchEventEnvelopePrepareRequest",
    "WorkflowDispatchEventEnvelopePrepareResult",
    "WorkflowDispatchEventEnvelopePrepareStatus",
    "WorkflowDispatchEventEnvelopeRepository",
]
