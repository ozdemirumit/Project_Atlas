from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from atlas.core.persistence.models import (
    WorkflowAttemptMaterializationClaimModel,
    WorkflowExecutionAttemptModel,
    WorkflowExecutionRunModel,
    WorkflowExecutionStepRunModel,
    WorkflowOrchestrationLeaseModel,
    WorkflowRunPlanModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowAttemptMaterializationError,
    WorkflowAttemptMaterializationRequest,
    WorkflowAttemptMaterializationStatus,
)
from atlas.modules.workflows.domain import canonical_digest

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
PLAN_ID = "workflow-plan.attempt-postgres"
RUN_ID = "workflow-run.attempt-postgres"
ROOT_STEP_RUN_ID = "workflow-step-run.attempt-root"
LEASE_ID = "workflow-lease.attempt-postgres"
WORKER_ID = "workload.atlas.workflow-worker-01"
SCOPE = {
    "organization_id": "organization.atlas",
    "environment_id": "environment.development",
    "site_id": "site.local",
}


class _FakeScalarResult:
    def __init__(self, values: Iterable[object]) -> None:
        self._values = tuple(values)

    def all(self) -> tuple[object, ...]:
        return self._values


class _FakeSession:
    def __init__(
        self,
        *,
        scalar_values: Iterable[object | None] = (),
        scalars_values: Iterable[Iterable[object]] = (),
    ) -> None:
        self.scalar_values = list(scalar_values)
        self.scalars_values = list(scalars_values)
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

    async def scalars(self, statement: object) -> _FakeScalarResult:
        self.statements.append(statement)
        return _FakeScalarResult(self.scalars_values.pop(0))

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


def _step_payload(*, root: bool = True) -> dict[str, Any]:
    ordinal = 1 if root else 2
    return _with_digest(
        {
            "step_run_id": ROOT_STEP_RUN_ID if root else "workflow-step-run.attempt-report",
            "run_id": RUN_ID,
            "step_id": "step.attempt-root" if root else "step.attempt-report",
            "ordinal": ordinal,
            "kind": "evidence_query" if root else "report_generation",
            "capability_class": "C0" if root else "C1",
            "timeout_seconds": 60,
            "depends_on": [] if root else ["step.attempt-root"],
            "state": "not_started",
        }
    )


def _run_payload() -> dict[str, Any]:
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
            "created_at": (NOW - timedelta(seconds=10)).isoformat(),
            "state": "created",
            "step_runs": [_step_payload(root=True), _step_payload(root=False)],
            "authority": _no_authority(),
        }
    )


def _no_authority() -> dict[str, bool]:
    return {
        "approval_creation_authorized": False,
        "connector_invocation_authorized": False,
        "infrastructure_change_authorized": False,
        "itsm_mutation_authorized": False,
        "retry_authorized": False,
        "runbook_execution_authorized": False,
        "signal_delivery_authorized": False,
        "worker_dispatch_authorized": False,
    }


def _attempt_payload(*, root: bool = True) -> dict[str, Any]:
    run = _run_payload()
    step = _step_payload(root=root)
    return _with_digest(
        {
            "attempt_id": "workflow-attempt.attempt-root",
            "run_id": RUN_ID,
            "run_digest": run["canonical_digest"],
            "step_run_id": step["step_run_id"],
            "step_run_digest": step["canonical_digest"],
            "step_id": step["step_id"],
            "attempt_number": 1,
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
            "authority": _no_authority(),
        }
    )


