from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Any, cast

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
    WorkflowExecutionRunModel,
    WorkflowExecutionStepRunModel,
    WorkflowIdempotencyModel,
    WorkflowLeaseIdempotencyModel,
    WorkflowOrchestrationLeaseModel,
    WorkflowPlanTransitionModel,
    WorkflowRunMaterializationClaimModel,
    WorkflowRunPlanModel,
)
from atlas.modules.workflows.application import (
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
from atlas.modules.workflows.domain import (
    WorkflowCapabilityClass,
    WorkflowExecutionRun,
    WorkflowExecutionRunState,
    WorkflowExecutionStepRun,
    WorkflowExecutionStepRunState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOrchestrationLeaseState,
    WorkflowPlanAuthority,
    WorkflowPlanState,
    WorkflowPlanStep,
    WorkflowPlanStepState,
    WorkflowPlanTransition,
    WorkflowRunPlan,
    WorkflowScope,
    WorkflowStepKind,
    canonical_digest,
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
