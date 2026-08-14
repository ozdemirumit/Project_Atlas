from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.adapters import (
    InMemoryWorkflowPlanRepository,
    UnavailableWorkflowPlanRepository,
)
from atlas.modules.workflows.application import (
    WORKFLOW_WORKER_AUDIENCE,
    WorkflowAccessContext,
    WorkflowAttemptMaterializationService,
    WorkflowDispatchIntentStagingError,
    WorkflowDispatchIntentStagingService,
    WorkflowOrchestrationLeaseService,
    WorkflowPlanningService,
    WorkflowRunMaterializationService,
    WorkflowWorkerContext,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchIntent,
    WorkflowExecutionAttempt,
    WorkflowExecutionRun,
    WorkflowOrchestrationLease,
    WorkflowRunPlan,
    WorkflowScope,
    code_owned_workflow_registry,
)

NOW = datetime(2026, 8, 14, 14, 0, tzinfo=UTC)
TARGET_ID = "asset.storage.lab.vsp-g400"
WORKER_ID = "workload.atlas.workflow-worker-01"


class _AuditSink:
    def __init__(self) -> None:
        self.events: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.events.append(event)


def _scope() -> WorkflowScope:
    return WorkflowScope(
        organization_id="organization.development",
        environment_id="environment.development",
        site_id="site.local",
    )


def _human_context() -> WorkflowAccessContext:
    return WorkflowAccessContext(
        subject_id="subject.operator",
        role_ids=frozenset({"role.infrastructure-operator"}),
        actor_type="human",
        authentication_method="ldap",
        assurance_level="single_factor",
        scope=_scope(),
        authorized_target_ids=frozenset({TARGET_ID}),
        correlation_id="correlation.dispatch-intent-plan",
        decision_id="decision.dispatch-intent-plan",
        requested_at=NOW,
    )


def _worker_context(
    *,
    requested_at: datetime,
    audience: str = WORKFLOW_WORKER_AUDIENCE,
) -> WorkflowWorkerContext:
    return WorkflowWorkerContext(
        subject_id=WORKER_ID,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=audience,
        scope=_scope(),
        authorized_target_ids=frozenset({TARGET_ID}),
        correlation_id="correlation.dispatch-intent-worker",
        decision_id="decision.dispatch-intent-worker",
        requested_at=requested_at,
    )


async def _fixture() -> tuple[
    InMemoryWorkflowPlanRepository,
    WorkflowDispatchIntentStagingService,
    WorkflowRunPlan,
    WorkflowOrchestrationLease,
    WorkflowExecutionRun,
    WorkflowExecutionAttempt,
]:
    repository = InMemoryWorkflowPlanRepository()
    audit = _AuditSink()
    registry = code_owned_workflow_registry()
    plan = await WorkflowPlanningService(
        registry=registry,
        repository=repository,
        audit_sink=audit,
    ).create_plan(
        definition_id="workflow.evidence-grounded-query",
        definition_version=1,
        target_id=TARGET_ID,
        inputs={
            "purpose": "Stage immutable dispatch evidence.",
            "input_summary": "No delivery or execution.",
        },
        idempotency_key="dispatch-intent-plan-0001",
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
        idempotency_key="dispatch-intent-lease-0001",
        context=_worker_context(requested_at=NOW + timedelta(seconds=1)),
    )
    run = await WorkflowRunMaterializationService(
        registry=registry,
        plan_repository=repository,
        lease_repository=repository,
        run_repository=repository,
        audit_sink=audit,
    ).materialize(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token,
        idempotency_key="dispatch-intent-run-0001",
        context=_worker_context(requested_at=NOW + timedelta(seconds=2)),
    )
    root = run.step_runs[0]
    attempt = await WorkflowAttemptMaterializationService(
        plan_repository=repository,
        lease_repository=repository,
        run_repository=repository,
        attempt_repository=repository,
        audit_sink=audit,
    ).materialize(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        run_id=run.run_id,
        run_digest=run.canonical_digest,
        step_run_id=root.step_run_id,
        step_run_digest=root.canonical_digest,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token,
        idempotency_key="dispatch-intent-attempt-0001",
        context=_worker_context(requested_at=NOW + timedelta(seconds=3)),
    )
    current_lease = await lease_service.heartbeat(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token,
        lease_seconds=90,
        context=_worker_context(requested_at=NOW + timedelta(seconds=4)),
    )
    service = WorkflowDispatchIntentStagingService(
        plan_repository=repository,
        lease_repository=repository,
        run_repository=repository,
        attempt_repository=repository,
        dispatch_intent_repository=repository,
        audit_sink=audit,
    )
    return repository, service, plan, current_lease, run, attempt


