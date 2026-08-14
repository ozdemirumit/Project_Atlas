from __future__ import annotations

import asyncio

from atlas.modules.workflows.application import (
    WorkflowAttemptMaterializationIdempotencyRecord,
    WorkflowAttemptMaterializationRequest,
    WorkflowAttemptMaterializationResult,
    WorkflowAttemptMaterializationStatus,
    WorkflowDispatchEventEnvelopePrepareIdempotencyRecord,
    WorkflowDispatchEventEnvelopePrepareRequest,
    WorkflowDispatchEventEnvelopePrepareResult,
    WorkflowDispatchEventEnvelopePrepareStatus,
    WorkflowDispatchIntentStagingIdempotencyRecord,
    WorkflowDispatchIntentStagingRequest,
    WorkflowDispatchIntentStagingResult,
    WorkflowDispatchIntentStagingStatus,
    WorkflowEventTransportAdmissionIdempotencyRecord,
    WorkflowEventTransportAdmissionRequest,
    WorkflowEventTransportAdmissionResult,
    WorkflowEventTransportAdmissionStatus,
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
from atlas.modules.workflows.application.publication_lease_ports import (
    WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord,
    WorkflowOutboxPublicationLeaseAcquireRequest,
    WorkflowOutboxPublicationLeaseAcquireResult,
    WorkflowOutboxPublicationLeaseAcquireStatus,
    WorkflowOutboxPublicationLeaseMutationRequest,
    WorkflowOutboxPublicationLeaseMutationResult,
    WorkflowOutboxPublicationLeaseMutationStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchEventEnvelopeState,
    WorkflowDispatchIntent,
    WorkflowDispatchIntentState,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionState,
    WorkflowExecutionAttempt,
    WorkflowExecutionAttemptState,
    WorkflowExecutionRun,
    WorkflowExecutionRunState,
    WorkflowExecutionStepRunState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowPlanState,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_json_byte_count,
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
        self._dispatch_outbox_entries_by_intent: dict[str, WorkflowDispatchOutboxEntry] = {}
        self._dispatch_intent_staging_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowDispatchIntentStagingIdempotencyRecord
        ] = {}
        self._publication_leases_by_outbox: dict[str, WorkflowOutboxPublicationLease] = {}
        self._publication_lease_acquire_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord,
        ] = {}
        self._dispatch_event_envelopes_by_outbox: dict[str, WorkflowDispatchEventEnvelope] = {}
        self._dispatch_event_envelope_prepare_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowDispatchEventEnvelopePrepareIdempotencyRecord,
        ] = {}
        self._event_transport_admissions_by_event: dict[str, WorkflowEventTransportAdmission] = {}
        self._event_transport_admission_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventTransportAdmissionIdempotencyRecord,
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

    async def list_dispatch_outbox_entries_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchOutboxEntry, ...]:
        async with self._lock:
            return tuple(
                sorted(
                    (
                        entry
                        for entry in self._dispatch_outbox_entries_by_intent.values()
                        if entry.run_id == run_id
                    ),
                    key=lambda item: (item.admitted_at, item.outbox_entry_id),
                )
            )

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        async with self._lock:
            return next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == outbox_entry_id
                ),
                None,
            )

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        async with self._lock:
            return self._publication_leases_by_outbox.get(outbox_entry_id)

    async def get_publication_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord | None:
        async with self._lock:
            return self._publication_lease_acquire_requests.get(
                (scope, publisher_subject_id, idempotency_key)
            )

    async def get_dispatch_event_envelope_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchEventEnvelope | None:
        async with self._lock:
            return self._dispatch_event_envelopes_by_outbox.get(outbox_entry_id)

    async def get_dispatch_event_envelope_prepare_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchEventEnvelopePrepareIdempotencyRecord | None:
        async with self._lock:
            return self._dispatch_event_envelope_prepare_requests.get(
                (scope, publisher_subject_id, idempotency_key)
            )

    async def prepare_dispatch_event_envelope(
        self, request: WorkflowDispatchEventEnvelopePrepareRequest
    ) -> WorkflowDispatchEventEnvelopePrepareResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.payload.scope, request.publisher_subject_id, request.idempotency_key)
            prior = self._dispatch_event_envelope_prepare_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowDispatchEventEnvelopePrepareStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowDispatchEventEnvelopePrepareStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowDispatchEventEnvelopePrepareResult(status, prior.envelope)

            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == candidate.payload.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(candidate.payload.plan_id)
            orchestration_lease = self._leases_by_plan.get(candidate.payload.plan_id)
            publication_lease = self._publication_leases_by_outbox.get(
                candidate.payload.outbox_entry_id
            )
            if not self._dispatch_event_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                request=request,
            ):
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.EVIDENCE_CONFLICT, None
                )
            current = self._dispatch_event_envelopes_by_outbox.get(
                candidate.payload.outbox_entry_id
            )
            if current is not None:
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.ALREADY_PREPARED, current
                )
            self._dispatch_event_envelopes_by_outbox[candidate.payload.outbox_entry_id] = candidate
            self._dispatch_event_envelope_prepare_requests[key] = (
                WorkflowDispatchEventEnvelopePrepareIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    envelope=candidate,
                )
            )
            return WorkflowDispatchEventEnvelopePrepareResult(
                WorkflowDispatchEventEnvelopePrepareStatus.PREPARED, candidate
            )

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None:
        async with self._lock:
            return self._event_transport_admissions_by_event.get(event_id)

    async def get_event_transport_admission_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportAdmissionIdempotencyRecord | None:
        async with self._lock:
            return self._event_transport_admission_requests.get(
                (scope, publisher_subject_id, idempotency_key)
            )

    async def admit_event_transport(
        self, request: WorkflowEventTransportAdmissionRequest
    ) -> WorkflowEventTransportAdmissionResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, request.publisher_subject_id, request.idempotency_key)
            prior = self._event_transport_admission_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowEventTransportAdmissionStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowEventTransportAdmissionStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowEventTransportAdmissionResult(status, prior.admission)

            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == candidate.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(candidate.plan_id)
            orchestration_lease = self._leases_by_plan.get(candidate.plan_id)
            publication_lease = self._publication_leases_by_outbox.get(candidate.outbox_entry_id)
            envelope = self._dispatch_event_envelopes_by_outbox.get(candidate.outbox_entry_id)
            if not self._event_transport_admission_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                envelope=envelope,
                request=request,
            ):
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.EVIDENCE_CONFLICT, None
                )
            current = self._event_transport_admissions_by_event.get(candidate.event_id)
            if current is not None:
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.ALREADY_ADMITTED, current
                )
            self._event_transport_admissions_by_event[candidate.event_id] = candidate
            self._event_transport_admission_requests[key] = (
                WorkflowEventTransportAdmissionIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    admission=candidate,
                )
            )
            return WorkflowEventTransportAdmissionResult(
                WorkflowEventTransportAdmissionStatus.ADMITTED, candidate
            )

    async def acquire_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseAcquireRequest
    ) -> WorkflowOutboxPublicationLeaseAcquireResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, candidate.publisher_subject_id, request.idempotency_key)
            prior = self._publication_lease_acquire_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowOutboxPublicationLeaseAcquireStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowOutboxPublicationLeaseAcquireStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowOutboxPublicationLeaseAcquireResult(status, prior.lease)

            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == candidate.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(candidate.plan_id)
            orchestration_lease = self._leases_by_plan.get(candidate.plan_id)
            if not self._publication_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                request=request,
            ):
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.EVIDENCE_CONFLICT,
                    None,
                )

            current = self._publication_leases_by_outbox.get(candidate.outbox_entry_id)
            if not self._publication_acquire_generation_matches(
                current=current,
                request=request,
            ):
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED,
                    current,
                )
            self._publication_leases_by_outbox[candidate.outbox_entry_id] = candidate
            self._publication_lease_acquire_requests[key] = (
                WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    lease=candidate,
                )
            )
            return WorkflowOutboxPublicationLeaseAcquireResult(
                WorkflowOutboxPublicationLeaseAcquireStatus.ACQUIRED,
                candidate,
            )

    async def heartbeat_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return await self._mutate_publication_lease(request)

    async def release_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return await self._mutate_publication_lease(request)

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
            outbox_entry = request.outbox_entry
            key = (dispatch_intent.scope, request.worker_subject_id, request.idempotency_key)
            prior = self._dispatch_intent_staging_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowDispatchIntentStagingStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowDispatchIntentStagingStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowDispatchIntentStagingResult(
                    status, prior.dispatch_intent, prior.outbox_entry
                )

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
                or outbox_entry is None
                or outbox_entry.dispatch_intent_id != dispatch_intent.dispatch_intent_id
                or outbox_entry.dispatch_intent_digest != dispatch_intent.canonical_digest
                or outbox_entry.plan_id != dispatch_intent.plan_id
                or outbox_entry.plan_digest != dispatch_intent.plan_digest
                or outbox_entry.run_id != dispatch_intent.run_id
                or outbox_entry.run_digest != dispatch_intent.run_digest
                or outbox_entry.step_run_id != dispatch_intent.step_run_id
                or outbox_entry.step_run_digest != dispatch_intent.step_run_digest
                or outbox_entry.step_id != dispatch_intent.step_id
                or outbox_entry.attempt_id != dispatch_intent.attempt_id
                or outbox_entry.attempt_digest != dispatch_intent.attempt_digest
                or outbox_entry.attempt_number != dispatch_intent.attempt_number
                or outbox_entry.scope != dispatch_intent.scope
                or outbox_entry.target_id != dispatch_intent.target_id
                or outbox_entry.target_type != dispatch_intent.target_type
                or outbox_entry.lease_id != lease.lease_id
                or outbox_entry.lease_digest != lease.canonical_digest
                or outbox_entry.fencing_token != lease.fencing_token
                or outbox_entry.worker_subject_id != request.worker_subject_id
                or outbox_entry.admitted_at != dispatch_intent.staged_at
                or outbox_entry.state is not WorkflowDispatchOutboxState.PENDING_PUBLICATION
                or any(outbox_entry.authority.canonical_value().values())
                or outbox_entry.grants_publication_authority
                or outbox_entry.grants_delivery_authority
                or outbox_entry.grants_dispatch_authority
                or outbox_entry.grants_execution_authority
            ):
                return WorkflowDispatchIntentStagingResult(
                    WorkflowDispatchIntentStagingStatus.STATE_CONFLICT, None
                )
            current = self._dispatch_intents_by_attempt.get(attempt.attempt_id)
            current_outbox = self._dispatch_outbox_entries_by_intent.get(
                dispatch_intent.dispatch_intent_id
            )
            if current is not None or current_outbox is not None:
                return WorkflowDispatchIntentStagingResult(
                    WorkflowDispatchIntentStagingStatus.STATE_CONFLICT,
                    current,
                    current_outbox,
                )
            self._dispatch_intents_by_attempt[attempt.attempt_id] = dispatch_intent
            self._dispatch_outbox_entries_by_intent[dispatch_intent.dispatch_intent_id] = (
                outbox_entry
            )
            self._dispatch_intent_staging_requests[key] = (
                WorkflowDispatchIntentStagingIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    dispatch_intent=dispatch_intent,
                    outbox_entry=outbox_entry,
                )
            )
            return WorkflowDispatchIntentStagingResult(
                WorkflowDispatchIntentStagingStatus.STAGED,
                dispatch_intent,
                outbox_entry,
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

    async def _mutate_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        async with self._lock:
            updated = request.updated_lease
            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == updated.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(updated.plan_id)
            orchestration_lease = self._leases_by_plan.get(updated.plan_id)
            if not self._publication_mutation_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                request=request,
            ):
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.EVIDENCE_CONFLICT,
                    None,
                )
            current = self._publication_leases_by_outbox.get(updated.outbox_entry_id)
            if current is None:
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.NOT_FOUND,
                    None,
                )
            if (
                current.publication_lease_id != request.expected_publication_lease_id
                or current.canonical_digest != request.expected_publication_lease_digest
                or current.publication_fencing_token != request.expected_publication_fencing_token
                or current.publisher_subject_id != request.publisher_subject_id
                or current.effective_state(requested_at=request.requested_at)
                is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
                or not self._same_publication_lease_generation(current, updated)
            ):
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.LEASE_CONFLICT,
                    current,
                )
            self._publication_leases_by_outbox[updated.outbox_entry_id] = updated
            return WorkflowOutboxPublicationLeaseMutationResult(
                WorkflowOutboxPublicationLeaseMutationStatus.UPDATED,
                updated,
            )

    @staticmethod
    def _publication_evidence_matches(
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            outbox is not None
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == candidate.outbox_entry_digest
            and outbox.outbox_entry_id == candidate.outbox_entry_id
            and outbox.dispatch_intent_id == candidate.dispatch_intent_id
            and outbox.dispatch_intent_digest == candidate.dispatch_intent_digest
            and outbox.plan_id == candidate.plan_id
            and outbox.plan_digest == candidate.plan_digest
            and outbox.run_id == candidate.run_id
            and outbox.run_digest == candidate.run_digest
            and outbox.step_run_id == candidate.step_run_id
            and outbox.step_run_digest == candidate.step_run_digest
            and outbox.step_id == candidate.step_id
            and outbox.attempt_id == candidate.attempt_id
            and outbox.attempt_digest == candidate.attempt_digest
            and outbox.attempt_number == candidate.attempt_number
            and outbox.scope == candidate.scope
            and outbox.target_id == candidate.target_id
            and outbox.target_type == candidate.target_type
            and not any(outbox.authority.canonical_value().values())
            and not outbox.grants_publication_authority
            and plan is not None
            and plan.state is WorkflowPlanState.PLANNED
            and plan.canonical_digest == candidate.plan_digest
            and plan.scope == candidate.scope
            and plan.target_id == candidate.target_id
            and plan.target_type == candidate.target_type
            and orchestration_lease is not None
            and orchestration_lease.lease_id
            == request.expected_orchestration_lease_id
            == candidate.orchestration_lease_id
            == outbox.lease_id
            and orchestration_lease.canonical_digest
            == request.expected_orchestration_lease_digest
            == candidate.orchestration_lease_digest
            == outbox.lease_digest
            and orchestration_lease.fencing_token
            == request.expected_orchestration_fencing_token
            == candidate.orchestration_fencing_token
            == outbox.fencing_token
            and orchestration_lease.plan_id == candidate.plan_id
            and orchestration_lease.plan_digest == candidate.plan_digest
            and orchestration_lease.scope == candidate.scope
            and orchestration_lease.target_id == candidate.target_id
            and orchestration_lease.target_type == candidate.target_type
            and orchestration_lease.worker_subject_id == outbox.worker_subject_id
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _dispatch_event_evidence_matches(
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        publication_lease: WorkflowOutboxPublicationLease | None,
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> bool:
        candidate = request.candidate
        payload = candidate.payload
        return bool(
            outbox is not None
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == payload.outbox_entry_digest
            and outbox.outbox_entry_id == payload.outbox_entry_id
            and outbox.dispatch_intent_id == payload.dispatch_intent_id
            and outbox.dispatch_intent_digest == payload.dispatch_intent_digest
            and outbox.plan_id == payload.plan_id
            and outbox.plan_digest == request.expected_plan_digest == payload.plan_digest
            and outbox.run_id == payload.run_id
            and outbox.run_digest == payload.run_digest
            and outbox.step_run_id == payload.step_run_id
            and outbox.step_run_digest == payload.step_run_digest
            and outbox.step_id == payload.step_id
            and outbox.attempt_id == payload.attempt_id
            and outbox.attempt_digest == payload.attempt_digest
            and outbox.attempt_number == payload.attempt_number
            and outbox.scope == payload.scope
            and outbox.target_id == payload.target_id
            and outbox.target_type == payload.target_type
            and not any(outbox.authority.canonical_value().values())
            and not outbox.grants_publication_authority
            and not outbox.grants_delivery_authority
            and not outbox.grants_dispatch_authority
            and not outbox.grants_execution_authority
            and plan is not None
            and plan.state is WorkflowPlanState.PLANNED
            and plan.canonical_digest == request.expected_plan_digest
            and plan.scope == payload.scope
            and plan.target_id == payload.target_id
            and plan.target_type == payload.target_type
            and orchestration_lease is not None
            and orchestration_lease.lease_id
            == request.expected_orchestration_lease_id
            == candidate.orchestration_lease_id
            == outbox.lease_id
            and orchestration_lease.canonical_digest
            == request.expected_orchestration_lease_digest
            == candidate.orchestration_lease_digest
            == outbox.lease_digest
            and orchestration_lease.fencing_token
            == request.expected_orchestration_fencing_token
            == candidate.orchestration_fencing_token
            == outbox.fencing_token
            and orchestration_lease.scope == payload.scope
            and orchestration_lease.target_id == payload.target_id
            and orchestration_lease.target_type == payload.target_type
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and publication_lease is not None
            and publication_lease.publication_lease_id
            == request.expected_publication_lease_id
            == candidate.publication_lease_id
            and publication_lease.canonical_digest
            == request.expected_publication_lease_digest
            == candidate.publication_lease_digest
            and publication_lease.publication_fencing_token
            == request.expected_publication_fencing_token
            == candidate.publication_fencing_token
            and publication_lease.outbox_entry_id == outbox.outbox_entry_id
            and publication_lease.outbox_entry_digest == outbox.canonical_digest
            and publication_lease.orchestration_lease_id == orchestration_lease.lease_id
            and publication_lease.orchestration_lease_digest == orchestration_lease.canonical_digest
            and publication_lease.orchestration_fencing_token == orchestration_lease.fencing_token
            and publication_lease.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and not any(publication_lease.authority.canonical_value().values())
            and not publication_lease.grants_publication_authority
            and not publication_lease.grants_delivery_authority
            and not publication_lease.grants_dispatch_authority
            and not publication_lease.grants_execution_authority
            and not candidate.extensions
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_transport_admission_evidence_matches(
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        publication_lease: WorkflowOutboxPublicationLease | None,
        envelope: WorkflowDispatchEventEnvelope | None,
        request: WorkflowEventTransportAdmissionRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            outbox is not None
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.outbox_entry_id == candidate.outbox_entry_id
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == candidate.outbox_entry_digest
            and outbox.dispatch_intent_id == candidate.dispatch_intent_id
            and outbox.dispatch_intent_digest == candidate.dispatch_intent_digest
            and outbox.plan_id == candidate.plan_id
            and outbox.plan_digest == request.expected_plan_digest == candidate.plan_digest
            and outbox.run_id == candidate.run_id
            and outbox.run_digest == candidate.run_digest
            and outbox.step_run_id == candidate.step_run_id
            and outbox.step_run_digest == candidate.step_run_digest
            and outbox.step_id == candidate.step_id
            and outbox.attempt_id == candidate.attempt_id
            and outbox.attempt_digest == candidate.attempt_digest
            and outbox.attempt_number == candidate.attempt_number
            and outbox.scope == candidate.scope
            and outbox.target_id == candidate.target_id
            and outbox.target_type == candidate.target_type
            and not any(outbox.authority.canonical_value().values())
            and plan is not None
            and plan.state is WorkflowPlanState.PLANNED
            and plan.canonical_digest == request.expected_plan_digest
            and plan.scope == candidate.scope
            and plan.target_id == candidate.target_id
            and plan.target_type == candidate.target_type
            and orchestration_lease is not None
            and orchestration_lease.lease_id
            == request.expected_orchestration_lease_id
            == candidate.orchestration_lease_id
            == outbox.lease_id
            and orchestration_lease.canonical_digest
            == request.expected_orchestration_lease_digest
            == candidate.orchestration_lease_digest
            == outbox.lease_digest
            and orchestration_lease.fencing_token
            == request.expected_orchestration_fencing_token
            == candidate.orchestration_fencing_token
            == outbox.fencing_token
            and orchestration_lease.scope == candidate.scope
            and orchestration_lease.target_id == candidate.target_id
            and orchestration_lease.target_type == candidate.target_type
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and publication_lease is not None
            and publication_lease.publication_lease_id
            == request.expected_publication_lease_id
            == candidate.publication_lease_id
            and publication_lease.canonical_digest
            == request.expected_publication_lease_digest
            == candidate.publication_lease_digest
            and publication_lease.publication_fencing_token
            == request.expected_publication_fencing_token
            == candidate.publication_fencing_token
            and publication_lease.outbox_entry_id == outbox.outbox_entry_id
            and publication_lease.outbox_entry_digest == outbox.canonical_digest
            and publication_lease.orchestration_lease_id == orchestration_lease.lease_id
            and publication_lease.orchestration_lease_digest == orchestration_lease.canonical_digest
            and publication_lease.orchestration_fencing_token == orchestration_lease.fencing_token
            and publication_lease.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and not any(publication_lease.authority.canonical_value().values())
            and envelope is not None
            and envelope.state is WorkflowDispatchEventEnvelopeState.PREPARED
            and envelope.event_id == request.expected_event_id == candidate.event_id
            and envelope.canonical_digest == request.expected_event_digest == candidate.event_digest
            and envelope.event_type == candidate.event_type
            and envelope.event_version == candidate.event_version
            and envelope.schema_uri == candidate.schema_uri
            and envelope.data_classification == candidate.data_classification
            and envelope.payload.outbox_entry_id == outbox.outbox_entry_id
            and envelope.payload.outbox_entry_digest == outbox.canonical_digest
            and envelope.payload.dispatch_intent_id == candidate.dispatch_intent_id
            and envelope.payload.dispatch_intent_digest == candidate.dispatch_intent_digest
            and envelope.payload.plan_id == candidate.plan_id
            and envelope.payload.plan_digest == candidate.plan_digest
            and envelope.payload.run_id == candidate.run_id
            and envelope.payload.run_digest == candidate.run_digest
            and envelope.payload.step_run_id == candidate.step_run_id
            and envelope.payload.step_run_digest == candidate.step_run_digest
            and envelope.payload.step_id == candidate.step_id
            and envelope.payload.attempt_id == candidate.attempt_id
            and envelope.payload.attempt_digest == candidate.attempt_digest
            and envelope.payload.attempt_number == candidate.attempt_number
            and envelope.payload.scope == candidate.scope
            and envelope.payload.target_id == candidate.target_id
            and envelope.payload.target_type == candidate.target_type
            and envelope.orchestration_lease_id == orchestration_lease.lease_id
            and envelope.orchestration_lease_digest == orchestration_lease.canonical_digest
            and envelope.orchestration_fencing_token == orchestration_lease.fencing_token
            and envelope.publication_lease_id == publication_lease.publication_lease_id
            and envelope.publication_lease_digest == publication_lease.canonical_digest
            and envelope.publication_fencing_token == publication_lease.publication_fencing_token
            and envelope.publisher_subject_id == publication_lease.publisher_subject_id
            and not envelope.extensions
            and not any(envelope.authority.canonical_value().values())
            and candidate.policy_digest == request.expected_policy_digest
            and candidate.representation_name == "canonical-json"
            and candidate.encoding == "utf-8"
            and candidate.canonical_byte_count
            == canonical_json_byte_count(envelope.canonical_value())
            and candidate.canonical_byte_count <= candidate.maximum_canonical_byte_count
            and candidate.state is WorkflowEventTransportAdmissionState.ADMITTED
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @classmethod
    def _publication_mutation_evidence_matches(
        cls,
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        request: WorkflowOutboxPublicationLeaseMutationRequest,
    ) -> bool:
        candidate = request.updated_lease
        acquire_shape = WorkflowOutboxPublicationLeaseAcquireRequest(
            expected_outbox_entry_digest=request.expected_outbox_entry_digest,
            expected_orchestration_lease_id=request.expected_orchestration_lease_id,
            expected_orchestration_lease_digest=request.expected_orchestration_lease_digest,
            expected_orchestration_fencing_token=request.expected_orchestration_fencing_token,
            candidate=candidate,
            requested_at=request.requested_at,
            idempotency_key="mutation-validation",
            request_fingerprint="0" * 64,
            expected_current_lease_digest=request.expected_publication_lease_digest,
            expected_current_publication_fencing_token=(request.expected_publication_fencing_token),
        )
        return cls._publication_evidence_matches(
            outbox=outbox,
            plan=plan,
            orchestration_lease=orchestration_lease,
            request=acquire_shape,
        )

    @staticmethod
    def _publication_acquire_generation_matches(
        *,
        current: WorkflowOutboxPublicationLease | None,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> bool:
        candidate = request.candidate
        if current is None:
            return bool(
                request.expected_current_lease_digest is None
                and request.expected_current_publication_fencing_token is None
                and candidate.publication_fencing_token == 1
            )
        return bool(
            current.canonical_digest == request.expected_current_lease_digest
            and current.publication_fencing_token
            == request.expected_current_publication_fencing_token
            and current.effective_state(requested_at=request.requested_at)
            is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and candidate.publication_fencing_token == current.publication_fencing_token + 1
        )

    @staticmethod
    def _same_publication_lease_generation(
        current: WorkflowOutboxPublicationLease,
        updated: WorkflowOutboxPublicationLease,
    ) -> bool:
        immutable_fields = (
            "publication_lease_id",
            "outbox_entry_id",
            "outbox_entry_digest",
            "dispatch_intent_id",
            "dispatch_intent_digest",
            "plan_id",
            "plan_digest",
            "run_id",
            "run_digest",
            "step_run_id",
            "step_run_digest",
            "step_id",
            "attempt_id",
            "attempt_digest",
            "attempt_number",
            "scope",
            "target_id",
            "target_type",
            "orchestration_lease_id",
            "orchestration_lease_digest",
            "orchestration_fencing_token",
            "publisher_subject_id",
            "acquired_at",
            "publication_fencing_token",
            "authority",
        )
        return all(getattr(current, field) == getattr(updated, field) for field in immutable_fields)

    async def close(self) -> None:
        return None
