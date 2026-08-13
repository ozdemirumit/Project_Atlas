from __future__ import annotations

import asyncio

from atlas.modules.workflows.application import (
    WorkflowPlanIdempotencyRecord,
    WorkflowPlanMutationResult,
    WorkflowPlanMutationStatus,
)
from atlas.modules.workflows.domain import WorkflowRunPlan, WorkflowScope


class InMemoryWorkflowPlanRepository:
    """Explicit development-only, non-durable workflow plan repository."""

    def __init__(self) -> None:
        self._plans: dict[str, WorkflowRunPlan] = {}
        self._requests: dict[tuple[WorkflowScope, str, str], WorkflowPlanIdempotencyRecord] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, plan_id: str) -> WorkflowRunPlan | None:
        async with self._lock:
            return self._plans.get(plan_id)

    async def list_scoped(
        self,
        *,
        scope: WorkflowScope,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[WorkflowRunPlan, ...]:
        async with self._lock:
            plans = sorted(
                (
                    plan
                    for plan in self._plans.values()
                    if plan.scope == scope and plan.target_id in authorized_target_ids
                ),
                key=lambda plan: (plan.created_at, plan.plan_id),
                reverse=True,
            )
            return tuple(plans[:limit])

    async def get_create_request(
        self,
        *,
        scope: WorkflowScope,
        creator_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanIdempotencyRecord | None:
        async with self._lock:
            return self._requests.get((scope, creator_subject_id, idempotency_key))

    async def create(
        self,
        plan: WorkflowRunPlan,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowPlanMutationResult:
        async with self._lock:
            key = (plan.scope, plan.creator_subject_id, idempotency_key)
            prior = self._requests.get(key)
            if prior is not None:
                status = (
                    WorkflowPlanMutationStatus.REPLAY
                    if prior.request_fingerprint == request_fingerprint
                    else WorkflowPlanMutationStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowPlanMutationResult(status=status, plan=prior.plan)
            if plan.plan_id in self._plans:
                return WorkflowPlanMutationResult(
                    status=WorkflowPlanMutationStatus.IDEMPOTENCY_CONFLICT,
                    plan=None,
                )
            self._plans[plan.plan_id] = plan
            self._requests[key] = WorkflowPlanIdempotencyRecord(
                request_fingerprint=request_fingerprint,
                plan=plan,
            )
            return WorkflowPlanMutationResult(
                status=WorkflowPlanMutationStatus.CREATED,
                plan=plan,
            )

    async def close(self) -> None:
        return None
