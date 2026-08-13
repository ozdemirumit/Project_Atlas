from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import WorkflowExecutionRun, WorkflowScope


class WorkflowRunMaterializationError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowRunMaterializationStatus(StrEnum):
    CREATED = "created"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    STATE_CONFLICT = "state_conflict"


@dataclass(frozen=True, slots=True)
class WorkflowRunMaterializationIdempotencyRecord:
    request_fingerprint: str
    run: WorkflowExecutionRun


@dataclass(frozen=True, slots=True)
class WorkflowRunMaterializationRequest:
    candidate: WorkflowExecutionRun
    expected_plan_digest: str
    expected_lease_id: str
    expected_lease_digest: str
    expected_fencing_token: int
    worker_subject_id: str
    requested_at: datetime
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowRunMaterializationResult:
    status: WorkflowRunMaterializationStatus
    run: WorkflowExecutionRun | None


class WorkflowRunMaterializationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_materialized_run_by_plan_id(
        self, *, plan_id: str
    ) -> WorkflowExecutionRun | None: ...

    async def get_run_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowRunMaterializationIdempotencyRecord | None: ...

    async def materialize_run(
        self, request: WorkflowRunMaterializationRequest
    ) -> WorkflowRunMaterializationResult: ...


__all__ = [
    "WorkflowRunMaterializationError",
    "WorkflowRunMaterializationIdempotencyRecord",
    "WorkflowRunMaterializationRepository",
    "WorkflowRunMaterializationRequest",
    "WorkflowRunMaterializationResult",
    "WorkflowRunMaterializationStatus",
]
