from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from atlas.core.audit import AuditRecord
from atlas.core.persistence.models import (
    WorkflowIdempotencyModel,
    WorkflowPlanTransitionModel,
)
from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowAccessContext,
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationStatus,
    WorkflowPlanningService,
)
from atlas.modules.workflows.domain import (
    WorkflowPlanState,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_registry,
)

NOW = datetime(2026, 8, 13, 15, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")
TARGET_ID = "asset.storage.lab.primary"


class _AuditSink:
    async def record(self, event: AuditRecord) -> None:
        return None


class _ScalarResult:
    def __init__(self, values: Iterable[object]) -> None:
        self._values = list(values)

    def all(self) -> list[object]:
        return self._values


class _RowcountResult:
    rowcount = 1


class _FakeSession:
    def __init__(
        self,
        *,
        scalar_values: Iterable[object | None] = (),
        scalar_batches: Iterable[Iterable[object]] = (),
    ) -> None:
        self.scalar_values = list(scalar_values)
        self.scalar_batches = [list(batch) for batch in scalar_batches]
        self.added: list[object] = []
        self.statements: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    async def scalar(self, statement: object) -> object | None:
        self.statements.append(statement)
        return self.scalar_values.pop(0)

    async def scalars(self, statement: object) -> _ScalarResult:
        self.statements.append(statement)
        return _ScalarResult(self.scalar_batches.pop(0))

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def execute(self, statement: object) -> _RowcountResult:
        self.statements.append(statement)
        return _RowcountResult()

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _repository(session: _FakeSession) -> PostgreSQLWorkflowPlanRepository:
    def factory() -> AsyncSession:
        return cast(AsyncSession, session)

    return PostgreSQLWorkflowPlanRepository(
        engine=cast(AsyncEngine, object()),
        session_factory=factory,
    )


def _context(*, requested_at: datetime) -> WorkflowAccessContext:
    return WorkflowAccessContext(
        subject_id="subject.operator",
        role_ids=frozenset({"role.infrastructure-operator"}),
        actor_type="human",
        authentication_method="browser_session",
        assurance_level="single_factor",
        scope=SCOPE,
        authorized_target_ids=frozenset({TARGET_ID}),
        correlation_id="correlation.workflow.postgres",
        decision_id="decision.workflow.postgres",
        requested_at=requested_at,
    )


async def _plan_pair() -> tuple[WorkflowRunPlan, WorkflowRunPlan]:
    memory = InMemoryWorkflowPlanRepository()
    service = WorkflowPlanningService(
        registry=code_owned_workflow_registry(),
        repository=memory,
        audit_sink=_AuditSink(),
    )
    planned = await service.create_plan(
        definition_id="workflow.evidence-grounded-query",
        definition_version=1,
        target_id=TARGET_ID,
        inputs={"question": "What is the current storage health?"},
        idempotency_key="workflow-postgres-plan-create",
        context=_context(requested_at=NOW),
    )
    cancelled = await service.cancel_plan(
        plan_id=planned.plan_id,
        reason="The assessment is no longer required.",
        acknowledge_no_external_undo=True,
        idempotency_key="workflow-postgres-plan-cancel",
        context=_context(requested_at=NOW + timedelta(minutes=1)),
    )
    return planned, cancelled


def _request(
    planned: WorkflowRunPlan,
    cancelled: WorkflowRunPlan,
    *,
    fingerprint: str = "f" * 64,
) -> WorkflowPlanCancellationRequest:
    return WorkflowPlanCancellationRequest(
        expected_plan_digest=planned.canonical_digest,
        cancelled_plan=cancelled,
        actor_subject_id="subject.operator",
        idempotency_key="workflow-postgres-plan-cancel",
        request_fingerprint=fingerprint,
    )


@pytest.mark.asyncio
async def test_cancel_persists_optimistic_state_transition_and_claim_in_one_commit() -> None:
    planned, cancelled = await _plan_pair()
    plan_row = PostgreSQLWorkflowPlanRepository._plan_model(planned)
    session = _FakeSession(
        scalar_values=(None, plan_row, None),
        scalar_batches=((),),
    )

    result = await _repository(session).cancel(_request(planned, cancelled))

    assert result.status is WorkflowPlanCancellationStatus.CANCELLED
    assert result.plan == cancelled
    assert session.commits == 1
    assert session.rollbacks == 0
    assert [type(item) for item in session.added] == [
        WorkflowPlanTransitionModel,
        WorkflowIdempotencyModel,
    ]
    transition = cast(WorkflowPlanTransitionModel, session.added[0])
    claim = cast(WorkflowIdempotencyModel, session.added[1])
    assert transition.plan_id == planned.plan_id
    assert transition.from_state == WorkflowPlanState.PLANNED.value
    assert transition.to_state == WorkflowPlanState.CANCELLED.value
    assert transition.sequence == 1
    assert claim.operation == "cancel"
    assert claim.plan_id == planned.plan_id
    assert claim.result_digest == cancelled.canonical_digest
    assert claim.payload["transition_digest"] == transition.canonical_digest
    assert any(statement.__class__.__name__ == "Update" for statement in session.statements)


@pytest.mark.asyncio
async def test_cancel_replays_exact_claim_and_rejects_changed_fingerprint_without_writes() -> None:
    planned, cancelled = await _plan_pair()
    request = _request(planned, cancelled)
    claim = PostgreSQLWorkflowPlanRepository._cancellation_idempotency_model(
        request,
        operation="cancel",
        scope_id=PostgreSQLWorkflowPlanRepository._idempotency_scope(
            SCOPE,
            request.actor_subject_id,
        ),
    )

    replay_session = _FakeSession(scalar_values=(claim,))
    replay = await _repository(replay_session).cancel(request)
    assert replay.status is WorkflowPlanCancellationStatus.REPLAY
    assert replay.plan == cancelled
    assert replay_session.commits == 0
    assert replay_session.added == []

    conflict_session = _FakeSession(scalar_values=(claim,))
    conflict = await _repository(conflict_session).cancel(
        _request(planned, cancelled, fingerprint=canonical_digest({"changed": True}))
    )
    assert conflict.status is WorkflowPlanCancellationStatus.IDEMPOTENCY_CONFLICT
    assert conflict.plan == cancelled
    assert conflict_session.commits == 0
    assert conflict_session.added == []


@pytest.mark.asyncio
async def test_cancelled_plan_round_trip_requires_the_separate_transition_history() -> None:
    _, cancelled = await _plan_pair()
    model = PostgreSQLWorkflowPlanRepository._plan_model(cancelled)
    transition_model = PostgreSQLWorkflowPlanRepository._transition_model(
        cancelled.plan_id,
        cancelled.transition_history[0],
        sequence=1,
    )

    transition = PostgreSQLWorkflowPlanRepository._transition_from_row(transition_model)
    restored = PostgreSQLWorkflowPlanRepository._plan_from_row(model, (transition,))

    assert restored == cancelled
    assert restored.transition_history == (transition,)
    assert restored.canonical_digest == canonical_digest(restored.digest_payload())