def _request(
    *, root: bool = True, fingerprint: str = "f" * 64
) -> WorkflowAttemptMaterializationRequest:
    attempt = PostgreSQLWorkflowPlanRepository._attempt_to_domain(_attempt_payload(root=root))
    return WorkflowAttemptMaterializationRequest(
        candidate=attempt,
        expected_plan_digest=attempt.plan_digest,
        expected_run_digest=attempt.run_digest,
        expected_step_run_digest=attempt.step_run_digest,
        expected_lease_id=attempt.lease_id,
        expected_lease_digest=attempt.lease_digest,
        expected_fencing_token=attempt.fencing_token,
        worker_subject_id=attempt.materialized_by_subject_id,
        requested_at=NOW,
        idempotency_key="workflow-attempt-materialization-postgres-0001",
        request_fingerprint=fingerprint,
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
) -> WorkflowOrchestrationLeaseModel:
    return WorkflowOrchestrationLeaseModel(
        lease_id=LEASE_ID,
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


def _run_row() -> WorkflowExecutionRunModel:
    run = PostgreSQLWorkflowPlanRepository._execution_run_to_domain(_run_payload())
    return PostgreSQLWorkflowPlanRepository._materialized_run_model(run)


def _step_row(*, root: bool = True) -> WorkflowExecutionStepRunModel:
    run = PostgreSQLWorkflowPlanRepository._execution_run_to_domain(_run_payload())
    step = run.step_runs[0 if root else 1]
    return PostgreSQLWorkflowPlanRepository._materialized_step_model(step)


def test_attempt_model_keeps_historical_lease_without_current_lease_fk() -> None:
    foreign_keys = {
        (foreign_key.parent.name, foreign_key.target_fullname)
        for foreign_key in WorkflowExecutionAttemptModel.__table__.foreign_keys
    }

    assert foreign_keys == {
        ("plan_id", "workflow_run_plans.plan_id"),
        ("run_id", "workflow_execution_runs.run_id"),
        ("step_run_id", "workflow_execution_step_runs.step_run_id"),
    }
    assert "lease_id" in WorkflowExecutionAttemptModel.__table__.columns
    assert "lease_digest" in WorkflowExecutionAttemptModel.__table__.columns
    assert "lease_fencing_token" in WorkflowExecutionAttemptModel.__table__.columns


def test_attempt_models_enforce_one_attempt_per_step_number_one_and_one_claim() -> None:
    attempt_table = cast(Table, WorkflowExecutionAttemptModel.__table__)
    claim_table = cast(Table, WorkflowAttemptMaterializationClaimModel.__table__)
    attempt_constraints = {constraint.name for constraint in attempt_table.constraints}
    claim_constraints = {constraint.name for constraint in claim_table.constraints}

    assert "uq_workflow_execution_attempt_step_run" in attempt_constraints
    assert "ck_workflow_execution_attempt_number" in attempt_constraints
    assert "ck_workflow_execution_attempt_state" in attempt_constraints
    assert "uq_workflow_attempt_materialization_scope_idem" in claim_constraints
    assert "uq_workflow_attempt_materialization_claim_attempt" in claim_constraints


def test_attempt_migration_follows_run_head_and_has_no_lease_foreign_key() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0111_workflow_attempt_materialization.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0111"' in migration
    assert 'down_revision: str | None = "20260814_0110"' in migration
    assert "fk_workflow_execution_attempt_run" in migration
    assert "fk_workflow_execution_attempt_step_run" in migration
    assert "fk_workflow_execution_attempt_lease" not in migration
    assert '["workflow_orchestration_leases.lease_id"]' not in migration
    assert "replaceable during fencing takeover" in migration


@pytest.mark.asyncio
async def test_first_attempt_write_locks_all_sources_and_commits_attempt_and_claim_atomically() -> (
    None
):
    request = _request()
    session = _FakeSession(
        scalar_values=(None, _plan_row(), _lease_row(), _run_row(), _step_row(), None)
    )

    result = await _repository(session).materialize_attempt(request)

    assert result.status is WorkflowAttemptMaterializationStatus.CREATED
    assert result.attempt == request.candidate
    assert session.commits == 1
    assert session.rollbacks == 0
    assert [type(item) for item in session.added] == [
        WorkflowExecutionAttemptModel,
        WorkflowAttemptMaterializationClaimModel,
    ]
    assert all("FOR UPDATE" in str(statement) for statement in session.statements[1:])


@pytest.mark.asyncio
async def test_exact_attempt_replay_returns_immutable_snapshot_without_writes() -> None:
    request = _request()
    claim = PostgreSQLWorkflowPlanRepository._attempt_materialization_claim_model(request)
    session = _FakeSession(scalar_values=(claim,))

    result = await _repository(session).materialize_attempt(request)

    assert result.status is WorkflowAttemptMaterializationStatus.REPLAY
    assert result.attempt == request.candidate
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_changed_attempt_idempotency_fails_closed_with_original_snapshot() -> None:
    original = _request()
    claim = PostgreSQLWorkflowPlanRepository._attempt_materialization_claim_model(original)
    session = _FakeSession(scalar_values=(claim,))

    result = await _repository(session).materialize_attempt(_request(fingerprint="e" * 64))

    assert result.status is WorkflowAttemptMaterializationStatus.IDEMPOTENCY_CONFLICT
    assert result.attempt == original.candidate
    assert session.added == []


@pytest.mark.asyncio
async def test_attempt_claim_and_list_round_trip_use_domain_contracts() -> None:
    request = _request()
    attempt_row = PostgreSQLWorkflowPlanRepository._attempt_model(request.candidate)
    claim = PostgreSQLWorkflowPlanRepository._attempt_materialization_claim_model(request)
    claim_session = _FakeSession(scalar_values=(claim,))
    list_session = _FakeSession(scalars_values=((attempt_row,),))
    repository = _repository(claim_session, list_session)

    record = await repository.get_attempt_materialization_request(
        scope=request.candidate.scope,
        worker_subject_id=request.worker_subject_id,
        idempotency_key=request.idempotency_key,
    )
    attempts = await repository.list_attempts_by_run_id(run_id=RUN_ID)

    assert record is not None
    assert record.request_fingerprint == request.request_fingerprint
    assert record.attempt == request.candidate
    assert attempts == (request.candidate,)
    assert "ORDER BY" in str(list_session.statements[0])


@pytest.mark.asyncio
async def test_non_root_step_is_rejected_before_attempt_creation() -> None:
    request = _request(root=False)
    session = _FakeSession(
        scalar_values=(None, _plan_row(), _lease_row(), _run_row(), _step_row(root=False))
    )

    result = await _repository(session).materialize_attempt(request)

    assert result.status is WorkflowAttemptMaterializationStatus.STATE_CONFLICT
    assert result.attempt is None
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("plan", "lease"),
    (
        (_plan_row(state="cancelled"), _lease_row()),
        (_plan_row(), _lease_row(state="released")),
        (_plan_row(), _lease_row(expires_at=NOW)),
        (_plan_row(), _lease_row(fencing_token=2)),
    ),
)
async def test_plan_or_lease_drift_fails_closed(
    plan: WorkflowRunPlanModel,
    lease: WorkflowOrchestrationLeaseModel,
) -> None:
    session = _FakeSession(scalar_values=(None, plan, lease, _run_row(), _step_row()))

    result = await _repository(session).materialize_attempt(_request())

    assert result.status is WorkflowAttemptMaterializationStatus.STATE_CONFLICT
    assert result.attempt is None
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ("run_digest", "step_digest", "run_fence"))
async def test_corrupt_run_or_step_storage_raises_repository_contract_error(
    drift: str,
) -> None:
    run = _run_row()
    step = _step_row()
    if drift == "run_digest":
        run.canonical_digest = "9" * 64
    elif drift == "step_digest":
        step.canonical_digest = "8" * 64
    else:
        run.lease_fencing_token = 2
    session = _FakeSession(scalar_values=(None, _plan_row(), _lease_row(), run, step))

    with pytest.raises(
        WorkflowAttemptMaterializationError,
        match="Workflow run evidence is inconsistent",
    ):
        await _repository(session).materialize_attempt(_request())

    assert session.added == []
    assert session.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ("run_digest", "step_digest", "fence"))
async def test_clean_stale_attempt_request_fails_with_state_conflict(drift: str) -> None:
    request = _request()
    if drift == "run_digest":
        request = replace(request, expected_run_digest="9" * 64)
    elif drift == "step_digest":
        request = replace(request, expected_step_run_digest="8" * 64)
    else:
        request = replace(request, expected_fencing_token=2)
    session = _FakeSession(scalar_values=(None, _plan_row(), _lease_row(), _run_row(), _step_row()))

    result = await _repository(session).materialize_attempt(request)

    assert result.status is WorkflowAttemptMaterializationStatus.STATE_CONFLICT
    assert result.attempt is None
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 1


def test_attempt_round_trip_retains_zero_authority_and_historical_lease_snapshot() -> None:
    request = _request()
    row = PostgreSQLWorkflowPlanRepository._attempt_model(request.candidate)

    restored = PostgreSQLWorkflowPlanRepository._attempt_from_row(row)

    assert restored == request.candidate
    assert restored.attempt_number == 1
    assert restored.grants_execution_authority is False
    assert restored.lease_id == LEASE_ID
    assert restored.fencing_token == 1
