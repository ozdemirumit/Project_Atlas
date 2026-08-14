from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowDispatchOutboxEntry,
    WorkflowEventByteArtifact,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventTransportAdmission,
    WorkflowOutboxPublicationLease,
    WorkflowScope,
)


class WorkflowEventLogicalChannelBindingError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowEventLogicalChannelBindingStatus(StrEnum):
    BOUND = "bound"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_BOUND = "already_bound"


@dataclass(frozen=True, slots=True)
class WorkflowEventLogicalChannelBindingIdempotencyRecord:
    request_fingerprint: str
    binding: WorkflowEventLogicalChannelBinding


@dataclass(frozen=True, slots=True)
class WorkflowEventLogicalChannelBindingRequest:
    expected_plan_digest: str
    expected_outbox_entry_digest: str
    expected_event_id: str
    expected_event_digest: str
    expected_admission_id: str
    expected_admission_digest: str
    expected_artifact_id: str
    expected_artifact_digest: str
    expected_content_sha256: str
    expected_canonical_byte_count: int
    expected_policy_digest: str
    expected_orchestration_lease_id: str
    expected_orchestration_lease_digest: str
    expected_orchestration_fencing_token: int
    expected_publication_lease_id: str
    expected_publication_lease_digest: str
    expected_publication_fencing_token: int
    publisher_subject_id: str
    requested_at: datetime
    candidate: WorkflowEventLogicalChannelBinding
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowEventLogicalChannelBindingResult:
    status: WorkflowEventLogicalChannelBindingStatus
    binding: WorkflowEventLogicalChannelBinding | None


class WorkflowEventLogicalChannelBindingRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None: ...

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None: ...

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None: ...

    async def get_event_byte_artifact_by_id(
        self, *, artifact_id: str
    ) -> WorkflowEventByteArtifact | None: ...

    async def get_event_logical_channel_binding_by_artifact_id(
        self, *, artifact_id: str
    ) -> WorkflowEventLogicalChannelBinding | None: ...

    async def get_event_logical_channel_binding_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventLogicalChannelBindingIdempotencyRecord | None: ...

    async def bind_event_logical_channel(
        self, request: WorkflowEventLogicalChannelBindingRequest
    ) -> WorkflowEventLogicalChannelBindingResult: ...


__all__ = [
    "WorkflowEventLogicalChannelBindingError",
    "WorkflowEventLogicalChannelBindingIdempotencyRecord",
    "WorkflowEventLogicalChannelBindingRepository",
    "WorkflowEventLogicalChannelBindingRequest",
    "WorkflowEventLogicalChannelBindingResult",
    "WorkflowEventLogicalChannelBindingStatus",
]
