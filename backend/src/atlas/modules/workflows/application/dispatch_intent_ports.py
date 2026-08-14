from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import WorkflowDispatchIntent, WorkflowScope


class WorkflowDispatchIntentStagingError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowDispatchIntentStagingStatus(StrEnum):
    STAGED = "staged"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    STATE_CONFLICT = "state_conflict"


@dataclass(frozen=True, slots=True)
class WorkflowDispatchIntentStagingIdempotencyRecord:
    request_fingerprint: str
    dispatch_intent: WorkflowDispatchIntent


@dataclass(frozen=True, slots=True)
class WorkflowDispatchIntentStagingRequest:
    candidate: WorkflowDispatchIntent
    expected_plan_digest: str
    expected_run_digest: str
    expected_step_run_digest: str
    expected_attempt_digest: str
    expected_lease_id: str
    expected_lease_digest: str
    expected_fencing_token: int
    worker_subject_id: str
    requested_at: datetime
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowDispatchIntentStagingResult:
    status: WorkflowDispatchIntentStagingStatus
    dispatch_intent: WorkflowDispatchIntent | None


class WorkflowDispatchIntentStagingRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def list_dispatch_intents_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchIntent, ...]: ...

    async def get_dispatch_intent_staging_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchIntentStagingIdempotencyRecord | None: ...

    async def stage_dispatch_intent(
        self, request: WorkflowDispatchIntentStagingRequest
    ) -> WorkflowDispatchIntentStagingResult: ...


__all__ = [
    "WorkflowDispatchIntentStagingError",
    "WorkflowDispatchIntentStagingIdempotencyRecord",
    "WorkflowDispatchIntentStagingRepository",
    "WorkflowDispatchIntentStagingRequest",
    "WorkflowDispatchIntentStagingResult",
    "WorkflowDispatchIntentStagingStatus",
]
