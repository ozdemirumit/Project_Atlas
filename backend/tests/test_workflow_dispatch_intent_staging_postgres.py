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
    WorkflowDispatchIntentModel,
    WorkflowDispatchIntentStagingClaimModel,
    WorkflowExecutionAttemptModel,
    WorkflowExecutionRunModel,
    WorkflowExecutionStepRunModel,
    WorkflowOrchestrationLeaseModel,
    WorkflowRunPlanModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application.dispatch_intent_ports import (
    WorkflowDispatchIntentStagingError,
    WorkflowDispatchIntentStagingRequest,
    WorkflowDispatchIntentStagingStatus,
)
from atlas.modules.workflows.domain import canonical_digest

NOW = datetime(2026, 8, 14, 14, 0, tzinfo=UTC)
PLAN_ID = "workflow-plan.dispatch-postgres"
RUN_ID = "workflow-run.dispatch-postgres"
STEP_RUN_ID = "workflow-step-run.dispatch-root"
ATTEMPT_ID = "workflow-attempt.dispatch-root"
INTENT_ID = "workflow-dispatch-intent.dispatch-root"
LEASE_ID = "workflow-lease.dispatch-postgres"
WORKER_ID = "workload.atlas.workflow-worker-01"
HISTORICAL_LEASE_DIGEST = "c" * 64
CURRENT_LEASE_DIGEST = "e" * 64
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


def _step_payload() -> dict[str, Any]:
    return _with_digest(
        {
            "step_run_id": STEP_RUN_ID,
            "run_id": RUN_ID,
            "step_id": "step.dispatch-root",
            "ordinal": 1,
            "kind": "evidence_query",
            "capability_class": "C0",
            "timeout_seconds": 60,
            "depends_on": [],
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
            "lease_digest": HISTORICAL_LEASE_DIGEST,
            "fencing_token": 1,
            "materialized_by_subject_id": WORKER_ID,
            "created_at": (NOW - timedelta(seconds=20)).isoformat(),
            "state": "created",
            "step_runs": [_step_payload()],
            "authority": _no_authority(),
        }
    )


def _attempt_payload() -> dict[str, Any]:
    run = _run_payload()
    step = _step_payload()
    return _with_digest(
        {
            "attempt_id": ATTEMPT_ID,
            "run_id": RUN_ID,
            "run_digest": run["canonical_digest"],
            "step_run_id": STEP_RUN_ID,
            "step_run_digest": step["canonical_digest"],
            "step_id": "step.dispatch-root",
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
            "lease_digest": HISTORICAL_LEASE_DIGEST,
            "fencing_token": 1,
            "materialized_by_subject_id": WORKER_ID,
            "created_at": (NOW - timedelta(seconds=10)).isoformat(),
            "state": "created",
            "authority": _no_authority(),
        }
    )


def _intent_payload() -> dict[str, Any]:
    run = _run_payload()
    step = _step_payload()
    attempt = _attempt_payload()
    return _with_digest(
        {
            "dispatch_intent_id": INTENT_ID,
            "plan_id": PLAN_ID,
            "plan_digest": "a" * 64,
            "run_id": RUN_ID,
            "run_digest": run["canonical_digest"],
            "step_run_id": STEP_RUN_ID,
            "step_run_digest": step["canonical_digest"],
            "step_id": "step.dispatch-root",
            "attempt_id": ATTEMPT_ID,
            "attempt_digest": attempt["canonical_digest"],
            "attempt_number": 1,
            "scope": SCOPE,
            "target_id": "asset.storage.lab.primary",
            "target_type": "storage",
            "lease_id": LEASE_ID,
            "lease_digest": CURRENT_LEASE_DIGEST,
            "fencing_token": 1,
            "worker_subject_id": WORKER_ID,
            "staged_at": NOW.isoformat(),
            "state": "staged",
            "authority": _no_authority(),
        }
    )


def _request(*, fingerprint: str = "f" * 64) -> WorkflowDispatchIntentStagingRequest:
    intent = PostgreSQLWorkflowPlanRepository._dispatch_intent_to_domain(_intent_payload())
    return WorkflowDispatchIntentStagingRequest(
        candidate=intent,
        expected_plan_digest=intent.plan_digest,
        expected_run_digest=intent.run_digest,
        expected_step_run_digest=intent.step_run_digest,
        expected_attempt_digest=intent.attempt_digest,
        expected_lease_id=intent.lease_id,
        expected_lease_digest=intent.lease_digest,
        expected_fencing_token=intent.fencing_token,
        worker_subject_id=intent.worker_subject_id,
        requested_at=NOW,
        idempotency_key="workflow-dispatch-intent-postgres-0001",
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
        acquired_at=NOW - timedelta(seconds=40),
        last_heartbeat_at=NOW - timedelta(seconds=5),
        expires_at=expires_at,
        fencing_token=fencing_token,
        state=state,
        version=2,
        canonical_digest=CURRENT_LEASE_DIGEST,
        payload={},
    )


