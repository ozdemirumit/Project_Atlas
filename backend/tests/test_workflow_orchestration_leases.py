from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_WORKER_AUDIENCE,
    WorkflowAccessContext,
    WorkflowOrchestrationLeaseError,
    WorkflowOrchestrationLeaseService,
    WorkflowPlanningService,
    WorkflowWorkerContext,
)
from atlas.modules.workflows.domain import (
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOrchestrationLeaseState,
    WorkflowPlanState,
    WorkflowPlanStepState,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_registry,
)

NOW = datetime(2026, 8, 13, 16, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")
TARGET_ID = "asset.storage.lab.primary"


class CollectingAuditSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail:
            raise RuntimeError("workflow lease audit unavailable")
        self.records.append(event)


class FailingLeaseRepository(InMemoryWorkflowPlanRepository):
    async def get_lease_by_plan_id(self, *, plan_id: str):  # type: ignore[no-untyped-def]
        raise RuntimeError("workflow lease repository unavailable")


def human_context(*, requested_at: datetime = NOW) -> WorkflowAccessContext:
    return WorkflowAccessContext(
        subject_id="subject.operator",
        role_ids=frozenset({"role.infrastructure-operator"}),
        actor_type="human",
        authentication_method="browser_session",
        assurance_level="single_factor",
        scope=SCOPE,
        authorized_target_ids=frozenset({TARGET_ID}),
        correlation_id="correlation.operator",
        decision_id="decision.operator",
        requested_at=requested_at,
    )


def worker_context(
    *,
    subject_id: str = "service.workflow-worker-01",
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_WORKER_AUDIENCE,
    scope: WorkflowScope = SCOPE,
    targets: frozenset[str] = frozenset({TARGET_ID}),
    requested_at: datetime = NOW,
) -> WorkflowWorkerContext:
    return WorkflowWorkerContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        authorized_target_ids=targets,
        correlation_id=f"correlation.{subject_id}",
        decision_id=f"decision.{subject_id}",
        requested_at=requested_at,
    )


async def fixture(
    *, audit: CollectingAuditSink | None = None
) -> tuple[
    WorkflowPlanningService,
    WorkflowOrchestrationLeaseService,
    InMemoryWorkflowPlanRepository,
    CollectingAuditSink,
    WorkflowRunPlan,
]:
    repository = InMemoryWorkflowPlanRepository()
    sink = audit or CollectingAuditSink()
    planning = WorkflowPlanningService(
        registry=code_owned_workflow_registry(), repository=repository, audit_sink=sink
    )
    plan = await planning.create_plan(
        definition_id="workflow.evidence-grounded-query",
        definition_version=1,
        target_id=TARGET_ID,
        inputs={"question": "What is the current storage health?"},
        idempotency_key="workflow-plan-lease-fixture",
        context=human_context(),
    )
    leases = WorkflowOrchestrationLeaseService(
        plan_repository=repository,
        lease_repository=repository,
        audit_sink=sink,
    )
    return planning, leases, repository, sink, plan


async def acquire(
    service: WorkflowOrchestrationLeaseService,
    plan: WorkflowRunPlan,
    *,
    context: WorkflowWorkerContext | None = None,
    key: str = "workflow-lease-acquire-0001",
    seconds: int = 60,
) -> WorkflowOrchestrationLease:
    return await service.acquire(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        lease_seconds=seconds,
        idempotency_key=key,
        context=context or worker_context(),
    )


@pytest.mark.asyncio
async def test_acquire_binds_exact_plan_worker_fence_and_zero_authority() -> None:
    _, service, repository, audit, plan = await fixture()

    lease = await acquire(service, plan)
    stored_plan = await repository.get_by_id(plan_id=plan.plan_id)

    assert lease.plan_id == plan.plan_id
    assert lease.plan_digest == plan.canonical_digest
    assert lease.scope == plan.scope
    assert lease.target_id == plan.target_id
    assert lease.target_type == plan.target_type
    assert lease.worker_subject_id == "service.workflow-worker-01"
    assert lease.acquired_at == NOW == lease.last_heartbeat_at
    assert lease.expires_at == NOW + timedelta(seconds=60)
    assert lease.fencing_token == 1
    assert lease.state is WorkflowOrchestrationLeaseState.ACTIVE
    assert lease.effective_state(requested_at=NOW + timedelta(seconds=59)).value == "active"
    assert lease.effective_state(requested_at=lease.expires_at).value == "expired"
    assert lease.canonical_digest == canonical_digest(lease.digest_payload())
    assert lease.grants_execution_authority is False
    assert stored_plan == plan
    assert stored_plan is not None
    assert stored_plan.state is WorkflowPlanState.PLANNED
    assert all(step.state is WorkflowPlanStepState.NOT_STARTED for step in stored_plan.steps)
    assert not any(stored_plan.authority.canonical_value().values())
    assert audit.records[-1].result_code == "workflow_lease_acquired"
    assert dict(audit.records[-1].target_metadata)["execution_authority"] == "false"