async def _stage(
    service: WorkflowDispatchIntentStagingService,
    plan: WorkflowRunPlan,
    lease: WorkflowOrchestrationLease,
    run: WorkflowExecutionRun,
    attempt: WorkflowExecutionAttempt,
    *,
    idempotency_key: str = "dispatch-intent-stage-0001",
    fencing_token: int | None = None,
    context: WorkflowWorkerContext | None = None,
) -> WorkflowDispatchIntent:
    root = run.step_runs[0]
    return await service.stage(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        run_id=run.run_id,
        run_digest=run.canonical_digest,
        step_run_id=root.step_run_id,
        step_run_digest=root.canonical_digest,
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token if fencing_token is None else fencing_token,
        idempotency_key=idempotency_key,
        context=context or _worker_context(requested_at=NOW + timedelta(seconds=5)),
    )


@pytest.mark.asyncio
async def test_stages_exactly_one_intent_against_current_lease_without_mutation() -> None:
    repository, service, plan, lease, run, attempt = await _fixture()
    plan_before = await repository.get_by_id(plan_id=plan.plan_id)
    run_before = await repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
    attempts_before = await repository.list_attempts_by_run_id(run_id=run.run_id)

    dispatch_intent = await _stage(service, plan, lease, run, attempt)
    replay = await _stage(service, plan, lease, run, attempt)

    assert replay == dispatch_intent
    assert dispatch_intent.state.value == "staged"
    assert dispatch_intent.plan_digest == plan.canonical_digest
    assert dispatch_intent.run_digest == run.canonical_digest
    assert dispatch_intent.step_run_digest == run.step_runs[0].canonical_digest
    assert dispatch_intent.attempt_digest == attempt.canonical_digest
    assert dispatch_intent.lease_digest == lease.canonical_digest
    assert dispatch_intent.lease_digest != attempt.lease_digest
    assert dispatch_intent.fencing_token == lease.fencing_token
    assert dispatch_intent.worker_subject_id == WORKER_ID
    assert not any(dispatch_intent.authority.canonical_value().values())
    assert dispatch_intent.grants_dispatch_authority is False
    assert dispatch_intent.grants_execution_authority is False
    assert await repository.list_dispatch_intents_by_run_id(run_id=run.run_id) == (dispatch_intent,)
    assert await repository.get_by_id(plan_id=plan.plan_id) == plan_before
    assert await repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id) == run_before
    assert await repository.list_attempts_by_run_id(run_id=run.run_id) == attempts_before
    assert run.state.value == "created"
    assert all(step.state.value == "not_started" for step in run.step_runs)
    assert attempt.state.value == "created"


@pytest.mark.asyncio
async def test_second_intent_and_stale_fence_fail_closed() -> None:
    repository, service, plan, lease, run, attempt = await _fixture()
    first = await _stage(service, plan, lease, run, attempt)

    with pytest.raises(WorkflowDispatchIntentStagingError) as duplicate_error:
        await _stage(
            service,
            plan,
            lease,
            run,
            attempt,
            idempotency_key="dispatch-intent-stage-0002",
        )
    assert duplicate_error.value.code == "workflow_dispatch_intent_state_conflict"

    with pytest.raises(WorkflowDispatchIntentStagingError) as fence_error:
        await _stage(
            service,
            plan,
            lease,
            run,
            attempt,
            idempotency_key="dispatch-intent-stale-fence-0001",
            fencing_token=lease.fencing_token + 1,
        )
    assert fence_error.value.code == "workflow_dispatch_intent_lease_conflict"
    assert await repository.list_dispatch_intents_by_run_id(run_id=run.run_id) == (first,)


@pytest.mark.asyncio
async def test_non_worker_audience_and_unavailable_repository_fail_closed() -> None:
    repository, service, plan, lease, run, attempt = await _fixture()
    wrong_audience = _worker_context(
        requested_at=NOW + timedelta(seconds=5),
        audience="audience.not-workflow-worker",
    )

    with pytest.raises(WorkflowDispatchIntentStagingError) as audience_error:
        await _stage(
            service,
            plan,
            lease,
            run,
            attempt,
            context=wrong_audience,
        )
    assert audience_error.value.code == "workflow_dispatch_intent_worker_required"
    assert await repository.list_dispatch_intents_by_run_id(run_id=run.run_id) == ()

    unavailable = UnavailableWorkflowPlanRepository()
    with pytest.raises(WorkflowDispatchIntentStagingError) as unavailable_error:
        await unavailable.list_dispatch_intents_by_run_id(run_id=run.run_id)
    assert unavailable_error.value.code == "workflow_dispatch_intent_repository_unavailable"
