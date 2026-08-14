from __future__ import annotations

import asyncio

from atlas.modules.workflows.application import (
    WorkflowAttemptMaterializationIdempotencyRecord,
    WorkflowAttemptMaterializationRequest,
    WorkflowAttemptMaterializationResult,
    WorkflowAttemptMaterializationStatus,
    WorkflowDispatchIntentStagingIdempotencyRecord,
    WorkflowDispatchIntentStagingRequest,
    WorkflowDispatchIntentStagingResult,
    WorkflowDispatchIntentStagingStatus,
    WorkflowLeaseAcquireIdempotencyRecord,
    WorkflowLeaseAcquireRequest,
    WorkflowLeaseAcquireResult,
    WorkflowLeaseAcquireStatus,
    WorkflowLeaseMutationRequest,
    WorkflowLeaseMutationResult,
    WorkflowLeaseMutationStatus,
    WorkflowPlanCancellationIdempotencyRecord,
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationResult,
    WorkflowPlanCancellationStatus,
    WorkflowPlanIdempotencyRecord,
    WorkflowPlanMutationResult,
    WorkflowPlanMutationStatus,
    WorkflowRunMaterializationIdempotencyRecord,
    WorkflowRunMaterializationRequest,
    WorkflowRunMaterializationResult,
    WorkflowRunMaterializationStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchIntent,
    WorkflowDispatchIntentState,
    WorkflowExecutionAttempt,
    WorkflowExecutionAttemptState,
    WorkflowExecutionRun,
    WorkflowExecutionRunState,
    WorkflowExecutionStepRunState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowPlanState,
    WorkflowRunPlan,
    WorkflowScope,
)