@pytest.mark.asyncio
async def test_same_acquisition_replays_exactly_and_changed_request_conflicts() -> None:
    _, service, _, audit, plan = await fixture()
    first = await acquire(service, plan)
    replay = await acquire(
        service,
        plan,
        context=worker_context(requested_at=NOW + timedelta(seconds=10)),
    )

    assert replay == first
    assert audit.records[-1].result_code == "workflow_lease_acquisition_replayed"
    with pytest.raises(WorkflowOrchestrationLeaseError) as conflict:
        await acquire(
            service,
            plan,
            context=worker_context(requested_at=NOW + timedelta(seconds=11)),
            seconds=90,
        )
    assert conflict.value.code == "workflow_lease_idempotency_conflict"
    assert audit.records[-1].outcome == "denied"


@pytest.mark.asyncio
async def test_unexpired_competition_and_concurrent_acquisition_fail_closed() -> None:
    _, service, _, audit, plan = await fixture()
    owner = await acquire(service, plan)
    with pytest.raises(WorkflowOrchestrationLeaseError) as contended:
        await acquire(
            service,
            plan,
            context=worker_context(
                subject_id="service.workflow-worker-02",
                requested_at=NOW + timedelta(seconds=1),
            ),
            key="workflow-lease-acquire-0002",
        )
    assert contended.value.code == "workflow_lease_contended"
    assert audit.records[-1].outcome == "denied"

    _, concurrent, _, _, concurrent_plan = await fixture()
    results = await asyncio.gather(
        acquire(concurrent, concurrent_plan, key="workflow-lease-concurrent-01"),
        acquire(
            concurrent,
            concurrent_plan,
            context=worker_context(subject_id="service.workflow-worker-02"),
            key="workflow-lease-concurrent-02",
        ),
        return_exceptions=True,
    )
    leases = [item for item in results if not isinstance(item, BaseException)]
    failures = [item for item in results if isinstance(item, WorkflowOrchestrationLeaseError)]
    assert len(leases) == 1
    assert len(failures) == 1
    assert failures[0].code == "workflow_lease_contended"
    assert leases[0].fencing_token == owner.fencing_token


@pytest.mark.asyncio
async def test_authoritative_expiry_allows_takeover_with_higher_fencing_token() -> None:
    _, service, _, _, plan = await fixture()
    first = await acquire(service, plan, seconds=30)

    second = await acquire(
        service,
        plan,
        context=worker_context(
            subject_id="service.workflow-worker-02",
            requested_at=first.expires_at,
        ),
        key="workflow-lease-takeover-0002",
    )

    assert second.worker_subject_id == "service.workflow-worker-02"
    assert second.fencing_token == first.fencing_token + 1
    assert second.lease_id != first.lease_id
    assert second.acquired_at == first.expires_at


@pytest.mark.asyncio
async def test_heartbeat_and_release_require_exact_active_fence() -> None:
    _, service, repository, audit, plan = await fixture()
    lease = await acquire(service, plan)
    heartbeat_context = worker_context(requested_at=NOW + timedelta(seconds=20))

    heartbeated = await service.heartbeat(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token,
        lease_seconds=120,
        context=heartbeat_context,
    )
    assert heartbeated.last_heartbeat_at == heartbeat_context.requested_at
    assert heartbeated.expires_at == heartbeat_context.requested_at + timedelta(seconds=120)
    assert heartbeated.fencing_token == lease.fencing_token
    assert heartbeated.canonical_digest != lease.canonical_digest

    released = await service.release(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        lease_id=heartbeated.lease_id,
        lease_digest=heartbeated.canonical_digest,
        fencing_token=heartbeated.fencing_token,
        context=worker_context(requested_at=NOW + timedelta(seconds=21)),
    )
    assert released.state is WorkflowOrchestrationLeaseState.RELEASED
    assert (
        released.effective_state(requested_at=NOW + timedelta(seconds=22))
        is WorkflowOrchestrationLeaseEffectiveState.RELEASED
    )
    assert audit.records[-1].result_code == "workflow_lease_released"
    with pytest.raises(WorkflowOrchestrationLeaseError) as stale:
        await service.heartbeat(
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            lease_id=lease.lease_id,
            lease_digest=lease.canonical_digest,
            fencing_token=lease.fencing_token,
            lease_seconds=60,
            context=worker_context(requested_at=NOW + timedelta(seconds=22)),
        )
    assert stale.value.code == "workflow_lease_conflict"
    assert await repository.get_by_id(plan_id=plan.plan_id) == plan


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subject_id", "lease_digest", "fencing_delta"),
    (
        ("service.workflow-worker-02", None, 0),
        ("service.workflow-worker-01", "0" * 64, 0),
        ("service.workflow-worker-01", None, 1),
    ),
)
async def test_wrong_actor_digest_or_fence_is_rejected(
    subject_id: str, lease_digest: str | None, fencing_delta: int
) -> None:
    _, service, _, audit, plan = await fixture()
    lease = await acquire(service, plan)

    with pytest.raises(WorkflowOrchestrationLeaseError) as rejected:
        await service.heartbeat(
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            lease_id=lease.lease_id,
            lease_digest=lease_digest or lease.canonical_digest,
            fencing_token=lease.fencing_token + fencing_delta,
            lease_seconds=60,
            context=worker_context(subject_id=subject_id, requested_at=NOW + timedelta(seconds=1)),
        )
    assert rejected.value.code == "workflow_lease_conflict"
    assert audit.records[-1].outcome == "denied"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actor_type", "method", "audience"),
    (
        ("human", "browser_session", WORKFLOW_WORKER_AUDIENCE),
        ("service", "api_token", WORKFLOW_WORKER_AUDIENCE),
        ("service", "workload_token", "audience.other"),
    ),
)
async def test_only_dedicated_workload_identity_can_mutate_leases(
    actor_type: str, method: str, audience: str
) -> None:
    _, service, _, audit, plan = await fixture()

    with pytest.raises(WorkflowOrchestrationLeaseError) as rejected:
        await acquire(
            service,
            plan,
            context=worker_context(
                actor_type=actor_type,
                authentication_method=method,
                audience=audience,
            ),
        )
    assert rejected.value.code == "workflow_worker_identity_required"
    assert audit.records[-1].result_code == "workflow_worker_identity_required"


