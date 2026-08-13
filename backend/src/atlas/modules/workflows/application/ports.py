from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from atlas.modules.workflows.domain import WorkflowRunPlan, WorkflowScope


class WorkflowPlanningError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class WorkflowPlanMutationStatus(StrEnum):
    CREATED = "created"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"


class WorkflowPlanCancellationStatus(StrEnum):
    CANCELLED = "cancelled"
    REPLAY = "replay"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    STATE_CONFLICT = "state_conflict"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class WorkflowPlanIdempotencyRecord:
    request_fingerprint: str
    plan: WorkflowRunPlan


@dataclass(frozen=True, slots=True)
class WorkflowPlanMutationResult:
    status: WorkflowPlanMutationStatus
    plan: WorkflowRunPlan | None


@dataclass(frozen=True, slots=True)
class WorkflowPlanCancellationIdempotencyRecord:
    request_fingerprint: str
    plan: WorkflowRunPlan


@dataclass(frozen=True, slots=True)
class WorkflowPlanCancellationRequest:
    expected_plan_digest: str
    cancelled_plan: WorkflowRunPlan
    actor_subject_id: str
    idempotency_key: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class WorkflowPlanCancellationResult:
    status: WorkflowPlanCancellationStatus
    plan: WorkflowRunPlan | None


class WorkflowPlanRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, plan_id: str) -> WorkflowRunPlan | None: ...

    async def list_scoped(
        self,
        *,
        scope: WorkflowScope,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[WorkflowRunPlan, ...]: ...

    async def get_create_request(
        self,
        *,
        scope: WorkflowScope,
        creator_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanIdempotencyRecord | None: ...

    async def create(
        self,
        plan: WorkflowRunPlan,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowPlanMutationResult: ...

    async def get_cancellation_request(
        self,
        *,
        scope: WorkflowScope,
        actor_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanCancellationIdempotencyRecord | None: ...

    async def cancel(
        self, request: WorkflowPlanCancellationRequest
    ) -> WorkflowPlanCancellationResult: ...

    async def close(self) -> None: ...