def _run_row() -> WorkflowExecutionRunModel:
    run = PostgreSQLWorkflowPlanRepository._execution_run_to_domain(_run_payload())
    return PostgreSQLWorkflowPlanRepository._materialized_run_model(run)


def _step_row() -> WorkflowExecutionStepRunModel:
    run = PostgreSQLWorkflowPlanRepository._execution_run_to_domain(_run_payload())
    return PostgreSQLWorkflowPlanRepository._materialized_step_model(run.step_runs[0])


def _attempt_row() -> WorkflowExecutionAttemptModel:
    attempt = PostgreSQLWorkflowPlanRepository._attempt_to_domain(_attempt_payload())
    return PostgreSQLWorkflowPlanRepository._attempt_model(attempt)


def test_dispatch_intent_model_has_exact_immutable_source_foreign_keys() -> None:
    foreign_keys = {
        (foreign_key.parent.name, foreign_key.target_fullname)
        for foreign_key in WorkflowDispatchIntentModel.__table__.foreign_keys
    }

    assert foreign_keys == {
        ("plan_id", "workflow_run_plans.plan_id"),
        ("run_id", "workflow_execution_runs.run_id"),
        ("step_run_id", "workflow_execution_step_runs.step_run_id"),
        ("attempt_id", "workflow_execution_attempts.attempt_id"),
    }
    assert "lease_id" in WorkflowDispatchIntentModel.__table__.columns
    assert "lease_digest" in WorkflowDispatchIntentModel.__table__.columns


def test_dispatch_intent_schema_is_staged_only_and_has_no_delivery_surface() -> None:
    intent_table = cast(Table, WorkflowDispatchIntentModel.__table__)
    claim_table = cast(Table, WorkflowDispatchIntentStagingClaimModel.__table__)
    intent_constraints = {constraint.name for constraint in intent_table.constraints}
    claim_constraints = {constraint.name for constraint in claim_table.constraints}

    assert "uq_workflow_dispatch_intent_attempt" in intent_constraints
    assert "ck_workflow_dispatch_intent_attempt_number" in intent_constraints
    assert "ck_workflow_dispatch_intent_state" in intent_constraints
    assert "uq_workflow_dispatch_intent_staging_scope_idem" in claim_constraints
    assert "uq_workflow_dispatch_intent_staging_claim_intent" in claim_constraints
    prohibited = {
        "queue",
        "broker",
        "message",
        "publication",
        "delivery",
        "dispatch",
        "worker_assignment",
    }
    assert prohibited.isdisjoint(intent_table.columns.keys())


def test_dispatch_intent_migration_follows_attempt_head_without_lease_fk_or_delivery_fields() -> (
    None
):
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0112_workflow_dispatch_intent_staging.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0112"' in migration
    assert 'down_revision: str | None = "20260814_0111"' in migration
    assert "fk_workflow_dispatch_intent_attempt" in migration
    assert "fk_workflow_dispatch_intent_lease" not in migration
    assert '["workflow_orchestration_leases.lease_id"]' not in migration
    assert "replaceable during fencing takeover" in migration
    for field in ('"queue"', '"broker"', '"delivery"', '"published_at"'):
        assert field not in migration


@pytest.mark.asyncio
async def test_first_stage_locks_every_source_and_commits_intent_and_claim_atomically() -> None:
    request = _request()
    session = _FakeSession(
        scalar_values=(
            None,
            _plan_row(),
            _lease_row(),
            _run_row(),
            _step_row(),
            _attempt_row(),
            None,
        )
    )

    result = await _repository(session).stage_dispatch_intent(request)

    assert result.status is WorkflowDispatchIntentStagingStatus.STAGED
    assert result.dispatch_intent == request.candidate
    assert session.commits == 1
    assert session.rollbacks == 0
    assert [type(item) for item in session.added] == [
        WorkflowDispatchIntentModel,
        WorkflowDispatchIntentStagingClaimModel,
    ]
    assert all("FOR UPDATE" in str(statement) for statement in session.statements[1:])


@pytest.mark.asyncio
async def test_exact_staging_replay_returns_immutable_snapshot_without_writes() -> None:
    request = _request()
    claim = PostgreSQLWorkflowPlanRepository._dispatch_intent_staging_claim_model(request)
    session = _FakeSession(scalar_values=(claim,))

    result = await _repository(session).stage_dispatch_intent(request)

    assert result.status is WorkflowDispatchIntentStagingStatus.REPLAY
    assert result.dispatch_intent == request.candidate
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_changed_staging_idempotency_fails_closed_with_original_snapshot() -> None:
    original = _request()
    claim = PostgreSQLWorkflowPlanRepository._dispatch_intent_staging_claim_model(original)
    session = _FakeSession(scalar_values=(claim,))

    result = await _repository(session).stage_dispatch_intent(_request(fingerprint="9" * 64))

    assert result.status is WorkflowDispatchIntentStagingStatus.IDEMPOTENCY_CONFLICT
    assert result.dispatch_intent == original.candidate
    assert session.added == []


