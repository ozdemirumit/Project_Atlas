from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Any, NoReturn, cast

from sqlalchemy import or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    EventPhysicalTransportProfileSnapshotClaimModel,
    EventPhysicalTransportProfileSnapshotModel,
    EventPhysicalTransportRouteSnapshotClaimModel,
    EventPhysicalTransportRouteSnapshotModel,
    WorkflowAttemptMaterializationClaimModel,
    WorkflowDispatchEventEnvelopeModel,
    WorkflowDispatchEventEnvelopePreparationClaimModel,
    WorkflowDispatchIntentModel,
    WorkflowDispatchIntentStagingClaimModel,
    WorkflowDispatchOutboxEntryModel,
    WorkflowEventByteArtifactClaimModel,
    WorkflowEventByteArtifactModel,
    WorkflowEventLogicalChannelBindingClaimModel,
    WorkflowEventLogicalChannelBindingModel,
    WorkflowEventTransportAdmissionClaimModel,
    WorkflowEventTransportAdmissionModel,
    WorkflowEventTransportCompatibilityAdmissionClaimModel,
    WorkflowEventTransportCompatibilityAdmissionModel,
    WorkflowExecutionAttemptModel,
    WorkflowExecutionRunModel,
    WorkflowExecutionStepRunModel,
    WorkflowIdempotencyModel,
    WorkflowLeaseIdempotencyModel,
    WorkflowOrchestrationLeaseModel,
    WorkflowOutboxPublicationLeaseAcquireClaimModel,
    WorkflowOutboxPublicationLeaseModel,
    WorkflowPlanTransitionModel,
    WorkflowRunMaterializationClaimModel,
    WorkflowRunPlanModel,
)
from atlas.modules.workflows.application import (
    WorkflowAttemptMaterializationError,
    WorkflowAttemptMaterializationIdempotencyRecord,
    WorkflowAttemptMaterializationRequest,
    WorkflowAttemptMaterializationResult,
    WorkflowAttemptMaterializationStatus,
    WorkflowLeaseAcquireIdempotencyRecord,
    WorkflowLeaseAcquireRequest,
    WorkflowLeaseAcquireResult,
    WorkflowLeaseAcquireStatus,
    WorkflowLeaseMutationRequest,
    WorkflowLeaseMutationResult,
    WorkflowLeaseMutationStatus,
    WorkflowOrchestrationLeaseError,
    WorkflowPlanCancellationIdempotencyRecord,
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationResult,
    WorkflowPlanCancellationStatus,
    WorkflowPlanIdempotencyRecord,
    WorkflowPlanMutationResult,
    WorkflowPlanMutationStatus,
    WorkflowPlanningError,
    WorkflowRunMaterializationIdempotencyRecord,
    WorkflowRunMaterializationRequest,
    WorkflowRunMaterializationResult,
    WorkflowRunMaterializationStatus,
)
from atlas.modules.workflows.application.byte_artifact_ports import (
    WorkflowEventByteArtifactError,
    WorkflowEventByteArtifactIdempotencyRecord,
    WorkflowEventByteArtifactRequest,
    WorkflowEventByteArtifactResult,
    WorkflowEventByteArtifactStatus,
)
from atlas.modules.workflows.application.dispatch_intent_ports import (
    WorkflowDispatchIntentStagingError,
    WorkflowDispatchIntentStagingIdempotencyRecord,
    WorkflowDispatchIntentStagingRequest,
    WorkflowDispatchIntentStagingResult,
    WorkflowDispatchIntentStagingStatus,
)
from atlas.modules.workflows.application.event_envelope_ports import (
    WorkflowDispatchEventEnvelopeError,
    WorkflowDispatchEventEnvelopePrepareIdempotencyRecord,
    WorkflowDispatchEventEnvelopePrepareRequest,
    WorkflowDispatchEventEnvelopePrepareResult,
    WorkflowDispatchEventEnvelopePrepareStatus,
)
from atlas.modules.workflows.application.logical_channel_binding_ports import (
    WorkflowEventLogicalChannelBindingError,
    WorkflowEventLogicalChannelBindingIdempotencyRecord,
    WorkflowEventLogicalChannelBindingRequest,
    WorkflowEventLogicalChannelBindingResult,
    WorkflowEventLogicalChannelBindingStatus,
)
from atlas.modules.workflows.application.publication_lease_ports import (
    WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord,
    WorkflowOutboxPublicationLeaseAcquireRequest,
    WorkflowOutboxPublicationLeaseAcquireResult,
    WorkflowOutboxPublicationLeaseAcquireStatus,
    WorkflowOutboxPublicationLeaseError,
    WorkflowOutboxPublicationLeaseMutationRequest,
    WorkflowOutboxPublicationLeaseMutationResult,
    WorkflowOutboxPublicationLeaseMutationStatus,
)
from atlas.modules.workflows.application.transport_admission_ports import (
    WorkflowEventTransportAdmissionError,
    WorkflowEventTransportAdmissionIdempotencyRecord,
    WorkflowEventTransportAdmissionRequest,
    WorkflowEventTransportAdmissionResult,
    WorkflowEventTransportAdmissionStatus,
)
from atlas.modules.workflows.application.transport_compatibility_admission_ports import (
    WorkflowEventTransportCompatibilityAdmissionError,
    WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord,
    WorkflowEventTransportCompatibilityAdmissionRequest,
    WorkflowEventTransportCompatibilityAdmissionResult,
    WorkflowEventTransportCompatibilityAdmissionStatus,
)
from atlas.modules.workflows.application.transport_profile_snapshot_ports import (
    WorkflowTransportProfileSnapshotError,
    WorkflowTransportProfileSnapshotIdempotencyRecord,
    WorkflowTransportProfileSnapshotRequest,
    WorkflowTransportProfileSnapshotResult,
    WorkflowTransportProfileSnapshotStatus,
)
from atlas.modules.workflows.application.transport_route_snapshot_ports import (
    WorkflowTransportRouteSnapshotError,
    WorkflowTransportRouteSnapshotIdempotencyRecord,
    WorkflowTransportRouteSnapshotRequest,
    WorkflowTransportRouteSnapshotResult,
    WorkflowTransportRouteSnapshotStatus,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportProfileSnapshotAuthority,
    EventPhysicalTransportProfileSnapshotState,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotAuthority,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowCapabilityClass,
    WorkflowDispatchEventAuthority,
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchEventEnvelopeState,
    WorkflowDispatchEventPayload,
    WorkflowDispatchIntent,
    WorkflowDispatchIntentState,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowEventByteArtifact,
    WorkflowEventByteArtifactAuthority,
    WorkflowEventByteArtifactState,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventLogicalChannelBindingAuthority,
    WorkflowEventLogicalChannelBindingState,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionAuthority,
    WorkflowEventTransportAdmissionState,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowEventTransportCompatibilityAdmissionAuthority,
    WorkflowEventTransportCompatibilityAdmissionState,
    WorkflowExecutionAttempt,
    WorkflowExecutionAttemptState,
    WorkflowExecutionRun,
    WorkflowExecutionRunState,
    WorkflowExecutionStepRun,
    WorkflowExecutionStepRunState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOrchestrationLeaseState,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowOutboxPublicationLeaseState,
    WorkflowPlanAuthority,
    WorkflowPlanState,
    WorkflowPlanStep,
    WorkflowPlanStepState,
    WorkflowPlanTransition,
    WorkflowRunPlan,
    WorkflowScope,
    WorkflowStepKind,
    canonical_digest,
    canonical_json_byte_count,
    canonical_json_bytes,
    code_owned_workflow_event_logical_channel_policy,
    code_owned_workflow_event_transport_admission_policy,
)


class PostgreSQLWorkflowPlanRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLWorkflowPlanRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, plan_id: str) -> WorkflowRunPlan | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowRunPlanModel, plan_id)
            if row is None:
                return None
            transitions = await self._load_transitions(session, (plan_id,))
            return self._plan_from_row(row, transitions.get(plan_id, ()))

    async def list_scoped(
        self,
        *,
        scope: WorkflowScope,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[WorkflowRunPlan, ...]:
        if not authorized_target_ids:
            return ()
        statement = (
            select(WorkflowRunPlanModel)
            .where(
                WorkflowRunPlanModel.organization_id == scope.organization_id,
                WorkflowRunPlanModel.environment_id == scope.environment_id,
                WorkflowRunPlanModel.site_id == scope.site_id,
                WorkflowRunPlanModel.target_id.in_(authorized_target_ids),
            )
            .order_by(WorkflowRunPlanModel.created_at.desc(), WorkflowRunPlanModel.plan_id.desc())
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = tuple((await session.scalars(statement)).all())
            transitions = await self._load_transitions(session, tuple(row.plan_id for row in rows))
            return tuple(self._plan_from_row(row, transitions.get(row.plan_id, ())) for row in rows)

    async def get_create_request(
        self,
        *,
        scope: WorkflowScope,
        creator_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_claim(
                session,
                operation="create",
                scope=scope,
                subject_id=creator_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            return WorkflowPlanIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                plan=self._plan_from_claim(claim, expected_operation="create"),
            )

    async def create(
        self,
        plan: WorkflowRunPlan,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowPlanMutationResult:
        async with self._sessions() as session:
            prior = await self._replay_result(
                session,
                plan=plan,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if prior is not None:
                return prior
            try:
                session.add(self._plan_model(plan))
                session.add(
                    self._idempotency_model(
                        plan,
                        idempotency_key=idempotency_key,
                        request_fingerprint=request_fingerprint,
                    )
                )
                await session.commit()
                return WorkflowPlanMutationResult(WorkflowPlanMutationStatus.CREATED, plan)
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._replay_result(
                session,
                plan=plan,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay
            return WorkflowPlanMutationResult(
                WorkflowPlanMutationStatus.IDEMPOTENCY_CONFLICT,
                None,
            )

    async def get_cancellation_request(
        self,
        *,
        scope: WorkflowScope,
        actor_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanCancellationIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_claim(
                session,
                operation="cancel",
                scope=scope,
                subject_id=actor_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            return WorkflowPlanCancellationIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                plan=self._plan_from_claim(claim, expected_operation="cancel"),
            )

    async def cancel(
        self, request: WorkflowPlanCancellationRequest
    ) -> WorkflowPlanCancellationResult:
        candidate = request.cancelled_plan
        operation = "cancel"
        scope_id = self._idempotency_scope(candidate.scope, request.actor_subject_id)
        async with self._sessions() as session:
            prior = await self._cancellation_replay_result(session, request=request)
            if prior is not None:
                return prior

            row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            if row is None:
                await session.rollback()
                return WorkflowPlanCancellationResult(
                    WorkflowPlanCancellationStatus.NOT_FOUND, None
                )

            # A competing cancellation may have completed while this transaction waited.
            prior = await self._cancellation_replay_result(session, request=request)
            if prior is not None:
                await session.rollback()
                return prior

            transitions = await self._load_transitions(session, (candidate.plan_id,))
            current = self._plan_from_row(row, transitions.get(candidate.plan_id, ()))
            if (
                current.state is not WorkflowPlanState.PLANNED
                or current.canonical_digest != request.expected_plan_digest
                or not self._valid_cancellation(
                    current=current,
                    candidate=candidate,
                    actor_subject_id=request.actor_subject_id,
                )
            ):
                await session.rollback()
                return WorkflowPlanCancellationResult(
                    WorkflowPlanCancellationStatus.STATE_CONFLICT, current
                )

            transition = candidate.transition_history[-1]
            try:
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        update(WorkflowRunPlanModel)
                        .where(
                            WorkflowRunPlanModel.plan_id == candidate.plan_id,
                            WorkflowRunPlanModel.state == WorkflowPlanState.PLANNED.value,
                            WorkflowRunPlanModel.canonical_digest == request.expected_plan_digest,
                            WorkflowRunPlanModel.state_version == row.state_version,
                        )
                        .values(
                            state=candidate.state.value,
                            updated_at=transition.occurred_at,
                            state_version=row.state_version + 1,
                            canonical_digest=candidate.canonical_digest,
                            payload=self._plan_payload(candidate),
                        )
                    ),
                )
                if result.rowcount != 1:
                    await session.rollback()
                    latest = await self.get_by_id(plan_id=candidate.plan_id)
                    return WorkflowPlanCancellationResult(
                        WorkflowPlanCancellationStatus.STATE_CONFLICT, latest
                    )
                session.add(self._transition_model(candidate.plan_id, transition, sequence=1))
                session.add(
                    self._cancellation_idempotency_model(
                        request,
                        operation=operation,
                        scope_id=scope_id,
                    )
                )
                await session.commit()
                return WorkflowPlanCancellationResult(
                    WorkflowPlanCancellationStatus.CANCELLED, candidate
                )
            except IntegrityError:
                await session.rollback()

        return await self._cancellation_result_after_integrity_conflict(request=request)

    async def get_lease_by_plan_id(self, *, plan_id: str) -> WorkflowOrchestrationLease | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel).where(
                        WorkflowOrchestrationLeaseModel.plan_id == plan_id
                    )
                ),
            )
            return None if row is None else self._lease_from_row(row)

    async def get_materialized_run_by_plan_id(self, *, plan_id: str) -> WorkflowExecutionRun | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowExecutionRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionRunModel).where(
                        WorkflowExecutionRunModel.plan_id == plan_id
                    )
                ),
            )
            return None if row is None else self._materialized_run_from_row(row)

    async def get_run_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowRunMaterializationIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_materialization_claim(
                session,
                scope=scope,
                worker_subject_id=worker_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            return WorkflowRunMaterializationIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                run=self._materialized_run_from_claim(claim),
            )

    async def materialize_run(
        self, request: WorkflowRunMaterializationRequest
    ) -> WorkflowRunMaterializationResult:
        self._validate_materialization_request(request)
        run = request.candidate
        async with self._sessions() as session:
            replay = await self._materialization_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == run.plan_id)
                    .with_for_update()
                ),
            )
            lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == run.plan_id)
                    .with_for_update()
                ),
            )
            if not self._materialization_sources_match(
                plan_row=plan_row,
                lease_row=lease_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.STATE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowExecutionRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionRunModel)
                    .where(WorkflowExecutionRunModel.plan_id == run.plan_id)
                    .with_for_update()
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.STATE_CONFLICT,
                    self._materialized_run_from_row(existing),
                )

            try:
                session.add(self._materialized_run_model(run))
                for step in run.step_runs:
                    session.add(self._materialized_step_model(step))
                session.add(self._materialization_claim_model(request))
                await session.commit()
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.CREATED,
                    run,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._materialization_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowRunMaterializationResult(
            WorkflowRunMaterializationStatus.STATE_CONFLICT,
            None,
        )

    async def list_attempts_by_run_id(self, *, run_id: str) -> tuple[WorkflowExecutionAttempt, ...]:
        statement = (
            select(WorkflowExecutionAttemptModel)
            .where(WorkflowExecutionAttemptModel.run_id == run_id)
            .order_by(
                WorkflowExecutionAttemptModel.created_at,
                WorkflowExecutionAttemptModel.attempt_id,
            )
        )
        async with self._sessions() as session:
            rows = tuple((await session.scalars(statement)).all())
            return tuple(self._attempt_from_row(row) for row in rows)

    async def get_attempt_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowAttemptMaterializationIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_attempt_materialization_claim(
                session,
                scope=scope,
                worker_subject_id=worker_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            return WorkflowAttemptMaterializationIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                attempt=self._attempt_from_claim(claim),
            )

    async def materialize_attempt(
        self, request: WorkflowAttemptMaterializationRequest
    ) -> WorkflowAttemptMaterializationResult:
        self._validate_attempt_materialization_request(request)
        attempt = request.candidate
        async with self._sessions() as session:
            replay = await self._attempt_materialization_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == attempt.plan_id)
                    .with_for_update()
                ),
            )
            lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == attempt.plan_id)
                    .with_for_update()
                ),
            )
            run_row = cast(
                WorkflowExecutionRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionRunModel)
                    .where(WorkflowExecutionRunModel.run_id == attempt.run_id)
                    .with_for_update()
                ),
            )
            step_row = cast(
                WorkflowExecutionStepRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionStepRunModel)
                    .where(WorkflowExecutionStepRunModel.step_run_id == attempt.step_run_id)
                    .with_for_update()
                ),
            )
            if not self._attempt_materialization_sources_match(
                plan_row=plan_row,
                lease_row=lease_row,
                run_row=run_row,
                step_row=step_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.STATE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowExecutionAttemptModel | None,
                await session.scalar(
                    select(WorkflowExecutionAttemptModel)
                    .where(WorkflowExecutionAttemptModel.step_run_id == attempt.step_run_id)
                    .with_for_update()
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.STATE_CONFLICT,
                    self._attempt_from_row(existing),
                )

            try:
                session.add(self._attempt_model(attempt))
                session.add(self._attempt_materialization_claim_model(request))
                await session.commit()
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.CREATED,
                    attempt,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._attempt_materialization_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowAttemptMaterializationResult(
            WorkflowAttemptMaterializationStatus.STATE_CONFLICT,
            None,
        )

    async def list_dispatch_intents_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchIntent, ...]:
        statement = (
            select(WorkflowDispatchIntentModel)
            .where(WorkflowDispatchIntentModel.run_id == run_id)
            .order_by(
                WorkflowDispatchIntentModel.staged_at,
                WorkflowDispatchIntentModel.dispatch_intent_id,
            )
        )
        async with self._sessions() as session:
            rows = tuple((await session.scalars(statement)).all())
            return tuple(self._dispatch_intent_from_row(row) for row in rows)

    async def list_dispatch_outbox_entries_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchOutboxEntry, ...]:
        statement = (
            select(WorkflowDispatchOutboxEntryModel)
            .where(WorkflowDispatchOutboxEntryModel.run_id == run_id)
            .order_by(
                WorkflowDispatchOutboxEntryModel.admitted_at,
                WorkflowDispatchOutboxEntryModel.outbox_entry_id,
            )
        )
        async with self._sessions() as session:
            rows = tuple((await session.scalars(statement)).all())
            return tuple(self._dispatch_outbox_from_row(row) for row in rows)

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowDispatchOutboxEntryModel, outbox_entry_id)
            return None if row is None else self._dispatch_outbox_from_row(row)

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel).where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id == outbox_entry_id
                    )
                ),
            )
            return None if row is None else self._publication_lease_from_row(row)

    async def get_publication_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_publication_lease_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            return None if claim is None else self._publication_lease_record_from_claim(claim)

    async def acquire_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseAcquireRequest
    ) -> WorkflowOutboxPublicationLeaseAcquireResult:
        self._validate_publication_lease_acquire_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._publication_lease_acquire_replay(session, request=request)
            if replay is not None:
                return replay

            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            current_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            if not self._publication_lease_evidence_matches(
                outbox_row=outbox_row,
                plan_row=plan_row,
                orchestration_lease_row=orchestration_lease_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.EVIDENCE_CONFLICT,
                    None,
                )

            current = None if current_row is None else self._publication_lease_from_row(current_row)
            if not self._publication_lease_acquire_generation_matches(
                current=current,
                request=request,
            ):
                await session.rollback()
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED,
                    current,
                )

            try:
                if current_row is None:
                    session.add(self._publication_lease_model(candidate, version=1))
                else:
                    result = cast(
                        CursorResult[Any],
                        await session.execute(
                            update(WorkflowOutboxPublicationLeaseModel)
                            .where(
                                WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                                == candidate.outbox_entry_id,
                                WorkflowOutboxPublicationLeaseModel.version == current_row.version,
                                WorkflowOutboxPublicationLeaseModel.canonical_digest
                                == current_row.canonical_digest,
                                WorkflowOutboxPublicationLeaseModel.publication_fencing_token
                                == current_row.publication_fencing_token,
                            )
                            .values(
                                **self._publication_lease_values(
                                    candidate,
                                    version=current_row.version + 1,
                                )
                            )
                        ),
                    )
                    if result.rowcount != 1:
                        await session.rollback()
                        return WorkflowOutboxPublicationLeaseAcquireResult(
                            WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED,
                            current,
                        )
                session.add(self._publication_lease_claim_model(request))
                await session.commit()
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.ACQUIRED,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._publication_lease_acquire_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowOutboxPublicationLeaseAcquireResult(
            WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED,
            None,
        )

    async def heartbeat_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return await self._mutate_publication_lease(request)

    async def release_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return await self._mutate_publication_lease(request)

    async def get_dispatch_event_envelope_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchEventEnvelope | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel).where(
                        WorkflowDispatchEventEnvelopeModel.outbox_entry_id == outbox_entry_id
                    )
                ),
            )
            return None if row is None else self._dispatch_event_envelope_from_row(row)

    async def get_dispatch_event_envelope_prepare_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchEventEnvelopePrepareIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_dispatch_event_envelope_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            return None if claim is None else self._dispatch_event_envelope_record_from_claim(claim)

    async def prepare_dispatch_event_envelope(
        self, request: WorkflowDispatchEventEnvelopePrepareRequest
    ) -> WorkflowDispatchEventEnvelopePrepareResult:
        self._validate_dispatch_event_envelope_preparation_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._dispatch_event_envelope_preparation_replay(
                session,
                request=request,
            )
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.payload.plan_id)
                    .with_for_update()
                ),
            )
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.payload.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.payload.plan_id)
                    .with_for_update()
                ),
            )
            publication_lease_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.payload.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            if not self._dispatch_event_envelope_evidence_matches(
                plan_row=plan_row,
                outbox_row=outbox_row,
                orchestration_lease_row=orchestration_lease_row,
                publication_lease_row=publication_lease_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.EVIDENCE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel).where(
                        WorkflowDispatchEventEnvelopeModel.outbox_entry_id
                        == candidate.payload.outbox_entry_id
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.ALREADY_PREPARED,
                    self._dispatch_event_envelope_from_row(existing),
                )

            try:
                session.add(self._dispatch_event_envelope_model(candidate))
                session.add(self._dispatch_event_envelope_claim_model(request))
                await session.commit()
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.PREPARED,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._dispatch_event_envelope_preparation_replay(
                session,
                request=request,
            )
            if replay is not None:
                return replay
        return WorkflowDispatchEventEnvelopePrepareResult(
            WorkflowDispatchEventEnvelopePrepareStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel).where(
                        WorkflowEventTransportAdmissionModel.event_id == event_id
                    )
                ),
            )
            return None if row is None else self._event_transport_admission_from_row(row)

    async def get_event_transport_admission_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowEventTransportAdmission | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel).where(
                        WorkflowEventTransportAdmissionModel.outbox_entry_id == outbox_entry_id
                    )
                ),
            )
            return None if row is None else self._event_transport_admission_from_row(row)

    async def get_event_transport_admission_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportAdmissionIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_event_transport_admission_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            return (
                None if claim is None else self._event_transport_admission_record_from_claim(claim)
            )

    async def admit_event_transport(
        self, request: WorkflowEventTransportAdmissionRequest
    ) -> WorkflowEventTransportAdmissionResult:
        self._validate_event_transport_admission_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._event_transport_admission_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            publication_lease_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            envelope_row = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel)
                    .where(WorkflowDispatchEventEnvelopeModel.event_id == candidate.event_id)
                    .with_for_update()
                ),
            )
            if not self._event_transport_admission_evidence_matches(
                plan_row=plan_row,
                outbox_row=outbox_row,
                orchestration_lease_row=orchestration_lease_row,
                publication_lease_row=publication_lease_row,
                envelope_row=envelope_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel).where(
                        or_(
                            WorkflowEventTransportAdmissionModel.event_id == candidate.event_id,
                            WorkflowEventTransportAdmissionModel.outbox_entry_id
                            == candidate.outbox_entry_id,
                        )
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.ALREADY_ADMITTED,
                    self._event_transport_admission_from_row(existing),
                )

            try:
                session.add(self._event_transport_admission_model(candidate))
                session.add(self._event_transport_admission_claim_model(request))
                await session.commit()
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.ADMITTED,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._event_transport_admission_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowEventTransportAdmissionResult(
            WorkflowEventTransportAdmissionStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_event_byte_artifact_by_admission_id(
        self, *, admission_id: str
    ) -> WorkflowEventByteArtifact | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventByteArtifactModel | None,
                await session.scalar(
                    select(WorkflowEventByteArtifactModel).where(
                        WorkflowEventByteArtifactModel.admission_id == admission_id
                    )
                ),
            )
            return None if row is None else self._event_byte_artifact_from_row(row)

    async def get_event_byte_artifact_by_id(
        self, *, artifact_id: str
    ) -> WorkflowEventByteArtifact | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowEventByteArtifactModel, artifact_id)
            return None if row is None else self._event_byte_artifact_from_row(row)

    async def get_event_byte_artifact_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventByteArtifactIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_event_byte_artifact_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            artifact_row = await session.get(WorkflowEventByteArtifactModel, claim.artifact_id)
            return self._event_byte_artifact_record_from_claim(claim, artifact_row)

    async def materialize_event_byte_artifact(
        self, request: WorkflowEventByteArtifactRequest
    ) -> WorkflowEventByteArtifactResult:
        self._validate_event_byte_artifact_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._event_byte_artifact_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            publication_lease_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            envelope_row = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel)
                    .where(WorkflowDispatchEventEnvelopeModel.event_id == candidate.event_id)
                    .with_for_update()
                ),
            )
            admission_row = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel)
                    .where(
                        WorkflowEventTransportAdmissionModel.admission_id == candidate.admission_id
                    )
                    .with_for_update()
                ),
            )
            if not self._event_byte_artifact_evidence_matches(
                plan_row=plan_row,
                outbox_row=outbox_row,
                orchestration_lease_row=orchestration_lease_row,
                publication_lease_row=publication_lease_row,
                envelope_row=envelope_row,
                admission_row=admission_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventByteArtifactResult(
                    WorkflowEventByteArtifactStatus.EVIDENCE_CONFLICT, None
                )

            existing = cast(
                WorkflowEventByteArtifactModel | None,
                await session.scalar(
                    select(WorkflowEventByteArtifactModel).where(
                        or_(
                            WorkflowEventByteArtifactModel.admission_id == candidate.admission_id,
                            WorkflowEventByteArtifactModel.event_id == candidate.event_id,
                            WorkflowEventByteArtifactModel.outbox_entry_id
                            == candidate.outbox_entry_id,
                        )
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventByteArtifactResult(
                    WorkflowEventByteArtifactStatus.ALREADY_MATERIALIZED,
                    self._event_byte_artifact_from_row(existing),
                )

            try:
                session.add(self._event_byte_artifact_model(candidate))
                session.add(self._event_byte_artifact_claim_model(request))
                await session.commit()
                return WorkflowEventByteArtifactResult(
                    WorkflowEventByteArtifactStatus.MATERIALIZED, candidate
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._event_byte_artifact_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowEventByteArtifactResult(
            WorkflowEventByteArtifactStatus.EVIDENCE_CONFLICT, None
        )

    async def get_event_logical_channel_binding_by_artifact_id(
        self, *, artifact_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventLogicalChannelBindingModel | None,
                await session.scalar(
                    select(WorkflowEventLogicalChannelBindingModel).where(
                        WorkflowEventLogicalChannelBindingModel.artifact_id == artifact_id
                    )
                ),
            )
            return None if row is None else self._event_logical_channel_binding_from_row(row)

    async def get_event_logical_channel_binding_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventLogicalChannelBindingIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_event_logical_channel_binding_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            binding_row = await session.get(
                WorkflowEventLogicalChannelBindingModel, claim.binding_id
            )
            return self._event_logical_channel_binding_record_from_claim(claim, binding_row)

    async def bind_event_logical_channel(
        self, request: WorkflowEventLogicalChannelBindingRequest
    ) -> WorkflowEventLogicalChannelBindingResult:
        self._validate_event_logical_channel_binding_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._event_logical_channel_binding_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            publication_lease_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            envelope_row = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel)
                    .where(WorkflowDispatchEventEnvelopeModel.event_id == candidate.event_id)
                    .with_for_update()
                ),
            )
            admission_row = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel)
                    .where(
                        WorkflowEventTransportAdmissionModel.admission_id == candidate.admission_id
                    )
                    .with_for_update()
                ),
            )
            artifact_row = cast(
                WorkflowEventByteArtifactModel | None,
                await session.scalar(
                    select(WorkflowEventByteArtifactModel)
                    .where(WorkflowEventByteArtifactModel.artifact_id == candidate.artifact_id)
                    .with_for_update()
                ),
            )
            if not self._event_logical_channel_binding_evidence_matches(
                plan_row=plan_row,
                outbox_row=outbox_row,
                orchestration_lease_row=orchestration_lease_row,
                publication_lease_row=publication_lease_row,
                envelope_row=envelope_row,
                admission_row=admission_row,
                artifact_row=artifact_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventLogicalChannelBindingResult(
                    WorkflowEventLogicalChannelBindingStatus.EVIDENCE_CONFLICT, None
                )

            existing = cast(
                WorkflowEventLogicalChannelBindingModel | None,
                await session.scalar(
                    select(WorkflowEventLogicalChannelBindingModel).where(
                        WorkflowEventLogicalChannelBindingModel.artifact_id == candidate.artifact_id
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventLogicalChannelBindingResult(
                    WorkflowEventLogicalChannelBindingStatus.ALREADY_BOUND,
                    self._event_logical_channel_binding_from_row(existing),
                )

            try:
                session.add(self._event_logical_channel_binding_model(candidate))
                session.add(self._event_logical_channel_binding_claim_model(request))
                await session.commit()
                return WorkflowEventLogicalChannelBindingResult(
                    WorkflowEventLogicalChannelBindingStatus.BOUND, candidate
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._event_logical_channel_binding_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowEventLogicalChannelBindingResult(
            WorkflowEventLogicalChannelBindingStatus.EVIDENCE_CONFLICT, None
        )

    async def get_transport_profile_snapshot(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
    ) -> EventPhysicalTransportProfileSnapshot | None:
        async with self._sessions() as session:
            row = cast(
                EventPhysicalTransportProfileSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportProfileSnapshotModel).where(
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_id
                        == transport_profile_id,
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_revision
                        == transport_profile_revision,
                    )
                ),
            )
            return None if row is None else self._transport_profile_snapshot_from_row(row)

    async def get_transport_profile_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportProfileSnapshotIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_transport_profile_snapshot_claim(
                session,
                scope=scope,
                snapshotter_subject_id=snapshotter_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            snapshot_row = await session.get(
                EventPhysicalTransportProfileSnapshotModel, claim.snapshot_id
            )
            return self._transport_profile_snapshot_record_from_claim(claim, snapshot_row)

    async def snapshot_transport_profile(
        self, request: WorkflowTransportProfileSnapshotRequest
    ) -> WorkflowTransportProfileSnapshotResult:
        self._validate_transport_profile_snapshot_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._transport_profile_snapshot_replay(session, request=request)
            if replay is not None:
                return replay

            existing = cast(
                EventPhysicalTransportProfileSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportProfileSnapshotModel)
                    .where(
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_id
                        == candidate.transport_profile_id,
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_revision
                        == candidate.transport_profile_revision,
                    )
                    .with_for_update()
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._transport_profile_snapshot_from_row(existing),
                )

            if not self._transport_profile_snapshot_evidence_matches(request):
                await session.rollback()
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.SOURCE_CONFLICT, None
                )

            try:
                session.add(self._transport_profile_snapshot_model(candidate))
                session.add(self._transport_profile_snapshot_claim_model(request))
                await session.commit()
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.SNAPSHOTTED, candidate
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._transport_profile_snapshot_replay(session, request=request)
            if replay is not None:
                return replay
            existing = cast(
                EventPhysicalTransportProfileSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportProfileSnapshotModel).where(
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_id
                        == candidate.transport_profile_id,
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_revision
                        == candidate.transport_profile_revision,
                    )
                ),
            )
            if existing is not None:
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._transport_profile_snapshot_from_row(existing),
                )
        return WorkflowTransportProfileSnapshotResult(
            WorkflowTransportProfileSnapshotStatus.SOURCE_CONFLICT, None
        )

    async def get_transport_route_snapshot(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> EventPhysicalTransportRouteSnapshot | None:
        async with self._sessions() as session:
            row = cast(
                EventPhysicalTransportRouteSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportRouteSnapshotModel).where(
                        EventPhysicalTransportRouteSnapshotModel.route_id == route_id,
                        EventPhysicalTransportRouteSnapshotModel.route_revision == route_revision,
                    )
                ),
            )
            return None if row is None else self._transport_route_snapshot_from_row(row)

    async def get_transport_route_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportRouteSnapshotIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_transport_route_snapshot_claim(
                session,
                scope=scope,
                snapshotter_subject_id=snapshotter_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            snapshot_row = await session.get(
                EventPhysicalTransportRouteSnapshotModel, claim.snapshot_id
            )
            return self._transport_route_snapshot_record_from_claim(claim, snapshot_row)

    async def snapshot_transport_route(
        self, request: WorkflowTransportRouteSnapshotRequest
    ) -> WorkflowTransportRouteSnapshotResult:
        self._validate_transport_route_snapshot_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._transport_route_snapshot_replay(session, request=request)
            if replay is not None:
                return replay

            existing = cast(
                EventPhysicalTransportRouteSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportRouteSnapshotModel)
                    .where(
                        EventPhysicalTransportRouteSnapshotModel.route_id == candidate.route_id,
                        EventPhysicalTransportRouteSnapshotModel.route_revision
                        == candidate.route_revision,
                    )
                    .with_for_update()
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._transport_route_snapshot_from_row(existing),
                )

            if not self._transport_route_snapshot_evidence_matches(request):
                await session.rollback()
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.SOURCE_CONFLICT, None
                )

            try:
                session.add(self._transport_route_snapshot_model(candidate))
                session.add(self._transport_route_snapshot_claim_model(request))
                await session.commit()
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.SNAPSHOTTED, candidate
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._transport_route_snapshot_replay(session, request=request)
            if replay is not None:
                return replay
            existing = cast(
                EventPhysicalTransportRouteSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportRouteSnapshotModel).where(
                        EventPhysicalTransportRouteSnapshotModel.route_id == candidate.route_id,
                        EventPhysicalTransportRouteSnapshotModel.route_revision
                        == candidate.route_revision,
                    )
                ),
            )
            if existing is not None:
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._transport_route_snapshot_from_row(existing),
                )
        return WorkflowTransportRouteSnapshotResult(
            WorkflowTransportRouteSnapshotStatus.SOURCE_CONFLICT, None
        )

    async def get_event_logical_channel_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowEventLogicalChannelBindingModel, binding_id)
            return None if row is None else self._event_logical_channel_binding_from_row(row)

    async def get_transport_profile_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportProfileSnapshot | None:
        async with self._sessions() as session:
            row = await session.get(EventPhysicalTransportProfileSnapshotModel, snapshot_id)
            return None if row is None else self._transport_profile_snapshot_from_row(row)

    async def get_transport_compatibility_admission(
        self,
        *,
        logical_channel_binding_id: str,
        transport_profile_snapshot_id: str,
        policy_digest: str,
    ) -> WorkflowEventTransportCompatibilityAdmission | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventTransportCompatibilityAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportCompatibilityAdmissionModel).where(
                        WorkflowEventTransportCompatibilityAdmissionModel.logical_channel_binding_id
                        == logical_channel_binding_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.transport_profile_snapshot_id
                        == transport_profile_snapshot_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.policy_digest
                        == policy_digest,
                    )
                ),
            )
            return None if row is None else self._transport_compatibility_admission_from_row(row)

    async def list_transport_compatibility_admissions_by_binding(
        self, *, logical_channel_binding_id: str
    ) -> tuple[WorkflowEventTransportCompatibilityAdmission, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(WorkflowEventTransportCompatibilityAdmissionModel)
                    .where(
                        WorkflowEventTransportCompatibilityAdmissionModel.logical_channel_binding_id
                        == logical_channel_binding_id
                    )
                    .order_by(
                        WorkflowEventTransportCompatibilityAdmissionModel.transport_profile_snapshot_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.policy_digest,
                        WorkflowEventTransportCompatibilityAdmissionModel.compatibility_admission_id,
                    )
                )
            ).all()
            return tuple(self._transport_compatibility_admission_from_row(row) for row in rows)

    async def get_transport_compatibility_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_transport_compatibility_admission_claim(
                session,
                scope=scope,
                admitter_subject_id=admitter_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            admission_row = await session.get(
                WorkflowEventTransportCompatibilityAdmissionModel,
                claim.compatibility_admission_id,
            )
            return self._transport_compatibility_admission_record_from_claim(claim, admission_row)

    async def admit_transport_compatibility(
        self, request: WorkflowEventTransportCompatibilityAdmissionRequest
    ) -> WorkflowEventTransportCompatibilityAdmissionResult:
        self._validate_transport_compatibility_admission_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._transport_compatibility_admission_replay(session, request=request)
            if replay is not None:
                return replay

            # Every caller locks the two immutable source types in this fixed
            # order, preventing inverse lock acquisition across competing pairs.
            binding_row = cast(
                WorkflowEventLogicalChannelBindingModel | None,
                await session.scalar(
                    select(WorkflowEventLogicalChannelBindingModel)
                    .where(
                        WorkflowEventLogicalChannelBindingModel.binding_id
                        == candidate.logical_channel_binding_id
                    )
                    .with_for_update()
                ),
            )
            profile_row = cast(
                EventPhysicalTransportProfileSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportProfileSnapshotModel)
                    .where(
                        EventPhysicalTransportProfileSnapshotModel.snapshot_id
                        == candidate.transport_profile_snapshot_id
                    )
                    .with_for_update()
                ),
            )
            if not self._transport_compatibility_admission_evidence_matches(
                binding_row=binding_row,
                profile_row=profile_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowEventTransportCompatibilityAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportCompatibilityAdmissionModel).where(
                        WorkflowEventTransportCompatibilityAdmissionModel.logical_channel_binding_id
                        == candidate.logical_channel_binding_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.transport_profile_snapshot_id
                        == candidate.transport_profile_snapshot_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.policy_digest
                        == candidate.policy_digest,
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.ALREADY_ADMITTED,
                    self._transport_compatibility_admission_from_row(existing),
                )

            try:
                session.add(self._transport_compatibility_admission_model(candidate))
                session.add(self._transport_compatibility_admission_claim_model(request))
                await session.commit()
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.ADMITTED,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        # A competing transaction may have committed either the same scoped
        # request or another immutable identity while this transaction waited.
        async with self._sessions() as session:
            replay = await self._transport_compatibility_admission_replay(session, request=request)
            if replay is not None:
                return replay
            existing = cast(
                WorkflowEventTransportCompatibilityAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportCompatibilityAdmissionModel).where(
                        WorkflowEventTransportCompatibilityAdmissionModel.logical_channel_binding_id
                        == candidate.logical_channel_binding_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.transport_profile_snapshot_id
                        == candidate.transport_profile_snapshot_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.policy_digest
                        == candidate.policy_digest,
                    )
                ),
            )
            if existing is not None:
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.ALREADY_ADMITTED,
                    self._transport_compatibility_admission_from_row(existing),
                )
        return WorkflowEventTransportCompatibilityAdmissionResult(
            WorkflowEventTransportCompatibilityAdmissionStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_dispatch_intent_staging_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchIntentStagingIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_dispatch_intent_staging_claim(
                session,
                scope=scope,
                worker_subject_id=worker_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            intent, outbox_entry = self._dispatch_pair_from_claim(claim)
            return WorkflowDispatchIntentStagingIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                dispatch_intent=intent,
                outbox_entry=outbox_entry,
            )

    async def stage_dispatch_intent(
        self, request: WorkflowDispatchIntentStagingRequest
    ) -> WorkflowDispatchIntentStagingResult:
        self._validate_dispatch_intent_staging_request(request)
        intent = request.candidate
        outbox_entry = request.outbox_entry
        if outbox_entry is None:
            raise ValueError("workflow dispatch outbox entry is required")
        async with self._sessions() as session:
            replay = await self._dispatch_intent_staging_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == intent.plan_id)
                    .with_for_update()
                ),
            )
            lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == intent.plan_id)
                    .with_for_update()
                ),
            )
            run_row = cast(
                WorkflowExecutionRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionRunModel)
                    .where(WorkflowExecutionRunModel.run_id == intent.run_id)
                    .with_for_update()
                ),
            )
            step_row = cast(
                WorkflowExecutionStepRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionStepRunModel)
                    .where(WorkflowExecutionStepRunModel.step_run_id == intent.step_run_id)
                    .with_for_update()
                ),
            )
            attempt_row = cast(
                WorkflowExecutionAttemptModel | None,
                await session.scalar(
                    select(WorkflowExecutionAttemptModel)
                    .where(WorkflowExecutionAttemptModel.attempt_id == intent.attempt_id)
                    .with_for_update()
                ),
            )
            if not self._dispatch_intent_sources_match(
                plan_row=plan_row,
                lease_row=lease_row,
                run_row=run_row,
                step_row=step_row,
                attempt_row=attempt_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowDispatchIntentStagingResult(
                    status=WorkflowDispatchIntentStagingStatus.STATE_CONFLICT,
                    dispatch_intent=None,
                    outbox_entry=None,
                )

            existing = cast(
                WorkflowDispatchIntentModel | None,
                await session.scalar(
                    select(WorkflowDispatchIntentModel)
                    .where(WorkflowDispatchIntentModel.attempt_id == intent.attempt_id)
                    .with_for_update()
                ),
            )
            if existing is not None:
                existing_outbox = cast(
                    WorkflowDispatchOutboxEntryModel | None,
                    await session.scalar(
                        select(WorkflowDispatchOutboxEntryModel)
                        .where(
                            WorkflowDispatchOutboxEntryModel.dispatch_intent_id
                            == existing.dispatch_intent_id
                        )
                        .with_for_update()
                    ),
                )
                await session.rollback()
                return WorkflowDispatchIntentStagingResult(
                    status=WorkflowDispatchIntentStagingStatus.STATE_CONFLICT,
                    dispatch_intent=self._dispatch_intent_from_row(existing),
                    outbox_entry=(
                        None
                        if existing_outbox is None
                        else self._dispatch_outbox_from_row(existing_outbox)
                    ),
                )

            try:
                session.add(self._dispatch_intent_model(intent))
                session.add(self._dispatch_outbox_model(outbox_entry))
                session.add(self._dispatch_intent_staging_claim_model(request))
                await session.commit()
                return WorkflowDispatchIntentStagingResult(
                    status=WorkflowDispatchIntentStagingStatus.STAGED,
                    dispatch_intent=intent,
                    outbox_entry=outbox_entry,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._dispatch_intent_staging_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowDispatchIntentStagingResult(
            status=WorkflowDispatchIntentStagingStatus.STATE_CONFLICT,
            dispatch_intent=None,
            outbox_entry=None,
        )

    async def _mutate_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        self._validate_publication_lease_mutation_request(request)
        updated = request.updated_lease
        async with self._sessions() as session:
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id == updated.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == updated.plan_id)
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == updated.plan_id)
                    .with_for_update()
                ),
            )
            current_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == updated.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            if not self._publication_lease_mutation_evidence_matches(
                outbox_row=outbox_row,
                plan_row=plan_row,
                orchestration_lease_row=orchestration_lease_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.EVIDENCE_CONFLICT,
                    None,
                )
            if current_row is None:
                await session.rollback()
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.NOT_FOUND,
                    None,
                )
            current = self._publication_lease_from_row(current_row)
            if (
                current.publication_lease_id != request.expected_publication_lease_id
                or current.canonical_digest != request.expected_publication_lease_digest
                or current.publication_fencing_token != request.expected_publication_fencing_token
                or current.publisher_subject_id != request.publisher_subject_id
                or current.effective_state(requested_at=request.requested_at)
                is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
                or not self._same_publication_lease_generation(current, updated)
            ):
                await session.rollback()
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.LEASE_CONFLICT,
                    current,
                )
            result = cast(
                CursorResult[Any],
                await session.execute(
                    update(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == updated.outbox_entry_id,
                        WorkflowOutboxPublicationLeaseModel.publication_lease_id
                        == request.expected_publication_lease_id,
                        WorkflowOutboxPublicationLeaseModel.canonical_digest
                        == request.expected_publication_lease_digest,
                        WorkflowOutboxPublicationLeaseModel.publication_fencing_token
                        == request.expected_publication_fencing_token,
                        WorkflowOutboxPublicationLeaseModel.publisher_subject_id
                        == request.publisher_subject_id,
                        WorkflowOutboxPublicationLeaseModel.version == current_row.version,
                        WorkflowOutboxPublicationLeaseModel.state
                        == WorkflowOutboxPublicationLeaseState.ACTIVE.value,
                        WorkflowOutboxPublicationLeaseModel.expires_at > request.requested_at,
                    )
                    .values(
                        **self._publication_lease_values(
                            updated,
                            version=current_row.version + 1,
                        )
                    )
                ),
            )
            if result.rowcount != 1:
                await session.rollback()
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.LEASE_CONFLICT,
                    current,
                )
            await session.commit()
            return WorkflowOutboxPublicationLeaseMutationResult(
                WorkflowOutboxPublicationLeaseMutationStatus.UPDATED,
                updated,
            )

    async def get_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowLeaseAcquireIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_lease_claim(
                session,
                operation="acquire",
                scope=scope,
                worker_subject_id=worker_subject_id,
                idempotency_key=idempotency_key,
            )
            return None if claim is None else self._lease_record_from_claim(claim)

    async def acquire_lease(
        self, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseAcquireResult:
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._lease_acquire_replay(session, request=request)
            if replay is not None:
                return replay
            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            if not self._lease_plan_matches(plan_row, candidate, request.expected_plan_digest):
                await session.rollback()
                return WorkflowLeaseAcquireResult(WorkflowLeaseAcquireStatus.PLAN_CONFLICT, None)

            row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            current = None if row is None else self._lease_from_row(row)
            if not self._valid_lease_takeover(current, candidate, request):
                await session.rollback()
                return WorkflowLeaseAcquireResult(WorkflowLeaseAcquireStatus.CONTENDED, current)

            try:
                if row is None:
                    session.add(self._lease_model(candidate, version=1))
                else:
                    result = cast(
                        CursorResult[Any],
                        await session.execute(
                            update(WorkflowOrchestrationLeaseModel)
                            .where(
                                WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id,
                                WorkflowOrchestrationLeaseModel.version == row.version,
                                WorkflowOrchestrationLeaseModel.canonical_digest
                                == request.expected_current_lease_digest,
                                WorkflowOrchestrationLeaseModel.fencing_token
                                == request.expected_current_fencing_token,
                                or_(
                                    WorkflowOrchestrationLeaseModel.expires_at
                                    <= request.requested_at,
                                    WorkflowOrchestrationLeaseModel.state
                                    == WorkflowOrchestrationLeaseState.RELEASED.value,
                                ),
                            )
                            .values(**self._lease_values(candidate, version=row.version + 1))
                        ),
                    )
                    if result.rowcount != 1:
                        await session.rollback()
                        latest = await self.get_lease_by_plan_id(plan_id=candidate.plan_id)
                        return WorkflowLeaseAcquireResult(
                            WorkflowLeaseAcquireStatus.CONTENDED, latest
                        )
                session.add(self._lease_claim_model(request))
                await session.commit()
                return WorkflowLeaseAcquireResult(WorkflowLeaseAcquireStatus.ACQUIRED, candidate)
            except IntegrityError:
                await session.rollback()
        return await self._lease_acquire_after_integrity(request=request)

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
        candidate = request.updated_lease
        async with self._sessions() as session:
            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            if not self._lease_plan_matches(plan_row, candidate, request.expected_plan_digest):
                await session.rollback()
                return WorkflowLeaseMutationResult(WorkflowLeaseMutationStatus.PLAN_CONFLICT, None)
            row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            if row is None:
                await session.rollback()
                return WorkflowLeaseMutationResult(WorkflowLeaseMutationStatus.NOT_FOUND, None)
            current = self._lease_from_row(row)
            if not self._valid_lease_mutation(current, candidate, request):
                await session.rollback()
                return WorkflowLeaseMutationResult(
                    WorkflowLeaseMutationStatus.LEASE_CONFLICT, current
                )
            result = cast(
                CursorResult[Any],
                await session.execute(
                    update(WorkflowOrchestrationLeaseModel)
                    .where(
                        WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id,
                        WorkflowOrchestrationLeaseModel.lease_id == request.expected_lease_id,
                        WorkflowOrchestrationLeaseModel.canonical_digest
                        == request.expected_lease_digest,
                        WorkflowOrchestrationLeaseModel.fencing_token
                        == request.expected_fencing_token,
                        WorkflowOrchestrationLeaseModel.worker_subject_id
                        == request.worker_subject_id,
                        WorkflowOrchestrationLeaseModel.version == row.version,
                        WorkflowOrchestrationLeaseModel.state
                        == WorkflowOrchestrationLeaseState.ACTIVE.value,
                        WorkflowOrchestrationLeaseModel.expires_at > request.requested_at,
                    )
                    .values(**self._lease_values(candidate, version=row.version + 1))
                ),
            )
            if result.rowcount != 1:
                await session.rollback()
                latest = await self.get_lease_by_plan_id(plan_id=candidate.plan_id)
                return WorkflowLeaseMutationResult(
                    WorkflowLeaseMutationStatus.LEASE_CONFLICT, latest
                )
            await session.commit()
            return WorkflowLeaseMutationResult(WorkflowLeaseMutationStatus.UPDATED, candidate)

    async def close(self) -> None:
        await self._engine.dispose()

    async def _materialization_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowRunMaterializationRequest,
    ) -> WorkflowRunMaterializationResult | None:
        run = request.candidate
        scope_id = self._materialization_scope_id(run)
        claim = cast(
            WorkflowRunMaterializationClaimModel | None,
            await session.scalar(
                select(WorkflowRunMaterializationClaimModel).where(
                    WorkflowRunMaterializationClaimModel.idempotency_scope_id == scope_id,
                    WorkflowRunMaterializationClaimModel.idempotency_key == request.idempotency_key,
                    WorkflowRunMaterializationClaimModel.organization_id
                    == run.scope.organization_id,
                    WorkflowRunMaterializationClaimModel.environment_id == run.scope.environment_id,
                    WorkflowRunMaterializationClaimModel.site_id == run.scope.site_id,
                    WorkflowRunMaterializationClaimModel.worker_subject_id
                    == run.materialized_by_subject_id,
                )
            ),
        )
        if claim is None:
            return None
        result = self._materialized_run_from_claim(claim)
        status = (
            WorkflowRunMaterializationStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowRunMaterializationStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowRunMaterializationResult(status, result)

    @classmethod
    async def _load_materialization_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowRunMaterializationClaimModel | None:
        scope_id = canonical_digest(
            {
                "scope": scope.canonical_value(),
                "worker_subject_id": worker_subject_id,
            }
        )
        return cast(
            WorkflowRunMaterializationClaimModel | None,
            await session.scalar(
                select(WorkflowRunMaterializationClaimModel).where(
                    WorkflowRunMaterializationClaimModel.idempotency_scope_id == scope_id,
                    WorkflowRunMaterializationClaimModel.idempotency_key == idempotency_key,
                    WorkflowRunMaterializationClaimModel.organization_id == scope.organization_id,
                    WorkflowRunMaterializationClaimModel.environment_id == scope.environment_id,
                    WorkflowRunMaterializationClaimModel.site_id == scope.site_id,
                    WorkflowRunMaterializationClaimModel.worker_subject_id == worker_subject_id,
                )
            ),
        )

    @classmethod
    def _materialized_run_from_row(cls, row: WorkflowExecutionRunModel) -> WorkflowExecutionRun:
        try:
            run = cls._execution_run_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_run_materialization_repository_contract_violation",
                "The workflow run repository contains an invalid run.",
            ) from exc
        if (
            row.run_id != run.run_id
            or row.plan_id != run.plan_id
            or row.plan_digest != run.plan_digest
            or row.definition_id != run.definition_id
            or row.definition_version != run.definition_version
            or row.definition_digest != run.definition_digest
            or row.organization_id != run.scope.organization_id
            or row.environment_id != run.scope.environment_id
            or row.site_id != run.scope.site_id
            or row.target_type != run.target_type
            or row.target_id != run.target_id
            or row.lease_id != run.lease_id
            or row.lease_digest != run.lease_digest
            or row.lease_fencing_token != run.fencing_token
            or row.materialized_by_subject_id != run.materialized_by_subject_id
            or row.created_at != run.created_at
            or row.state != run.state.value
            or row.canonical_digest != run.canonical_digest
        ):
            cls._materialization_contract_violation()
        return run

    @classmethod
    def _materialized_run_from_claim(
        cls, claim: WorkflowRunMaterializationClaimModel
    ) -> WorkflowExecutionRun:
        raw = claim.payload.get("result_run")
        if not isinstance(raw, dict):
            cls._materialization_contract_violation()
        try:
            run = cls._execution_run_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_run_materialization_repository_contract_violation",
                "The workflow run repository contains an invalid idempotency result.",
            ) from exc
        run_payload = cls._execution_run_payload(run)
        scope_id = cls._materialization_scope_id(run)
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": run.canonical_digest,
            "result_run": run_payload,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != run.canonical_digest
            or claim.run_id != run.run_id
            or claim.plan_id != run.plan_id
            or claim.organization_id != run.scope.organization_id
            or claim.environment_id != run.scope.environment_id
            or claim.site_id != run.scope.site_id
            or claim.worker_subject_id != run.materialized_by_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._materialization_contract_violation()
        return run

    @classmethod
    def _materialized_run_model(cls, run: WorkflowExecutionRun) -> WorkflowExecutionRunModel:
        return WorkflowExecutionRunModel(
            run_id=run.run_id,
            plan_id=run.plan_id,
            plan_digest=run.plan_digest,
            definition_id=run.definition_id,
            definition_version=run.definition_version,
            definition_digest=run.definition_digest,
            organization_id=run.scope.organization_id,
            environment_id=run.scope.environment_id,
            site_id=run.scope.site_id,
            target_type=run.target_type,
            target_id=run.target_id,
            lease_id=run.lease_id,
            lease_digest=run.lease_digest,
            lease_fencing_token=run.fencing_token,
            materialized_by_subject_id=run.materialized_by_subject_id,
            created_at=run.created_at,
            state=run.state.value,
            canonical_digest=run.canonical_digest,
            payload=cls._execution_run_payload(run),
        )

    @staticmethod
    def _materialized_step_model(step: WorkflowExecutionStepRun) -> WorkflowExecutionStepRunModel:
        return WorkflowExecutionStepRunModel(
            step_run_id=step.step_run_id,
            run_id=step.run_id,
            step_id=step.step_id,
            ordinal=step.ordinal,
            kind=step.kind.value,
            capability_class=step.capability_class.value,
            timeout_seconds=step.timeout_seconds,
            depends_on=list(step.depends_on),
            state=step.state.value,
            canonical_digest=step.canonical_digest,
            payload=cast(dict[str, Any], step.canonical_value()),
        )

    @classmethod
    def _materialization_claim_model(
        cls, request: WorkflowRunMaterializationRequest
    ) -> WorkflowRunMaterializationClaimModel:
        run = request.candidate
        run_payload = cls._execution_run_payload(run)
        scope_id = cls._materialization_scope_id(run)
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": run.canonical_digest,
            "result_run": run_payload,
        }
        digest = canonical_digest(payload)
        return WorkflowRunMaterializationClaimModel(
            claim_id=f"workflow_run_mat_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=run.canonical_digest,
            run_id=run.run_id,
            plan_id=run.plan_id,
            organization_id=run.scope.organization_id,
            environment_id=run.scope.environment_id,
            site_id=run.scope.site_id,
            worker_subject_id=run.materialized_by_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _validate_materialization_request(cls, request: WorkflowRunMaterializationRequest) -> None:
        run = request.candidate
        if run.state is not WorkflowExecutionRunState.CREATED or run.grants_execution_authority:
            raise ValueError("workflow run materialization payload is unsafe")
        if len(request.idempotency_key) > 128 or not request.idempotency_key:
            raise ValueError("workflow run materialization idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow run materialization request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow run materialization time must be timezone-aware")

    @staticmethod
    def _materialization_sources_match(
        *,
        plan_row: WorkflowRunPlanModel | None,
        lease_row: WorkflowOrchestrationLeaseModel | None,
        request: WorkflowRunMaterializationRequest,
    ) -> bool:
        run = request.candidate
        return bool(
            plan_row is not None
            and lease_row is not None
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == run.plan_digest
            and plan_row.definition_id == run.definition_id
            and plan_row.definition_version == run.definition_version
            and plan_row.definition_digest == run.definition_digest
            and plan_row.organization_id == run.scope.organization_id
            and plan_row.environment_id == run.scope.environment_id
            and plan_row.site_id == run.scope.site_id
            and plan_row.target_type == run.target_type
            and plan_row.target_id == run.target_id
            and lease_row.plan_id == run.plan_id
            and lease_row.plan_digest == run.plan_digest
            and lease_row.organization_id == run.scope.organization_id
            and lease_row.environment_id == run.scope.environment_id
            and lease_row.site_id == run.scope.site_id
            and lease_row.target_type == run.target_type
            and lease_row.target_id == run.target_id
            and lease_row.lease_id == request.expected_lease_id == run.lease_id
            and lease_row.canonical_digest == request.expected_lease_digest == run.lease_digest
            and lease_row.fencing_token == request.expected_fencing_token == run.fencing_token
            and lease_row.worker_subject_id
            == request.worker_subject_id
            == run.materialized_by_subject_id
            and lease_row.state == WorkflowOrchestrationLeaseState.ACTIVE.value
            and lease_row.expires_at > request.requested_at
        )

    @staticmethod
    def _materialization_scope_id(run: WorkflowExecutionRun) -> str:
        return canonical_digest(
            {
                "scope": run.scope.canonical_value(),
                "worker_subject_id": run.materialized_by_subject_id,
            }
        )

    @staticmethod
    def _execution_run_payload(run: WorkflowExecutionRun) -> dict[str, Any]:
        return cast(dict[str, Any], run.canonical_value())

    @staticmethod
    def _execution_run_to_domain(raw: dict[str, Any]) -> WorkflowExecutionRun:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["state"] = WorkflowExecutionRunState(str(payload["state"]))
        payload["step_runs"] = tuple(
            WorkflowExecutionStepRun(
                step_run_id=str(item["step_run_id"]),
                run_id=str(item["run_id"]),
                step_id=str(item["step_id"]),
                ordinal=int(item["ordinal"]),
                kind=WorkflowStepKind(str(item["kind"])),
                capability_class=WorkflowCapabilityClass(str(item["capability_class"])),
                timeout_seconds=int(item["timeout_seconds"]),
                depends_on=tuple(str(value) for value in item["depends_on"]),
                state=WorkflowExecutionStepRunState(str(item["state"])),
                canonical_digest=str(item["canonical_digest"]),
            )
            for item in payload["step_runs"]
        )
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowExecutionRun(**cast(Any, payload))

    @staticmethod
    def _materialization_contract_violation() -> None:
        raise WorkflowPlanningError(
            "workflow_run_materialization_repository_contract_violation",
            "The workflow run materialization record does not match its canonical payload.",
        )

    async def _attempt_materialization_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowAttemptMaterializationRequest,
    ) -> WorkflowAttemptMaterializationResult | None:
        attempt = request.candidate
        claim = cast(
            WorkflowAttemptMaterializationClaimModel | None,
            await session.scalar(
                select(WorkflowAttemptMaterializationClaimModel).where(
                    WorkflowAttemptMaterializationClaimModel.idempotency_scope_id
                    == self._attempt_materialization_scope_id(attempt),
                    WorkflowAttemptMaterializationClaimModel.idempotency_key
                    == request.idempotency_key,
                    WorkflowAttemptMaterializationClaimModel.organization_id
                    == attempt.scope.organization_id,
                    WorkflowAttemptMaterializationClaimModel.environment_id
                    == attempt.scope.environment_id,
                    WorkflowAttemptMaterializationClaimModel.site_id == attempt.scope.site_id,
                    WorkflowAttemptMaterializationClaimModel.worker_subject_id
                    == attempt.materialized_by_subject_id,
                )
            ),
        )
        if claim is None:
            return None
        result = self._attempt_from_claim(claim)
        status = (
            WorkflowAttemptMaterializationStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowAttemptMaterializationStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowAttemptMaterializationResult(status, result)

    @classmethod
    async def _load_attempt_materialization_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowAttemptMaterializationClaimModel | None:
        scope_id = canonical_digest(
            {
                "scope": scope.canonical_value(),
                "worker_subject_id": worker_subject_id,
            }
        )
        return cast(
            WorkflowAttemptMaterializationClaimModel | None,
            await session.scalar(
                select(WorkflowAttemptMaterializationClaimModel).where(
                    WorkflowAttemptMaterializationClaimModel.idempotency_scope_id == scope_id,
                    WorkflowAttemptMaterializationClaimModel.idempotency_key == idempotency_key,
                    WorkflowAttemptMaterializationClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowAttemptMaterializationClaimModel.environment_id == scope.environment_id,
                    WorkflowAttemptMaterializationClaimModel.site_id == scope.site_id,
                    WorkflowAttemptMaterializationClaimModel.worker_subject_id == worker_subject_id,
                )
            ),
        )

    @classmethod
    def _attempt_from_row(cls, row: WorkflowExecutionAttemptModel) -> WorkflowExecutionAttempt:
        try:
            attempt = cls._attempt_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_materialization_repository_contract_violation",
                "The workflow attempt repository contains an invalid attempt.",
            ) from exc
        if (
            row.attempt_id != attempt.attempt_id
            or row.run_id != attempt.run_id
            or row.run_digest != attempt.run_digest
            or row.step_run_id != attempt.step_run_id
            or row.step_run_digest != attempt.step_run_digest
            or row.step_id != attempt.step_id
            or row.attempt_number != attempt.attempt_number
            or row.plan_id != attempt.plan_id
            or row.plan_digest != attempt.plan_digest
            or row.definition_id != attempt.definition_id
            or row.definition_version != attempt.definition_version
            or row.definition_digest != attempt.definition_digest
            or row.organization_id != attempt.scope.organization_id
            or row.environment_id != attempt.scope.environment_id
            or row.site_id != attempt.scope.site_id
            or row.target_type != attempt.target_type
            or row.target_id != attempt.target_id
            or row.lease_id != attempt.lease_id
            or row.lease_digest != attempt.lease_digest
            or row.lease_fencing_token != attempt.fencing_token
            or row.materialized_by_subject_id != attempt.materialized_by_subject_id
            or row.created_at != attempt.created_at
            or row.state != attempt.state.value
            or row.canonical_digest != attempt.canonical_digest
        ):
            cls._attempt_contract_violation()
        return attempt

    @classmethod
    def _attempt_from_claim(
        cls, claim: WorkflowAttemptMaterializationClaimModel
    ) -> WorkflowExecutionAttempt:
        raw = claim.payload.get("result_attempt")
        if not isinstance(raw, dict):
            cls._attempt_contract_violation()
        try:
            attempt = cls._attempt_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_materialization_repository_contract_violation",
                "The workflow attempt repository contains an invalid idempotency result.",
            ) from exc
        attempt_payload = cls._attempt_payload(attempt)
        scope_id = cls._attempt_materialization_scope_id(attempt)
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_attempt": attempt_payload,
            "result_digest": attempt.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != attempt.canonical_digest
            or claim.attempt_id != attempt.attempt_id
            or claim.run_id != attempt.run_id
            or claim.plan_id != attempt.plan_id
            or claim.organization_id != attempt.scope.organization_id
            or claim.environment_id != attempt.scope.environment_id
            or claim.site_id != attempt.scope.site_id
            or claim.worker_subject_id != attempt.materialized_by_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._attempt_contract_violation()
        return attempt

    @classmethod
    def _attempt_model(cls, attempt: WorkflowExecutionAttempt) -> WorkflowExecutionAttemptModel:
        return WorkflowExecutionAttemptModel(
            attempt_id=attempt.attempt_id,
            run_id=attempt.run_id,
            run_digest=attempt.run_digest,
            step_run_id=attempt.step_run_id,
            step_run_digest=attempt.step_run_digest,
            step_id=attempt.step_id,
            attempt_number=attempt.attempt_number,
            plan_id=attempt.plan_id,
            plan_digest=attempt.plan_digest,
            definition_id=attempt.definition_id,
            definition_version=attempt.definition_version,
            definition_digest=attempt.definition_digest,
            organization_id=attempt.scope.organization_id,
            environment_id=attempt.scope.environment_id,
            site_id=attempt.scope.site_id,
            target_type=attempt.target_type,
            target_id=attempt.target_id,
            lease_id=attempt.lease_id,
            lease_digest=attempt.lease_digest,
            lease_fencing_token=attempt.fencing_token,
            materialized_by_subject_id=attempt.materialized_by_subject_id,
            created_at=attempt.created_at,
            state=attempt.state.value,
            canonical_digest=attempt.canonical_digest,
            payload=cls._attempt_payload(attempt),
        )

    @classmethod
    def _attempt_materialization_claim_model(
        cls, request: WorkflowAttemptMaterializationRequest
    ) -> WorkflowAttemptMaterializationClaimModel:
        attempt = request.candidate
        scope_id = cls._attempt_materialization_scope_id(attempt)
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_attempt": cls._attempt_payload(attempt),
            "result_digest": attempt.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowAttemptMaterializationClaimModel(
            claim_id=f"workflow_attempt_mat_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=attempt.canonical_digest,
            attempt_id=attempt.attempt_id,
            run_id=attempt.run_id,
            plan_id=attempt.plan_id,
            organization_id=attempt.scope.organization_id,
            environment_id=attempt.scope.environment_id,
            site_id=attempt.scope.site_id,
            worker_subject_id=attempt.materialized_by_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _validate_attempt_materialization_request(
        cls, request: WorkflowAttemptMaterializationRequest
    ) -> None:
        attempt = request.candidate
        if (
            attempt.state is not WorkflowExecutionAttemptState.CREATED
            or attempt.attempt_number != 1
            or attempt.grants_execution_authority
        ):
            raise ValueError("workflow attempt materialization payload is unsafe")
        if len(request.idempotency_key) > 128 or not request.idempotency_key:
            raise ValueError("workflow attempt materialization idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow attempt materialization request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow attempt materialization time must be timezone-aware")

    @classmethod
    def _attempt_materialization_sources_match(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        lease_row: WorkflowOrchestrationLeaseModel | None,
        run_row: WorkflowExecutionRunModel | None,
        step_row: WorkflowExecutionStepRunModel | None,
        request: WorkflowAttemptMaterializationRequest,
    ) -> bool:
        if plan_row is None or lease_row is None or run_row is None or step_row is None:
            return False
        attempt = request.candidate
        try:
            run = cls._materialized_run_from_row(run_row)
            step = cls._materialized_step_from_row(step_row)
        except (WorkflowAttemptMaterializationError, WorkflowPlanningError) as exc:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_materialization_repository_contract_violation",
                "Workflow run evidence is inconsistent during attempt materialization.",
            ) from exc
        return bool(
            plan_row.plan_id == attempt.plan_id
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == attempt.plan_digest
            and plan_row.definition_id == attempt.definition_id
            and plan_row.definition_version == attempt.definition_version
            and plan_row.definition_digest == attempt.definition_digest
            and plan_row.organization_id == attempt.scope.organization_id
            and plan_row.environment_id == attempt.scope.environment_id
            and plan_row.site_id == attempt.scope.site_id
            and plan_row.target_type == attempt.target_type
            and plan_row.target_id == attempt.target_id
            and run.run_id == attempt.run_id
            and run.canonical_digest == request.expected_run_digest == attempt.run_digest
            and run.plan_id == attempt.plan_id
            and run.plan_digest == attempt.plan_digest
            and run.definition_id == attempt.definition_id
            and run.definition_version == attempt.definition_version
            and run.definition_digest == attempt.definition_digest
            and run.scope == attempt.scope
            and run.target_type == attempt.target_type
            and run.target_id == attempt.target_id
            and run.lease_id == attempt.lease_id
            and run.fencing_token == attempt.fencing_token
            and run.materialized_by_subject_id == attempt.materialized_by_subject_id
            and run.state is WorkflowExecutionRunState.CREATED
            and not run.grants_execution_authority
            and step in run.step_runs
            and step.step_run_id == attempt.step_run_id
            and step.canonical_digest == request.expected_step_run_digest == attempt.step_run_digest
            and step.run_id == attempt.run_id
            and step.step_id == attempt.step_id
            and step.state is WorkflowExecutionStepRunState.NOT_STARTED
            and not step.depends_on
            and lease_row.plan_id == attempt.plan_id
            and lease_row.plan_digest == attempt.plan_digest
            and lease_row.organization_id == attempt.scope.organization_id
            and lease_row.environment_id == attempt.scope.environment_id
            and lease_row.site_id == attempt.scope.site_id
            and lease_row.target_type == attempt.target_type
            and lease_row.target_id == attempt.target_id
            and lease_row.lease_id == request.expected_lease_id == attempt.lease_id
            and lease_row.canonical_digest == request.expected_lease_digest == attempt.lease_digest
            and lease_row.fencing_token == request.expected_fencing_token == attempt.fencing_token
            and lease_row.worker_subject_id
            == request.worker_subject_id
            == attempt.materialized_by_subject_id
            and lease_row.state == WorkflowOrchestrationLeaseState.ACTIVE.value
            and lease_row.expires_at > request.requested_at
        )

    @staticmethod
    def _attempt_materialization_scope_id(attempt: WorkflowExecutionAttempt) -> str:
        return canonical_digest(
            {
                "scope": attempt.scope.canonical_value(),
                "worker_subject_id": attempt.materialized_by_subject_id,
            }
        )

    @staticmethod
    def _attempt_payload(attempt: WorkflowExecutionAttempt) -> dict[str, Any]:
        return cast(dict[str, Any], attempt.canonical_value())

    @staticmethod
    def _attempt_to_domain(raw: dict[str, Any]) -> WorkflowExecutionAttempt:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["state"] = WorkflowExecutionAttemptState(str(payload["state"]))
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowExecutionAttempt(**cast(Any, payload))

    @staticmethod
    def _materialized_step_from_row(
        row: WorkflowExecutionStepRunModel,
    ) -> WorkflowExecutionStepRun:
        try:
            raw = row.payload
            step = WorkflowExecutionStepRun(
                step_run_id=str(raw["step_run_id"]),
                run_id=str(raw["run_id"]),
                step_id=str(raw["step_id"]),
                ordinal=int(raw["ordinal"]),
                kind=WorkflowStepKind(str(raw["kind"])),
                capability_class=WorkflowCapabilityClass(str(raw["capability_class"])),
                timeout_seconds=int(raw["timeout_seconds"]),
                depends_on=tuple(str(value) for value in raw["depends_on"]),
                state=WorkflowExecutionStepRunState(str(raw["state"])),
                canonical_digest=str(raw["canonical_digest"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_materialization_repository_contract_violation",
                "The workflow step-run repository contains invalid materialization evidence.",
            ) from exc
        if (
            row.step_run_id != step.step_run_id
            or row.run_id != step.run_id
            or row.step_id != step.step_id
            or row.ordinal != step.ordinal
            or row.kind != step.kind.value
            or row.capability_class != step.capability_class.value
            or row.timeout_seconds != step.timeout_seconds
            or row.depends_on != list(step.depends_on)
            or row.state != step.state.value
            or row.canonical_digest != step.canonical_digest
        ):
            PostgreSQLWorkflowPlanRepository._attempt_contract_violation()
        return step

    @staticmethod
    def _attempt_contract_violation() -> None:
        raise WorkflowAttemptMaterializationError(
            "workflow_attempt_materialization_repository_contract_violation",
            "The workflow attempt materialization record does not match its canonical payload.",
        )

    async def _dispatch_intent_staging_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowDispatchIntentStagingRequest,
    ) -> WorkflowDispatchIntentStagingResult | None:
        intent = request.candidate
        claim = cast(
            WorkflowDispatchIntentStagingClaimModel | None,
            await session.scalar(
                select(WorkflowDispatchIntentStagingClaimModel).where(
                    WorkflowDispatchIntentStagingClaimModel.idempotency_scope_id
                    == self._dispatch_intent_staging_scope_id(intent),
                    WorkflowDispatchIntentStagingClaimModel.idempotency_key
                    == request.idempotency_key,
                    WorkflowDispatchIntentStagingClaimModel.organization_id
                    == intent.scope.organization_id,
                    WorkflowDispatchIntentStagingClaimModel.environment_id
                    == intent.scope.environment_id,
                    WorkflowDispatchIntentStagingClaimModel.site_id == intent.scope.site_id,
                    WorkflowDispatchIntentStagingClaimModel.worker_subject_id
                    == intent.worker_subject_id,
                )
            ),
        )
        if claim is None:
            return None
        intent, outbox_entry = self._dispatch_pair_from_claim(claim)
        status = (
            WorkflowDispatchIntentStagingStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowDispatchIntentStagingStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowDispatchIntentStagingResult(
            status=status,
            dispatch_intent=intent,
            outbox_entry=outbox_entry,
        )

    @classmethod
    async def _load_dispatch_intent_staging_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchIntentStagingClaimModel | None:
        scope_id = canonical_digest(
            {
                "scope": scope.canonical_value(),
                "worker_subject_id": worker_subject_id,
            }
        )
        return cast(
            WorkflowDispatchIntentStagingClaimModel | None,
            await session.scalar(
                select(WorkflowDispatchIntentStagingClaimModel).where(
                    WorkflowDispatchIntentStagingClaimModel.idempotency_scope_id == scope_id,
                    WorkflowDispatchIntentStagingClaimModel.idempotency_key == idempotency_key,
                    WorkflowDispatchIntentStagingClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowDispatchIntentStagingClaimModel.environment_id == scope.environment_id,
                    WorkflowDispatchIntentStagingClaimModel.site_id == scope.site_id,
                    WorkflowDispatchIntentStagingClaimModel.worker_subject_id == worker_subject_id,
                )
            ),
        )

    @classmethod
    def _dispatch_intent_from_row(cls, row: WorkflowDispatchIntentModel) -> WorkflowDispatchIntent:
        try:
            intent = cls._dispatch_intent_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_repository_contract_violation",
                "The workflow dispatch-intent repository contains an invalid intent.",
            ) from exc
        if (
            row.dispatch_intent_id != intent.dispatch_intent_id
            or row.plan_id != intent.plan_id
            or row.plan_digest != intent.plan_digest
            or row.run_id != intent.run_id
            or row.run_digest != intent.run_digest
            or row.step_run_id != intent.step_run_id
            or row.step_run_digest != intent.step_run_digest
            or row.step_id != intent.step_id
            or row.attempt_id != intent.attempt_id
            or row.attempt_digest != intent.attempt_digest
            or row.attempt_number != intent.attempt_number
            or row.organization_id != intent.scope.organization_id
            or row.environment_id != intent.scope.environment_id
            or row.site_id != intent.scope.site_id
            or row.target_type != intent.target_type
            or row.target_id != intent.target_id
            or row.lease_id != intent.lease_id
            or row.lease_digest != intent.lease_digest
            or row.lease_fencing_token != intent.fencing_token
            or row.worker_subject_id != intent.worker_subject_id
            or row.staged_at != intent.staged_at
            or row.state != intent.state.value
            or row.canonical_digest != intent.canonical_digest
        ):
            cls._dispatch_intent_contract_violation()
        return intent

    @classmethod
    def _dispatch_intent_from_claim(
        cls, claim: WorkflowDispatchIntentStagingClaimModel
    ) -> WorkflowDispatchIntent:
        return cls._dispatch_pair_from_claim(claim)[0]

    @classmethod
    def _dispatch_pair_from_claim(
        cls, claim: WorkflowDispatchIntentStagingClaimModel
    ) -> tuple[WorkflowDispatchIntent, WorkflowDispatchOutboxEntry]:
        raw = claim.payload.get("result_dispatch_intent")
        raw_outbox = claim.payload.get("result_outbox_entry")
        if not isinstance(raw, dict) or not isinstance(raw_outbox, dict):
            cls._dispatch_intent_contract_violation()
        try:
            intent = cls._dispatch_intent_to_domain(cast(dict[str, Any], raw))
            outbox_entry = cls._dispatch_outbox_to_domain(cast(dict[str, Any], raw_outbox))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_repository_contract_violation",
                "The dispatch-intent repository contains an invalid idempotency result.",
            ) from exc
        intent_payload = cls._dispatch_intent_payload(intent)
        outbox_payload = cls._dispatch_outbox_payload(outbox_entry)
        scope_id = cls._dispatch_intent_staging_scope_id(intent)
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_dispatch_intent": intent_payload,
            "result_digest": intent.canonical_digest,
            "result_outbox_digest": outbox_entry.canonical_digest,
            "result_outbox_entry": outbox_payload,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != intent.canonical_digest
            or claim.result_outbox_digest != outbox_entry.canonical_digest
            or claim.dispatch_intent_id != intent.dispatch_intent_id
            or claim.outbox_entry_id != outbox_entry.outbox_entry_id
            or claim.attempt_id != intent.attempt_id
            or claim.run_id != intent.run_id
            or claim.plan_id != intent.plan_id
            or claim.organization_id != intent.scope.organization_id
            or claim.environment_id != intent.scope.environment_id
            or claim.site_id != intent.scope.site_id
            or claim.worker_subject_id != intent.worker_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
            or not cls._dispatch_outbox_matches_intent(outbox_entry, intent)
        ):
            cls._dispatch_intent_contract_violation()
        return intent, outbox_entry

    @classmethod
    def _dispatch_intent_model(cls, intent: WorkflowDispatchIntent) -> WorkflowDispatchIntentModel:
        return WorkflowDispatchIntentModel(
            dispatch_intent_id=intent.dispatch_intent_id,
            plan_id=intent.plan_id,
            plan_digest=intent.plan_digest,
            run_id=intent.run_id,
            run_digest=intent.run_digest,
            step_run_id=intent.step_run_id,
            step_run_digest=intent.step_run_digest,
            step_id=intent.step_id,
            attempt_id=intent.attempt_id,
            attempt_digest=intent.attempt_digest,
            attempt_number=intent.attempt_number,
            organization_id=intent.scope.organization_id,
            environment_id=intent.scope.environment_id,
            site_id=intent.scope.site_id,
            target_type=intent.target_type,
            target_id=intent.target_id,
            lease_id=intent.lease_id,
            lease_digest=intent.lease_digest,
            lease_fencing_token=intent.fencing_token,
            worker_subject_id=intent.worker_subject_id,
            staged_at=intent.staged_at,
            state=intent.state.value,
            canonical_digest=intent.canonical_digest,
            payload=cls._dispatch_intent_payload(intent),
        )

    @classmethod
    def _dispatch_outbox_model(
        cls, entry: WorkflowDispatchOutboxEntry
    ) -> WorkflowDispatchOutboxEntryModel:
        return WorkflowDispatchOutboxEntryModel(
            outbox_entry_id=entry.outbox_entry_id,
            dispatch_intent_id=entry.dispatch_intent_id,
            dispatch_intent_digest=entry.dispatch_intent_digest,
            plan_id=entry.plan_id,
            plan_digest=entry.plan_digest,
            run_id=entry.run_id,
            run_digest=entry.run_digest,
            step_run_id=entry.step_run_id,
            step_run_digest=entry.step_run_digest,
            step_id=entry.step_id,
            attempt_id=entry.attempt_id,
            attempt_digest=entry.attempt_digest,
            attempt_number=entry.attempt_number,
            organization_id=entry.scope.organization_id,
            environment_id=entry.scope.environment_id,
            site_id=entry.scope.site_id,
            target_type=entry.target_type,
            target_id=entry.target_id,
            lease_id=entry.lease_id,
            lease_digest=entry.lease_digest,
            lease_fencing_token=entry.fencing_token,
            worker_subject_id=entry.worker_subject_id,
            admitted_at=entry.admitted_at,
            state=entry.state.value,
            publication_authority_granted=entry.grants_publication_authority,
            delivery_authority_granted=entry.grants_delivery_authority,
            dispatch_authority_granted=entry.grants_dispatch_authority,
            execution_authority_granted=entry.grants_execution_authority,
            canonical_digest=entry.canonical_digest,
            payload=cls._dispatch_outbox_payload(entry),
        )

    @classmethod
    def _dispatch_outbox_from_row(
        cls, row: WorkflowDispatchOutboxEntryModel
    ) -> WorkflowDispatchOutboxEntry:
        try:
            entry = cls._dispatch_outbox_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_outbox_repository_contract_violation",
                "The workflow dispatch outbox repository contains an invalid entry.",
            ) from exc
        if (
            row.outbox_entry_id != entry.outbox_entry_id
            or row.dispatch_intent_id != entry.dispatch_intent_id
            or row.dispatch_intent_digest != entry.dispatch_intent_digest
            or row.plan_id != entry.plan_id
            or row.plan_digest != entry.plan_digest
            or row.run_id != entry.run_id
            or row.run_digest != entry.run_digest
            or row.step_run_id != entry.step_run_id
            or row.step_run_digest != entry.step_run_digest
            or row.step_id != entry.step_id
            or row.attempt_id != entry.attempt_id
            or row.attempt_digest != entry.attempt_digest
            or row.attempt_number != entry.attempt_number
            or row.organization_id != entry.scope.organization_id
            or row.environment_id != entry.scope.environment_id
            or row.site_id != entry.scope.site_id
            or row.target_type != entry.target_type
            or row.target_id != entry.target_id
            or row.lease_id != entry.lease_id
            or row.lease_digest != entry.lease_digest
            or row.lease_fencing_token != entry.fencing_token
            or row.worker_subject_id != entry.worker_subject_id
            or row.admitted_at != entry.admitted_at
            or row.state != entry.state.value
            or row.publication_authority_granted != entry.grants_publication_authority
            or row.delivery_authority_granted != entry.grants_delivery_authority
            or row.dispatch_authority_granted != entry.grants_dispatch_authority
            or row.execution_authority_granted != entry.grants_execution_authority
            or row.canonical_digest != entry.canonical_digest
        ):
            cls._dispatch_outbox_contract_violation()
        return entry

    @classmethod
    def _dispatch_intent_staging_claim_model(
        cls, request: WorkflowDispatchIntentStagingRequest
    ) -> WorkflowDispatchIntentStagingClaimModel:
        intent = request.candidate
        outbox_entry = request.outbox_entry
        if outbox_entry is None:
            raise ValueError("workflow dispatch outbox entry is required")
        scope_id = cls._dispatch_intent_staging_scope_id(intent)
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_dispatch_intent": cls._dispatch_intent_payload(intent),
            "result_digest": intent.canonical_digest,
            "result_outbox_digest": outbox_entry.canonical_digest,
            "result_outbox_entry": cls._dispatch_outbox_payload(outbox_entry),
        }
        digest = canonical_digest(payload)
        return WorkflowDispatchIntentStagingClaimModel(
            claim_id=f"workflow_dispatch_intent_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=intent.canonical_digest,
            result_outbox_digest=outbox_entry.canonical_digest,
            dispatch_intent_id=intent.dispatch_intent_id,
            outbox_entry_id=outbox_entry.outbox_entry_id,
            attempt_id=intent.attempt_id,
            run_id=intent.run_id,
            plan_id=intent.plan_id,
            organization_id=intent.scope.organization_id,
            environment_id=intent.scope.environment_id,
            site_id=intent.scope.site_id,
            worker_subject_id=intent.worker_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _validate_dispatch_intent_staging_request(
        cls, request: WorkflowDispatchIntentStagingRequest
    ) -> None:
        intent = request.candidate
        outbox_entry = request.outbox_entry
        if outbox_entry is None:
            raise ValueError("workflow dispatch outbox entry is required")
        if (
            intent.state is not WorkflowDispatchIntentState.STAGED
            or intent.attempt_number != 1
            or intent.grants_dispatch_authority
            or intent.grants_execution_authority
            or outbox_entry.state is not WorkflowDispatchOutboxState.PENDING_PUBLICATION
            or outbox_entry.grants_publication_authority
            or outbox_entry.grants_delivery_authority
            or outbox_entry.grants_dispatch_authority
            or outbox_entry.grants_execution_authority
            or not cls._dispatch_outbox_matches_intent(outbox_entry, intent)
        ):
            raise ValueError("workflow dispatch-intent staging payload is unsafe")
        if len(request.idempotency_key) > 128 or not request.idempotency_key:
            raise ValueError("workflow dispatch-intent idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow dispatch-intent request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow dispatch-intent staging time must be timezone-aware")

    @classmethod
    def _dispatch_intent_sources_match(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        lease_row: WorkflowOrchestrationLeaseModel | None,
        run_row: WorkflowExecutionRunModel | None,
        step_row: WorkflowExecutionStepRunModel | None,
        attempt_row: WorkflowExecutionAttemptModel | None,
        request: WorkflowDispatchIntentStagingRequest,
    ) -> bool:
        if any(item is None for item in (plan_row, lease_row, run_row, step_row, attempt_row)):
            return False
        assert plan_row is not None
        assert lease_row is not None
        assert run_row is not None
        assert step_row is not None
        assert attempt_row is not None
        intent = request.candidate
        try:
            run = cls._materialized_run_from_row(run_row)
            step = cls._materialized_step_from_row(step_row)
            attempt = cls._attempt_from_row(attempt_row)
        except (
            WorkflowAttemptMaterializationError,
            WorkflowPlanningError,
        ) as exc:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_repository_contract_violation",
                "Workflow execution evidence is inconsistent during dispatch-intent staging.",
            ) from exc
        return bool(
            plan_row.plan_id == intent.plan_id
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == intent.plan_digest
            and plan_row.organization_id == intent.scope.organization_id
            and plan_row.environment_id == intent.scope.environment_id
            and plan_row.site_id == intent.scope.site_id
            and plan_row.target_type == intent.target_type
            and plan_row.target_id == intent.target_id
            and run.run_id == intent.run_id
            and run.canonical_digest == request.expected_run_digest == intent.run_digest
            and run.plan_id == intent.plan_id
            and run.plan_digest == intent.plan_digest
            and run.scope == intent.scope
            and run.target_type == intent.target_type
            and run.target_id == intent.target_id
            and run.lease_id == intent.lease_id
            and run.fencing_token == intent.fencing_token
            and run.materialized_by_subject_id == intent.worker_subject_id
            and run.state is WorkflowExecutionRunState.CREATED
            and not run.grants_execution_authority
            and step in run.step_runs
            and step.step_run_id == intent.step_run_id
            and step.canonical_digest == request.expected_step_run_digest == intent.step_run_digest
            and step.run_id == intent.run_id
            and step.step_id == intent.step_id
            and step.state is WorkflowExecutionStepRunState.NOT_STARTED
            and not step.depends_on
            and attempt.attempt_id == intent.attempt_id
            and attempt.canonical_digest == request.expected_attempt_digest == intent.attempt_digest
            and attempt.run_id == intent.run_id
            and attempt.run_digest == intent.run_digest
            and attempt.step_run_id == intent.step_run_id
            and attempt.step_run_digest == intent.step_run_digest
            and attempt.step_id == intent.step_id
            and attempt.attempt_number == intent.attempt_number == 1
            and attempt.plan_id == intent.plan_id
            and attempt.plan_digest == intent.plan_digest
            and attempt.scope == intent.scope
            and attempt.target_type == intent.target_type
            and attempt.target_id == intent.target_id
            and attempt.lease_id == intent.lease_id
            and attempt.fencing_token == intent.fencing_token
            and attempt.materialized_by_subject_id == intent.worker_subject_id
            and attempt.state is WorkflowExecutionAttemptState.CREATED
            and not attempt.grants_execution_authority
            and lease_row.plan_id == intent.plan_id
            and lease_row.plan_digest == intent.plan_digest
            and lease_row.organization_id == intent.scope.organization_id
            and lease_row.environment_id == intent.scope.environment_id
            and lease_row.site_id == intent.scope.site_id
            and lease_row.target_type == intent.target_type
            and lease_row.target_id == intent.target_id
            and lease_row.lease_id == request.expected_lease_id == intent.lease_id
            and lease_row.canonical_digest == request.expected_lease_digest == intent.lease_digest
            and lease_row.fencing_token == request.expected_fencing_token == intent.fencing_token
            and lease_row.worker_subject_id == request.worker_subject_id == intent.worker_subject_id
            and lease_row.state == WorkflowOrchestrationLeaseState.ACTIVE.value
            and lease_row.expires_at > request.requested_at
        )

    @staticmethod
    def _dispatch_intent_staging_scope_id(intent: WorkflowDispatchIntent) -> str:
        return canonical_digest(
            {
                "scope": intent.scope.canonical_value(),
                "worker_subject_id": intent.worker_subject_id,
            }
        )

    @staticmethod
    def _dispatch_intent_payload(intent: WorkflowDispatchIntent) -> dict[str, Any]:
        return cast(dict[str, Any], intent.canonical_value())

    @staticmethod
    def _dispatch_intent_to_domain(raw: dict[str, Any]) -> WorkflowDispatchIntent:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["staged_at"] = datetime.fromisoformat(str(payload["staged_at"]))
        payload["state"] = WorkflowDispatchIntentState(str(payload["state"]))
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowDispatchIntent(**cast(Any, payload))

    @staticmethod
    def _dispatch_outbox_payload(entry: WorkflowDispatchOutboxEntry) -> dict[str, Any]:
        return cast(dict[str, Any], entry.canonical_value())

    @staticmethod
    def _dispatch_outbox_to_domain(raw: dict[str, Any]) -> WorkflowDispatchOutboxEntry:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["admitted_at"] = datetime.fromisoformat(str(payload["admitted_at"]))
        payload["state"] = WorkflowDispatchOutboxState(str(payload["state"]))
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowDispatchOutboxEntry(**cast(Any, payload))

    @staticmethod
    def _dispatch_outbox_matches_intent(
        entry: WorkflowDispatchOutboxEntry,
        intent: WorkflowDispatchIntent,
    ) -> bool:
        return bool(
            entry.dispatch_intent_id == intent.dispatch_intent_id
            and entry.dispatch_intent_digest == intent.canonical_digest
            and entry.plan_id == intent.plan_id
            and entry.plan_digest == intent.plan_digest
            and entry.run_id == intent.run_id
            and entry.run_digest == intent.run_digest
            and entry.step_run_id == intent.step_run_id
            and entry.step_run_digest == intent.step_run_digest
            and entry.step_id == intent.step_id
            and entry.attempt_id == intent.attempt_id
            and entry.attempt_digest == intent.attempt_digest
            and entry.attempt_number == intent.attempt_number
            and entry.scope == intent.scope
            and entry.target_id == intent.target_id
            and entry.target_type == intent.target_type
            and entry.lease_id == intent.lease_id
            and entry.lease_digest == intent.lease_digest
            and entry.fencing_token == intent.fencing_token
            and entry.worker_subject_id == intent.worker_subject_id
            and entry.admitted_at == intent.staged_at
        )

    @staticmethod
    def _dispatch_outbox_contract_violation() -> None:
        raise WorkflowDispatchIntentStagingError(
            "workflow_dispatch_outbox_repository_contract_violation",
            "The workflow dispatch outbox entry does not match its canonical payload.",
        )

    @staticmethod
    def _dispatch_intent_contract_violation() -> None:
        raise WorkflowDispatchIntentStagingError(
            "workflow_dispatch_intent_repository_contract_violation",
            "The workflow dispatch-intent record does not match its canonical payload.",
        )

    async def _dispatch_event_envelope_preparation_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> WorkflowDispatchEventEnvelopePrepareResult | None:
        envelope = request.candidate
        claim = await self._load_dispatch_event_envelope_claim(
            session,
            scope=envelope.payload.scope,
            publisher_subject_id=envelope.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        record = self._dispatch_event_envelope_record_from_claim(claim)
        status = (
            WorkflowDispatchEventEnvelopePrepareStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowDispatchEventEnvelopePrepareStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowDispatchEventEnvelopePrepareResult(status, record.envelope)

    @classmethod
    async def _load_dispatch_event_envelope_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchEventEnvelopePreparationClaimModel | None:
        scope_id = cls._dispatch_event_envelope_idempotency_scope(
            scope,
            publisher_subject_id,
        )
        return cast(
            WorkflowDispatchEventEnvelopePreparationClaimModel | None,
            await session.scalar(
                select(WorkflowDispatchEventEnvelopePreparationClaimModel).where(
                    WorkflowDispatchEventEnvelopePreparationClaimModel.idempotency_scope_id
                    == scope_id,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.site_id == scope.site_id,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _dispatch_event_envelope_record_from_claim(
        cls,
        claim: WorkflowDispatchEventEnvelopePreparationClaimModel,
    ) -> WorkflowDispatchEventEnvelopePrepareIdempotencyRecord:
        raw = claim.payload.get("result_envelope")
        if not isinstance(raw, dict):
            cls._dispatch_event_envelope_contract_violation()
        try:
            envelope = cls._dispatch_event_envelope_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchEventEnvelopeError(
                "workflow_dispatch_event_envelope_repository_contract_violation",
                "The dispatch-event envelope repository contains an invalid idempotency result.",
            ) from exc
        scope_id = cls._dispatch_event_envelope_idempotency_scope(
            envelope.payload.scope,
            envelope.publisher_subject_id,
        )
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": envelope.canonical_digest,
            "result_envelope": cls._dispatch_event_envelope_payload(envelope),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != envelope.canonical_digest
            or claim.event_id != envelope.event_id
            or claim.outbox_entry_id != envelope.payload.outbox_entry_id
            or claim.plan_id != envelope.payload.plan_id
            or claim.organization_id != envelope.payload.scope.organization_id
            or claim.environment_id != envelope.payload.scope.environment_id
            or claim.site_id != envelope.payload.scope.site_id
            or claim.publisher_subject_id != envelope.publisher_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._dispatch_event_envelope_contract_violation()
        return WorkflowDispatchEventEnvelopePrepareIdempotencyRecord(
            claim.request_fingerprint,
            envelope,
        )

    @classmethod
    def _dispatch_event_envelope_from_row(
        cls,
        row: WorkflowDispatchEventEnvelopeModel,
    ) -> WorkflowDispatchEventEnvelope:
        try:
            envelope = cls._dispatch_event_envelope_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchEventEnvelopeError(
                "workflow_dispatch_event_envelope_repository_contract_violation",
                "The dispatch-event envelope repository contains an invalid envelope.",
            ) from exc
        payload = envelope.payload
        if (
            row.event_id != envelope.event_id
            or row.event_type != envelope.event_type
            or row.event_version != envelope.event_version
            or row.occurred_at != envelope.occurred_at
            or row.recorded_at != envelope.recorded_at
            or row.producer != envelope.producer
            or row.producer_version != envelope.producer_version
            or row.subject_type != envelope.subject_type
            or row.subject_id != envelope.subject_id
            or row.organization_id != envelope.organization_id
            or row.environment_id != envelope.environment_id
            or row.site_id != payload.scope.site_id
            or row.correlation_id != envelope.correlation_id
            or row.causation_id != envelope.causation_id
            or row.workflow_id != envelope.workflow_id
            or row.data_classification != envelope.data_classification
            or row.schema_uri != envelope.schema_uri
            or row.outbox_entry_id != payload.outbox_entry_id
            or row.outbox_entry_digest != payload.outbox_entry_digest
            or row.dispatch_intent_id != payload.dispatch_intent_id
            or row.dispatch_intent_digest != payload.dispatch_intent_digest
            or row.plan_id != payload.plan_id
            or row.plan_digest != payload.plan_digest
            or row.run_id != payload.run_id
            or row.run_digest != payload.run_digest
            or row.step_run_id != payload.step_run_id
            or row.step_run_digest != payload.step_run_digest
            or row.step_id != payload.step_id
            or row.attempt_id != payload.attempt_id
            or row.attempt_digest != payload.attempt_digest
            or row.attempt_number != payload.attempt_number
            or row.target_type != payload.target_type
            or row.target_id != payload.target_id
            or row.orchestration_lease_id != envelope.orchestration_lease_id
            or row.orchestration_lease_digest != envelope.orchestration_lease_digest
            or row.orchestration_fencing_token != envelope.orchestration_fencing_token
            or row.publication_lease_id != envelope.publication_lease_id
            or row.publication_lease_digest != envelope.publication_lease_digest
            or row.publication_fencing_token != envelope.publication_fencing_token
            or row.publisher_subject_id != envelope.publisher_subject_id
            or row.prepared_at != envelope.prepared_at
            or row.state != envelope.state.value
            or row.publication_authority_granted != envelope.grants_publication_authority
            or row.delivery_authority_granted != envelope.grants_delivery_authority
            or row.dispatch_authority_granted != envelope.grants_dispatch_authority
            or row.execution_authority_granted != envelope.grants_execution_authority
            or row.canonical_digest != envelope.canonical_digest
        ):
            cls._dispatch_event_envelope_contract_violation()
        return envelope

    @classmethod
    def _dispatch_event_envelope_model(
        cls,
        envelope: WorkflowDispatchEventEnvelope,
    ) -> WorkflowDispatchEventEnvelopeModel:
        payload = envelope.payload
        return WorkflowDispatchEventEnvelopeModel(
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            event_version=envelope.event_version,
            occurred_at=envelope.occurred_at,
            recorded_at=envelope.recorded_at,
            producer=envelope.producer,
            producer_version=envelope.producer_version,
            subject_type=envelope.subject_type,
            subject_id=envelope.subject_id,
            organization_id=envelope.organization_id,
            environment_id=envelope.environment_id,
            site_id=payload.scope.site_id,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            workflow_id=envelope.workflow_id,
            data_classification=envelope.data_classification,
            schema_uri=envelope.schema_uri,
            outbox_entry_id=payload.outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            dispatch_intent_id=payload.dispatch_intent_id,
            dispatch_intent_digest=payload.dispatch_intent_digest,
            plan_id=payload.plan_id,
            plan_digest=payload.plan_digest,
            run_id=payload.run_id,
            run_digest=payload.run_digest,
            step_run_id=payload.step_run_id,
            step_run_digest=payload.step_run_digest,
            step_id=payload.step_id,
            attempt_id=payload.attempt_id,
            attempt_digest=payload.attempt_digest,
            attempt_number=payload.attempt_number,
            target_type=payload.target_type,
            target_id=payload.target_id,
            orchestration_lease_id=envelope.orchestration_lease_id,
            orchestration_lease_digest=envelope.orchestration_lease_digest,
            orchestration_fencing_token=envelope.orchestration_fencing_token,
            publication_lease_id=envelope.publication_lease_id,
            publication_lease_digest=envelope.publication_lease_digest,
            publication_fencing_token=envelope.publication_fencing_token,
            publisher_subject_id=envelope.publisher_subject_id,
            prepared_at=envelope.prepared_at,
            state=envelope.state.value,
            publication_authority_granted=envelope.grants_publication_authority,
            delivery_authority_granted=envelope.grants_delivery_authority,
            dispatch_authority_granted=envelope.grants_dispatch_authority,
            execution_authority_granted=envelope.grants_execution_authority,
            canonical_digest=envelope.canonical_digest,
            payload=cls._dispatch_event_envelope_payload(envelope),
        )

    @classmethod
    def _dispatch_event_envelope_claim_model(
        cls,
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> WorkflowDispatchEventEnvelopePreparationClaimModel:
        envelope = request.candidate
        scope = envelope.payload.scope
        scope_id = cls._dispatch_event_envelope_idempotency_scope(
            scope,
            envelope.publisher_subject_id,
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": envelope.canonical_digest,
            "result_envelope": cls._dispatch_event_envelope_payload(envelope),
        }
        digest = canonical_digest(payload)
        return WorkflowDispatchEventEnvelopePreparationClaimModel(
            claim_id=f"workflow_dispatch_event_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=envelope.canonical_digest,
            event_id=envelope.event_id,
            outbox_entry_id=envelope.payload.outbox_entry_id,
            plan_id=envelope.payload.plan_id,
            organization_id=scope.organization_id,
            environment_id=scope.environment_id,
            site_id=scope.site_id,
            publisher_subject_id=envelope.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _dispatch_event_envelope_evidence_matches(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        publication_lease_row: WorkflowOutboxPublicationLeaseModel | None,
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> bool:
        if any(
            item is None
            for item in (
                plan_row,
                outbox_row,
                orchestration_lease_row,
                publication_lease_row,
            )
        ):
            return False
        assert plan_row is not None
        assert outbox_row is not None
        assert orchestration_lease_row is not None
        assert publication_lease_row is not None
        candidate = request.candidate
        payload = candidate.payload
        try:
            outbox = cls._dispatch_outbox_from_row(outbox_row)
            orchestration_lease = cls._lease_from_row(orchestration_lease_row)
            publication_lease = cls._publication_lease_from_row(publication_lease_row)
        except (
            WorkflowDispatchIntentStagingError,
            WorkflowOrchestrationLeaseError,
            WorkflowOutboxPublicationLeaseError,
        ) as exc:
            raise WorkflowDispatchEventEnvelopeError(
                "workflow_dispatch_event_envelope_repository_contract_violation",
                "Workflow evidence is inconsistent during event-envelope preparation.",
            ) from exc
        return bool(
            plan_row.plan_id == payload.plan_id
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == payload.plan_digest
            and plan_row.organization_id == payload.scope.organization_id
            and plan_row.environment_id == payload.scope.environment_id
            and plan_row.site_id == payload.scope.site_id
            and plan_row.target_type == payload.target_type
            and plan_row.target_id == payload.target_id
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == payload.outbox_entry_digest
            and outbox.outbox_entry_id == payload.outbox_entry_id
            and outbox.dispatch_intent_id == payload.dispatch_intent_id
            and outbox.dispatch_intent_digest == payload.dispatch_intent_digest
            and outbox.plan_id == payload.plan_id
            and outbox.plan_digest == payload.plan_digest
            and outbox.run_id == payload.run_id
            and outbox.run_digest == payload.run_digest
            and outbox.step_run_id == payload.step_run_id
            and outbox.step_run_digest == payload.step_run_digest
            and outbox.step_id == payload.step_id
            and outbox.attempt_id == payload.attempt_id
            and outbox.attempt_digest == payload.attempt_digest
            and outbox.attempt_number == payload.attempt_number == 1
            and outbox.scope == payload.scope
            and outbox.target_id == payload.target_id
            and outbox.target_type == payload.target_type
            and not any(outbox.authority.canonical_value().values())
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
            and orchestration_lease.plan_id == payload.plan_id
            and orchestration_lease.plan_digest == payload.plan_digest
            and orchestration_lease.scope == payload.scope
            and orchestration_lease.target_id == payload.target_id
            and orchestration_lease.target_type == payload.target_type
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and publication_lease.publication_lease_id
            == request.expected_publication_lease_id
            == candidate.publication_lease_id
            and publication_lease.canonical_digest
            == request.expected_publication_lease_digest
            == candidate.publication_lease_digest
            and publication_lease.publication_fencing_token
            == request.expected_publication_fencing_token
            == candidate.publication_fencing_token
            and publication_lease.outbox_entry_id == payload.outbox_entry_id
            and publication_lease.outbox_entry_digest == payload.outbox_entry_digest
            and publication_lease.dispatch_intent_id == payload.dispatch_intent_id
            and publication_lease.dispatch_intent_digest == payload.dispatch_intent_digest
            and publication_lease.plan_id == payload.plan_id
            and publication_lease.plan_digest == payload.plan_digest
            and publication_lease.run_id == payload.run_id
            and publication_lease.run_digest == payload.run_digest
            and publication_lease.step_run_id == payload.step_run_id
            and publication_lease.step_run_digest == payload.step_run_digest
            and publication_lease.step_id == payload.step_id
            and publication_lease.attempt_id == payload.attempt_id
            and publication_lease.attempt_digest == payload.attempt_digest
            and publication_lease.attempt_number == payload.attempt_number
            and publication_lease.scope == payload.scope
            and publication_lease.target_id == payload.target_id
            and publication_lease.target_type == payload.target_type
            and publication_lease.orchestration_lease_id == candidate.orchestration_lease_id
            and publication_lease.orchestration_lease_digest == candidate.orchestration_lease_digest
            and publication_lease.orchestration_fencing_token
            == candidate.orchestration_fencing_token
            and publication_lease.publisher_subject_id == candidate.publisher_subject_id
            and publication_lease.publisher_subject_id == request.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _dispatch_event_envelope_idempotency_scope(
        scope: WorkflowScope,
        publisher_subject_id: str,
    ) -> str:
        return canonical_digest(
            {
                "publisher_subject_id": publisher_subject_id,
                "scope": scope.canonical_value(),
            }
        )

    @staticmethod
    def _dispatch_event_envelope_payload(
        envelope: WorkflowDispatchEventEnvelope,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], envelope.canonical_value())

    @staticmethod
    def _dispatch_event_envelope_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowDispatchEventEnvelope:
        values = dict(raw)
        event_payload = dict(cast(dict[str, Any], values["payload"]))
        event_payload["scope"] = WorkflowScope(**cast(Any, event_payload["scope"]))
        values["payload"] = WorkflowDispatchEventPayload(**cast(Any, event_payload))
        values["occurred_at"] = datetime.fromisoformat(str(values["occurred_at"]))
        values["recorded_at"] = datetime.fromisoformat(str(values["recorded_at"]))
        values["prepared_at"] = datetime.fromisoformat(str(values["prepared_at"]))
        values["extensions"] = tuple(sorted(cast(dict[str, str], values["extensions"]).items()))
        values["state"] = WorkflowDispatchEventEnvelopeState(str(values["state"]))
        values["authority"] = WorkflowDispatchEventAuthority(**cast(Any, values["authority"]))
        return WorkflowDispatchEventEnvelope(**cast(Any, values))

    @staticmethod
    def _validate_dispatch_event_envelope_preparation_request(
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowDispatchEventEnvelopeState.PREPARED
            or candidate.payload.attempt_number != 1
            or candidate.publisher_subject_id != request.publisher_subject_id
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow dispatch-event envelope preparation payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow dispatch-event envelope idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow dispatch-event envelope request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow dispatch-event envelope preparation time must be aware")

    @staticmethod
    def _dispatch_event_envelope_contract_violation() -> None:
        raise WorkflowDispatchEventEnvelopeError(
            "workflow_dispatch_event_envelope_repository_contract_violation",
            "The workflow dispatch-event envelope does not match its canonical payload.",
        )

    async def _event_transport_admission_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventTransportAdmissionRequest,
    ) -> WorkflowEventTransportAdmissionResult | None:
        candidate = request.candidate
        claim = await self._load_event_transport_admission_claim(
            session,
            scope=candidate.scope,
            publisher_subject_id=candidate.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        record = self._event_transport_admission_record_from_claim(claim)
        status = (
            WorkflowEventTransportAdmissionStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowEventTransportAdmissionStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventTransportAdmissionResult(status, record.admission)

    @classmethod
    async def _load_event_transport_admission_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportAdmissionClaimModel | None:
        scope_id = cls._event_transport_admission_idempotency_scope(
            scope,
            publisher_subject_id,
        )
        return cast(
            WorkflowEventTransportAdmissionClaimModel | None,
            await session.scalar(
                select(WorkflowEventTransportAdmissionClaimModel).where(
                    WorkflowEventTransportAdmissionClaimModel.idempotency_scope_id == scope_id,
                    WorkflowEventTransportAdmissionClaimModel.idempotency_key == idempotency_key,
                    WorkflowEventTransportAdmissionClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventTransportAdmissionClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventTransportAdmissionClaimModel.site_id == scope.site_id,
                    WorkflowEventTransportAdmissionClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _event_transport_admission_record_from_claim(
        cls,
        claim: WorkflowEventTransportAdmissionClaimModel,
    ) -> WorkflowEventTransportAdmissionIdempotencyRecord:
        raw = claim.payload.get("result_admission")
        if not isinstance(raw, dict):
            cls._event_transport_admission_contract_violation()
        try:
            admission = cls._event_transport_admission_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_repository_contract_violation",
                "The transport-admission repository contains an invalid idempotency result.",
            ) from exc
        scope_id = cls._event_transport_admission_idempotency_scope(
            admission.scope,
            admission.publisher_subject_id,
        )
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": admission.canonical_digest,
            "result_admission": cls._event_transport_admission_payload(admission),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != admission.canonical_digest
            or claim.admission_id != admission.admission_id
            or claim.event_id != admission.event_id
            or claim.outbox_entry_id != admission.outbox_entry_id
            or claim.plan_id != admission.plan_id
            or claim.organization_id != admission.scope.organization_id
            or claim.environment_id != admission.scope.environment_id
            or claim.site_id != admission.scope.site_id
            or claim.publisher_subject_id != admission.publisher_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._event_transport_admission_contract_violation()
        return WorkflowEventTransportAdmissionIdempotencyRecord(
            claim.request_fingerprint,
            admission,
        )

    @classmethod
    def _event_transport_admission_from_row(
        cls,
        row: WorkflowEventTransportAdmissionModel,
    ) -> WorkflowEventTransportAdmission:
        try:
            admission = cls._event_transport_admission_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_repository_contract_violation",
                "The transport-admission repository contains an invalid admission.",
            ) from exc
        if (
            row.admission_id != admission.admission_id
            or row.event_id != admission.event_id
            or row.event_digest != admission.event_digest
            or row.outbox_entry_id != admission.outbox_entry_id
            or row.outbox_entry_digest != admission.outbox_entry_digest
            or row.dispatch_intent_id != admission.dispatch_intent_id
            or row.dispatch_intent_digest != admission.dispatch_intent_digest
            or row.plan_id != admission.plan_id
            or row.plan_digest != admission.plan_digest
            or row.run_id != admission.run_id
            or row.run_digest != admission.run_digest
            or row.step_run_id != admission.step_run_id
            or row.step_run_digest != admission.step_run_digest
            or row.step_id != admission.step_id
            or row.attempt_id != admission.attempt_id
            or row.attempt_digest != admission.attempt_digest
            or row.attempt_number != admission.attempt_number
            or row.organization_id != admission.scope.organization_id
            or row.environment_id != admission.scope.environment_id
            or row.site_id != admission.scope.site_id
            or row.target_type != admission.target_type
            or row.target_id != admission.target_id
            or row.policy_id != admission.policy_id
            or row.policy_version != admission.policy_version
            or row.policy_digest != admission.policy_digest
            or row.event_type != admission.event_type
            or row.event_version != admission.event_version
            or row.schema_uri != admission.schema_uri
            or row.data_classification != admission.data_classification
            or row.representation_name != admission.representation_name
            or row.encoding != admission.encoding
            or row.maximum_canonical_byte_count != admission.maximum_canonical_byte_count
            or row.canonical_byte_count != admission.canonical_byte_count
            or row.orchestration_lease_id != admission.orchestration_lease_id
            or row.orchestration_lease_digest != admission.orchestration_lease_digest
            or row.orchestration_fencing_token != admission.orchestration_fencing_token
            or row.publication_lease_id != admission.publication_lease_id
            or row.publication_lease_digest != admission.publication_lease_digest
            or row.publication_fencing_token != admission.publication_fencing_token
            or row.publisher_subject_id != admission.publisher_subject_id
            or row.admitted_at != admission.admitted_at
            or row.state != admission.state.value
            or row.publication_authority_granted != admission.grants_publication_authority
            or row.delivery_authority_granted != admission.grants_delivery_authority
            or row.dispatch_authority_granted != admission.grants_dispatch_authority
            or row.execution_authority_granted != admission.grants_execution_authority
            or row.canonical_digest != admission.canonical_digest
        ):
            cls._event_transport_admission_contract_violation()
        return admission

    @classmethod
    def _event_transport_admission_model(
        cls,
        admission: WorkflowEventTransportAdmission,
    ) -> WorkflowEventTransportAdmissionModel:
        return WorkflowEventTransportAdmissionModel(
            admission_id=admission.admission_id,
            event_id=admission.event_id,
            event_digest=admission.event_digest,
            outbox_entry_id=admission.outbox_entry_id,
            outbox_entry_digest=admission.outbox_entry_digest,
            dispatch_intent_id=admission.dispatch_intent_id,
            dispatch_intent_digest=admission.dispatch_intent_digest,
            plan_id=admission.plan_id,
            plan_digest=admission.plan_digest,
            run_id=admission.run_id,
            run_digest=admission.run_digest,
            step_run_id=admission.step_run_id,
            step_run_digest=admission.step_run_digest,
            step_id=admission.step_id,
            attempt_id=admission.attempt_id,
            attempt_digest=admission.attempt_digest,
            attempt_number=admission.attempt_number,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            target_type=admission.target_type,
            target_id=admission.target_id,
            policy_id=admission.policy_id,
            policy_version=admission.policy_version,
            policy_digest=admission.policy_digest,
            event_type=admission.event_type,
            event_version=admission.event_version,
            schema_uri=admission.schema_uri,
            data_classification=admission.data_classification,
            representation_name=admission.representation_name,
            encoding=admission.encoding,
            maximum_canonical_byte_count=admission.maximum_canonical_byte_count,
            canonical_byte_count=admission.canonical_byte_count,
            orchestration_lease_id=admission.orchestration_lease_id,
            orchestration_lease_digest=admission.orchestration_lease_digest,
            orchestration_fencing_token=admission.orchestration_fencing_token,
            publication_lease_id=admission.publication_lease_id,
            publication_lease_digest=admission.publication_lease_digest,
            publication_fencing_token=admission.publication_fencing_token,
            publisher_subject_id=admission.publisher_subject_id,
            admitted_at=admission.admitted_at,
            state=admission.state.value,
            publication_authority_granted=admission.grants_publication_authority,
            delivery_authority_granted=admission.grants_delivery_authority,
            dispatch_authority_granted=admission.grants_dispatch_authority,
            execution_authority_granted=admission.grants_execution_authority,
            canonical_digest=admission.canonical_digest,
            payload=cls._event_transport_admission_payload(admission),
        )

    @classmethod
    def _event_transport_admission_claim_model(
        cls,
        request: WorkflowEventTransportAdmissionRequest,
    ) -> WorkflowEventTransportAdmissionClaimModel:
        admission = request.candidate
        scope_id = cls._event_transport_admission_idempotency_scope(
            admission.scope,
            admission.publisher_subject_id,
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": admission.canonical_digest,
            "result_admission": cls._event_transport_admission_payload(admission),
        }
        digest = canonical_digest(payload)
        return WorkflowEventTransportAdmissionClaimModel(
            claim_id=f"workflow_event_transport_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=admission.canonical_digest,
            admission_id=admission.admission_id,
            event_id=admission.event_id,
            outbox_entry_id=admission.outbox_entry_id,
            plan_id=admission.plan_id,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            publisher_subject_id=admission.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _event_transport_admission_evidence_matches(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        publication_lease_row: WorkflowOutboxPublicationLeaseModel | None,
        envelope_row: WorkflowDispatchEventEnvelopeModel | None,
        request: WorkflowEventTransportAdmissionRequest,
    ) -> bool:
        if any(
            item is None
            for item in (
                plan_row,
                outbox_row,
                orchestration_lease_row,
                publication_lease_row,
                envelope_row,
            )
        ):
            return False
        assert plan_row is not None
        assert outbox_row is not None
        assert orchestration_lease_row is not None
        assert publication_lease_row is not None
        assert envelope_row is not None
        candidate = request.candidate
        policy = code_owned_workflow_event_transport_admission_policy()
        try:
            outbox = cls._dispatch_outbox_from_row(outbox_row)
            orchestration_lease = cls._lease_from_row(orchestration_lease_row)
            publication_lease = cls._publication_lease_from_row(publication_lease_row)
            envelope = cls._dispatch_event_envelope_from_row(envelope_row)
        except (
            WorkflowDispatchIntentStagingError,
            WorkflowOrchestrationLeaseError,
            WorkflowOutboxPublicationLeaseError,
            WorkflowDispatchEventEnvelopeError,
        ) as exc:
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_repository_contract_violation",
                "Workflow evidence is inconsistent during transport admission.",
            ) from exc
        event_payload = envelope.payload
        return bool(
            plan_row.plan_id == candidate.plan_id
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == candidate.plan_digest
            and plan_row.organization_id == candidate.scope.organization_id
            and plan_row.environment_id == candidate.scope.environment_id
            and plan_row.site_id == candidate.scope.site_id
            and plan_row.target_type == candidate.target_type
            and plan_row.target_id == candidate.target_id
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.outbox_entry_id == candidate.outbox_entry_id
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == candidate.outbox_entry_digest
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
            and outbox.attempt_number == candidate.attempt_number == 1
            and outbox.scope == candidate.scope
            and outbox.target_id == candidate.target_id
            and outbox.target_type == candidate.target_type
            and not any(outbox.authority.canonical_value().values())
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
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and publication_lease.publication_lease_id
            == request.expected_publication_lease_id
            == candidate.publication_lease_id
            and publication_lease.canonical_digest
            == request.expected_publication_lease_digest
            == candidate.publication_lease_digest
            and publication_lease.publication_fencing_token
            == request.expected_publication_fencing_token
            == candidate.publication_fencing_token
            and publication_lease.outbox_entry_id == candidate.outbox_entry_id
            and publication_lease.outbox_entry_digest == candidate.outbox_entry_digest
            and publication_lease.dispatch_intent_id == candidate.dispatch_intent_id
            and publication_lease.dispatch_intent_digest == candidate.dispatch_intent_digest
            and publication_lease.plan_id == candidate.plan_id
            and publication_lease.plan_digest == candidate.plan_digest
            and publication_lease.run_id == candidate.run_id
            and publication_lease.run_digest == candidate.run_digest
            and publication_lease.step_run_id == candidate.step_run_id
            and publication_lease.step_run_digest == candidate.step_run_digest
            and publication_lease.step_id == candidate.step_id
            and publication_lease.attempt_id == candidate.attempt_id
            and publication_lease.attempt_digest == candidate.attempt_digest
            and publication_lease.attempt_number == candidate.attempt_number
            and publication_lease.scope == candidate.scope
            and publication_lease.target_id == candidate.target_id
            and publication_lease.target_type == candidate.target_type
            and publication_lease.orchestration_lease_id == candidate.orchestration_lease_id
            and publication_lease.orchestration_lease_digest == candidate.orchestration_lease_digest
            and publication_lease.orchestration_fencing_token
            == candidate.orchestration_fencing_token
            and publication_lease.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and envelope.state is WorkflowDispatchEventEnvelopeState.PREPARED
            and envelope.event_id == request.expected_event_id == candidate.event_id
            and envelope.canonical_digest == request.expected_event_digest == candidate.event_digest
            and envelope.event_type == candidate.event_type
            and envelope.event_version == candidate.event_version
            and envelope.schema_uri == candidate.schema_uri
            and envelope.data_classification == candidate.data_classification
            and event_payload.outbox_entry_id == candidate.outbox_entry_id
            and event_payload.outbox_entry_digest == candidate.outbox_entry_digest
            and event_payload.dispatch_intent_id == candidate.dispatch_intent_id
            and event_payload.dispatch_intent_digest == candidate.dispatch_intent_digest
            and event_payload.plan_id == candidate.plan_id
            and event_payload.plan_digest == candidate.plan_digest
            and event_payload.run_id == candidate.run_id
            and event_payload.run_digest == candidate.run_digest
            and event_payload.step_run_id == candidate.step_run_id
            and event_payload.step_run_digest == candidate.step_run_digest
            and event_payload.step_id == candidate.step_id
            and event_payload.attempt_id == candidate.attempt_id
            and event_payload.attempt_digest == candidate.attempt_digest
            and event_payload.attempt_number == candidate.attempt_number
            and event_payload.scope == candidate.scope
            and event_payload.target_id == candidate.target_id
            and event_payload.target_type == candidate.target_type
            and envelope.orchestration_lease_id == candidate.orchestration_lease_id
            and envelope.orchestration_lease_digest == candidate.orchestration_lease_digest
            and envelope.orchestration_fencing_token == candidate.orchestration_fencing_token
            and envelope.publication_lease_id == candidate.publication_lease_id
            and envelope.publication_lease_digest == candidate.publication_lease_digest
            and envelope.publication_fencing_token == candidate.publication_fencing_token
            and envelope.publisher_subject_id == candidate.publisher_subject_id
            and candidate.canonical_byte_count
            == canonical_json_byte_count(envelope.canonical_value())
            and candidate.policy_id == policy.policy_id
            and candidate.policy_version == policy.policy_version
            and candidate.policy_digest == request.expected_policy_digest == policy.canonical_digest
            and candidate.event_type in policy.allowed_event_types
            and candidate.event_version in policy.allowed_event_versions
            and candidate.schema_uri in policy.allowed_schema_uris
            and candidate.data_classification in policy.allowed_data_classifications
            and candidate.representation_name == policy.representation_name
            and candidate.encoding == policy.encoding
            and candidate.maximum_canonical_byte_count == policy.maximum_canonical_byte_count
            and candidate.canonical_byte_count <= candidate.maximum_canonical_byte_count
            and not any(envelope.authority.canonical_value().values())
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_transport_admission_idempotency_scope(
        scope: WorkflowScope,
        publisher_subject_id: str,
    ) -> str:
        return canonical_digest(
            {
                "publisher_subject_id": publisher_subject_id,
                "scope": scope.canonical_value(),
            }
        )

    @staticmethod
    def _event_transport_admission_payload(
        admission: WorkflowEventTransportAdmission,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], admission.canonical_value())

    @staticmethod
    def _event_transport_admission_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventTransportAdmission:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["admitted_at"] = datetime.fromisoformat(str(values["admitted_at"]))
        values["state"] = WorkflowEventTransportAdmissionState(str(values["state"]))
        values["authority"] = WorkflowEventTransportAdmissionAuthority(
            **cast(Any, values["authority"])
        )
        return WorkflowEventTransportAdmission(**cast(Any, values))

    @staticmethod
    def _validate_event_transport_admission_request(
        request: WorkflowEventTransportAdmissionRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowEventTransportAdmissionState.ADMITTED
            or candidate.attempt_number != 1
            or candidate.publisher_subject_id != request.publisher_subject_id
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow event transport admission payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow event transport admission idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow event transport admission request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow event transport admission time must be aware")

    @staticmethod
    def _event_transport_admission_contract_violation() -> None:
        raise WorkflowEventTransportAdmissionError(
            "workflow_event_transport_admission_repository_contract_violation",
            "The workflow event transport admission does not match its canonical payload.",
        )

    async def _event_byte_artifact_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventByteArtifactRequest,
    ) -> WorkflowEventByteArtifactResult | None:
        candidate = request.candidate
        claim = await self._load_event_byte_artifact_claim(
            session,
            scope=candidate.scope,
            publisher_subject_id=candidate.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        artifact_row = await session.get(WorkflowEventByteArtifactModel, claim.artifact_id)
        record = self._event_byte_artifact_record_from_claim(claim, artifact_row)
        status = (
            WorkflowEventByteArtifactStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowEventByteArtifactStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventByteArtifactResult(status, record.artifact)

    @classmethod
    async def _load_event_byte_artifact_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventByteArtifactClaimModel | None:
        scope_id = cls._event_byte_artifact_idempotency_scope(scope, publisher_subject_id)
        return cast(
            WorkflowEventByteArtifactClaimModel | None,
            await session.scalar(
                select(WorkflowEventByteArtifactClaimModel).where(
                    WorkflowEventByteArtifactClaimModel.idempotency_scope_id == scope_id,
                    WorkflowEventByteArtifactClaimModel.idempotency_key == idempotency_key,
                    WorkflowEventByteArtifactClaimModel.organization_id == scope.organization_id,
                    WorkflowEventByteArtifactClaimModel.environment_id == scope.environment_id,
                    WorkflowEventByteArtifactClaimModel.site_id == scope.site_id,
                    WorkflowEventByteArtifactClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _event_byte_artifact_record_from_claim(
        cls,
        claim: WorkflowEventByteArtifactClaimModel,
        artifact_row: WorkflowEventByteArtifactModel | None,
    ) -> WorkflowEventByteArtifactIdempotencyRecord:
        if artifact_row is None:
            cls._event_byte_artifact_contract_violation()
        assert artifact_row is not None
        artifact = cls._event_byte_artifact_from_row(artifact_row)
        scope_id = cls._event_byte_artifact_idempotency_scope(
            artifact.scope, artifact.publisher_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_artifact": cls._event_byte_artifact_payload(artifact),
            "result_digest": artifact.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != artifact.canonical_digest
            or claim.artifact_id != artifact.artifact_id
            or claim.admission_id != artifact.admission_id
            or claim.event_id != artifact.event_id
            or claim.outbox_entry_id != artifact.outbox_entry_id
            or claim.plan_id != artifact.plan_id
            or claim.organization_id != artifact.scope.organization_id
            or claim.environment_id != artifact.scope.environment_id
            or claim.site_id != artifact.scope.site_id
            or claim.publisher_subject_id != artifact.publisher_subject_id
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._event_byte_artifact_contract_violation()
        return WorkflowEventByteArtifactIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            artifact=artifact,
        )

    @classmethod
    def _event_byte_artifact_from_row(
        cls, row: WorkflowEventByteArtifactModel
    ) -> WorkflowEventByteArtifact:
        try:
            artifact = cls._event_byte_artifact_to_domain(row.payload, row.canonical_bytes)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventByteArtifactError(
                "workflow_event_byte_artifact_repository_contract_violation",
                "The byte-artifact repository contains an invalid artifact.",
            ) from exc
        if (
            row.artifact_id != artifact.artifact_id
            or row.admission_id != artifact.admission_id
            or row.admission_digest != artifact.admission_digest
            or row.event_id != artifact.event_id
            or row.event_digest != artifact.event_digest
            or row.event_type != artifact.event_type
            or row.event_version != artifact.event_version
            or row.schema_uri != artifact.schema_uri
            or row.data_classification != artifact.data_classification
            or row.outbox_entry_id != artifact.outbox_entry_id
            or row.outbox_entry_digest != artifact.outbox_entry_digest
            or row.dispatch_intent_id != artifact.dispatch_intent_id
            or row.dispatch_intent_digest != artifact.dispatch_intent_digest
            or row.plan_id != artifact.plan_id
            or row.plan_digest != artifact.plan_digest
            or row.run_id != artifact.run_id
            or row.run_digest != artifact.run_digest
            or row.step_run_id != artifact.step_run_id
            or row.step_run_digest != artifact.step_run_digest
            or row.step_id != artifact.step_id
            or row.attempt_id != artifact.attempt_id
            or row.attempt_digest != artifact.attempt_digest
            or row.attempt_number != artifact.attempt_number
            or row.organization_id != artifact.scope.organization_id
            or row.environment_id != artifact.scope.environment_id
            or row.site_id != artifact.scope.site_id
            or row.target_type != artifact.target_type
            or row.target_id != artifact.target_id
            or row.policy_id != artifact.policy_id
            or row.policy_version != artifact.policy_version
            or row.policy_digest != artifact.policy_digest
            or row.representation_name != artifact.representation_name
            or row.encoding != artifact.encoding
            or row.maximum_canonical_byte_count != artifact.maximum_canonical_byte_count
            or row.canonical_byte_count != artifact.canonical_byte_count
            or row.content_sha256 != artifact.content_sha256
            or row.orchestration_lease_id != artifact.orchestration_lease_id
            or row.orchestration_lease_digest != artifact.orchestration_lease_digest
            or row.orchestration_fencing_token != artifact.orchestration_fencing_token
            or row.publication_lease_id != artifact.publication_lease_id
            or row.publication_lease_digest != artifact.publication_lease_digest
            or row.publication_fencing_token != artifact.publication_fencing_token
            or row.publisher_subject_id != artifact.publisher_subject_id
            or row.materialized_at != artifact.materialized_at
            or row.state != artifact.state.value
            or row.publication_authority_granted != artifact.authority.publication_authorized
            or row.delivery_authority_granted != artifact.authority.delivery_authorized
            or row.dispatch_authority_granted != artifact.authority.dispatch_authorized
            or row.execution_authority_granted != artifact.authority.execution_authorized
            or row.canonical_digest != artifact.canonical_digest
            or row.canonical_bytes != artifact.canonical_bytes
            or row.payload != cls._event_byte_artifact_payload(artifact)
        ):
            cls._event_byte_artifact_contract_violation()
        return artifact

    @classmethod
    def _event_byte_artifact_model(
        cls, artifact: WorkflowEventByteArtifact
    ) -> WorkflowEventByteArtifactModel:
        return WorkflowEventByteArtifactModel(
            artifact_id=artifact.artifact_id,
            admission_id=artifact.admission_id,
            admission_digest=artifact.admission_digest,
            event_id=artifact.event_id,
            event_digest=artifact.event_digest,
            event_type=artifact.event_type,
            event_version=artifact.event_version,
            schema_uri=artifact.schema_uri,
            data_classification=artifact.data_classification,
            outbox_entry_id=artifact.outbox_entry_id,
            outbox_entry_digest=artifact.outbox_entry_digest,
            dispatch_intent_id=artifact.dispatch_intent_id,
            dispatch_intent_digest=artifact.dispatch_intent_digest,
            plan_id=artifact.plan_id,
            plan_digest=artifact.plan_digest,
            run_id=artifact.run_id,
            run_digest=artifact.run_digest,
            step_run_id=artifact.step_run_id,
            step_run_digest=artifact.step_run_digest,
            step_id=artifact.step_id,
            attempt_id=artifact.attempt_id,
            attempt_digest=artifact.attempt_digest,
            attempt_number=artifact.attempt_number,
            organization_id=artifact.scope.organization_id,
            environment_id=artifact.scope.environment_id,
            site_id=artifact.scope.site_id,
            target_type=artifact.target_type,
            target_id=artifact.target_id,
            policy_id=artifact.policy_id,
            policy_version=artifact.policy_version,
            policy_digest=artifact.policy_digest,
            representation_name=artifact.representation_name,
            encoding=artifact.encoding,
            maximum_canonical_byte_count=artifact.maximum_canonical_byte_count,
            canonical_byte_count=artifact.canonical_byte_count,
            content_sha256=artifact.content_sha256,
            orchestration_lease_id=artifact.orchestration_lease_id,
            orchestration_lease_digest=artifact.orchestration_lease_digest,
            orchestration_fencing_token=artifact.orchestration_fencing_token,
            publication_lease_id=artifact.publication_lease_id,
            publication_lease_digest=artifact.publication_lease_digest,
            publication_fencing_token=artifact.publication_fencing_token,
            publisher_subject_id=artifact.publisher_subject_id,
            materialized_at=artifact.materialized_at,
            state=artifact.state.value,
            publication_authority_granted=artifact.authority.publication_authorized,
            delivery_authority_granted=artifact.authority.delivery_authorized,
            dispatch_authority_granted=artifact.authority.dispatch_authorized,
            execution_authority_granted=artifact.authority.execution_authorized,
            canonical_digest=artifact.canonical_digest,
            canonical_bytes=artifact.canonical_bytes,
            payload=cls._event_byte_artifact_payload(artifact),
        )

    @classmethod
    def _event_byte_artifact_claim_model(
        cls, request: WorkflowEventByteArtifactRequest
    ) -> WorkflowEventByteArtifactClaimModel:
        artifact = request.candidate
        scope_id = cls._event_byte_artifact_idempotency_scope(
            artifact.scope, artifact.publisher_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_artifact": cls._event_byte_artifact_payload(artifact),
            "result_digest": artifact.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventByteArtifactClaimModel(
            claim_id=f"workflow_event_byte_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=artifact.canonical_digest,
            artifact_id=artifact.artifact_id,
            admission_id=artifact.admission_id,
            event_id=artifact.event_id,
            outbox_entry_id=artifact.outbox_entry_id,
            plan_id=artifact.plan_id,
            organization_id=artifact.scope.organization_id,
            environment_id=artifact.scope.environment_id,
            site_id=artifact.scope.site_id,
            publisher_subject_id=artifact.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _event_byte_artifact_evidence_matches(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        publication_lease_row: WorkflowOutboxPublicationLeaseModel | None,
        envelope_row: WorkflowDispatchEventEnvelopeModel | None,
        admission_row: WorkflowEventTransportAdmissionModel | None,
        request: WorkflowEventByteArtifactRequest,
    ) -> bool:
        if any(
            row is None
            for row in (
                plan_row,
                outbox_row,
                orchestration_lease_row,
                publication_lease_row,
                envelope_row,
                admission_row,
            )
        ):
            return False
        assert plan_row is not None
        assert outbox_row is not None
        assert orchestration_lease_row is not None
        assert publication_lease_row is not None
        assert envelope_row is not None
        assert admission_row is not None
        try:
            envelope = cls._dispatch_event_envelope_from_row(envelope_row)
            admission = cls._event_transport_admission_from_row(admission_row)
        except (WorkflowDispatchEventEnvelopeError, WorkflowEventTransportAdmissionError) as exc:
            raise WorkflowEventByteArtifactError(
                "workflow_event_byte_artifact_repository_contract_violation",
                "Workflow evidence is inconsistent during byte materialization.",
            ) from exc
        transport_request = WorkflowEventTransportAdmissionRequest(
            expected_plan_digest=request.expected_plan_digest,
            expected_outbox_entry_digest=request.expected_outbox_entry_digest,
            expected_event_id=request.expected_event_id,
            expected_event_digest=request.expected_event_digest,
            expected_policy_digest=request.expected_policy_digest,
            expected_orchestration_lease_id=request.expected_orchestration_lease_id,
            expected_orchestration_lease_digest=request.expected_orchestration_lease_digest,
            expected_orchestration_fencing_token=request.expected_orchestration_fencing_token,
            expected_publication_lease_id=request.expected_publication_lease_id,
            expected_publication_lease_digest=request.expected_publication_lease_digest,
            expected_publication_fencing_token=request.expected_publication_fencing_token,
            publisher_subject_id=request.publisher_subject_id,
            requested_at=request.requested_at,
            candidate=admission,
            idempotency_key="byte-artifact-evidence-validation",
            request_fingerprint="0" * 64,
        )
        if not cls._event_transport_admission_evidence_matches(
            plan_row=plan_row,
            outbox_row=outbox_row,
            orchestration_lease_row=orchestration_lease_row,
            publication_lease_row=publication_lease_row,
            envelope_row=envelope_row,
            request=transport_request,
        ):
            return False
        candidate = request.candidate
        shared_fields = (
            "policy_id",
            "policy_version",
            "policy_digest",
            "event_id",
            "event_digest",
            "event_type",
            "event_version",
            "schema_uri",
            "data_classification",
            "representation_name",
            "encoding",
            "canonical_byte_count",
            "maximum_canonical_byte_count",
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
            "publication_lease_id",
            "publication_lease_digest",
            "publication_fencing_token",
            "publisher_subject_id",
        )
        return bool(
            admission.admission_id == request.expected_admission_id == candidate.admission_id
            and admission.canonical_digest
            == request.expected_admission_digest
            == candidate.admission_digest
            and all(
                getattr(admission, field) == getattr(candidate, field) for field in shared_fields
            )
            and candidate.canonical_bytes == canonical_json_bytes(envelope.canonical_value())
            and candidate.state is WorkflowEventByteArtifactState.MATERIALIZED
            and not any(admission.authority.canonical_value().values())
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_byte_artifact_idempotency_scope(
        scope: WorkflowScope, publisher_subject_id: str
    ) -> str:
        return canonical_digest(
            {"publisher_subject_id": publisher_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _event_byte_artifact_payload(artifact: WorkflowEventByteArtifact) -> dict[str, Any]:
        return cast(dict[str, Any], artifact.canonical_value())

    @staticmethod
    def _event_byte_artifact_to_domain(
        raw: dict[str, Any], canonical_bytes_value: bytes
    ) -> WorkflowEventByteArtifact:
        values = dict(raw)
        values["canonical_bytes"] = bytes(canonical_bytes_value)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["materialized_at"] = datetime.fromisoformat(str(values["materialized_at"]))
        values["state"] = WorkflowEventByteArtifactState(str(values["state"]))
        values["authority"] = WorkflowEventByteArtifactAuthority(**cast(Any, values["authority"]))
        return WorkflowEventByteArtifact(**cast(Any, values))

    @staticmethod
    def _validate_event_byte_artifact_request(
        request: WorkflowEventByteArtifactRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowEventByteArtifactState.MATERIALIZED
            or candidate.attempt_number != 1
            or candidate.publisher_subject_id != request.publisher_subject_id
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow event byte artifact payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow event byte artifact idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow event byte artifact request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow event byte artifact time must be aware")

    @staticmethod
    def _event_byte_artifact_contract_violation() -> NoReturn:
        raise WorkflowEventByteArtifactError(
            "workflow_event_byte_artifact_repository_contract_violation",
            "The workflow event byte artifact does not match its durable evidence.",
        )

    async def _event_logical_channel_binding_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventLogicalChannelBindingRequest,
    ) -> WorkflowEventLogicalChannelBindingResult | None:
        candidate = request.candidate
        claim = await self._load_event_logical_channel_binding_claim(
            session,
            scope=candidate.scope,
            publisher_subject_id=candidate.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        binding_row = await session.get(WorkflowEventLogicalChannelBindingModel, claim.binding_id)
        record = self._event_logical_channel_binding_record_from_claim(claim, binding_row)
        status = (
            WorkflowEventLogicalChannelBindingStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowEventLogicalChannelBindingStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventLogicalChannelBindingResult(status, record.binding)

    @classmethod
    async def _load_event_logical_channel_binding_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventLogicalChannelBindingClaimModel | None:
        scope_id = cls._event_logical_channel_binding_idempotency_scope(scope, publisher_subject_id)
        return cast(
            WorkflowEventLogicalChannelBindingClaimModel | None,
            await session.scalar(
                select(WorkflowEventLogicalChannelBindingClaimModel).where(
                    WorkflowEventLogicalChannelBindingClaimModel.idempotency_scope_id == scope_id,
                    WorkflowEventLogicalChannelBindingClaimModel.idempotency_key == idempotency_key,
                    WorkflowEventLogicalChannelBindingClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventLogicalChannelBindingClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventLogicalChannelBindingClaimModel.site_id == scope.site_id,
                    WorkflowEventLogicalChannelBindingClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _event_logical_channel_binding_record_from_claim(
        cls,
        claim: WorkflowEventLogicalChannelBindingClaimModel,
        binding_row: WorkflowEventLogicalChannelBindingModel | None,
    ) -> WorkflowEventLogicalChannelBindingIdempotencyRecord:
        if binding_row is None:
            cls._event_logical_channel_binding_contract_violation()
        assert binding_row is not None
        binding = cls._event_logical_channel_binding_from_row(binding_row)
        scope_id = cls._event_logical_channel_binding_idempotency_scope(
            binding.scope, binding.publisher_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_binding": cls._event_logical_channel_binding_payload(binding),
            "result_digest": binding.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != binding.canonical_digest
            or claim.binding_id != binding.binding_id
            or claim.artifact_id != binding.artifact_id
            or claim.admission_id != binding.admission_id
            or claim.event_id != binding.event_id
            or claim.outbox_entry_id != binding.outbox_entry_id
            or claim.plan_id != binding.plan_id
            or claim.organization_id != binding.scope.organization_id
            or claim.environment_id != binding.scope.environment_id
            or claim.site_id != binding.scope.site_id
            or claim.publisher_subject_id != binding.publisher_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != binding.bound_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._event_logical_channel_binding_contract_violation()
        return WorkflowEventLogicalChannelBindingIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            binding=binding,
        )

    @classmethod
    def _event_logical_channel_binding_from_row(
        cls, row: WorkflowEventLogicalChannelBindingModel
    ) -> WorkflowEventLogicalChannelBinding:
        try:
            binding = cls._event_logical_channel_binding_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventLogicalChannelBindingError(
                "workflow_event_logical_channel_binding_repository_contract_violation",
                "The logical-channel repository contains an invalid binding.",
            ) from exc
        if (
            row.binding_id != binding.binding_id
            or row.artifact_id != binding.artifact_id
            or row.artifact_digest != binding.artifact_digest
            or row.content_sha256 != binding.content_sha256
            or row.canonical_byte_count != binding.canonical_byte_count
            or row.admission_id != binding.admission_id
            or row.admission_digest != binding.admission_digest
            or row.event_id != binding.event_id
            or row.event_digest != binding.event_digest
            or row.event_type != binding.event_type
            or row.event_version != binding.event_version
            or row.schema_uri != binding.schema_uri
            or row.outbox_entry_id != binding.outbox_entry_id
            or row.outbox_entry_digest != binding.outbox_entry_digest
            or row.dispatch_intent_id != binding.dispatch_intent_id
            or row.dispatch_intent_digest != binding.dispatch_intent_digest
            or row.plan_id != binding.plan_id
            or row.plan_digest != binding.plan_digest
            or row.run_id != binding.run_id
            or row.run_digest != binding.run_digest
            or row.step_run_id != binding.step_run_id
            or row.step_run_digest != binding.step_run_digest
            or row.step_id != binding.step_id
            or row.attempt_id != binding.attempt_id
            or row.attempt_digest != binding.attempt_digest
            or row.attempt_number != binding.attempt_number
            or row.organization_id != binding.scope.organization_id
            or row.environment_id != binding.scope.environment_id
            or row.site_id != binding.scope.site_id
            or row.target_type != binding.target_type
            or row.target_id != binding.target_id
            or row.policy_id != binding.policy_id
            or row.policy_version != binding.policy_version
            or row.policy_digest != binding.policy_digest
            or row.logical_channel_id != binding.logical_channel_id
            or row.logical_channel_version != binding.logical_channel_version
            or row.data_classification != binding.data_classification
            or row.representation_name != binding.representation_name
            or row.encoding != binding.encoding
            or row.delivery_semantics != binding.delivery_semantics
            or row.durability_required != binding.durability_required
            or row.ordering_key_kind != binding.ordering_key_kind
            or row.ordering_key_value != binding.ordering_key_value
            or row.retention_class != binding.retention_class
            or row.maximum_canonical_byte_count != binding.maximum_canonical_byte_count
            or row.orchestration_lease_id != binding.orchestration_lease_id
            or row.orchestration_lease_digest != binding.orchestration_lease_digest
            or row.orchestration_fencing_token != binding.orchestration_fencing_token
            or row.publication_lease_id != binding.publication_lease_id
            or row.publication_lease_digest != binding.publication_lease_digest
            or row.publication_fencing_token != binding.publication_fencing_token
            or row.publisher_subject_id != binding.publisher_subject_id
            or row.bound_at != binding.bound_at
            or row.state != binding.state.value
            or row.publication_authority_granted != binding.authority.publication_authorized
            or row.delivery_authority_granted != binding.authority.delivery_authorized
            or row.dispatch_authority_granted != binding.authority.dispatch_authorized
            or row.execution_authority_granted != binding.authority.execution_authorized
            or row.canonical_digest != binding.canonical_digest
            or row.payload != cls._event_logical_channel_binding_payload(binding)
        ):
            cls._event_logical_channel_binding_contract_violation()
        return binding

    @classmethod
    def _event_logical_channel_binding_model(
        cls, binding: WorkflowEventLogicalChannelBinding
    ) -> WorkflowEventLogicalChannelBindingModel:
        return WorkflowEventLogicalChannelBindingModel(
            binding_id=binding.binding_id,
            artifact_id=binding.artifact_id,
            artifact_digest=binding.artifact_digest,
            content_sha256=binding.content_sha256,
            canonical_byte_count=binding.canonical_byte_count,
            admission_id=binding.admission_id,
            admission_digest=binding.admission_digest,
            event_id=binding.event_id,
            event_digest=binding.event_digest,
            event_type=binding.event_type,
            event_version=binding.event_version,
            schema_uri=binding.schema_uri,
            outbox_entry_id=binding.outbox_entry_id,
            outbox_entry_digest=binding.outbox_entry_digest,
            dispatch_intent_id=binding.dispatch_intent_id,
            dispatch_intent_digest=binding.dispatch_intent_digest,
            plan_id=binding.plan_id,
            plan_digest=binding.plan_digest,
            run_id=binding.run_id,
            run_digest=binding.run_digest,
            step_run_id=binding.step_run_id,
            step_run_digest=binding.step_run_digest,
            step_id=binding.step_id,
            attempt_id=binding.attempt_id,
            attempt_digest=binding.attempt_digest,
            attempt_number=binding.attempt_number,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            target_type=binding.target_type,
            target_id=binding.target_id,
            policy_id=binding.policy_id,
            policy_version=binding.policy_version,
            policy_digest=binding.policy_digest,
            logical_channel_id=binding.logical_channel_id,
            logical_channel_version=binding.logical_channel_version,
            data_classification=binding.data_classification,
            representation_name=binding.representation_name,
            encoding=binding.encoding,
            delivery_semantics=binding.delivery_semantics,
            durability_required=binding.durability_required,
            ordering_key_kind=binding.ordering_key_kind,
            ordering_key_value=binding.ordering_key_value,
            retention_class=binding.retention_class,
            maximum_canonical_byte_count=binding.maximum_canonical_byte_count,
            orchestration_lease_id=binding.orchestration_lease_id,
            orchestration_lease_digest=binding.orchestration_lease_digest,
            orchestration_fencing_token=binding.orchestration_fencing_token,
            publication_lease_id=binding.publication_lease_id,
            publication_lease_digest=binding.publication_lease_digest,
            publication_fencing_token=binding.publication_fencing_token,
            publisher_subject_id=binding.publisher_subject_id,
            bound_at=binding.bound_at,
            state=binding.state.value,
            publication_authority_granted=binding.authority.publication_authorized,
            delivery_authority_granted=binding.authority.delivery_authorized,
            dispatch_authority_granted=binding.authority.dispatch_authorized,
            execution_authority_granted=binding.authority.execution_authorized,
            canonical_digest=binding.canonical_digest,
            payload=cls._event_logical_channel_binding_payload(binding),
        )

    @classmethod
    def _event_logical_channel_binding_claim_model(
        cls, request: WorkflowEventLogicalChannelBindingRequest
    ) -> WorkflowEventLogicalChannelBindingClaimModel:
        binding = request.candidate
        scope_id = cls._event_logical_channel_binding_idempotency_scope(
            binding.scope, binding.publisher_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_binding": cls._event_logical_channel_binding_payload(binding),
            "result_digest": binding.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventLogicalChannelBindingClaimModel(
            claim_id=f"workflow_event_channel_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=binding.canonical_digest,
            binding_id=binding.binding_id,
            artifact_id=binding.artifact_id,
            admission_id=binding.admission_id,
            event_id=binding.event_id,
            outbox_entry_id=binding.outbox_entry_id,
            plan_id=binding.plan_id,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            publisher_subject_id=binding.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _event_logical_channel_binding_evidence_matches(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        publication_lease_row: WorkflowOutboxPublicationLeaseModel | None,
        envelope_row: WorkflowDispatchEventEnvelopeModel | None,
        admission_row: WorkflowEventTransportAdmissionModel | None,
        artifact_row: WorkflowEventByteArtifactModel | None,
        request: WorkflowEventLogicalChannelBindingRequest,
    ) -> bool:
        if any(
            row is None
            for row in (
                plan_row,
                outbox_row,
                orchestration_lease_row,
                publication_lease_row,
                envelope_row,
                admission_row,
                artifact_row,
            )
        ):
            return False
        assert plan_row is not None
        assert outbox_row is not None
        assert orchestration_lease_row is not None
        assert publication_lease_row is not None
        assert envelope_row is not None
        assert admission_row is not None
        assert artifact_row is not None
        try:
            admission = cls._event_transport_admission_from_row(admission_row)
            artifact = cls._event_byte_artifact_from_row(artifact_row)
        except (WorkflowEventTransportAdmissionError, WorkflowEventByteArtifactError) as exc:
            raise WorkflowEventLogicalChannelBindingError(
                "workflow_event_logical_channel_binding_repository_contract_violation",
                "Workflow evidence is inconsistent during logical-channel binding.",
            ) from exc
        artifact_request = WorkflowEventByteArtifactRequest(
            expected_plan_digest=request.expected_plan_digest,
            expected_outbox_entry_digest=request.expected_outbox_entry_digest,
            expected_event_id=request.expected_event_id,
            expected_event_digest=request.expected_event_digest,
            expected_admission_id=request.expected_admission_id,
            expected_admission_digest=request.expected_admission_digest,
            expected_policy_digest=artifact.policy_digest,
            expected_orchestration_lease_id=request.expected_orchestration_lease_id,
            expected_orchestration_lease_digest=request.expected_orchestration_lease_digest,
            expected_orchestration_fencing_token=request.expected_orchestration_fencing_token,
            expected_publication_lease_id=request.expected_publication_lease_id,
            expected_publication_lease_digest=request.expected_publication_lease_digest,
            expected_publication_fencing_token=request.expected_publication_fencing_token,
            publisher_subject_id=request.publisher_subject_id,
            requested_at=request.requested_at,
            candidate=artifact,
            idempotency_key="logical-channel-evidence-validation",
            request_fingerprint="0" * 64,
        )
        if not cls._event_byte_artifact_evidence_matches(
            plan_row=plan_row,
            outbox_row=outbox_row,
            orchestration_lease_row=orchestration_lease_row,
            publication_lease_row=publication_lease_row,
            envelope_row=envelope_row,
            admission_row=admission_row,
            request=artifact_request,
        ):
            return False
        candidate = request.candidate
        policy = code_owned_workflow_event_logical_channel_policy()
        return bool(
            artifact.artifact_id == request.expected_artifact_id == candidate.artifact_id
            and artifact.canonical_digest
            == request.expected_artifact_digest
            == candidate.artifact_digest
            and artifact.content_sha256
            == request.expected_content_sha256
            == candidate.content_sha256
            and artifact.canonical_byte_count
            == request.expected_canonical_byte_count
            == candidate.canonical_byte_count
            and artifact.admission_id == candidate.admission_id == admission.admission_id
            and artifact.admission_digest
            == candidate.admission_digest
            == admission.canonical_digest
            and artifact.event_id == candidate.event_id
            and artifact.event_digest == candidate.event_digest
            and artifact.event_type == candidate.event_type
            and artifact.event_version == candidate.event_version
            and artifact.schema_uri == candidate.schema_uri
            and artifact.outbox_entry_id == candidate.outbox_entry_id
            and artifact.outbox_entry_digest == candidate.outbox_entry_digest
            and artifact.dispatch_intent_id == candidate.dispatch_intent_id
            and artifact.dispatch_intent_digest == candidate.dispatch_intent_digest
            and artifact.plan_id == candidate.plan_id
            and artifact.plan_digest == candidate.plan_digest
            and artifact.run_id == candidate.run_id
            and artifact.run_digest == candidate.run_digest
            and artifact.step_run_id == candidate.step_run_id
            and artifact.step_run_digest == candidate.step_run_digest
            and artifact.step_id == candidate.step_id
            and artifact.attempt_id == candidate.attempt_id
            and artifact.attempt_digest == candidate.attempt_digest
            and artifact.attempt_number == candidate.attempt_number == 1
            and artifact.scope == candidate.scope
            and artifact.target_id == candidate.target_id
            and artifact.target_type == candidate.target_type
            and artifact.data_classification == candidate.data_classification
            and artifact.representation_name == candidate.representation_name
            and artifact.encoding == candidate.encoding
            and artifact.maximum_canonical_byte_count
            == candidate.maximum_canonical_byte_count
            == policy.maximum_canonical_byte_count
            and artifact.orchestration_lease_id == candidate.orchestration_lease_id
            and artifact.orchestration_lease_digest == candidate.orchestration_lease_digest
            and artifact.orchestration_fencing_token == candidate.orchestration_fencing_token
            and artifact.publication_lease_id == candidate.publication_lease_id
            and artifact.publication_lease_digest == candidate.publication_lease_digest
            and artifact.publication_fencing_token == candidate.publication_fencing_token
            and artifact.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and candidate.policy_id == policy.policy_id
            and candidate.policy_version == policy.policy_version
            and candidate.policy_digest == request.expected_policy_digest == policy.canonical_digest
            and candidate.logical_channel_id == policy.logical_channel_id
            and candidate.logical_channel_version == policy.logical_channel_version
            and candidate.event_type in policy.allowed_event_types
            and candidate.event_version in policy.allowed_event_versions
            and candidate.schema_uri in policy.allowed_schema_uris
            and candidate.data_classification in policy.allowed_data_classifications
            and candidate.representation_name == policy.representation_name
            and candidate.encoding == policy.encoding
            and candidate.delivery_semantics == policy.delivery_semantics
            and candidate.durability_required == policy.durability_required
            and candidate.ordering_key_kind == policy.ordering_key_kind
            and candidate.ordering_key_value == candidate.run_id
            and candidate.retention_class == policy.retention_class
            and candidate.state is WorkflowEventLogicalChannelBindingState.BOUND
            and not any(artifact.authority.canonical_value().values())
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_logical_channel_binding_idempotency_scope(
        scope: WorkflowScope, publisher_subject_id: str
    ) -> str:
        return canonical_digest(
            {"publisher_subject_id": publisher_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _event_logical_channel_binding_payload(
        binding: WorkflowEventLogicalChannelBinding,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], binding.canonical_value())

    @staticmethod
    def _event_logical_channel_binding_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventLogicalChannelBinding:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["bound_at"] = datetime.fromisoformat(str(values["bound_at"]))
        values["state"] = WorkflowEventLogicalChannelBindingState(str(values["state"]))
        values["authority"] = WorkflowEventLogicalChannelBindingAuthority(
            **cast(Any, values["authority"])
        )
        return WorkflowEventLogicalChannelBinding(**cast(Any, values))

    @staticmethod
    def _validate_event_logical_channel_binding_request(
        request: WorkflowEventLogicalChannelBindingRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowEventLogicalChannelBindingState.BOUND
            or candidate.attempt_number != 1
            or candidate.publisher_subject_id != request.publisher_subject_id
            or candidate.bound_at != request.requested_at
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow event logical-channel binding payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow event logical-channel binding idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError(
                "workflow event logical-channel binding request fingerprint is invalid"
            )
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow event logical-channel binding time must be aware")

    @staticmethod
    def _event_logical_channel_binding_contract_violation() -> NoReturn:
        raise WorkflowEventLogicalChannelBindingError(
            "workflow_event_logical_channel_binding_repository_contract_violation",
            "The workflow event logical-channel binding does not match its durable evidence.",
        )

    async def _transport_profile_snapshot_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportProfileSnapshotRequest,
    ) -> WorkflowTransportProfileSnapshotResult | None:
        candidate = request.candidate
        claim = await self._load_transport_profile_snapshot_claim(
            session,
            scope=candidate.scope,
            snapshotter_subject_id=candidate.snapshotter_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        snapshot_row = await session.get(
            EventPhysicalTransportProfileSnapshotModel, claim.snapshot_id
        )
        record = self._transport_profile_snapshot_record_from_claim(claim, snapshot_row)
        status = (
            WorkflowTransportProfileSnapshotStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowTransportProfileSnapshotStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowTransportProfileSnapshotResult(status, record.snapshot)

    @classmethod
    async def _load_transport_profile_snapshot_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> EventPhysicalTransportProfileSnapshotClaimModel | None:
        scope_id = cls._transport_profile_snapshot_idempotency_scope(scope, snapshotter_subject_id)
        return cast(
            EventPhysicalTransportProfileSnapshotClaimModel | None,
            await session.scalar(
                select(EventPhysicalTransportProfileSnapshotClaimModel).where(
                    EventPhysicalTransportProfileSnapshotClaimModel.idempotency_scope_id
                    == scope_id,
                    EventPhysicalTransportProfileSnapshotClaimModel.idempotency_key
                    == idempotency_key,
                    EventPhysicalTransportProfileSnapshotClaimModel.organization_id
                    == scope.organization_id,
                    EventPhysicalTransportProfileSnapshotClaimModel.environment_id
                    == scope.environment_id,
                    EventPhysicalTransportProfileSnapshotClaimModel.site_id == scope.site_id,
                    EventPhysicalTransportProfileSnapshotClaimModel.snapshotter_subject_id
                    == snapshotter_subject_id,
                )
            ),
        )

    @classmethod
    def _transport_profile_snapshot_record_from_claim(
        cls,
        claim: EventPhysicalTransportProfileSnapshotClaimModel,
        snapshot_row: EventPhysicalTransportProfileSnapshotModel | None,
    ) -> WorkflowTransportProfileSnapshotIdempotencyRecord:
        if snapshot_row is None:
            cls._transport_profile_snapshot_contract_violation()
        assert snapshot_row is not None
        snapshot = cls._transport_profile_snapshot_from_row(snapshot_row)
        scope_id = cls._transport_profile_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._transport_profile_snapshot_payload(snapshot),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != snapshot.canonical_digest
            or claim.snapshot_id != snapshot.snapshot_id
            or claim.transport_profile_id != snapshot.transport_profile_id
            or claim.transport_profile_revision != snapshot.transport_profile_revision
            or claim.source_profile_digest != snapshot.source_profile_digest
            or claim.organization_id != snapshot.scope.organization_id
            or claim.environment_id != snapshot.scope.environment_id
            or claim.site_id != snapshot.scope.site_id
            or claim.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != snapshot.captured_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._transport_profile_snapshot_contract_violation()
        return WorkflowTransportProfileSnapshotIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            snapshot=snapshot,
        )

    @classmethod
    def _transport_profile_snapshot_from_row(
        cls, row: EventPhysicalTransportProfileSnapshotModel
    ) -> EventPhysicalTransportProfileSnapshot:
        try:
            snapshot = cls._transport_profile_snapshot_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowTransportProfileSnapshotError(
                "workflow_transport_profile_snapshot_repository_contract_violation",
                "The transport profile snapshot repository contains an invalid record.",
            ) from exc
        if (
            row.snapshot_id != snapshot.snapshot_id
            or row.transport_profile_id != snapshot.transport_profile_id
            or row.transport_profile_revision != snapshot.transport_profile_revision
            or row.source_profile_digest != snapshot.source_profile_digest
            or row.deployment_release_id != snapshot.deployment_release_id
            or row.deployment_profile != snapshot.deployment_profile
            or row.organization_id != snapshot.scope.organization_id
            or row.environment_id != snapshot.scope.environment_id
            or row.site_id != snapshot.scope.site_id
            or row.transport_resource_id != snapshot.transport_resource_id
            or row.transport_resource_digest != snapshot.transport_resource_digest
            or row.transport_implementation_id != snapshot.transport_implementation_id
            or row.transport_implementation_version != snapshot.transport_implementation_version
            or row.adapter_contract_id != snapshot.adapter_contract_id
            or row.adapter_contract_version != snapshot.adapter_contract_version
            or row.adapter_contract_digest != snapshot.adapter_contract_digest
            or row.supported_event_contracts != list(snapshot.supported_event_contracts)
            or row.supported_classifications != list(snapshot.supported_classifications)
            or row.supported_representations != list(snapshot.supported_representations)
            or row.supported_encodings != list(snapshot.supported_encodings)
            or row.supported_delivery_semantics != list(snapshot.supported_delivery_semantics)
            or row.durable_delivery_supported != snapshot.durable_delivery_supported
            or row.supported_ordering_key_kinds != list(snapshot.supported_ordering_key_kinds)
            or row.supported_retention_classes != list(snapshot.supported_retention_classes)
            or row.maximum_message_byte_count != snapshot.maximum_message_byte_count
            or row.transport_encryption_required != snapshot.transport_encryption_required
            or row.restricted_network_supported != snapshot.restricted_network_supported
            or row.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or row.captured_at != snapshot.captured_at
            or row.state != snapshot.state.value
            or row.route_selection_authority_granted
            != snapshot.authority.route_selection_authorized
            or row.publication_authority_granted != snapshot.authority.publication_authorized
            or row.delivery_authority_granted != snapshot.authority.delivery_authorized
            or row.dispatch_authority_granted != snapshot.authority.dispatch_authorized
            or row.execution_authority_granted != snapshot.authority.execution_authorized
            or row.canonical_digest != snapshot.canonical_digest
            or row.payload != cls._transport_profile_snapshot_payload(snapshot)
        ):
            cls._transport_profile_snapshot_contract_violation()
        return snapshot

    @classmethod
    def _transport_profile_snapshot_model(
        cls, snapshot: EventPhysicalTransportProfileSnapshot
    ) -> EventPhysicalTransportProfileSnapshotModel:
        return EventPhysicalTransportProfileSnapshotModel(
            snapshot_id=snapshot.snapshot_id,
            transport_profile_id=snapshot.transport_profile_id,
            transport_profile_revision=snapshot.transport_profile_revision,
            source_profile_digest=snapshot.source_profile_digest,
            deployment_release_id=snapshot.deployment_release_id,
            deployment_profile=snapshot.deployment_profile,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            transport_resource_id=snapshot.transport_resource_id,
            transport_resource_digest=snapshot.transport_resource_digest,
            transport_implementation_id=snapshot.transport_implementation_id,
            transport_implementation_version=snapshot.transport_implementation_version,
            adapter_contract_id=snapshot.adapter_contract_id,
            adapter_contract_version=snapshot.adapter_contract_version,
            adapter_contract_digest=snapshot.adapter_contract_digest,
            supported_event_contracts=list(snapshot.supported_event_contracts),
            supported_classifications=list(snapshot.supported_classifications),
            supported_representations=list(snapshot.supported_representations),
            supported_encodings=list(snapshot.supported_encodings),
            supported_delivery_semantics=list(snapshot.supported_delivery_semantics),
            durable_delivery_supported=snapshot.durable_delivery_supported,
            supported_ordering_key_kinds=list(snapshot.supported_ordering_key_kinds),
            supported_retention_classes=list(snapshot.supported_retention_classes),
            maximum_message_byte_count=snapshot.maximum_message_byte_count,
            transport_encryption_required=snapshot.transport_encryption_required,
            restricted_network_supported=snapshot.restricted_network_supported,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            captured_at=snapshot.captured_at,
            state=snapshot.state.value,
            route_selection_authority_granted=(snapshot.authority.route_selection_authorized),
            publication_authority_granted=snapshot.authority.publication_authorized,
            delivery_authority_granted=snapshot.authority.delivery_authorized,
            dispatch_authority_granted=snapshot.authority.dispatch_authorized,
            execution_authority_granted=snapshot.authority.execution_authorized,
            canonical_digest=snapshot.canonical_digest,
            payload=cls._transport_profile_snapshot_payload(snapshot),
        )

    @classmethod
    def _transport_profile_snapshot_claim_model(
        cls, request: WorkflowTransportProfileSnapshotRequest
    ) -> EventPhysicalTransportProfileSnapshotClaimModel:
        snapshot = request.candidate
        scope_id = cls._transport_profile_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._transport_profile_snapshot_payload(snapshot),
        }
        digest = canonical_digest(payload)
        return EventPhysicalTransportProfileSnapshotClaimModel(
            claim_id=f"event_transport_profile_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=snapshot.canonical_digest,
            snapshot_id=snapshot.snapshot_id,
            transport_profile_id=snapshot.transport_profile_id,
            transport_profile_revision=snapshot.transport_profile_revision,
            source_profile_digest=snapshot.source_profile_digest,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @staticmethod
    def _transport_profile_snapshot_evidence_matches(
        request: WorkflowTransportProfileSnapshotRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            candidate.transport_profile_id == request.expected_source_profile_id
            and candidate.transport_profile_revision == request.expected_source_profile_revision
            and candidate.source_profile_digest == request.expected_source_profile_digest
            and candidate.scope == request.scope
            and candidate.snapshotter_subject_id == request.snapshotter_subject_id
            and candidate.captured_at == request.requested_at
            and candidate.state is EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_route_selection_authority
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _transport_profile_snapshot_idempotency_scope(
        scope: WorkflowScope, snapshotter_subject_id: str
    ) -> str:
        return canonical_digest(
            {
                "scope": scope.canonical_value(),
                "snapshotter_subject_id": snapshotter_subject_id,
            }
        )

    @staticmethod
    def _transport_profile_snapshot_payload(
        snapshot: EventPhysicalTransportProfileSnapshot,
    ) -> dict[str, Any]:
        payload = cast(dict[str, Any], snapshot.canonical_value())
        for field in (
            "supported_event_contracts",
            "supported_classifications",
            "supported_representations",
            "supported_encodings",
            "supported_delivery_semantics",
            "supported_ordering_key_kinds",
            "supported_retention_classes",
        ):
            payload[field] = list(cast(tuple[str, ...], payload[field]))
        return payload

    @staticmethod
    def _transport_profile_snapshot_to_domain(
        raw: dict[str, Any],
    ) -> EventPhysicalTransportProfileSnapshot:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["captured_at"] = datetime.fromisoformat(str(values["captured_at"]))
        values["state"] = EventPhysicalTransportProfileSnapshotState(str(values["state"]))
        values["authority"] = EventPhysicalTransportProfileSnapshotAuthority(
            **cast(Any, values["authority"])
        )
        for field in (
            "supported_event_contracts",
            "supported_classifications",
            "supported_representations",
            "supported_encodings",
            "supported_delivery_semantics",
            "supported_ordering_key_kinds",
            "supported_retention_classes",
        ):
            values[field] = tuple(cast(list[str] | tuple[str, ...], values[field]))
        return EventPhysicalTransportProfileSnapshot(**cast(Any, values))

    @staticmethod
    def _validate_transport_profile_snapshot_request(
        request: WorkflowTransportProfileSnapshotRequest,
    ) -> None:
        candidate = request.candidate
        if not PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_evidence_matches(
            request
        ):
            raise ValueError("event transport profile snapshot payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("event transport profile snapshot idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("event transport profile snapshot request fingerprint is invalid")
        if request.requested_at.tzinfo is None or candidate.captured_at.tzinfo is None:
            raise ValueError("event transport profile snapshot time must be aware")

    @staticmethod
    def _transport_profile_snapshot_contract_violation() -> NoReturn:
        raise WorkflowTransportProfileSnapshotError(
            "workflow_transport_profile_snapshot_repository_contract_violation",
            "The event transport profile snapshot does not match its durable evidence.",
        )

    async def _transport_route_snapshot_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportRouteSnapshotRequest,
    ) -> WorkflowTransportRouteSnapshotResult | None:
        candidate = request.candidate
        claim = await self._load_transport_route_snapshot_claim(
            session,
            scope=candidate.scope,
            snapshotter_subject_id=candidate.snapshotter_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        snapshot_row = await session.get(
            EventPhysicalTransportRouteSnapshotModel, claim.snapshot_id
        )
        record = self._transport_route_snapshot_record_from_claim(claim, snapshot_row)
        status = (
            WorkflowTransportRouteSnapshotStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowTransportRouteSnapshotStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowTransportRouteSnapshotResult(status, record.snapshot)

    @classmethod
    async def _load_transport_route_snapshot_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> EventPhysicalTransportRouteSnapshotClaimModel | None:
        scope_id = cls._transport_route_snapshot_idempotency_scope(scope, snapshotter_subject_id)
        return cast(
            EventPhysicalTransportRouteSnapshotClaimModel | None,
            await session.scalar(
                select(EventPhysicalTransportRouteSnapshotClaimModel).where(
                    EventPhysicalTransportRouteSnapshotClaimModel.idempotency_scope_id == scope_id,
                    EventPhysicalTransportRouteSnapshotClaimModel.idempotency_key
                    == idempotency_key,
                    EventPhysicalTransportRouteSnapshotClaimModel.organization_id
                    == scope.organization_id,
                    EventPhysicalTransportRouteSnapshotClaimModel.environment_id
                    == scope.environment_id,
                    EventPhysicalTransportRouteSnapshotClaimModel.site_id == scope.site_id,
                    EventPhysicalTransportRouteSnapshotClaimModel.snapshotter_subject_id
                    == snapshotter_subject_id,
                )
            ),
        )

    @classmethod
    def _transport_route_snapshot_record_from_claim(
        cls,
        claim: EventPhysicalTransportRouteSnapshotClaimModel,
        snapshot_row: EventPhysicalTransportRouteSnapshotModel | None,
    ) -> WorkflowTransportRouteSnapshotIdempotencyRecord:
        if snapshot_row is None:
            cls._transport_route_snapshot_contract_violation()
        snapshot = cls._transport_route_snapshot_from_row(snapshot_row)
        scope_id = cls._transport_route_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._transport_route_snapshot_payload(snapshot),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != snapshot.canonical_digest
            or claim.snapshot_id != snapshot.snapshot_id
            or claim.route_id != snapshot.route_id
            or claim.route_revision != snapshot.route_revision
            or claim.source_route_digest != snapshot.source_route_digest
            or claim.organization_id != snapshot.scope.organization_id
            or claim.environment_id != snapshot.scope.environment_id
            or claim.site_id != snapshot.scope.site_id
            or claim.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or claim.canonical_digest != canonical_digest(payload)
            or claim.payload != payload
        ):
            cls._transport_route_snapshot_contract_violation()
        return WorkflowTransportRouteSnapshotIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            snapshot=snapshot,
        )

    @classmethod
    def _transport_route_snapshot_from_row(
        cls, row: EventPhysicalTransportRouteSnapshotModel
    ) -> EventPhysicalTransportRouteSnapshot:
        try:
            snapshot = cls._transport_route_snapshot_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowTransportRouteSnapshotError(
                "workflow_transport_route_snapshot_repository_contract_violation",
                "The event transport route snapshot does not match its durable evidence.",
            ) from exc
        authority = snapshot.authority
        if (
            row.snapshot_id != snapshot.snapshot_id
            or row.route_id != snapshot.route_id
            or row.route_revision != snapshot.route_revision
            or row.route_set_id != snapshot.route_set_id
            or row.route_set_revision != snapshot.route_set_revision
            or row.selection_epoch_id != snapshot.selection_epoch_id
            or row.selection_epoch_revision != snapshot.selection_epoch_revision
            or row.source_route_digest != snapshot.source_route_digest
            or row.deployment_release_id != snapshot.deployment_release_id
            or row.deployment_profile != snapshot.deployment_profile
            or row.organization_id != snapshot.scope.organization_id
            or row.environment_id != snapshot.scope.environment_id
            or row.site_id != snapshot.scope.site_id
            or row.transport_profile_id != snapshot.transport_profile_id
            or row.transport_profile_revision != snapshot.transport_profile_revision
            or row.transport_resource_id != snapshot.transport_resource_id
            or row.transport_resource_digest != snapshot.transport_resource_digest
            or row.transport_implementation_id != snapshot.transport_implementation_id
            or row.transport_implementation_version != snapshot.transport_implementation_version
            or row.adapter_contract_id != snapshot.adapter_contract_id
            or row.adapter_contract_version != snapshot.adapter_contract_version
            or row.adapter_contract_digest != snapshot.adapter_contract_digest
            or row.route_kind != snapshot.route_kind
            or row.endpoint_set_id != snapshot.endpoint_set_id
            or row.endpoint_set_revision != snapshot.endpoint_set_revision
            or row.destination_id != snapshot.destination_id
            or row.destination_revision != snapshot.destination_revision
            or row.routing_contract_id != snapshot.routing_contract_id
            or row.routing_contract_revision != snapshot.routing_contract_revision
            or row.private_route_descriptor_commitment
            != snapshot.private_route_descriptor_commitment
            or row.transport_security_policy_id != snapshot.transport_security_policy_id
            or row.transport_security_policy_version != snapshot.transport_security_policy_version
            or row.transport_security_policy_digest != snapshot.transport_security_policy_digest
            or row.minimum_tls_version != snapshot.minimum_tls_version
            or row.server_authentication_required != snapshot.server_authentication_required
            or row.client_authentication_required != snapshot.client_authentication_required
            or row.plaintext_fallback_prohibited != snapshot.plaintext_fallback_prohibited
            or row.network_policy_id != snapshot.network_policy_id
            or row.network_policy_version != snapshot.network_policy_version
            or row.network_policy_digest != snapshot.network_policy_digest
            or row.source_zone_class != snapshot.source_zone_class
            or row.destination_zone_class != snapshot.destination_zone_class
            or row.restricted_network_enforced != snapshot.restricted_network_enforced
            or row.public_egress_prohibited != snapshot.public_egress_prohibited
            or row.proxy_mode != snapshot.proxy_mode
            or row.credential_requirement_profile_id != snapshot.credential_requirement_profile_id
            or row.credential_requirement_profile_version
            != snapshot.credential_requirement_profile_version
            or row.credential_requirement_profile_digest
            != snapshot.credential_requirement_profile_digest
            or row.authentication_mechanism_class != snapshot.authentication_mechanism_class
            or row.principal_class != snapshot.principal_class
            or row.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or row.captured_at != snapshot.captured_at
            or row.state != snapshot.state.value
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.endpoint_resolution_authority_granted != authority.endpoint_resolution_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.network_access_authority_granted != authority.network_access_authorized
            or row.readiness_probe_authority_granted != authority.readiness_probe_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.canonical_digest != snapshot.canonical_digest
            or row.payload != cls._transport_route_snapshot_payload(snapshot)
        ):
            cls._transport_route_snapshot_contract_violation()
        return snapshot

    @classmethod
    def _transport_route_snapshot_model(
        cls, snapshot: EventPhysicalTransportRouteSnapshot
    ) -> EventPhysicalTransportRouteSnapshotModel:
        authority = snapshot.authority
        return EventPhysicalTransportRouteSnapshotModel(
            snapshot_id=snapshot.snapshot_id,
            route_id=snapshot.route_id,
            route_revision=snapshot.route_revision,
            route_set_id=snapshot.route_set_id,
            route_set_revision=snapshot.route_set_revision,
            selection_epoch_id=snapshot.selection_epoch_id,
            selection_epoch_revision=snapshot.selection_epoch_revision,
            source_route_digest=snapshot.source_route_digest,
            deployment_release_id=snapshot.deployment_release_id,
            deployment_profile=snapshot.deployment_profile,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            transport_profile_id=snapshot.transport_profile_id,
            transport_profile_revision=snapshot.transport_profile_revision,
            transport_resource_id=snapshot.transport_resource_id,
            transport_resource_digest=snapshot.transport_resource_digest,
            transport_implementation_id=snapshot.transport_implementation_id,
            transport_implementation_version=snapshot.transport_implementation_version,
            adapter_contract_id=snapshot.adapter_contract_id,
            adapter_contract_version=snapshot.adapter_contract_version,
            adapter_contract_digest=snapshot.adapter_contract_digest,
            route_kind=snapshot.route_kind,
            endpoint_set_id=snapshot.endpoint_set_id,
            endpoint_set_revision=snapshot.endpoint_set_revision,
            destination_id=snapshot.destination_id,
            destination_revision=snapshot.destination_revision,
            routing_contract_id=snapshot.routing_contract_id,
            routing_contract_revision=snapshot.routing_contract_revision,
            private_route_descriptor_commitment=snapshot.private_route_descriptor_commitment,
            transport_security_policy_id=snapshot.transport_security_policy_id,
            transport_security_policy_version=snapshot.transport_security_policy_version,
            transport_security_policy_digest=snapshot.transport_security_policy_digest,
            minimum_tls_version=snapshot.minimum_tls_version,
            server_authentication_required=snapshot.server_authentication_required,
            client_authentication_required=snapshot.client_authentication_required,
            plaintext_fallback_prohibited=snapshot.plaintext_fallback_prohibited,
            network_policy_id=snapshot.network_policy_id,
            network_policy_version=snapshot.network_policy_version,
            network_policy_digest=snapshot.network_policy_digest,
            source_zone_class=snapshot.source_zone_class,
            destination_zone_class=snapshot.destination_zone_class,
            restricted_network_enforced=snapshot.restricted_network_enforced,
            public_egress_prohibited=snapshot.public_egress_prohibited,
            proxy_mode=snapshot.proxy_mode,
            credential_requirement_profile_id=snapshot.credential_requirement_profile_id,
            credential_requirement_profile_version=(
                snapshot.credential_requirement_profile_version
            ),
            credential_requirement_profile_digest=snapshot.credential_requirement_profile_digest,
            authentication_mechanism_class=snapshot.authentication_mechanism_class,
            principal_class=snapshot.principal_class,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            captured_at=snapshot.captured_at,
            state=snapshot.state.value,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=snapshot.canonical_digest,
            payload=cls._transport_route_snapshot_payload(snapshot),
        )

    @classmethod
    def _transport_route_snapshot_claim_model(
        cls, request: WorkflowTransportRouteSnapshotRequest
    ) -> EventPhysicalTransportRouteSnapshotClaimModel:
        snapshot = request.candidate
        scope_id = cls._transport_route_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._transport_route_snapshot_payload(snapshot),
        }
        digest = canonical_digest(payload)
        return EventPhysicalTransportRouteSnapshotClaimModel(
            claim_id=f"event_transport_route_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=snapshot.canonical_digest,
            snapshot_id=snapshot.snapshot_id,
            route_id=snapshot.route_id,
            route_revision=snapshot.route_revision,
            source_route_digest=snapshot.source_route_digest,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @staticmethod
    def _transport_route_snapshot_evidence_matches(
        request: WorkflowTransportRouteSnapshotRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            candidate.route_id == request.expected_source_route_id
            and candidate.route_revision == request.expected_source_route_revision
            and candidate.source_route_digest == request.expected_source_route_digest
            and candidate.scope == request.scope
            and candidate.snapshotter_subject_id == request.snapshotter_subject_id
            and candidate.captured_at == request.requested_at
            and candidate.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            and not any(candidate.authority.canonical_value().values())
        )

    @staticmethod
    def _transport_route_snapshot_idempotency_scope(
        scope: WorkflowScope, snapshotter_subject_id: str
    ) -> str:
        return canonical_digest(
            {
                "scope": scope.canonical_value(),
                "snapshotter_subject_id": snapshotter_subject_id,
            }
        )

    @staticmethod
    def _transport_route_snapshot_payload(
        snapshot: EventPhysicalTransportRouteSnapshot,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], snapshot.canonical_value())

    @staticmethod
    def _transport_route_snapshot_to_domain(
        raw: dict[str, Any],
    ) -> EventPhysicalTransportRouteSnapshot:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["captured_at"] = datetime.fromisoformat(str(values["captured_at"]))
        values["state"] = EventPhysicalTransportRouteSnapshotState(str(values["state"]))
        values["authority"] = EventPhysicalTransportRouteSnapshotAuthority(
            **cast(Any, values["authority"])
        )
        return EventPhysicalTransportRouteSnapshot(**cast(Any, values))

    @staticmethod
    def _validate_transport_route_snapshot_request(
        request: WorkflowTransportRouteSnapshotRequest,
    ) -> None:
        candidate = request.candidate
        if not PostgreSQLWorkflowPlanRepository._transport_route_snapshot_evidence_matches(request):
            raise ValueError("event transport route snapshot payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("event transport route snapshot idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("event transport route snapshot request fingerprint is invalid")
        if request.requested_at.tzinfo is None or candidate.captured_at.tzinfo is None:
            raise ValueError("event transport route snapshot time must be aware")

    @staticmethod
    def _transport_route_snapshot_contract_violation() -> NoReturn:
        raise WorkflowTransportRouteSnapshotError(
            "workflow_transport_route_snapshot_repository_contract_violation",
            "The event transport route snapshot does not match its durable evidence.",
        )

    async def _transport_compatibility_admission_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventTransportCompatibilityAdmissionRequest,
    ) -> WorkflowEventTransportCompatibilityAdmissionResult | None:
        candidate = request.candidate
        claim = await self._load_transport_compatibility_admission_claim(
            session,
            scope=candidate.scope,
            admitter_subject_id=candidate.admitter_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        admission_row = await session.get(
            WorkflowEventTransportCompatibilityAdmissionModel,
            claim.compatibility_admission_id,
        )
        record = self._transport_compatibility_admission_record_from_claim(claim, admission_row)
        status = (
            WorkflowEventTransportCompatibilityAdmissionStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowEventTransportCompatibilityAdmissionStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventTransportCompatibilityAdmissionResult(status, record.admission)

    @classmethod
    async def _load_transport_compatibility_admission_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportCompatibilityAdmissionClaimModel | None:
        scope_id = cls._transport_compatibility_admission_idempotency_scope(
            scope, admitter_subject_id
        )
        return cast(
            WorkflowEventTransportCompatibilityAdmissionClaimModel | None,
            await session.scalar(
                select(WorkflowEventTransportCompatibilityAdmissionClaimModel).where(
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.idempotency_scope_id
                    == scope_id,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.site_id == scope.site_id,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.admitter_subject_id
                    == admitter_subject_id,
                )
            ),
        )

    @classmethod
    def _transport_compatibility_admission_record_from_claim(
        cls,
        claim: WorkflowEventTransportCompatibilityAdmissionClaimModel,
        admission_row: WorkflowEventTransportCompatibilityAdmissionModel | None,
    ) -> WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord:
        if admission_row is None:
            cls._transport_compatibility_admission_contract_violation()
        assert admission_row is not None
        admission = cls._transport_compatibility_admission_from_row(admission_row)
        scope_id = cls._transport_compatibility_admission_idempotency_scope(
            admission.scope, admission.admitter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_admission": cls._transport_compatibility_admission_payload(admission),
            "result_digest": admission.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != admission.canonical_digest
            or claim.compatibility_admission_id != admission.compatibility_admission_id
            or claim.logical_channel_binding_id != admission.logical_channel_binding_id
            or claim.transport_profile_snapshot_id != admission.transport_profile_snapshot_id
            or claim.policy_digest != admission.policy_digest
            or claim.organization_id != admission.scope.organization_id
            or claim.environment_id != admission.scope.environment_id
            or claim.site_id != admission.scope.site_id
            or claim.admitter_subject_id != admission.admitter_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != admission.admitted_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._transport_compatibility_admission_contract_violation()
        return WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            admission=admission,
        )

    @classmethod
    def _transport_compatibility_admission_from_row(
        cls, row: WorkflowEventTransportCompatibilityAdmissionModel
    ) -> WorkflowEventTransportCompatibilityAdmission:
        try:
            admission = cls._transport_compatibility_admission_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventTransportCompatibilityAdmissionError(
                "workflow_transport_compatibility_admission_repository_contract_violation",
                "The workflow transport compatibility repository contains an invalid record.",
            ) from exc
        authority = admission.authority
        if (
            row.compatibility_admission_id != admission.compatibility_admission_id
            or row.logical_channel_binding_id != admission.logical_channel_binding_id
            or row.logical_channel_binding_digest != admission.logical_channel_binding_digest
            or row.transport_profile_snapshot_id != admission.transport_profile_snapshot_id
            or row.transport_profile_snapshot_digest != admission.transport_profile_snapshot_digest
            or row.transport_profile_id != admission.transport_profile_id
            or row.transport_profile_revision != admission.transport_profile_revision
            or row.policy_id != admission.policy_id
            or row.policy_version != admission.policy_version
            or row.policy_digest != admission.policy_digest
            or row.organization_id != admission.scope.organization_id
            or row.environment_id != admission.scope.environment_id
            or row.site_id != admission.scope.site_id
            or row.event_type != admission.event_type
            or row.event_version != admission.event_version
            or row.schema_uri != admission.schema_uri
            or row.data_classification != admission.data_classification
            or row.representation_name != admission.representation_name
            or row.encoding != admission.encoding
            or row.delivery_semantics != admission.delivery_semantics
            or row.durability_required != admission.durability_required
            or row.ordering_key_kind != admission.ordering_key_kind
            or row.retention_class != admission.retention_class
            or row.logical_maximum_byte_count != admission.logical_maximum_byte_count
            or row.artifact_byte_count != admission.artifact_byte_count
            or row.profile_maximum_message_byte_count
            != admission.profile_maximum_message_byte_count
            or row.admitter_subject_id != admission.admitter_subject_id
            or row.admitted_at != admission.admitted_at
            or row.state != admission.state.value
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.canonical_digest != admission.canonical_digest
            or row.payload != cls._transport_compatibility_admission_payload(admission)
        ):
            cls._transport_compatibility_admission_contract_violation()
        return admission

    @classmethod
    def _transport_compatibility_admission_model(
        cls, admission: WorkflowEventTransportCompatibilityAdmission
    ) -> WorkflowEventTransportCompatibilityAdmissionModel:
        authority = admission.authority
        return WorkflowEventTransportCompatibilityAdmissionModel(
            compatibility_admission_id=admission.compatibility_admission_id,
            logical_channel_binding_id=admission.logical_channel_binding_id,
            logical_channel_binding_digest=admission.logical_channel_binding_digest,
            transport_profile_snapshot_id=admission.transport_profile_snapshot_id,
            transport_profile_snapshot_digest=admission.transport_profile_snapshot_digest,
            transport_profile_id=admission.transport_profile_id,
            transport_profile_revision=admission.transport_profile_revision,
            policy_id=admission.policy_id,
            policy_version=admission.policy_version,
            policy_digest=admission.policy_digest,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            event_type=admission.event_type,
            event_version=admission.event_version,
            schema_uri=admission.schema_uri,
            data_classification=admission.data_classification,
            representation_name=admission.representation_name,
            encoding=admission.encoding,
            delivery_semantics=admission.delivery_semantics,
            durability_required=admission.durability_required,
            ordering_key_kind=admission.ordering_key_kind,
            retention_class=admission.retention_class,
            logical_maximum_byte_count=admission.logical_maximum_byte_count,
            artifact_byte_count=admission.artifact_byte_count,
            profile_maximum_message_byte_count=admission.profile_maximum_message_byte_count,
            admitter_subject_id=admission.admitter_subject_id,
            admitted_at=admission.admitted_at,
            state=admission.state.value,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=admission.canonical_digest,
            payload=cls._transport_compatibility_admission_payload(admission),
        )

    @classmethod
    def _transport_compatibility_admission_claim_model(
        cls, request: WorkflowEventTransportCompatibilityAdmissionRequest
    ) -> WorkflowEventTransportCompatibilityAdmissionClaimModel:
        admission = request.candidate
        scope_id = cls._transport_compatibility_admission_idempotency_scope(
            admission.scope, admission.admitter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_admission": cls._transport_compatibility_admission_payload(admission),
            "result_digest": admission.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventTransportCompatibilityAdmissionClaimModel(
            claim_id=f"wf_transport_compat_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=admission.canonical_digest,
            compatibility_admission_id=admission.compatibility_admission_id,
            logical_channel_binding_id=admission.logical_channel_binding_id,
            transport_profile_snapshot_id=admission.transport_profile_snapshot_id,
            policy_digest=admission.policy_digest,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            admitter_subject_id=admission.admitter_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _transport_compatibility_admission_evidence_matches(
        cls,
        *,
        binding_row: WorkflowEventLogicalChannelBindingModel | None,
        profile_row: EventPhysicalTransportProfileSnapshotModel | None,
        request: WorkflowEventTransportCompatibilityAdmissionRequest,
    ) -> bool:
        if binding_row is None or profile_row is None:
            return False
        binding = cls._event_logical_channel_binding_from_row(binding_row)
        profile = cls._transport_profile_snapshot_from_row(profile_row)
        candidate = request.candidate
        event_contract = f"{binding.event_type}|{binding.event_version}|{binding.schema_uri}"
        return bool(
            binding.binding_id
            == request.expected_logical_channel_binding_id
            == candidate.logical_channel_binding_id
            and binding.canonical_digest
            == request.expected_logical_channel_binding_digest
            == candidate.logical_channel_binding_digest
            and binding.state is WorkflowEventLogicalChannelBindingState.BOUND
            and not any(binding.authority.canonical_value().values())
            and profile.snapshot_id
            == request.expected_transport_profile_snapshot_id
            == candidate.transport_profile_snapshot_id
            and profile.canonical_digest
            == request.expected_transport_profile_snapshot_digest
            == candidate.transport_profile_snapshot_digest
            and profile.state is EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
            and not any(profile.authority.canonical_value().values())
            and binding.scope == profile.scope == candidate.scope
            and profile.transport_profile_id == candidate.transport_profile_id
            and profile.transport_profile_revision == candidate.transport_profile_revision
            and candidate.policy_digest == request.expected_policy_digest
            and binding.event_type == candidate.event_type
            and binding.event_version == candidate.event_version
            and binding.schema_uri == candidate.schema_uri
            and binding.data_classification == candidate.data_classification
            and binding.representation_name == candidate.representation_name
            and binding.encoding == candidate.encoding
            and binding.delivery_semantics == candidate.delivery_semantics
            and binding.durability_required == candidate.durability_required
            and binding.ordering_key_kind == candidate.ordering_key_kind
            and binding.retention_class == candidate.retention_class
            and binding.maximum_canonical_byte_count == candidate.logical_maximum_byte_count
            and binding.canonical_byte_count == candidate.artifact_byte_count
            and profile.maximum_message_byte_count == candidate.profile_maximum_message_byte_count
            and event_contract in profile.supported_event_contracts
            and binding.data_classification in profile.supported_classifications
            and binding.representation_name in profile.supported_representations
            and binding.encoding in profile.supported_encodings
            and binding.delivery_semantics in profile.supported_delivery_semantics
            and (not binding.durability_required or profile.durable_delivery_supported)
            and binding.ordering_key_kind in profile.supported_ordering_key_kinds
            and binding.retention_class in profile.supported_retention_classes
            and binding.maximum_canonical_byte_count <= profile.maximum_message_byte_count
            and binding.canonical_byte_count <= profile.maximum_message_byte_count
            and candidate.admitter_subject_id == request.admitter_subject_id
            and candidate.admitted_at == request.requested_at
            and candidate.state is WorkflowEventTransportCompatibilityAdmissionState.ADMITTED
            and not any(candidate.authority.canonical_value().values())
        )

    @staticmethod
    def _transport_compatibility_admission_idempotency_scope(
        scope: WorkflowScope, admitter_subject_id: str
    ) -> str:
        return canonical_digest(
            {
                "admitter_subject_id": admitter_subject_id,
                "scope": scope.canonical_value(),
            }
        )

    @staticmethod
    def _transport_compatibility_admission_payload(
        admission: WorkflowEventTransportCompatibilityAdmission,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], admission.canonical_value())

    @staticmethod
    def _transport_compatibility_admission_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventTransportCompatibilityAdmission:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["admitted_at"] = datetime.fromisoformat(str(values["admitted_at"]))
        values["state"] = WorkflowEventTransportCompatibilityAdmissionState(str(values["state"]))
        values["authority"] = WorkflowEventTransportCompatibilityAdmissionAuthority(
            **cast(Any, values["authority"])
        )
        return WorkflowEventTransportCompatibilityAdmission(**cast(Any, values))

    @staticmethod
    def _validate_transport_compatibility_admission_request(
        request: WorkflowEventTransportCompatibilityAdmissionRequest,
    ) -> None:
        candidate = request.candidate
        if candidate.scope != request.scope:
            raise ValueError("workflow transport compatibility scope is invalid")
        if candidate.admitter_subject_id != request.admitter_subject_id:
            raise ValueError("workflow transport compatibility admitter is invalid")
        if candidate.admitted_at != request.requested_at:
            raise ValueError("workflow transport compatibility time is invalid")
        if candidate.state is not WorkflowEventTransportCompatibilityAdmissionState.ADMITTED:
            raise ValueError("workflow transport compatibility state is invalid")
        if any(candidate.authority.canonical_value().values()):
            raise ValueError("workflow transport compatibility authority is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow transport compatibility idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow transport compatibility request fingerprint is invalid")
        if request.requested_at.tzinfo is None or candidate.admitted_at.tzinfo is None:
            raise ValueError("workflow transport compatibility time must be aware")

    @staticmethod
    def _transport_compatibility_admission_contract_violation() -> NoReturn:
        raise WorkflowEventTransportCompatibilityAdmissionError(
            "workflow_transport_compatibility_admission_repository_contract_violation",
            "The workflow transport compatibility admission does not match its durable evidence.",
        )

    async def _publication_lease_acquire_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> WorkflowOutboxPublicationLeaseAcquireResult | None:
        candidate = request.candidate
        claim = await self._load_publication_lease_claim(
            session,
            scope=candidate.scope,
            publisher_subject_id=candidate.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        record = self._publication_lease_record_from_claim(claim)
        status = (
            WorkflowOutboxPublicationLeaseAcquireStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowOutboxPublicationLeaseAcquireStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowOutboxPublicationLeaseAcquireResult(status, record.lease)

    @classmethod
    async def _load_publication_lease_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireClaimModel | None:
        return cast(
            WorkflowOutboxPublicationLeaseAcquireClaimModel | None,
            await session.scalar(
                select(WorkflowOutboxPublicationLeaseAcquireClaimModel).where(
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.idempotency_scope_id
                    == cls._publication_lease_idempotency_scope(
                        scope,
                        publisher_subject_id,
                    ),
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.site_id == scope.site_id,
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _publication_lease_record_from_claim(
        cls,
        claim: WorkflowOutboxPublicationLeaseAcquireClaimModel,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord:
        raw = claim.payload.get("result_lease")
        if not isinstance(raw, dict):
            cls._publication_lease_contract_violation()
        try:
            lease = cls._publication_lease_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_repository_contract_violation",
                "The publication lease repository contains an invalid idempotency result.",
            ) from exc
        scope_id = cls._publication_lease_idempotency_scope(
            lease.scope,
            lease.publisher_subject_id,
        )
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._publication_lease_payload(lease),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != lease.canonical_digest
            or claim.publication_lease_id != lease.publication_lease_id
            or claim.outbox_entry_id != lease.outbox_entry_id
            or claim.plan_id != lease.plan_id
            or claim.organization_id != lease.scope.organization_id
            or claim.environment_id != lease.scope.environment_id
            or claim.site_id != lease.scope.site_id
            or claim.publisher_subject_id != lease.publisher_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._publication_lease_contract_violation()
        return WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord(
            claim.request_fingerprint,
            lease,
        )

    @classmethod
    def _publication_lease_from_row(
        cls,
        row: WorkflowOutboxPublicationLeaseModel,
    ) -> WorkflowOutboxPublicationLease:
        try:
            lease = cls._publication_lease_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_repository_contract_violation",
                "The publication lease repository contains an invalid lease.",
            ) from exc
        if (
            row.publication_lease_id != lease.publication_lease_id
            or row.outbox_entry_id != lease.outbox_entry_id
            or row.outbox_entry_digest != lease.outbox_entry_digest
            or row.dispatch_intent_id != lease.dispatch_intent_id
            or row.dispatch_intent_digest != lease.dispatch_intent_digest
            or row.plan_id != lease.plan_id
            or row.plan_digest != lease.plan_digest
            or row.run_id != lease.run_id
            or row.run_digest != lease.run_digest
            or row.step_run_id != lease.step_run_id
            or row.step_run_digest != lease.step_run_digest
            or row.step_id != lease.step_id
            or row.attempt_id != lease.attempt_id
            or row.attempt_digest != lease.attempt_digest
            or row.attempt_number != lease.attempt_number
            or row.organization_id != lease.scope.organization_id
            or row.environment_id != lease.scope.environment_id
            or row.site_id != lease.scope.site_id
            or row.target_type != lease.target_type
            or row.target_id != lease.target_id
            or row.orchestration_lease_id != lease.orchestration_lease_id
            or row.orchestration_lease_digest != lease.orchestration_lease_digest
            or row.orchestration_fencing_token != lease.orchestration_fencing_token
            or row.publisher_subject_id != lease.publisher_subject_id
            or row.acquired_at != lease.acquired_at
            or row.last_heartbeat_at != lease.last_heartbeat_at
            or row.expires_at != lease.expires_at
            or row.publication_fencing_token != lease.publication_fencing_token
            or row.state != lease.state.value
            or row.version < 1
            or row.canonical_digest != lease.canonical_digest
        ):
            cls._publication_lease_contract_violation()
        return lease

    @classmethod
    def _publication_lease_model(
        cls,
        lease: WorkflowOutboxPublicationLease,
        *,
        version: int,
    ) -> WorkflowOutboxPublicationLeaseModel:
        return WorkflowOutboxPublicationLeaseModel(
            **cls._publication_lease_values(lease, version=version)
        )

    @classmethod
    def _publication_lease_values(
        cls,
        lease: WorkflowOutboxPublicationLease,
        *,
        version: int,
    ) -> dict[str, Any]:
        return {
            "publication_lease_id": lease.publication_lease_id,
            "outbox_entry_id": lease.outbox_entry_id,
            "outbox_entry_digest": lease.outbox_entry_digest,
            "dispatch_intent_id": lease.dispatch_intent_id,
            "dispatch_intent_digest": lease.dispatch_intent_digest,
            "plan_id": lease.plan_id,
            "plan_digest": lease.plan_digest,
            "run_id": lease.run_id,
            "run_digest": lease.run_digest,
            "step_run_id": lease.step_run_id,
            "step_run_digest": lease.step_run_digest,
            "step_id": lease.step_id,
            "attempt_id": lease.attempt_id,
            "attempt_digest": lease.attempt_digest,
            "attempt_number": lease.attempt_number,
            "organization_id": lease.scope.organization_id,
            "environment_id": lease.scope.environment_id,
            "site_id": lease.scope.site_id,
            "target_type": lease.target_type,
            "target_id": lease.target_id,
            "orchestration_lease_id": lease.orchestration_lease_id,
            "orchestration_lease_digest": lease.orchestration_lease_digest,
            "orchestration_fencing_token": lease.orchestration_fencing_token,
            "publisher_subject_id": lease.publisher_subject_id,
            "acquired_at": lease.acquired_at,
            "last_heartbeat_at": lease.last_heartbeat_at,
            "expires_at": lease.expires_at,
            "publication_fencing_token": lease.publication_fencing_token,
            "state": lease.state.value,
            "version": version,
            "canonical_digest": lease.canonical_digest,
            "payload": cls._publication_lease_payload(lease),
        }

    @classmethod
    def _publication_lease_claim_model(
        cls,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> WorkflowOutboxPublicationLeaseAcquireClaimModel:
        lease = request.candidate
        scope_id = cls._publication_lease_idempotency_scope(
            lease.scope,
            lease.publisher_subject_id,
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._publication_lease_payload(lease),
        }
        digest = canonical_digest(payload)
        return WorkflowOutboxPublicationLeaseAcquireClaimModel(
            claim_id=f"workflow_outbox_publication_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=lease.canonical_digest,
            publication_lease_id=lease.publication_lease_id,
            outbox_entry_id=lease.outbox_entry_id,
            plan_id=lease.plan_id,
            organization_id=lease.scope.organization_id,
            environment_id=lease.scope.environment_id,
            site_id=lease.scope.site_id,
            publisher_subject_id=lease.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _publication_lease_evidence_matches(
        cls,
        *,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        plan_row: WorkflowRunPlanModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> bool:
        if outbox_row is None or plan_row is None or orchestration_lease_row is None:
            return False
        candidate = request.candidate
        try:
            outbox = cls._dispatch_outbox_from_row(outbox_row)
            orchestration_lease = cls._lease_from_row(orchestration_lease_row)
        except (WorkflowDispatchIntentStagingError, WorkflowOrchestrationLeaseError) as exc:
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_repository_contract_violation",
                "Workflow evidence is inconsistent during publication lease acquisition.",
            ) from exc
        return bool(
            outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
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
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == candidate.plan_digest
            and plan_row.organization_id == candidate.scope.organization_id
            and plan_row.environment_id == candidate.scope.environment_id
            and plan_row.site_id == candidate.scope.site_id
            and plan_row.target_type == candidate.target_type
            and plan_row.target_id == candidate.target_id
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

    @classmethod
    def _publication_lease_mutation_evidence_matches(
        cls,
        *,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        plan_row: WorkflowRunPlanModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        request: WorkflowOutboxPublicationLeaseMutationRequest,
    ) -> bool:
        acquire_shape = WorkflowOutboxPublicationLeaseAcquireRequest(
            expected_outbox_entry_digest=request.expected_outbox_entry_digest,
            expected_orchestration_lease_id=request.expected_orchestration_lease_id,
            expected_orchestration_lease_digest=request.expected_orchestration_lease_digest,
            expected_orchestration_fencing_token=request.expected_orchestration_fencing_token,
            candidate=request.updated_lease,
            requested_at=request.requested_at,
            idempotency_key="mutation-validation",
            request_fingerprint="0" * 64,
            expected_current_lease_digest=request.expected_publication_lease_digest,
            expected_current_publication_fencing_token=(request.expected_publication_fencing_token),
        )
        return cls._publication_lease_evidence_matches(
            outbox_row=outbox_row,
            plan_row=plan_row,
            orchestration_lease_row=orchestration_lease_row,
            request=acquire_shape,
        )

    @staticmethod
    def _publication_lease_acquire_generation_matches(
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

    @staticmethod
    def _publication_lease_idempotency_scope(
        scope: WorkflowScope,
        publisher_subject_id: str,
    ) -> str:
        return canonical_digest(
            {
                "publisher_subject_id": publisher_subject_id,
                "scope": scope.canonical_value(),
            }
        )

    @staticmethod
    def _publication_lease_payload(
        lease: WorkflowOutboxPublicationLease,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], lease.canonical_value())

    @staticmethod
    def _publication_lease_to_domain(raw: dict[str, Any]) -> WorkflowOutboxPublicationLease:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["acquired_at"] = datetime.fromisoformat(str(payload["acquired_at"]))
        payload["last_heartbeat_at"] = datetime.fromisoformat(str(payload["last_heartbeat_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        payload["state"] = WorkflowOutboxPublicationLeaseState(str(payload["state"]))
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowOutboxPublicationLease(**cast(Any, payload))

    @staticmethod
    def _validate_publication_lease_acquire_request(
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowOutboxPublicationLeaseState.ACTIVE
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow outbox publication lease acquisition payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow publication lease idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow publication lease request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow publication lease acquisition time must be timezone-aware")

    @staticmethod
    def _validate_publication_lease_mutation_request(
        request: WorkflowOutboxPublicationLeaseMutationRequest,
    ) -> None:
        candidate = request.updated_lease
        if (
            candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow outbox publication lease mutation payload is unsafe")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow publication lease mutation time must be timezone-aware")

    @staticmethod
    def _publication_lease_contract_violation() -> None:
        raise WorkflowOutboxPublicationLeaseError(
            "workflow_outbox_publication_lease_repository_contract_violation",
            "The workflow outbox publication lease does not match its canonical payload.",
        )

    async def _lease_acquire_after_integrity(
        self, *, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseAcquireResult:
        async with self._sessions() as session:
            replay = await self._lease_acquire_replay(session, request=request)
            if replay is not None:
                return replay
        latest = await self.get_lease_by_plan_id(plan_id=request.candidate.plan_id)
        return WorkflowLeaseAcquireResult(WorkflowLeaseAcquireStatus.CONTENDED, latest)

    async def _lease_acquire_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowLeaseAcquireRequest,
    ) -> WorkflowLeaseAcquireResult | None:
        candidate = request.candidate
        claim = await self._load_lease_claim(
            session,
            operation="acquire",
            scope=candidate.scope,
            worker_subject_id=candidate.worker_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        record = self._lease_record_from_claim(claim)
        status = (
            WorkflowLeaseAcquireStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowLeaseAcquireStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowLeaseAcquireResult(status, record.lease)

    @classmethod
    async def _load_lease_claim(
        cls,
        session: AsyncSession,
        *,
        operation: str,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowLeaseIdempotencyModel | None:
        return cast(
            WorkflowLeaseIdempotencyModel | None,
            await session.scalar(
                select(WorkflowLeaseIdempotencyModel).where(
                    WorkflowLeaseIdempotencyModel.operation == operation,
                    WorkflowLeaseIdempotencyModel.idempotency_scope_id
                    == cls._lease_idempotency_scope(scope, worker_subject_id),
                    WorkflowLeaseIdempotencyModel.idempotency_key == idempotency_key,
                    WorkflowLeaseIdempotencyModel.organization_id == scope.organization_id,
                    WorkflowLeaseIdempotencyModel.environment_id == scope.environment_id,
                    WorkflowLeaseIdempotencyModel.site_id == scope.site_id,
                    WorkflowLeaseIdempotencyModel.worker_subject_id == worker_subject_id,
                )
            ),
        )

    @classmethod
    def _lease_record_from_claim(
        cls, claim: WorkflowLeaseIdempotencyModel
    ) -> WorkflowLeaseAcquireIdempotencyRecord:
        raw = claim.payload.get("result_lease")
        if not isinstance(raw, dict):
            cls._lease_contract_violation()
        try:
            lease = cls._lease_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_repository_contract_violation",
                "The workflow lease repository contains an invalid idempotency result.",
            ) from exc
        expected_payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": claim.idempotency_scope_id,
            "operation": claim.operation,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": claim.result_digest,
            "result_lease": cls._lease_payload(lease),
        }
        if (
            claim.operation != "acquire"
            or claim.lease_id != lease.lease_id
            or claim.plan_id != lease.plan_id
            or claim.result_digest != lease.canonical_digest
            or claim.organization_id != lease.scope.organization_id
            or claim.environment_id != lease.scope.environment_id
            or claim.site_id != lease.scope.site_id
            or claim.worker_subject_id != lease.worker_subject_id
            or claim.idempotency_scope_id
            != cls._lease_idempotency_scope(lease.scope, lease.worker_subject_id)
            or claim.payload != expected_payload
            or claim.canonical_digest != canonical_digest(expected_payload)
        ):
            cls._lease_contract_violation()
        return WorkflowLeaseAcquireIdempotencyRecord(claim.request_fingerprint, lease)

    @classmethod
    def _lease_from_row(cls, row: WorkflowOrchestrationLeaseModel) -> WorkflowOrchestrationLease:
        try:
            lease = cls._lease_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_repository_contract_violation",
                "The workflow lease repository contains an invalid lease.",
            ) from exc
        if (
            row.lease_id != lease.lease_id
            or row.plan_id != lease.plan_id
            or row.plan_digest != lease.plan_digest
            or row.organization_id != lease.scope.organization_id
            or row.environment_id != lease.scope.environment_id
            or row.site_id != lease.scope.site_id
            or row.target_type != lease.target_type
            or row.target_id != lease.target_id
            or row.worker_subject_id != lease.worker_subject_id
            or row.acquired_at != lease.acquired_at
            or row.last_heartbeat_at != lease.last_heartbeat_at
            or row.expires_at != lease.expires_at
            or row.fencing_token != lease.fencing_token
            or row.state != lease.state.value
            or row.version < 1
            or row.canonical_digest != lease.canonical_digest
        ):
            cls._lease_contract_violation()
        return lease

    @staticmethod
    def _lease_contract_violation() -> None:
        raise WorkflowOrchestrationLeaseError(
            "workflow_lease_repository_contract_violation",
            "The workflow lease record does not match its canonical payload.",
        )

    @classmethod
    def _lease_model(
        cls, lease: WorkflowOrchestrationLease, *, version: int
    ) -> WorkflowOrchestrationLeaseModel:
        return WorkflowOrchestrationLeaseModel(**cls._lease_values(lease, version=version))

    @classmethod
    def _lease_values(cls, lease: WorkflowOrchestrationLease, *, version: int) -> dict[str, Any]:
        return {
            "lease_id": lease.lease_id,
            "plan_id": lease.plan_id,
            "plan_digest": lease.plan_digest,
            "organization_id": lease.scope.organization_id,
            "environment_id": lease.scope.environment_id,
            "site_id": lease.scope.site_id,
            "target_type": lease.target_type,
            "target_id": lease.target_id,
            "worker_subject_id": lease.worker_subject_id,
            "acquired_at": lease.acquired_at,
            "last_heartbeat_at": lease.last_heartbeat_at,
            "expires_at": lease.expires_at,
            "fencing_token": lease.fencing_token,
            "state": lease.state.value,
            "version": version,
            "canonical_digest": lease.canonical_digest,
            "payload": cls._lease_payload(lease),
        }

    @classmethod
    def _lease_claim_model(
        cls, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseIdempotencyModel:
        lease = request.candidate
        scope_id = cls._lease_idempotency_scope(lease.scope, lease.worker_subject_id)
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "operation": "acquire",
            "request_fingerprint": request.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._lease_payload(lease),
        }
        digest = canonical_digest(payload)
        return WorkflowLeaseIdempotencyModel(
            record_id=f"workflow_lease_idem_{sha256(digest.encode()).hexdigest()[:32]}",
            operation="acquire",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=lease.canonical_digest,
            lease_id=lease.lease_id,
            plan_id=lease.plan_id,
            organization_id=lease.scope.organization_id,
            environment_id=lease.scope.environment_id,
            site_id=lease.scope.site_id,
            worker_subject_id=lease.worker_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @staticmethod
    def _lease_idempotency_scope(scope: WorkflowScope, worker_subject_id: str) -> str:
        return canonical_digest(
            {"scope": scope.canonical_value(), "worker_subject_id": worker_subject_id}
        )

    @staticmethod
    def _lease_plan_matches(
        row: WorkflowRunPlanModel | None,
        candidate: WorkflowOrchestrationLease,
        expected_plan_digest: str,
    ) -> bool:
        return bool(
            row is not None
            and row.state == WorkflowPlanState.PLANNED.value
            and row.canonical_digest == expected_plan_digest == candidate.plan_digest
            and row.organization_id == candidate.scope.organization_id
            and row.environment_id == candidate.scope.environment_id
            and row.site_id == candidate.scope.site_id
            and row.target_type == candidate.target_type
            and row.target_id == candidate.target_id
        )

    @staticmethod
    def _valid_lease_takeover(
        current: WorkflowOrchestrationLease | None,
        candidate: WorkflowOrchestrationLease,
        request: WorkflowLeaseAcquireRequest,
    ) -> bool:
        if current is None:
            return (
                request.expected_current_lease_digest is None
                and request.expected_current_fencing_token is None
                and candidate.fencing_token == 1
            )
        return (
            current.canonical_digest == request.expected_current_lease_digest
            and current.fencing_token == request.expected_current_fencing_token
            and current.effective_state(requested_at=request.requested_at)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and candidate.fencing_token == current.fencing_token + 1
        )

    @staticmethod
    def _valid_lease_mutation(
        current: WorkflowOrchestrationLease,
        candidate: WorkflowOrchestrationLease,
        request: WorkflowLeaseMutationRequest,
    ) -> bool:
        return (
            current.lease_id == request.expected_lease_id
            and current.canonical_digest == request.expected_lease_digest
            and current.fencing_token == request.expected_fencing_token
            and current.worker_subject_id == request.worker_subject_id
            and current.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and candidate.lease_id == current.lease_id
            and candidate.plan_id == current.plan_id
            and candidate.plan_digest == current.plan_digest
            and candidate.scope == current.scope
            and candidate.target_id == current.target_id
            and candidate.target_type == current.target_type
            and candidate.worker_subject_id == current.worker_subject_id
            and candidate.acquired_at == current.acquired_at
            and candidate.fencing_token == current.fencing_token
        )

    @classmethod
    def _lease_payload(cls, lease: WorkflowOrchestrationLease) -> dict[str, Any]:
        return cast(dict[str, Any], cls._normalize(lease.canonical_value()))

    @staticmethod
    def _lease_to_domain(raw: dict[str, Any]) -> WorkflowOrchestrationLease:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["acquired_at"] = datetime.fromisoformat(str(payload["acquired_at"]))
        payload["last_heartbeat_at"] = datetime.fromisoformat(str(payload["last_heartbeat_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        payload["state"] = WorkflowOrchestrationLeaseState(str(payload["state"]))
        return WorkflowOrchestrationLease(**cast(Any, payload))

    async def _cancellation_result_after_integrity_conflict(
        self,
        *,
        request: WorkflowPlanCancellationRequest,
    ) -> WorkflowPlanCancellationResult:
        async with self._sessions() as session:
            replay = await self._cancellation_replay_result(session, request=request)
            if replay is not None:
                return replay
        current = await self.get_by_id(plan_id=request.cancelled_plan.plan_id)
        return WorkflowPlanCancellationResult(
            WorkflowPlanCancellationStatus.STATE_CONFLICT
            if current is not None
            else WorkflowPlanCancellationStatus.NOT_FOUND,
            current,
        )

    async def _cancellation_replay_result(
        self,
        session: AsyncSession,
        *,
        request: WorkflowPlanCancellationRequest,
    ) -> WorkflowPlanCancellationResult | None:
        candidate = request.cancelled_plan
        claim = await self._load_claim(
            session,
            operation="cancel",
            scope=candidate.scope,
            subject_id=request.actor_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        plan = self._plan_from_claim(claim, expected_operation="cancel")
        status = (
            WorkflowPlanCancellationStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowPlanCancellationStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowPlanCancellationResult(status, plan)

    async def _replay_result(
        self,
        session: AsyncSession,
        *,
        plan: WorkflowRunPlan,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowPlanMutationResult | None:
        claim = await self._load_claim(
            session,
            operation="create",
            scope=plan.scope,
            subject_id=plan.creator_subject_id,
            idempotency_key=idempotency_key,
        )
        if claim is None:
            return None
        claimed_plan = self._plan_from_claim(claim, expected_operation="create")
        status = (
            WorkflowPlanMutationStatus.REPLAY
            if claim.request_fingerprint == request_fingerprint
            else WorkflowPlanMutationStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowPlanMutationResult(status, claimed_plan)

    @classmethod
    async def _load_claim(
        cls,
        session: AsyncSession,
        *,
        operation: str,
        scope: WorkflowScope,
        subject_id: str,
        idempotency_key: str,
    ) -> WorkflowIdempotencyModel | None:
        return cast(
            WorkflowIdempotencyModel | None,
            await session.scalar(
                select(WorkflowIdempotencyModel).where(
                    WorkflowIdempotencyModel.operation == operation,
                    WorkflowIdempotencyModel.idempotency_scope_id
                    == cls._idempotency_scope(scope, subject_id),
                    WorkflowIdempotencyModel.idempotency_key == idempotency_key,
                    WorkflowIdempotencyModel.organization_id == scope.organization_id,
                    WorkflowIdempotencyModel.environment_id == scope.environment_id,
                    WorkflowIdempotencyModel.site_id == scope.site_id,
                    WorkflowIdempotencyModel.creator_subject_id == subject_id,
                )
            ),
        )

    @classmethod
    def _plan_from_claim(
        cls,
        claim: WorkflowIdempotencyModel,
        *,
        expected_operation: str,
    ) -> WorkflowRunPlan:
        raw = claim.payload.get("result_plan")
        if not isinstance(raw, dict):
            cls._contract_violation()
        try:
            plan = cls._to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_repository_contract_violation",
                "The workflow repository contains an invalid idempotency result.",
            ) from exc
        if (
            claim.operation != expected_operation
            or claim.plan_id != plan.plan_id
            or claim.result_digest != plan.canonical_digest
            or claim.organization_id != plan.scope.organization_id
            or claim.environment_id != plan.scope.environment_id
            or claim.site_id != plan.scope.site_id
            or claim.creator_subject_id
            != (
                plan.creator_subject_id
                if expected_operation == "create"
                else plan.transition_history[-1].actor_subject_id
            )
            or claim.idempotency_scope_id
            != cls._idempotency_scope(
                plan.scope,
                plan.creator_subject_id
                if expected_operation == "create"
                else plan.transition_history[-1].actor_subject_id,
            )
        ):
            cls._contract_violation()
        return plan

    @classmethod
    def _plan_from_row(
        cls,
        row: WorkflowRunPlanModel,
        transitions: tuple[WorkflowPlanTransition, ...],
    ) -> WorkflowRunPlan:
        try:
            plan = cls._to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_repository_contract_violation",
                "The workflow repository contains an invalid run plan.",
            ) from exc
        if (
            row.plan_id != plan.plan_id
            or row.state != plan.state.value
            or row.definition_id != plan.definition_id
            or row.definition_version != plan.definition_version
            or row.definition_digest != plan.definition_digest
            or row.organization_id != plan.scope.organization_id
            or row.environment_id != plan.scope.environment_id
            or row.site_id != plan.scope.site_id
            or row.creator_subject_id != plan.creator_subject_id
            or row.target_type != plan.target_type
            or row.target_id != plan.target_id
            or row.canonical_input_digest != plan.canonical_input_digest
            or row.created_at != plan.created_at
            or row.canonical_digest != plan.canonical_digest
            or plan.transition_history != transitions
            or row.state_version != len(transitions) + 1
            or row.updated_at != (transitions[-1].occurred_at if transitions else plan.created_at)
        ):
            cls._contract_violation()
        return plan

    @staticmethod
    def _contract_violation() -> None:
        raise WorkflowPlanningError(
            "workflow_repository_contract_violation",
            "The workflow repository record does not match its canonical payload.",
        )

    @classmethod
    def _plan_model(cls, plan: WorkflowRunPlan) -> WorkflowRunPlanModel:
        updated_at = (
            plan.transition_history[-1].occurred_at if plan.transition_history else plan.created_at
        )
        return WorkflowRunPlanModel(
            plan_id=plan.plan_id,
            state=plan.state.value,
            definition_id=plan.definition_id,
            definition_version=plan.definition_version,
            definition_digest=plan.definition_digest,
            organization_id=plan.scope.organization_id,
            environment_id=plan.scope.environment_id,
            site_id=plan.scope.site_id,
            creator_subject_id=plan.creator_subject_id,
            target_type=plan.target_type,
            target_id=plan.target_id,
            canonical_input_digest=plan.canonical_input_digest,
            created_at=plan.created_at,
            updated_at=updated_at,
            state_version=len(plan.transition_history) + 1,
            canonical_digest=plan.canonical_digest,
            payload=cls._plan_payload(plan),
        )

    @classmethod
    def _transition_model(
        cls,
        plan_id: str,
        transition: WorkflowPlanTransition,
        *,
        sequence: int,
    ) -> WorkflowPlanTransitionModel:
        return WorkflowPlanTransitionModel(
            transition_id=transition.transition_id,
            plan_id=plan_id,
            sequence=sequence,
            from_state=transition.prior_state.value,
            to_state=transition.new_state.value,
            actor_subject_id=transition.actor_subject_id,
            organization_id=transition.scope.organization_id,
            environment_id=transition.scope.environment_id,
            site_id=transition.scope.site_id,
            target_type=transition.target_type,
            target_id=transition.target_id,
            reason_digest=transition.reason_digest,
            correlation_id=transition.correlation_id,
            occurred_at=transition.occurred_at,
            canonical_digest=transition.canonical_digest,
            payload=cast(dict[str, Any], cls._normalize(asdict(transition))),
        )

    @classmethod
    def _cancellation_idempotency_model(
        cls,
        request: WorkflowPlanCancellationRequest,
        *,
        operation: str,
        scope_id: str,
    ) -> WorkflowIdempotencyModel:
        plan = request.cancelled_plan
        transition = plan.transition_history[-1]
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "operation": operation,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": plan.canonical_digest,
            "result_plan": cls._plan_payload(plan),
            "transition_digest": transition.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowIdempotencyModel(
            record_id=f"workflow_idem_{sha256(digest.encode()).hexdigest()[:32]}",
            operation=operation,
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=plan.canonical_digest,
            plan_id=plan.plan_id,
            organization_id=plan.scope.organization_id,
            environment_id=plan.scope.environment_id,
            site_id=plan.scope.site_id,
            creator_subject_id=request.actor_subject_id,
            created_at=transition.occurred_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _idempotency_model(
        cls,
        plan: WorkflowRunPlan,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowIdempotencyModel:
        scope_id = cls._idempotency_scope(plan.scope, plan.creator_subject_id)
        payload: dict[str, Any] = {
            "idempotency_key": idempotency_key,
            "idempotency_scope_id": scope_id,
            "operation": "create",
            "request_fingerprint": request_fingerprint,
            "result_digest": plan.canonical_digest,
            "result_plan": cls._plan_payload(plan),
        }
        digest = canonical_digest(payload)
        return WorkflowIdempotencyModel(
            record_id=f"workflow_idem_{sha256(digest.encode()).hexdigest()[:32]}",
            operation="create",
            idempotency_scope_id=scope_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            result_digest=plan.canonical_digest,
            plan_id=plan.plan_id,
            organization_id=plan.scope.organization_id,
            environment_id=plan.scope.environment_id,
            site_id=plan.scope.site_id,
            creator_subject_id=plan.creator_subject_id,
            created_at=plan.created_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _plan_payload(cls, plan: WorkflowRunPlan) -> dict[str, Any]:
        return cast(dict[str, Any], cls._normalize(asdict(plan)))

    @staticmethod
    def _idempotency_scope(scope: WorkflowScope, creator_subject_id: str) -> str:
        return canonical_digest(
            {"creator_subject_id": creator_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _valid_cancellation(
        *,
        current: WorkflowRunPlan,
        candidate: WorkflowRunPlan,
        actor_subject_id: str,
    ) -> bool:
        if (
            candidate.state is not WorkflowPlanState.CANCELLED
            or len(candidate.transition_history) != 1
        ):
            return False
        transition = candidate.transition_history[0]
        return (
            transition.actor_subject_id == actor_subject_id
            and transition.prior_state is WorkflowPlanState.PLANNED
            and transition.new_state is WorkflowPlanState.CANCELLED
            and current.plan_id == candidate.plan_id
            and current.definition_id == candidate.definition_id
            and current.definition_version == candidate.definition_version
            and current.definition_digest == candidate.definition_digest
            and current.scope == candidate.scope
            and current.target_id == candidate.target_id
            and current.target_type == candidate.target_type
            and current.canonical_input_digest == candidate.canonical_input_digest
            and current.creator_subject_id == candidate.creator_subject_id
            and current.created_at == candidate.created_at
            and current.steps == candidate.steps
            and current.durable == candidate.durable
            and current.authority == candidate.authority
            and current.safety_notice == candidate.safety_notice
            and not current.transition_history
        )

    @classmethod
    async def _load_transitions(
        cls,
        session: AsyncSession,
        plan_ids: tuple[str, ...],
    ) -> dict[str, tuple[WorkflowPlanTransition, ...]]:
        if not plan_ids:
            return {}
        rows = (
            await session.scalars(
                select(WorkflowPlanTransitionModel)
                .where(WorkflowPlanTransitionModel.plan_id.in_(plan_ids))
                .order_by(
                    WorkflowPlanTransitionModel.plan_id,
                    WorkflowPlanTransitionModel.sequence,
                )
            )
        ).all()
        grouped: dict[str, list[WorkflowPlanTransition]] = {}
        for row in rows:
            grouped.setdefault(row.plan_id, []).append(cls._transition_from_row(row))
        return {plan_id: tuple(items) for plan_id, items in grouped.items()}

    @classmethod
    def _transition_from_row(cls, row: WorkflowPlanTransitionModel) -> WorkflowPlanTransition:
        try:
            transition = cls._transition_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_repository_contract_violation",
                "The workflow repository contains an invalid transition.",
            ) from exc
        if (
            row.transition_id != transition.transition_id
            or row.sequence != 1
            or row.from_state != transition.prior_state.value
            or row.to_state != transition.new_state.value
            or row.actor_subject_id != transition.actor_subject_id
            or row.organization_id != transition.scope.organization_id
            or row.environment_id != transition.scope.environment_id
            or row.site_id != transition.scope.site_id
            or row.target_type != transition.target_type
            or row.target_id != transition.target_id
            or row.reason_digest != transition.reason_digest
            or row.correlation_id != transition.correlation_id
            or row.occurred_at != transition.occurred_at
            or row.canonical_digest != transition.canonical_digest
        ):
            cls._contract_violation()
        return transition

    @staticmethod
    def _normalize(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {
                str(key): PostgreSQLWorkflowPlanRepository._normalize(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [PostgreSQLWorkflowPlanRepository._normalize(item) for item in value]
        return value

    @staticmethod
    def _to_domain(raw: dict[str, Any]) -> WorkflowRunPlan:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["state"] = WorkflowPlanState(str(payload["state"]))
        payload["steps"] = tuple(
            WorkflowPlanStep(
                step_id=str(item["step_id"]),
                ordinal=int(item["ordinal"]),
                kind=WorkflowStepKind(str(item["kind"])),
                capability_class=WorkflowCapabilityClass(str(item["capability_class"])),
                state=WorkflowPlanStepState(str(item["state"])),
            )
            for item in payload["steps"]
        )
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        payload["transition_history"] = tuple(
            PostgreSQLWorkflowPlanRepository._transition_to_domain(cast(dict[str, Any], item))
            for item in payload.get("transition_history", ())
        )
        return WorkflowRunPlan(**cast(Any, payload))

    @staticmethod
    def _transition_to_domain(raw: dict[str, Any]) -> WorkflowPlanTransition:
        payload = dict(raw)
        payload["prior_state"] = WorkflowPlanState(str(payload["prior_state"]))
        payload["new_state"] = WorkflowPlanState(str(payload["new_state"]))
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["occurred_at"] = datetime.fromisoformat(str(payload["occurred_at"]))
        return WorkflowPlanTransition(**cast(Any, payload))
