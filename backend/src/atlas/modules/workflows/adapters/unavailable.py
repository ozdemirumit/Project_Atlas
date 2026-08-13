from __future__ import annotations

from typing import NoReturn

from atlas.modules.workflows.application import (
    WorkflowPlanCancellationIdempotencyRecord,
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationResult,
    WorkflowPlanIdempotencyRecord,
    WorkflowPlanMutationResult,
    WorkflowPlanningError,
)
from atlas.modules.workflows.domain import WorkflowRunPlan, WorkflowScope


class UnavailableWorkflowPlanRepository:
    """Fail-closed adapter used when durable production storage is unavailable."""

    @property
    def durable(self) -> bool:
        return False

    @staticmethod
    def _raise() -> NoReturn:
        raise WorkflowPlanningError(
            "workflow_repository_unavailable",
            "Durable workflow plan storage is not configured.",
        )

    async def get_by_id(self, *, plan_id: str) -> WorkflowRunPlan | None:
        self._raise()

    async def list_scoped(
        self,
        *,
        scope: WorkflowScope,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[WorkflowRunPlan, ...]:
        self._raise()

    async def get_create_request(
        self,
        *,
        scope: WorkflowScope,
        creator_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanIdempotencyRecord | None:
        self._raise()

    async def create(
        self,
        plan: WorkflowRunPlan,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowPlanMutationResult:
        self._raise()

    async def get_cancellation_request(
        self,
        *,
        scope: WorkflowScope,
        actor_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanCancellationIdempotencyRecord | None:
        self._raise()

    async def cancel(
        self, request: WorkflowPlanCancellationRequest
    ) -> WorkflowPlanCancellationResult:
        self._raise()

    async def close(self) -> None:
        return None
