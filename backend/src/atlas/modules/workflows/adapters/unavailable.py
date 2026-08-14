from __future__ import annotations

from typing import NoReturn

from atlas.modules.workflows.application import (
    WorkflowAttemptMaterializationError,
    WorkflowAttemptMaterializationIdempotencyRecord,
    WorkflowAttemptMaterializationRequest,
    WorkflowAttemptMaterializationResult,
    WorkflowDispatchIntentStagingError,
    WorkflowDispatchIntentStagingIdempotencyRecord,
    WorkflowDispatchIntentStagingRequest,
    WorkflowDispatchIntentStagingResult,
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
from atlas.modules.workflows.application.publication_lease_ports import (
    WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord,
    WorkflowOutboxPublicationLeaseAcquireRequest,
    WorkflowOutboxPublicationLeaseAcquireResult,
    WorkflowOutboxPublicationLeaseError,
    WorkflowOutboxPublicationLeaseMutationRequest,
    WorkflowOutboxPublicationLeaseMutationResult,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchIntent,
    WorkflowDispatchOutboxEntry,
    WorkflowExecutionAttempt,
    WorkflowExecutionRun,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
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

    async def list_attempts_by_run_id(self, *, run_id: str) -> tuple[WorkflowExecutionAttempt, ...]:
        self._raise_attempt()

    async def get_attempt_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowAttemptMaterializationIdempotencyRecord | None:
        self._raise_attempt()

    async def materialize_attempt(
        self, request: WorkflowAttemptMaterializationRequest
    ) -> WorkflowAttemptMaterializationResult:
        self._raise_attempt()

    async def list_dispatch_intents_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchIntent, ...]:
        self._raise_dispatch_intent()

    async def list_dispatch_outbox_entries_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchOutboxEntry, ...]:
        self._raise_dispatch_intent()

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        self._raise_publication_lease()

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        self._raise_publication_lease()

    async def get_publication_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord | None:
        self._raise_publication_lease()

    async def acquire_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseAcquireRequest
    ) -> WorkflowOutboxPublicationLeaseAcquireResult:
        self._raise_publication_lease()

    async def heartbeat_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        self._raise_publication_lease()

    async def release_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        self._raise_publication_lease()

    async def get_dispatch_intent_staging_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchIntentStagingIdempotencyRecord | None:
        self._raise_dispatch_intent()

    async def stage_dispatch_intent(
        self, request: WorkflowDispatchIntentStagingRequest
    ) -> WorkflowDispatchIntentStagingResult:
        self._raise_dispatch_intent()

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

    @staticmethod
    def _raise_attempt() -> NoReturn:
        raise WorkflowAttemptMaterializationError(
            "workflow_attempt_repository_unavailable",
            "Durable workflow attempt materialization storage is not configured.",
        )

    @staticmethod
    def _raise_dispatch_intent() -> NoReturn:
        raise WorkflowDispatchIntentStagingError(
            "workflow_dispatch_intent_repository_unavailable",
            "Durable workflow dispatch intent staging storage is not configured.",
        )

    @staticmethod
    def _raise_publication_lease() -> NoReturn:
        raise WorkflowOutboxPublicationLeaseError(
            "workflow_outbox_publication_lease_repository_unavailable",
            "Durable workflow outbox publication lease storage is not configured.",
        )
