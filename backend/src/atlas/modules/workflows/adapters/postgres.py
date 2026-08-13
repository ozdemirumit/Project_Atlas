from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    WorkflowIdempotencyModel,
    WorkflowPlanTransitionModel,
    WorkflowRunPlanModel,
)
from atlas.modules.workflows.application import (
    WorkflowPlanCancellationIdempotencyRecord,
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationResult,
    WorkflowPlanCancellationStatus,
    WorkflowPlanIdempotencyRecord,
    WorkflowPlanMutationResult,
    WorkflowPlanMutationStatus,
    WorkflowPlanningError,
)
from atlas.modules.workflows.domain import (
    WorkflowCapabilityClass,
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

    async def close(self) -> None:
        await self._engine.dispose()

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
