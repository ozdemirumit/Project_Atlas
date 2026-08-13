from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.adapters import (
    InMemoryWorkflowPlanRepository,
    UnavailableWorkflowPlanRepository,
)
from atlas.modules.workflows.application import (
    WorkflowAccessContext,
    WorkflowPlanningError,
    WorkflowPlanningService,
)
from atlas.modules.workflows.domain import (
    WorkflowPlanState,
    WorkflowPlanStepState,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_registry,
)

NOW = datetime(2026, 8, 13, 14, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")
TARGET_ID = "asset.storage.lab.primary"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def context(
    *,
    subject_id: str = "subject.operator",
    actor_type: str = "human",
    scope: WorkflowScope = SCOPE,
    targets: frozenset[str] = frozenset({TARGET_ID}),
    requested_at: datetime = NOW,
) -> WorkflowAccessContext:
    return WorkflowAccessContext(
        subject_id=subject_id,
        role_ids=frozenset({"role.infrastructure-operator"}),
        actor_type=actor_type,
        authentication_method="browser_session",
        assurance_level="single_factor",
        scope=scope,
        authorized_target_ids=targets,
        correlation_id=f"correlation.{subject_id}",
        decision_id=f"decision.{subject_id}",
        requested_at=requested_at,
    )


def fixture() -> tuple[
    WorkflowPlanningService, InMemoryWorkflowPlanRepository, CollectingAuditSink
]:
    repository = InMemoryWorkflowPlanRepository()
    audit = CollectingAuditSink()
    return (
        WorkflowPlanningService(
            registry=code_owned_workflow_registry(),
            repository=repository,
            audit_sink=audit,
        ),
        repository,
        audit,
    )


async def create_plan(
    service: WorkflowPlanningService, *, access: WorkflowAccessContext | None = None
) -> WorkflowRunPlan:
    return await service.create_plan(
        definition_id="workflow.evidence-grounded-query",
        definition_version=1,
        target_id=TARGET_ID,
        inputs={"question": "What is the current storage health?"},
        idempotency_key="workflow-plan-cancel-fixture",
        context=access or context(),
    )


async def cancel_plan(
    service: WorkflowPlanningService,
    *,
    access: WorkflowAccessContext,
    plan_id: str,
    reason: str = "The maintenance window was withdrawn.",
    key: str = "workflow-cancel-0001",
    acknowledged: bool = True,
) -> WorkflowRunPlan:
    return await service.cancel_plan(
        plan_id=plan_id,
        reason=reason,
        acknowledge_no_external_undo=acknowledged,
        idempotency_key=key,
        context=access,
    )


@pytest.mark.asyncio
async def test_cancel_planned_plan_appends_one_immutable_bound_transition() -> None:
    service, _, audit = fixture()
    planned = await create_plan(service)

    cancelled = await cancel_plan(
        service,
        access=context(requested_at=NOW + timedelta(minutes=1)),
        plan_id=planned.plan_id,
        reason="  Maintenance   window\nwithdrawn.  ",
    )

    assert cancelled.state is WorkflowPlanState.CANCELLED
    assert len(cancelled.transition_history) == 1
    transition = cancelled.transition_history[0]
    assert transition.prior_state is WorkflowPlanState.PLANNED
    assert transition.new_state is WorkflowPlanState.CANCELLED
    assert transition.actor_subject_id == "subject.operator"
    assert transition.scope == SCOPE
    assert transition.target_id == TARGET_ID
    assert transition.reason == "Maintenance window withdrawn."
    assert transition.reason_digest == canonical_digest({"reason": transition.reason})
    assert transition.canonical_digest == canonical_digest(transition.digest_payload())
    assert cancelled.canonical_digest == canonical_digest(cancelled.digest_payload())
    assert all(step.state is WorkflowPlanStepState.NOT_STARTED for step in cancelled.steps)
    assert not any(cancelled.authority.canonical_value().values())
    assert audit.records[-1].result_code == "workflow_plan_cancelled"
    with pytest.raises(FrozenInstanceError):
        transition.__setattr__("reason", "changed")


@pytest.mark.asyncio
async def test_same_key_and_normalized_request_replays_exactly_but_changed_request_conflicts() -> (
    None
):
    service, _, audit = fixture()
    planned = await create_plan(service)
    first = await cancel_plan(
        service,
        access=context(requested_at=NOW + timedelta(minutes=1)),
        plan_id=planned.plan_id,
        reason="Window withdrawn",
    )
    replay = await cancel_plan(
        service,
        access=context(requested_at=NOW + timedelta(minutes=2)),
        plan_id=planned.plan_id,
        reason=" Window   withdrawn ",
    )

    assert replay == first
    assert len(replay.transition_history) == 1
    assert audit.records[-1].result_code == "workflow_plan_cancellation_replayed"
    with pytest.raises(WorkflowPlanningError) as conflict:
        await cancel_plan(
            service,
            access=context(requested_at=NOW + timedelta(minutes=3)),
            plan_id=planned.plan_id,
            reason="A different reason",
        )
    assert conflict.value.code == "workflow_cancellation_idempotency_conflict"


@pytest.mark.asyncio
async def test_cancelled_is_terminal_and_concurrent_keys_create_only_one_transition() -> None:
    service, _, _ = fixture()
    planned = await create_plan(service)
    attempts = await asyncio.gather(
        cancel_plan(
            service,
            access=context(requested_at=NOW + timedelta(minutes=1)),
            plan_id=planned.plan_id,
            key="workflow-cancel-race-a",
        ),
        cancel_plan(
            service,
            access=context(requested_at=NOW + timedelta(minutes=1)),
            plan_id=planned.plan_id,
            key="workflow-cancel-race-b",
        ),
        return_exceptions=True,
    )

    successes = [item for item in attempts if not isinstance(item, BaseException)]
    failures = [item for item in attempts if isinstance(item, WorkflowPlanningError)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].code in {
        "workflow_cancellation_state_conflict",
        "workflow_plan_not_cancellable",
    }
    assert len(successes[0].transition_history) == 1

    with pytest.raises(WorkflowPlanningError) as terminal:
        await cancel_plan(
            service,
            access=context(requested_at=NOW + timedelta(minutes=2)),
            plan_id=planned.plan_id,
            key="workflow-cancel-terminal",
        )
    assert terminal.value.code == "workflow_plan_not_cancellable"


@pytest.mark.asyncio
async def test_cancellation_requires_human_exact_scope_target_reason_and_acknowledgement() -> None:
    service, _, _ = fixture()
    planned = await create_plan(service)
    foreign_scope = WorkflowScope("organization.foreign", "environment.dev", "site.local")

    cases = (
        (context(actor_type="service"), "workflow_human_required"),
        (context(scope=foreign_scope), "workflow_plan_not_found"),
        (
            context(targets=frozenset({"asset.storage.lab.secondary"})),
            "workflow_plan_not_found",
        ),
    )
    for index, (access, expected) in enumerate(cases):
        with pytest.raises(WorkflowPlanningError) as denied:
            await cancel_plan(
                service,
                access=access,
                plan_id=planned.plan_id,
                key=f"workflow-cancel-denied-{index}",
            )
        assert denied.value.code == expected

    for reason in ("", " " * 4, "x" * 501):
        with pytest.raises(WorkflowPlanningError) as invalid:
            await cancel_plan(
                service,
                access=context(),
                plan_id=planned.plan_id,
                reason=reason,
                key="workflow-cancel-bad-reason",
            )
        assert invalid.value.code == "workflow_cancellation_reason_invalid"

    with pytest.raises(WorkflowPlanningError) as acknowledgement:
        await cancel_plan(
            service,
            access=context(),
            plan_id=planned.plan_id,
            acknowledged=False,
            key="workflow-cancel-no-ack",
        )
    assert acknowledgement.value.code == "workflow_cancellation_acknowledgement_required"


@pytest.mark.asyncio
async def test_unavailable_repository_fails_closed_for_cancellation() -> None:
    service = WorkflowPlanningService(
        registry=code_owned_workflow_registry(),
        repository=UnavailableWorkflowPlanRepository(),
        audit_sink=CollectingAuditSink(),
    )

    with pytest.raises(WorkflowPlanningError) as unavailable:
        await cancel_plan(
            service,
            access=context(),
            plan_id="workflow-plan.unavailable",
        )
    assert unavailable.value.code == "workflow_repository_unavailable"
