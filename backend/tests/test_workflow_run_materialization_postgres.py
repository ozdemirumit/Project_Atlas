from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from atlas.core.persistence.models import (
    WorkflowExecutionRunModel,
    WorkflowExecutionStepRunModel,
    WorkflowOrchestrationLeaseModel,
    WorkflowRunMaterializationClaimModel,
    WorkflowRunPlanModel,
)
from atlas.modules.workflows.adapters.postgres import (
    PostgreSQLWorkflowPlanRepository,
)
from atlas.modules.workflows.application import (
    WorkflowRunMaterializationRequest,
    WorkflowRunMaterializationStatus,
)
from atlas.modules.workflows.domain import canonical_digest

NOW = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)
PLAN_ID = "workflow-plan.materialization-postgres"
RUN_ID = "workflow-run.materialization-postgres"
LEASE_ID = "workflow-lease.materialization-postgres"
WORKER_ID = "workload.atlas.workflow-worker-01"
SCOPE = {
    "organization_id": "organization.atlas",
    "environment_id": "environment.development",
    "site_id": "site.local",
}


class _FakeSession:
    def __init__(self, *, scalar_values: Iterable[object | None]) -> None:
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

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _repository(*sessions: _FakeSession) -> PostgreSQLWorkflowPlanRepository:
    remaining = list(sessions)

    def factory() -> AsyncSession:
        return cast(AsyncSession, remaining.pop(0))

    return PostgreSQLWorkflowPlanRepository(
        engine=cast(AsyncEngine, object()),
        session_factory=factory,
    )


def _with_digest(payload: dict[str, Any]) -> dict[str, Any]:
    return payload | {"canonical_digest": canonical_digest(payload)}


def _step_payload(*, ordinal: int = 1) -> dict[str, Any]:
    return _with_digest(
        {
            "step_run_id": f"workflow-step-run.materialization-{ordinal}",
            "run_id": RUN_ID,
            "step_id": f"step.materialization-{ordinal}",
            "ordinal": ordinal,
            "kind": "evidence_query" if ordinal == 1 else "report_generation",
            "capability_class": "C0" if ordinal == 1 else "C1",
            "timeout_seconds": 60,
            "depends_on": [] if ordinal == 1 else ["step.materialization-1"],
            "state": "not_started",
        }
    )


def _run_payload() -> dict[str, Any]:
    steps = [_step_payload(ordinal=1), _step_payload(ordinal=2)]
    return _with_digest(
        {
            "run_id": RUN_ID,
            "plan_id": PLAN_ID,
            "plan_digest": "a" * 64,
            "definition_id": "workflow.evidence-grounded-query",
            "definition_version": 1,
            "definition_digest": "b" * 64,
            "scope": SCOPE,
            "target_id": "asset.storage.lab.primary",
            "target_type": "storage",
            "lease_id": LEASE_ID,
            "lease_digest": "c" * 64,
            "fencing_token": 1,
            "materialized_by_subject_id": WORKER_ID,
            "created_at": NOW.isoformat(),
            "state": "created",
            "step_runs": steps,
            "authority": {
                "approval_creation_authorized": False,
                "connector_invocation_authorized": False,
                "infrastructure_change_authorized": False,
                "itsm_mutation_authorized": False,
                "retry_authorized": False,
                "runbook_execution_authorized": False,
                "signal_delivery_authorized": False,
                "worker_dispatch_authorized": False,
            },
        }
    )


def _request(*, fingerprint: str = "f" * 64) -> WorkflowRunMaterializationRequest:
    run = PostgreSQLWorkflowPlanRepository._execution_run_to_domain(_run_payload())
    return WorkflowRunMaterializationRequest(
        candidate=run,
        expected_plan_digest=run.plan_digest,
        expected_lease_id=run.lease_id,
        expected_lease_digest=run.lease_digest,
        expected_fencing_token=run.fencing_token,
        worker_subject_id=run.materialized_by_subject_id,
        idempotency_key="workflow-run-materialization-postgres-0001",
        request_fingerprint=fingerprint,
        requested_at=NOW,
    )