@pytest.mark.asyncio
async def test_duration_scope_target_plan_digest_and_cancelled_plan_fail_closed() -> None:
    planning, service, _, audit, plan = await fixture()
    for seconds in (29, 301):
        with pytest.raises(WorkflowOrchestrationLeaseError) as invalid_duration:
            await acquire(service, plan, seconds=seconds)
        assert invalid_duration.value.code == "workflow_lease_duration_invalid"

    with pytest.raises(WorkflowOrchestrationLeaseError) as wrong_digest:
        await service.acquire(
            plan_id=plan.plan_id,
            plan_digest="0" * 64,
            lease_seconds=60,
            idempotency_key="workflow-lease-wrong-digest",
            context=worker_context(),
        )
    assert wrong_digest.value.code == "workflow_lease_plan_conflict"

    with pytest.raises(WorkflowOrchestrationLeaseError) as hidden:
        await acquire(service, plan, context=worker_context(targets=frozenset()))
    assert hidden.value.code == "workflow_lease_plan_not_found"

    lease = await acquire(service, plan, key="workflow-lease-before-cancel")
    cancelled = await planning.cancel_plan(
        plan_id=plan.plan_id,
        reason="The maintenance window was withdrawn.",
        acknowledge_no_external_undo=True,
        idempotency_key="workflow-cancel-after-lease",
        context=human_context(requested_at=NOW + timedelta(seconds=1)),
    )
    assert cancelled.state is WorkflowPlanState.CANCELLED
    with pytest.raises(WorkflowOrchestrationLeaseError) as terminal:
        await service.release(
            plan_id=plan.plan_id,
            plan_digest=plan.canonical_digest,
            lease_id=lease.lease_id,
            lease_digest=lease.canonical_digest,
            fencing_token=lease.fencing_token,
            context=worker_context(requested_at=NOW + timedelta(seconds=2)),
        )
    assert terminal.value.code == "workflow_lease_plan_conflict"
    assert audit.records[-1].outcome == "denied"


@pytest.mark.asyncio
async def test_audit_and_repository_failure_never_return_success() -> None:
    _, _, memory, _, plan = await fixture()
    service = WorkflowOrchestrationLeaseService(
        plan_repository=memory,
        lease_repository=memory,
        audit_sink=CollectingAuditSink(fail=True),
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await acquire(service, plan)

    repository = FailingLeaseRepository()
    audit = CollectingAuditSink()
    planning = WorkflowPlanningService(
        registry=code_owned_workflow_registry(), repository=repository, audit_sink=audit
    )
    plan = await planning.create_plan(
        definition_id="workflow.evidence-grounded-query",
        definition_version=1,
        target_id=TARGET_ID,
        inputs={"question": "health"},
        idempotency_key="workflow-plan-failing-repository",
        context=human_context(),
    )
    service = WorkflowOrchestrationLeaseService(
        plan_repository=repository, lease_repository=repository, audit_sink=audit
    )
    with pytest.raises(RuntimeError, match="repository unavailable"):
        await acquire(service, plan)
