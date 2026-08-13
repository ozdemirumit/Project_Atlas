from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import WorkflowExecutionAttempt, WorkflowScope


class WorkflowAttemptMaterializationError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowAttemptMaterializationStatus(StrEnum):
    CREATED = "created"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    STATE_CONFLICT = "state_conflict"


@dataclass(frozen=True, slots=True)
class WorkflowAttemptMaterializationIdempotencyRecord:
    request_fingerprint: str
    attempt: WorkflowExecutionAttempt


@dataclass(frozen=True, slots=True)
class WorkflowAttemptMaterializationRequest:
    candidate: WorkflowExecutionAttempt
    expected_plan_digest: str
    expected_run_digest: str
    expected_step_run_digest: str
    expected_lease_id: str
    expected_lease_digest: str
    expected_fencing_token: int
    worker_subject_id: str
    requested_at: datetime
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowAttemptMaterializationResult:
    status: WorkflowAttemptMaterializationStatus
    attempt: WorkflowExecutionAttempt | None


class WorkflowAttemptMaterializationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def list_attempts_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowExecutionAttempt, ...]: ...

    async def get_attempt_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowAttemptMaterializationIdempotencyRecord | None: ...

    async def materialize_attempt(
        self, request: WorkflowAttemptMaterializationRequest
    ) -> WorkflowAttemptMaterializationResult: ...


__all__ = [
    "WorkflowAttemptMaterializationError",
    "WorkflowAttemptMaterializationIdempotencyRecord",
    "WorkflowAttemptMaterializationRepository",
    "WorkflowAttemptMaterializationRequest",
    "WorkflowAttemptMaterializationResult",
    "WorkflowAttemptMaterializationStatus",
]
