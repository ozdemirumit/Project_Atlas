from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchOutboxEntry,
    WorkflowEventTransportAdmission,
    WorkflowOutboxPublicationLease,
    WorkflowScope,
)


class WorkflowEventTransportAdmissionError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowEventTransportAdmissionStatus(StrEnum):
    ADMITTED = "admitted"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_ADMITTED = "already_admitted"


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportAdmissionIdempotencyRecord:
    request_fingerprint: str
    admission: WorkflowEventTransportAdmission


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportAdmissionRequest:
    expected_plan_digest: str
    expected_outbox_entry_digest: str
    expected_event_id: str
    expected_event_digest: str
    expected_policy_digest: str
    expected_orchestration_lease_id: str
    expected_orchestration_lease_digest: str
    expected_orchestration_fencing_token: int
    expected_publication_lease_id: str
    expected_publication_lease_digest: str
    expected_publication_fencing_token: int
    publisher_subject_id: str
    requested_at: datetime
    candidate: WorkflowEventTransportAdmission
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportAdmissionResult:
    status: WorkflowEventTransportAdmissionStatus
    admission: WorkflowEventTransportAdmission | None


class WorkflowEventTransportAdmissionRepository(Protocol):
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

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None: ...

    async def get_event_transport_admission_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportAdmissionIdempotencyRecord | None: ...

    async def admit_event_transport(
        self, request: WorkflowEventTransportAdmissionRequest
    ) -> WorkflowEventTransportAdmissionResult: ...


__all__ = [
    "WorkflowEventTransportAdmissionError",
    "WorkflowEventTransportAdmissionIdempotencyRecord",
    "WorkflowEventTransportAdmissionRepository",
    "WorkflowEventTransportAdmissionRequest",
    "WorkflowEventTransportAdmissionResult",
    "WorkflowEventTransportAdmissionStatus",
]