def _plan_row(*, state: str = "planned") -> WorkflowRunPlanModel:
    return WorkflowRunPlanModel(
        plan_id=PLAN_ID,
        state=state,
        definition_id="workflow.evidence-grounded-query",
        definition_version=1,
        definition_digest="b" * 64,
        organization_id=SCOPE["organization_id"],
        environment_id=SCOPE["environment_id"],
        site_id=SCOPE["site_id"],
        creator_subject_id="subject.operator",
        target_type="storage",
        target_id="asset.storage.lab.primary",
        canonical_input_digest="d" * 64,
        created_at=NOW - timedelta(minutes=2),
        updated_at=NOW - timedelta(minutes=2),
        state_version=1,
        canonical_digest="a" * 64,
        payload={},
    )


def _lease_row(
    *,
    state: str = "active",
    expires_at: datetime = NOW + timedelta(seconds=90),
    fencing_token: int = 1,
    lease_id: str = LEASE_ID,
) -> WorkflowOrchestrationLeaseModel:
    return WorkflowOrchestrationLeaseModel(
        lease_id=lease_id,
        plan_id=PLAN_ID,
        plan_digest="a" * 64,
        organization_id=SCOPE["organization_id"],
        environment_id=SCOPE["environment_id"],
        site_id=SCOPE["site_id"],
        target_type="storage",
        target_id="asset.storage.lab.primary",
        worker_subject_id=WORKER_ID,
        acquired_at=NOW - timedelta(seconds=30),
        last_heartbeat_at=NOW - timedelta(seconds=10),
        expires_at=expires_at,
        fencing_token=fencing_token,
        state=state,
        version=1,
        canonical_digest="c" * 64,
        payload={},
    )


def test_execution_run_keeps_historical_lease_binding_without_current_lease_fk() -> None:
    foreign_keys = {
        (foreign_key.parent.name, foreign_key.target_fullname)
        for foreign_key in WorkflowExecutionRunModel.__table__.foreign_keys
    }

    assert foreign_keys == {("plan_id", "workflow_run_plans.plan_id")}
    assert "lease_id" in WorkflowExecutionRunModel.__table__.columns
    assert "lease_digest" in WorkflowExecutionRunModel.__table__.columns
    assert "lease_fencing_token" in WorkflowExecutionRunModel.__table__.columns


def test_materialization_models_enforce_one_run_ordered_steps_and_one_claim() -> None:
    run_table = cast(Table, WorkflowExecutionRunModel.__table__)
    step_table = cast(Table, WorkflowExecutionStepRunModel.__table__)
    claim_table = cast(Table, WorkflowRunMaterializationClaimModel.__table__)
    run_constraints = {constraint.name for constraint in run_table.constraints}
    step_constraints = {constraint.name for constraint in step_table.constraints}
    claim_constraints = {constraint.name for constraint in claim_table.constraints}

    assert "uq_workflow_execution_run_plan" in run_constraints
    assert "uq_workflow_execution_run_digest" in run_constraints
    assert "ck_workflow_execution_run_state" in run_constraints
    assert "uq_workflow_step_run_step" in step_constraints
    assert "uq_workflow_step_run_ordinal" in step_constraints
    assert "ck_workflow_step_run_state" in step_constraints
    assert "uq_workflow_run_materialization_scope_idem" in claim_constraints
    assert "uq_workflow_run_materialization_claim_run" in claim_constraints


def test_migration_preserves_takeover_compatibility_without_lease_foreign_key() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0110_workflow_run_materialization.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0110"' in migration
    assert 'down_revision: str | None = "20260813_0109"' in migration
    assert "fk_workflow_execution_run_plan" in migration
    assert "fk_workflow_execution_run_lease" not in migration
    assert '["workflow_orchestration_leases.lease_id"]' not in migration
    assert "replaceable during fencing takeover" in migration


