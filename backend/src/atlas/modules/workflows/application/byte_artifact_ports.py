from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchOutboxEntry,
    WorkflowEventByteArtifact,
    WorkflowEventTransportAdmission,
    WorkflowOutboxPublicationLease,
    WorkflowScope,
)


class WorkflowEventByteArtifactError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowEventByteArtifactStatus(StrEnum):
    MATERIALIZED = "materialized"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_MATERIALIZED = "already_materialized"


@dataclass(frozen=True, slots=True)
class WorkflowEventByteArtifactIdempotencyRecord:
    request_fingerprint: str
    artifact: WorkflowEventByteArtifact


@dataclass(frozen=True, slots=True)
class WorkflowEventByteArtifactRequest:
    expected_plan_digest: str
    expected_outbox_entry_digest: str
    expected_event_id: str
    expected_event_digest: str
    expected_admission_id: str
    expected_admission_digest: str
    expected_policy_digest: str
    expected_orchestration_lease_id: str
    expected_orchestration_lease_digest: str
    expected_orchestration_fencing_token: int
    expected_publication_lease_id: str
    expected_publication_lease_digest: str
    expected_publication_fencing_token: int
    publisher_subject_id: str
    requested_at: datetime
    candidate: WorkflowEventByteArtifact
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowEventByteArtifactResult:
    status: WorkflowEventByteArtifactStatus
    artifact: WorkflowEventByteArtifact | None


class WorkflowEventByteArtifactRepository(Protocol):
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

    async def get_event_byte_artifact_by_admission_id(
        self, *, admission_id: str
    ) -> WorkflowEventByteArtifact | None: ...

    async def get_event_byte_artifact_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventByteArtifactIdempotencyRecord | None: ...

    async def materialize_event_byte_artifact(
        self, request: WorkflowEventByteArtifactRequest
    ) -> WorkflowEventByteArtifactResult: ...


__all__ = [
    "WorkflowEventByteArtifactError",
    "WorkflowEventByteArtifactIdempotencyRecord",
    "WorkflowEventByteArtifactRepository",
    "WorkflowEventByteArtifactRequest",
    "WorkflowEventByteArtifactResult",
    "WorkflowEventByteArtifactStatus",
]
