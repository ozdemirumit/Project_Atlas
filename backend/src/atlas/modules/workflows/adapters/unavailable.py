from __future__ import annotations

from typing import NoReturn

from atlas.modules.workflows.application import (
    WorkflowLeaseAcquireIdempotencyRecord,
    WorkflowLeaseAcquireRequest,
    WorkflowLeaseAcquireResult,
    WorkflowLeaseMutationRequest,
    WorkflowLeaseMutationResult,
    WorkflowPlanCancellationIdempotencyRecord,
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationResult,
    WorkflowPlanIdempotencyRecord,
    WorkflowPlanMutationResult,
    WorkflowPlanningError,
    WorkflowRunMaterializationError,
    WorkflowRunMaterializationIdempotencyRecord,
    WorkflowRunMaterializationRequest,
    WorkflowRunMaterializationResult,
)
from atlas.modules.workflows.domain import (
    WorkflowExecutionRun,
    WorkflowOrchestrationLease,
    WorkflowRunPlan,
    WorkflowScope,
)


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

    async def get_lease_by_plan_id(self, *, plan_id: str) -> WorkflowOrchestrationLease | None:
        self._raise()

    async def get_materialized_run_by_plan_id(self, *, plan_id: str) -> WorkflowExecutionRun | None:
        self._raise_run()

    async def get_run_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowRunMaterializationIdempotencyRecord | None:
        self._raise_run()

    async def materialize_run(
        self, request: WorkflowRunMaterializationRequest
    ) -> WorkflowRunMaterializationResult:
        self._raise_run()

    async def get_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowLeaseAcquireIdempotencyRecord | None:
        self._raise()

    async def acquire_lease(
        self, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseAcquireResult:
        self._raise()

    async def heartbeat_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        self._raise()

    async def release_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        self._raise()

    async def close(self) -> None:
        return None

    @staticmethod
    def _raise_run() -> NoReturn:
        raise WorkflowRunMaterializationError(
            "workflow_run_repository_unavailable",
            "Durable workflow run materialization storage is not configured.",
        )