class InMemoryWorkflowPlanRepository:
    """Explicit development-only, non-durable workflow plan repository."""

    def __init__(self) -> None:
        self._plans: dict[str, WorkflowRunPlan] = {}
        self._requests: dict[tuple[WorkflowScope, str, str], WorkflowPlanIdempotencyRecord] = {}
        self._cancellation_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowPlanCancellationIdempotencyRecord
        ] = {}
        self._leases_by_plan: dict[str, WorkflowOrchestrationLease] = {}
        self._lease_acquire_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowLeaseAcquireIdempotencyRecord
        ] = {}
        self._runs_by_plan: dict[str, WorkflowExecutionRun] = {}
        self._run_materialization_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowRunMaterializationIdempotencyRecord
        ] = {}
        self._attempts_by_step_run: dict[str, WorkflowExecutionAttempt] = {}
        self._attempt_materialization_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowAttemptMaterializationIdempotencyRecord
        ] = {}
        self._dispatch_intents_by_attempt: dict[str, WorkflowDispatchIntent] = {}
        self._dispatch_intent_staging_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowDispatchIntentStagingIdempotencyRecord
        ] = {}
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

    async def get_cancellation_request(
        self,
        *,
        scope: WorkflowScope,
        actor_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanCancellationIdempotencyRecord | None:
        async with self._lock:
            return self._cancellation_requests.get((scope, actor_subject_id, idempotency_key))

    async def cancel(
        self, request: WorkflowPlanCancellationRequest
    ) -> WorkflowPlanCancellationResult:
        async with self._lock:
            plan = request.cancelled_plan
            key = (plan.scope, request.actor_subject_id, request.idempotency_key)
            prior = self._cancellation_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowPlanCancellationStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowPlanCancellationStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowPlanCancellationResult(status=status, plan=prior.plan)
            current = self._plans.get(plan.plan_id)
            if current is None:
                return WorkflowPlanCancellationResult(
                    status=WorkflowPlanCancellationStatus.NOT_FOUND, plan=None
                )
            if (
                current.canonical_digest != request.expected_plan_digest
                or current.state.value != "planned"
            ):
                return WorkflowPlanCancellationResult(
                    status=WorkflowPlanCancellationStatus.STATE_CONFLICT,
                    plan=current,
                )
            self._plans[plan.plan_id] = plan
            self._cancellation_requests[key] = WorkflowPlanCancellationIdempotencyRecord(
                request_fingerprint=request.request_fingerprint,
                plan=plan,
            )
            return WorkflowPlanCancellationResult(
                status=WorkflowPlanCancellationStatus.CANCELLED,
                plan=plan,
            )

    async def get_lease_by_plan_id(self, *, plan_id: str) -> WorkflowOrchestrationLease | None:
        async with self._lock:
            return self._leases_by_plan.get(plan_id)

    async def get_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowLeaseAcquireIdempotencyRecord | None:
        async with self._lock:
            return self._lease_acquire_requests.get((scope, worker_subject_id, idempotency_key))

    async def get_materialized_run_by_plan_id(self, *, plan_id: str) -> WorkflowExecutionRun | None:
        async with self._lock:
            return self._runs_by_plan.get(plan_id)

    async def get_run_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowRunMaterializationIdempotencyRecord | None:
        async with self._lock:
            return self._run_materialization_requests.get(
                (scope, worker_subject_id, idempotency_key)
            )

    async def materialize_run(
        self, request: WorkflowRunMaterializationRequest
    ) -> WorkflowRunMaterializationResult:
        async with self._lock:
            run = request.candidate
            key = (run.scope, request.worker_subject_id, request.idempotency_key)
            prior = self._run_materialization_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowRunMaterializationStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowRunMaterializationStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowRunMaterializationResult(status, prior.run)
            plan = self._plans.get(run.plan_id)
            lease = self._leases_by_plan.get(run.plan_id)
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest == run.plan_digest
                or plan.scope != run.scope
                or plan.target_id != run.target_id
                or plan.target_type != run.target_type
                or lease is None
                or lease.lease_id != request.expected_lease_id == run.lease_id
                or lease.canonical_digest != request.expected_lease_digest == run.lease_digest
                or lease.fencing_token != request.expected_fencing_token == run.fencing_token
                or lease.worker_subject_id != request.worker_subject_id
                or request.worker_subject_id != run.materialized_by_subject_id
                or lease.effective_state(requested_at=request.requested_at)
                is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                or lease.grants_execution_authority
            ):
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.STATE_CONFLICT, None
                )
            current = self._runs_by_plan.get(run.plan_id)
            if current is not None:
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.STATE_CONFLICT, current
                )
            self._runs_by_plan[run.plan_id] = run
            self._run_materialization_requests[key] = WorkflowRunMaterializationIdempotencyRecord(
                request_fingerprint=request.request_fingerprint,
                run=run,
            )
            return WorkflowRunMaterializationResult(WorkflowRunMaterializationStatus.CREATED, run)

    async def list_attempts_by_run_id(self, *, run_id: str) -> tuple[WorkflowExecutionAttempt, ...]:
        async with self._lock:
            return tuple(
                sorted(
                    (
                        attempt
                        for attempt in self._attempts_by_step_run.values()
                        if attempt.run_id == run_id
                    ),
                    key=lambda item: (item.attempt_number, item.step_run_id),
                )
            )

    async def get_attempt_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowAttemptMaterializationIdempotencyRecord | None:
        async with self._lock:
            return self._attempt_materialization_requests.get(
                (scope, worker_subject_id, idempotency_key)
            )

    async def materialize_attempt(
        self, request: WorkflowAttemptMaterializationRequest
    ) -> WorkflowAttemptMaterializationResult:
        async with self._lock:
            attempt = request.candidate
            key = (attempt.scope, request.worker_subject_id, request.idempotency_key)
            prior = self._attempt_materialization_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowAttemptMaterializationStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowAttemptMaterializationStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowAttemptMaterializationResult(status, prior.attempt)
            plan = self._plans.get(attempt.plan_id)
            run = self._runs_by_plan.get(attempt.plan_id)
            lease = self._leases_by_plan.get(attempt.plan_id)
            step = (
                None
                if run is None
                else next(
                    (item for item in run.step_runs if item.step_run_id == attempt.step_run_id),
                    None,
                )
            )
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest
                or request.expected_plan_digest != attempt.plan_digest
                or run is None
                or run.state is not WorkflowExecutionRunState.CREATED
                or run.canonical_digest != request.expected_run_digest
                or request.expected_run_digest != attempt.run_digest
                or run.scope != attempt.scope
                or run.target_id != attempt.target_id
                or run.target_type != attempt.target_type
                or step is None
                or step.state is not WorkflowExecutionStepRunState.NOT_STARTED
                or step.depends_on
                or step.canonical_digest != request.expected_step_run_digest
                or request.expected_step_run_digest != attempt.step_run_digest
                or step.step_id != attempt.step_id
                or lease is None
                or lease.lease_id != request.expected_lease_id
                or request.expected_lease_id != attempt.lease_id
                or lease.canonical_digest != request.expected_lease_digest
                or request.expected_lease_digest != attempt.lease_digest
                or lease.fencing_token != request.expected_fencing_token
                or request.expected_fencing_token != attempt.fencing_token
                or lease.worker_subject_id != request.worker_subject_id
                or request.worker_subject_id != attempt.materialized_by_subject_id
                or lease.effective_state(requested_at=request.requested_at)
                is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                or lease.grants_execution_authority
                or attempt.attempt_number != 1
                or attempt.state is not WorkflowExecutionAttemptState.CREATED
                or attempt.grants_execution_authority
            ):
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.STATE_CONFLICT, None
                )
            current = self._attempts_by_step_run.get(step.step_run_id)
            if current is not None:
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.STATE_CONFLICT, current
                )
            self._attempts_by_step_run[step.step_run_id] = attempt
            self._attempt_materialization_requests[key] = (
                WorkflowAttemptMaterializationIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    attempt=attempt,
                )
            )
            return WorkflowAttemptMaterializationResult(
                WorkflowAttemptMaterializationStatus.CREATED, attempt
            )

    async def list_dispatch_intents_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchIntent, ...]:
        async with self._lock:
            return tuple(
                sorted(
                    (
                        dispatch_intent
                        for dispatch_intent in self._dispatch_intents_by_attempt.values()
                        if dispatch_intent.run_id == run_id
                    ),
                    key=lambda item: (item.staged_at, item.dispatch_intent_id),
                )
            )

    async def get_dispatch_intent_staging_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchIntentStagingIdempotencyRecord | None:
        async with self._lock:
            return self._dispatch_intent_staging_requests.get(
                (scope, worker_subject_id, idempotency_key)
            )

    async def stage_dispatch_intent(
        self, request: WorkflowDispatchIntentStagingRequest
    ) -> WorkflowDispatchIntentStagingResult:
        async with self._lock:
            dispatch_intent = request.candidate
            key = (dispatch_intent.scope, request.worker_subject_id, request.idempotency_key)
            prior = self._dispatch_intent_staging_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowDispatchIntentStagingStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowDispatchIntentStagingStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowDispatchIntentStagingResult(status, prior.dispatch_intent)

            plan = self._plans.get(dispatch_intent.plan_id)
            run = self._runs_by_plan.get(dispatch_intent.plan_id)
            lease = self._leases_by_plan.get(dispatch_intent.plan_id)
            step = (
                None
                if run is None
                else next(
                    (
                        item
                        for item in run.step_runs
                        if item.step_run_id == dispatch_intent.step_run_id
                    ),
                    None,
                )
            )
            attempt = self._attempts_by_step_run.get(dispatch_intent.step_run_id)
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest
                or request.expected_plan_digest != dispatch_intent.plan_digest
                or plan.scope != dispatch_intent.scope
                or plan.target_id != dispatch_intent.target_id
                or plan.target_type != dispatch_intent.target_type
                or run is None
                or run.state is not WorkflowExecutionRunState.CREATED
                or run.canonical_digest != request.expected_run_digest
                or request.expected_run_digest != dispatch_intent.run_digest
                or run.run_id != dispatch_intent.run_id
                or step is None
                or step.state is not WorkflowExecutionStepRunState.NOT_STARTED
                or step.canonical_digest != request.expected_step_run_digest
                or request.expected_step_run_digest != dispatch_intent.step_run_digest
                or step.step_id != dispatch_intent.step_id
                or attempt is None
                or attempt.state is not WorkflowExecutionAttemptState.CREATED
                or attempt.canonical_digest != request.expected_attempt_digest
                or request.expected_attempt_digest != dispatch_intent.attempt_digest
                or attempt.attempt_id != dispatch_intent.attempt_id
                or attempt.attempt_number != dispatch_intent.attempt_number
                or attempt.run_id != run.run_id
                or attempt.step_run_id != step.step_run_id
                or attempt.grants_execution_authority
                or lease is None
                or lease.lease_id != request.expected_lease_id
                or request.expected_lease_id != dispatch_intent.lease_id
                or lease.canonical_digest != request.expected_lease_digest
                or request.expected_lease_digest != dispatch_intent.lease_digest
                or lease.fencing_token != request.expected_fencing_token
                or request.expected_fencing_token != dispatch_intent.fencing_token
                or lease.worker_subject_id != request.worker_subject_id
                or request.worker_subject_id != dispatch_intent.worker_subject_id
                or run.lease_id != lease.lease_id
                or run.fencing_token != lease.fencing_token
                or attempt.lease_id != lease.lease_id
                or attempt.fencing_token != lease.fencing_token
                or lease.effective_state(requested_at=request.requested_at)
                is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                or lease.grants_execution_authority
                or dispatch_intent.state is not WorkflowDispatchIntentState.STAGED
                or any(dispatch_intent.authority.canonical_value().values())
                or dispatch_intent.grants_dispatch_authority
                or dispatch_intent.grants_execution_authority
            ):
                return WorkflowDispatchIntentStagingResult(
                    WorkflowDispatchIntentStagingStatus.STATE_CONFLICT, None
                )
            current = self._dispatch_intents_by_attempt.get(attempt.attempt_id)
            if current is not None:
                return WorkflowDispatchIntentStagingResult(
                    WorkflowDispatchIntentStagingStatus.STATE_CONFLICT, current
                )
            self._dispatch_intents_by_attempt[attempt.attempt_id] = dispatch_intent
            self._dispatch_intent_staging_requests[key] = (
                WorkflowDispatchIntentStagingIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    dispatch_intent=dispatch_intent,
                )
            )
            return WorkflowDispatchIntentStagingResult(
                WorkflowDispatchIntentStagingStatus.STAGED, dispatch_intent
            )

    async def acquire_lease(
        self, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseAcquireResult:
        """Atomically checks the exact plan and replaces only an expired lease."""
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, candidate.worker_subject_id, request.idempotency_key)
            prior = self._lease_acquire_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowLeaseAcquireStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowLeaseAcquireStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowLeaseAcquireResult(status=status, lease=prior.lease)
            plan = self._plans.get(candidate.plan_id)
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest
                or plan.canonical_digest != candidate.plan_digest
                or plan.scope != candidate.scope
                or plan.target_id != candidate.target_id
                or plan.target_type != candidate.target_type
            ):
                return WorkflowLeaseAcquireResult(
                    status=WorkflowLeaseAcquireStatus.PLAN_CONFLICT, lease=None
                )
            current = self._leases_by_plan.get(candidate.plan_id)
            if current is None:
                if (
                    request.expected_current_lease_digest is not None
                    or request.expected_current_fencing_token is not None
                    or candidate.fencing_token != 1
                ):
                    return WorkflowLeaseAcquireResult(
                        status=WorkflowLeaseAcquireStatus.CONTENDED, lease=None
                    )
            else:
                if (
                    current.canonical_digest != request.expected_current_lease_digest
                    or current.fencing_token != request.expected_current_fencing_token
                    or current.effective_state(requested_at=request.requested_at)
                    is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                    or candidate.fencing_token != current.fencing_token + 1
                ):
                    return WorkflowLeaseAcquireResult(
                        status=WorkflowLeaseAcquireStatus.CONTENDED, lease=current
                    )
            self._leases_by_plan[candidate.plan_id] = candidate
            self._lease_acquire_requests[key] = WorkflowLeaseAcquireIdempotencyRecord(
                request_fingerprint=request.request_fingerprint,
                lease=candidate,
            )
            return WorkflowLeaseAcquireResult(
                status=WorkflowLeaseAcquireStatus.ACQUIRED, lease=candidate
            )

    async def heartbeat_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        return await self._mutate_lease(request)

    async def release_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        return await self._mutate_lease(request)

    async def _mutate_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        async with self._lock:
            updated = request.updated_lease
            plan = self._plans.get(updated.plan_id)
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest
                or plan.canonical_digest != updated.plan_digest
            ):
                return WorkflowLeaseMutationResult(
                    status=WorkflowLeaseMutationStatus.PLAN_CONFLICT, lease=None
                )
            current = self._leases_by_plan.get(updated.plan_id)
            if current is None:
                return WorkflowLeaseMutationResult(
                    status=WorkflowLeaseMutationStatus.NOT_FOUND, lease=None
                )
            if (
                current.lease_id != request.expected_lease_id
                or current.canonical_digest != request.expected_lease_digest
                or current.fencing_token != request.expected_fencing_token
                or current.worker_subject_id != request.worker_subject_id
                or current.effective_state(requested_at=request.requested_at)
                is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                or updated.lease_id != current.lease_id
                or updated.plan_id != current.plan_id
                or updated.plan_digest != current.plan_digest
                or updated.scope != current.scope
                or updated.target_id != current.target_id
                or updated.target_type != current.target_type
                or updated.worker_subject_id != current.worker_subject_id
                or updated.fencing_token != current.fencing_token
            ):
                return WorkflowLeaseMutationResult(
                    status=WorkflowLeaseMutationStatus.LEASE_CONFLICT, lease=current
                )
            self._leases_by_plan[updated.plan_id] = updated
            return WorkflowLeaseMutationResult(
                status=WorkflowLeaseMutationStatus.UPDATED, lease=updated
            )

    async def close(self) -> None:
        return None
