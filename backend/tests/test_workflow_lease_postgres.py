from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from atlas.core.audit import AuditRecord
from atlas.core.persistence.models import (
    WorkflowLeaseIdempotencyModel,
    WorkflowOrchestrationLeaseModel,
)
from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowAccessContext,
    WorkflowLeaseAcquireRequest,
    WorkflowLeaseAcquireStatus,
    WorkflowLeaseMutationRequest,
    WorkflowLeaseMutationStatus,
    WorkflowPlanningService,
)
from atlas.modules.workflows.domain import (
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseState,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_registry,
)

NOW = datetime(2026, 8, 13, 18, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")
TARGET_ID = "asset.storage.lab.primary"
WORKER_ID = "workload.atlas.workflow-worker-01"


class _AuditSink:
    async def record(self, event: AuditRecord) -> None:
        return None


class _RowcountResult:
    rowcount = 1


class _FakeSession:
    def __init__(self, *, scalar_values: Iterable[object | None] = ()) -> None:
        self.scalar_values = list(scalar_values)
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


def _human_context() -> WorkflowAccessContext:
    return WorkflowAccessContext(
        subject_id="subject.operator",
        role_ids=frozenset({"role.infrastructure-operator"}),
        actor_type="human",
        authentication_method="browser_session",
        assurance_level="single_factor",
        scope=SCOPE,
        authorized_target_ids=frozenset({TARGET_ID}),
        correlation_id="correlation.workflow-lease.postgres",
        decision_id="decision.workflow-lease.postgres",
        requested_at=NOW,
    )


async def _plan() -> WorkflowRunPlan:
    service = WorkflowPlanningService(
        registry=code_owned_workflow_registry(),
        repository=InMemoryWorkflowPlanRepository(),
        audit_sink=_AuditSink(),
    )
    return await service.create_plan(
        definition_id="workflow.evidence-grounded-query",
        definition_version=1,
        target_id=TARGET_ID,
        inputs={"question": "What is the current storage health?"},
        idempotency_key="workflow-lease-postgres-plan",
        context=_human_context(),
    )


def _lease(
    plan: WorkflowRunPlan,
    *,
    lease_id: str = "workflow-lease.postgres-01",
    acquired_at: datetime = NOW,
    heartbeat_at: datetime = NOW,
    expires_at: datetime = NOW + timedelta(seconds=90),
    fencing_token: int = 1,
    state: WorkflowOrchestrationLeaseState = WorkflowOrchestrationLeaseState.ACTIVE,
) -> WorkflowOrchestrationLease:
    payload: dict[str, object] = {
        "acquired_at": acquired_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "fencing_token": fencing_token,
        "last_heartbeat_at": heartbeat_at.isoformat(),
        "lease_id": lease_id,
        "plan_digest": plan.canonical_digest,
        "plan_id": plan.plan_id,
        "scope": plan.scope.canonical_value(),
        "state": state.value,
        "target_id": plan.target_id,
        "target_type": plan.target_type,
        "worker_subject_id": WORKER_ID,
    }
    return WorkflowOrchestrationLease(
        lease_id=lease_id,
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        scope=plan.scope,
        target_id=plan.target_id,
        target_type=plan.target_type,
        worker_subject_id=WORKER_ID,
        acquired_at=acquired_at,
        last_heartbeat_at=heartbeat_at,
        expires_at=expires_at,
        fencing_token=fencing_token,
        state=state,
        canonical_digest=canonical_digest(payload),
    )


def _acquire_request(
    lease: WorkflowOrchestrationLease,
    *,
    key: str = "workflow-lease-postgres-acquire-0001",
    fingerprint: str = "f" * 64,
    requested_at: datetime = NOW,
    current: WorkflowOrchestrationLease | None = None,
) -> WorkflowLeaseAcquireRequest:
    return WorkflowLeaseAcquireRequest(
        expected_plan_digest=lease.plan_digest,
        candidate=lease,
        requested_at=requested_at,
        idempotency_key=key,
        request_fingerprint=fingerprint,
        expected_current_lease_digest=(None if current is None else current.canonical_digest),
        expected_current_fencing_token=(None if current is None else current.fencing_token),
    )


def _mutation_request(
    current: WorkflowOrchestrationLease,
    updated: WorkflowOrchestrationLease,
    *,
    requested_at: datetime,
) -> WorkflowLeaseMutationRequest:
    return WorkflowLeaseMutationRequest(
        expected_plan_digest=current.plan_digest,
        expected_lease_id=current.lease_id,
        expected_lease_digest=current.canonical_digest,
        expected_fencing_token=current.fencing_token,
        worker_subject_id=current.worker_subject_id,
        requested_at=requested_at,
        updated_lease=updated,
    )


@pytest.mark.asyncio
async def test_acquire_persists_lease_and_idempotency_claim_in_one_commit() -> None:
    plan = await _plan()
    lease = _lease(plan)
    session = _FakeSession(
        scalar_values=(
            None,
            PostgreSQLWorkflowPlanRepository._plan_model(plan),
            None,
        )
    )

    result = await _repository(session).acquire_lease(_acquire_request(lease))

    assert result.status is WorkflowLeaseAcquireStatus.ACQUIRED
    assert result.lease == lease
    assert session.commits == 1
    assert session.rollbacks == 0
    assert [type(item) for item in session.added] == [
        WorkflowOrchestrationLeaseModel,
        WorkflowLeaseIdempotencyModel,
    ]
    lease_row = cast(WorkflowOrchestrationLeaseModel, session.added[0])
    claim = cast(WorkflowLeaseIdempotencyModel, session.added[1])
    assert PostgreSQLWorkflowPlanRepository._lease_from_row(lease_row) == lease
    assert PostgreSQLWorkflowPlanRepository._lease_record_from_claim(claim).lease == lease
    assert lease_row.fencing_token == 1
    assert claim.operation == "acquire"
    assert claim.result_digest == lease.canonical_digest
    assert lease.grants_execution_authority is False


@pytest.mark.asyncio
async def test_acquire_replays_exact_claim_without_writes() -> None:
    plan = await _plan()
    lease = _lease(plan)
    request = _acquire_request(lease)
    claim = PostgreSQLWorkflowPlanRepository._lease_claim_model(request)
    session = _FakeSession(scalar_values=(claim,))

    result = await _repository(session).acquire_lease(request)

    assert result.status is WorkflowLeaseAcquireStatus.REPLAY
    assert result.lease == lease
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_expired_takeover_increments_fence_and_uses_optimistic_update() -> None:
    plan = await _plan()
    expired = _lease(plan, expires_at=NOW + timedelta(seconds=30))
    takeover_at = NOW + timedelta(seconds=31)
    replacement = _lease(
        plan,
        lease_id="workflow-lease.postgres-02",
        acquired_at=takeover_at,
        heartbeat_at=takeover_at,
        expires_at=takeover_at + timedelta(seconds=90),
        fencing_token=2,
    )
    session = _FakeSession(
        scalar_values=(
            None,
            PostgreSQLWorkflowPlanRepository._plan_model(plan),
            PostgreSQLWorkflowPlanRepository._lease_model(expired, version=1),
        )
    )

    result = await _repository(session).acquire_lease(
        _acquire_request(
            replacement,
            key="workflow-lease-postgres-takeover-0001",
            requested_at=takeover_at,
            current=expired,
        )
    )

    assert result.status is WorkflowLeaseAcquireStatus.ACQUIRED
    assert result.lease == replacement
    assert replacement.fencing_token == expired.fencing_token + 1
    assert session.commits == 1
    assert [type(item) for item in session.added] == [WorkflowLeaseIdempotencyModel]
    assert any(statement.__class__.__name__ == "Update" for statement in session.statements)


@pytest.mark.asyncio
async def test_heartbeat_and_release_are_fenced_optimistic_updates_without_side_effect_rows() -> (
    None
):
    plan = await _plan()
    active = _lease(plan)
    heartbeat_at = NOW + timedelta(seconds=10)
    renewed = _lease(
        plan,
        heartbeat_at=heartbeat_at,
        expires_at=heartbeat_at + timedelta(seconds=120),
    )
    heartbeat_session = _FakeSession(
        scalar_values=(
            PostgreSQLWorkflowPlanRepository._plan_model(plan),
            PostgreSQLWorkflowPlanRepository._lease_model(active, version=1),
        )
    )

    heartbeat = await _repository(heartbeat_session).heartbeat_lease(
        _mutation_request(active, renewed, requested_at=heartbeat_at)
    )

    assert heartbeat.status is WorkflowLeaseMutationStatus.UPDATED
    assert heartbeat.lease == renewed
    assert heartbeat_session.commits == 1
    assert heartbeat_session.added == []
    assert any(
        statement.__class__.__name__ == "Update" for statement in heartbeat_session.statements
    )

    released_at = heartbeat_at + timedelta(seconds=10)
    released = _lease(
        plan,
        heartbeat_at=renewed.last_heartbeat_at,
        expires_at=renewed.expires_at,
        state=WorkflowOrchestrationLeaseState.RELEASED,
    )
    release_session = _FakeSession(
        scalar_values=(
            PostgreSQLWorkflowPlanRepository._plan_model(plan),
            PostgreSQLWorkflowPlanRepository._lease_model(renewed, version=2),
        )
    )

    release = await _repository(release_session).release_lease(
        _mutation_request(renewed, released, requested_at=released_at)
    )

    assert release.status is WorkflowLeaseMutationStatus.UPDATED
    assert release.lease == released
    assert release.lease.grants_execution_authority is False
    assert release_session.commits == 1
    assert release_session.added == []
    assert any(statement.__class__.__name__ == "Update" for statement in release_session.statements)
