from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_WORKER_AUDIENCE,
    WorkflowAccessContext,
    WorkflowAttemptMaterializationError,
    WorkflowAttemptMaterializationService,
    WorkflowOrchestrationLeaseService,
    WorkflowPlanningService,
    WorkflowRunMaterializationService,
    WorkflowWorkerContext,
)
from atlas.modules.workflows.domain import (
    WorkflowExecutionRun,
    WorkflowOrchestrationLease,
    WorkflowRunPlan,
    WorkflowScope,
    code_owned_workflow_registry,
)

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
TARGET_ID = "asset.storage.lab.vsp-g400"
WORKER_ID = "workload.atlas.workflow-worker-01"


class _AuditSink:
    def __init__(self) -> None:
        self.events: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.events.append(event)


def _human_context() -> WorkflowAccessContext:
    return WorkflowAccessContext(
        subject_id="subject.operator",
        role_ids=frozenset({"role.infrastructure-operator"}),
        actor_type="human",
        authentication_method="ldap",
        assurance_level="single_factor",
        scope=WorkflowScope(
            organization_id="organization.development",
            environment_id="environment.development",
            site_id="site.local",
        ),
        authorized_target_ids=frozenset({TARGET_ID}),
        correlation_id="correlation.attempt-plan",
        decision_id="decision.attempt-plan",
        requested_at=NOW,
    )


def _worker_context(
    *, requested_at: datetime = NOW + timedelta(seconds=1)
) -> WorkflowWorkerContext:
    human = _human_context()
    return WorkflowWorkerContext(
        subject_id=WORKER_ID,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_WORKER_AUDIENCE,
        scope=human.scope,
        authorized_target_ids=human.authorized_target_ids,
        correlation_id="correlation.attempt-worker",
        decision_id="decision.attempt-worker",
        requested_at=requested_at,
    )


async def _materialized_fixture() -> tuple[
    InMemoryWorkflowPlanRepository,
    WorkflowAttemptMaterializationService,
    WorkflowRunPlan,
    WorkflowOrchestrationLease,
    WorkflowExecutionRun,
]:
    repository = InMemoryWorkflowPlanRepository()
    audit = _AuditSink()
    registry = code_owned_workflow_registry()
    planning = WorkflowPlanningService(
        registry=registry,
        repository=repository,
        audit_sink=audit,
    )
    plan = await planning.create_plan(
        definition_id="workflow.evidence-grounded-query",
        definition_version=1,
        target_id=TARGET_ID,
        inputs={
            "purpose": "Materialize an attempt identity.",
            "input_summary": "Read-only evidence only.",
        },
        idempotency_key="workflow-attempt-plan-0001",
        context=_human_context(),
    )
    lease_service = WorkflowOrchestrationLeaseService(
        plan_repository=repository,
        lease_repository=repository,
        audit_sink=audit,
    )
    lease = await lease_service.acquire(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        lease_seconds=90,
        idempotency_key="workflow-attempt-lease-0001",
        context=_worker_context(),
    )
    run_service = WorkflowRunMaterializationService(
        registry=registry,
        plan_repository=repository,
        lease_repository=repository,
        run_repository=repository,
        audit_sink=audit,
    )
    run = await run_service.materialize(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token,
        idempotency_key="workflow-attempt-run-0001",
        context=_worker_context(requested_at=NOW + timedelta(seconds=2)),
    )
    service = WorkflowAttemptMaterializationService(
        plan_repository=repository,
        lease_repository=repository,
        run_repository=repository,
        attempt_repository=repository,
        audit_sink=audit,
    )
    return repository, service, plan, lease, run


@pytest.mark.asyncio
async def test_materializes_one_root_attempt_without_changing_run_or_step_state() -> None:
    repository, service, plan, lease, run = await _materialized_fixture()
    root = run.step_runs[0]
    context = _worker_context(requested_at=NOW + timedelta(seconds=3))

    attempt = await service.materialize(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        run_id=run.run_id,
        run_digest=run.canonical_digest,
        step_run_id=root.step_run_id,
        step_run_digest=root.canonical_digest,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token,
        idempotency_key="workflow-attempt-materialize-0001",
        context=context,
    )
    replay = await service.materialize(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        run_id=run.run_id,
        run_digest=run.canonical_digest,
        step_run_id=root.step_run_id,
        step_run_digest=root.canonical_digest,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token,
        idempotency_key="workflow-attempt-materialize-0001",
        context=context,
    )

    assert replay == attempt
    assert attempt.attempt_number == 1
    assert attempt.state.value == "created"
    assert attempt.run_digest == run.canonical_digest
    assert attempt.step_run_digest == root.canonical_digest
    assert attempt.grants_execution_authority is False
    assert not any(attempt.authority.canonical_value().values())
    assert run.state.value == "created"
    assert all(step.state.value == "not_started" for step in run.step_runs)
    assert await repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id) == run
    assert await repository.list_attempts_by_run_id(run_id=run.run_id) == (attempt,)


@pytest.mark.asyncio
async def test_dependency_step_and_stale_fence_fail_closed() -> None:
    _, service, plan, lease, run = await _materialized_fixture()
    dependent = run.step_runs[1]
    context = _worker_context(requested_at=NOW + timedelta(seconds=3))

    with pytest.raises(WorkflowAttemptMaterializationError) as dependent_error:
        await service.materialize(
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            run_id=run.run_id,
            run_digest=run.canonical_digest,
            step_run_id=dependent.step_run_id,
            step_run_digest=dependent.canonical_digest,
            lease_id=lease.lease_id,
            lease_digest=lease.canonical_digest,
            fencing_token=lease.fencing_token,
            idempotency_key="workflow-attempt-dependent-0001",
            context=context,
        )
    assert dependent_error.value.code == "workflow_attempt_step_ineligible"

    root = run.step_runs[0]
    with pytest.raises(WorkflowAttemptMaterializationError) as fence_error:
        await service.materialize(
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            run_id=run.run_id,
            run_digest=run.canonical_digest,
            step_run_id=root.step_run_id,
            step_run_digest=root.canonical_digest,
            lease_id=lease.lease_id,
            lease_digest=lease.canonical_digest,
            fencing_token=lease.fencing_token + 1,
            idempotency_key="workflow-attempt-stale-fence-0001",
            context=context,
        )
    assert fence_error.value.code == "workflow_attempt_lease_conflict"