@pytest.mark.asyncio
async def test_intent_claim_and_list_round_trip_use_domain_contracts() -> None:
    request = _request()
    intent_row = PostgreSQLWorkflowPlanRepository._dispatch_intent_model(request.candidate)
    claim = PostgreSQLWorkflowPlanRepository._dispatch_intent_staging_claim_model(request)
    claim_session = _FakeSession(scalar_values=(claim,))
    list_session = _FakeSession(scalars_values=((intent_row,),))
    repository = _repository(claim_session, list_session)

    record = await repository.get_dispatch_intent_staging_request(
        scope=request.candidate.scope,
        worker_subject_id=request.worker_subject_id,
        idempotency_key=request.idempotency_key,
    )
    intents = await repository.list_dispatch_intents_by_run_id(run_id=RUN_ID)

    assert record is not None
    assert record.request_fingerprint == request.request_fingerprint
    assert record.dispatch_intent == request.candidate
    assert intents == (request.candidate,)
    assert "ORDER BY" in str(list_session.statements[0])


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
async def test_plan_or_current_lease_drift_fails_closed(
    plan: WorkflowRunPlanModel,
    lease: WorkflowOrchestrationLeaseModel,
) -> None:
    session = _FakeSession(
        scalar_values=(None, plan, lease, _run_row(), _step_row(), _attempt_row())
    )

    result = await _repository(session).stage_dispatch_intent(_request())

    assert result.status is WorkflowDispatchIntentStagingStatus.STATE_CONFLICT
    assert result.dispatch_intent is None
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "drift",
    ("run_digest", "step_digest", "attempt_digest", "fence"),
)
async def test_stale_exact_request_fails_closed(drift: str) -> None:
    request = _request()
    if drift == "run_digest":
        request = replace(request, expected_run_digest="7" * 64)
    elif drift == "step_digest":
        request = replace(request, expected_step_run_digest="8" * 64)
    elif drift == "attempt_digest":
        request = replace(request, expected_attempt_digest="9" * 64)
    else:
        request = replace(request, expected_fencing_token=2)
    session = _FakeSession(
        scalar_values=(
            None,
            _plan_row(),
            _lease_row(),
            _run_row(),
            _step_row(),
            _attempt_row(),
        )
    )

    result = await _repository(session).stage_dispatch_intent(request)

    assert result.status is WorkflowDispatchIntentStagingStatus.STATE_CONFLICT
    assert result.dispatch_intent is None
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_corrupt_attempt_storage_raises_repository_contract_error() -> None:
    attempt = _attempt_row()
    attempt.canonical_digest = "9" * 64
    session = _FakeSession(
        scalar_values=(None, _plan_row(), _lease_row(), _run_row(), _step_row(), attempt)
    )

    with pytest.raises(
        WorkflowDispatchIntentStagingError,
        match="Workflow execution evidence is inconsistent",
    ):
        await _repository(session).stage_dispatch_intent(_request())

    assert session.added == []
    assert session.commits == 0


@pytest.mark.asyncio
async def test_competing_intent_for_same_attempt_is_state_conflict() -> None:
    request = _request()
    existing = PostgreSQLWorkflowPlanRepository._dispatch_intent_model(request.candidate)
    session = _FakeSession(
        scalar_values=(
            None,
            _plan_row(),
            _lease_row(),
            _run_row(),
            _step_row(),
            _attempt_row(),
            existing,
        )
    )

    result = await _repository(session).stage_dispatch_intent(request)

    assert result.status is WorkflowDispatchIntentStagingStatus.STATE_CONFLICT
    assert result.dispatch_intent == request.candidate
    assert session.added == []
    assert session.commits == 0
    assert session.rollbacks == 1


def test_dispatch_intent_round_trip_retains_zero_authority_and_current_lease_snapshot() -> None:
    request = _request()
    row = PostgreSQLWorkflowPlanRepository._dispatch_intent_model(request.candidate)

    restored = PostgreSQLWorkflowPlanRepository._dispatch_intent_from_row(row)

    assert restored == request.candidate
    assert restored.state.value == "staged"
    assert restored.grants_dispatch_authority is False
    assert restored.grants_execution_authority is False
    assert restored.lease_digest == CURRENT_LEASE_DIGEST
    assert restored.lease_digest != HISTORICAL_LEASE_DIGEST
