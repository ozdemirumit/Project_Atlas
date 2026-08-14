from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import (
    EventPhysicalTransportProfileSnapshot,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowScope,
)


class WorkflowEventTransportCompatibilityAdmissionError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowEventTransportCompatibilityAdmissionStatus(StrEnum):
    ADMITTED = "admitted"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ALREADY_ADMITTED = "already_admitted"


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord:
    request_fingerprint: str
    admission: WorkflowEventTransportCompatibilityAdmission


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportCompatibilityAdmissionRequest:
    expected_logical_channel_binding_id: str
    expected_logical_channel_binding_digest: str
    expected_transport_profile_snapshot_id: str
    expected_transport_profile_snapshot_digest: str
    expected_policy_digest: str
    scope: WorkflowScope
    admitter_subject_id: str
    requested_at: datetime
    candidate: WorkflowEventTransportCompatibilityAdmission
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowEventTransportCompatibilityAdmissionResult:
    status: WorkflowEventTransportCompatibilityAdmissionStatus
    admission: WorkflowEventTransportCompatibilityAdmission | None


class WorkflowEventTransportCompatibilityAdmissionRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_event_logical_channel_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventLogicalChannelBinding | None: ...

    async def get_transport_profile_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportProfileSnapshot | None: ...

    async def get_transport_compatibility_admission(
        self,
        *,
        logical_channel_binding_id: str,
        transport_profile_snapshot_id: str,
        policy_digest: str,
    ) -> WorkflowEventTransportCompatibilityAdmission | None: ...

    async def list_transport_compatibility_admissions_by_binding(
        self, *, logical_channel_binding_id: str
    ) -> tuple[WorkflowEventTransportCompatibilityAdmission, ...]: ...

    async def get_transport_compatibility_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord | None: ...

    async def admit_transport_compatibility(
        self, request: WorkflowEventTransportCompatibilityAdmissionRequest
    ) -> WorkflowEventTransportCompatibilityAdmissionResult: ...


__all__ = [
    "WorkflowEventTransportCompatibilityAdmissionError",
    "WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord",
    "WorkflowEventTransportCompatibilityAdmissionRepository",
    "WorkflowEventTransportCompatibilityAdmissionRequest",
    "WorkflowEventTransportCompatibilityAdmissionResult",
    "WorkflowEventTransportCompatibilityAdmissionStatus",
]