@pytest.mark.asyncio
async def test_first_materialization_writes_run_ordered_steps_and_claim_in_one_commit() -> None:
    request = _request()
    session = _FakeSession(scalar_values=(None, _plan_row(), _lease_row(), None))

    result = await _repository(session).materialize_run(request)

    assert result.status is WorkflowRunMaterializationStatus.CREATED
    assert result.run == request.candidate
    assert session.commits == 1
    assert session.rollbacks == 0
    assert [type(item) for item in session.added] == [
        WorkflowExecutionRunModel,
        WorkflowExecutionStepRunModel,
        WorkflowExecutionStepRunModel,
        WorkflowRunMaterializationClaimModel,
    ]
    assert "FOR UPDATE" in str(session.statements[1])
    assert "FOR UPDATE" in str(session.statements[2])
    run_row = cast(WorkflowExecutionRunModel, session.added[0])
    assert PostgreSQLWorkflowPlanRepository._materialized_run_from_row(run_row) == (
        request.candidate
    )
    assert [cast(WorkflowExecutionStepRunModel, item).ordinal for item in session.added[1:3]] == [
        1,
        2,
    ]


@pytest.mark.asyncio
async def test_exact_materialization_replay_returns_immutable_snapshot_without_writes() -> None:
    request = _request()
    claim = PostgreSQLWorkflowPlanRepository._materialization_claim_model(request)
    session = _FakeSession(scalar_values=(claim,))

    result = await _repository(session).materialize_run(request)

    assert result.status is WorkflowRunMaterializationStatus.REPLAY
    assert result.run == request.candidate
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_materialization_claim_round_trip_uses_application_record() -> None:
    request = _request()
    claim = PostgreSQLWorkflowPlanRepository._materialization_claim_model(request)
    session = _FakeSession(scalar_values=(claim,))

    record = await _repository(session).get_run_materialization_request(
        scope=request.candidate.scope,
        worker_subject_id=request.worker_subject_id,
        idempotency_key=request.idempotency_key,
    )

    assert record is not None
    assert record.request_fingerprint == request.request_fingerprint
    assert record.run == request.candidate


@pytest.mark.asyncio
async def test_changed_idempotent_request_fails_closed_with_original_snapshot() -> None:
    original = _request()
    claim = PostgreSQLWorkflowPlanRepository._materialization_claim_model(original)
    changed = _request(fingerprint="e" * 64)
    session = _FakeSession(scalar_values=(claim,))

    result = await _repository(session).materialize_run(changed)

    assert result.status is WorkflowRunMaterializationStatus.IDEMPOTENCY_CONFLICT
    assert result.run == original.candidate
    assert session.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("plan", "lease"),
    (
        (_plan_row(state="cancelled"), _lease_row()),
        (_plan_row(), _lease_row(state="released")),
        (_plan_row(), _lease_row(expires_at=NOW)),
        (_plan_row(), _lease_row(fencing_token=2)),
        (_plan_row(), _lease_row(lease_id="workflow-lease.takeover-generation-2")),
    ),
)
async def test_plan_or_lease_drift_fails_closed_without_materialization(
    plan: WorkflowRunPlanModel,
    lease: WorkflowOrchestrationLeaseModel,
) -> None:
    session = _FakeSession(scalar_values=(None, plan, lease))

    result = await _repository(session).materialize_run(_request())

    assert result.status is WorkflowRunMaterializationStatus.STATE_CONFLICT
    assert result.run is None
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 1


def test_historical_run_round_trip_survives_current_lease_takeover_identity() -> None:
    request = _request()
    historical = PostgreSQLWorkflowPlanRepository._materialized_run_model(request.candidate)
    current = _lease_row(lease_id="workflow-lease.takeover-generation-2", fencing_token=2)

    restored = PostgreSQLWorkflowPlanRepository._materialized_run_from_row(historical)

    assert restored.lease_id == LEASE_ID
    assert restored.fencing_token == 1
    assert current.lease_id != restored.lease_id
    assert current.fencing_token > restored.fencing_token
