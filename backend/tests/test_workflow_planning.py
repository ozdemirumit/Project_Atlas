from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import cast

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
    NO_EXECUTION_SAFETY_NOTICE,
    WorkflowCapabilityClass,
    WorkflowDefinition,
    WorkflowDefinitionRegistry,
    WorkflowPlanAuthority,
    WorkflowPlanState,
    WorkflowPlanStepState,
    WorkflowScope,
    WorkflowStepDefinition,
    WorkflowStepKind,
    canonical_digest,
    code_owned_workflow_registry,
)

NOW = datetime(2026, 8, 13, 11, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")
TARGET_ID = "asset.storage.lab.primary"


class CollectingAuditSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail:
            raise RuntimeError("workflow audit unavailable")
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


def fixture(
    *, audit: CollectingAuditSink | None = None
) -> tuple[WorkflowPlanningService, InMemoryWorkflowPlanRepository, CollectingAuditSink]:
    repository = InMemoryWorkflowPlanRepository()
    sink = audit or CollectingAuditSink()
    return (
        WorkflowPlanningService(
            registry=code_owned_workflow_registry(),
            repository=repository,
            audit_sink=sink,
        ),
        repository,
        sink,
    )


async def create_plan(
    service: WorkflowPlanningService,
    *,
    access: WorkflowAccessContext | None = None,
    key: str = "workflow-plan-0001",
    inputs: dict[str, object] | None = None,
    definition_id: str = "workflow.evidence-grounded-query",
    definition_version: int = 1,
    target_id: str = TARGET_ID,
):
    return await service.create_plan(
        definition_id=definition_id,
        definition_version=definition_version,
        target_id=target_id,
        inputs=inputs or {"question": "What is the current storage health?"},
        idempotency_key=key,
        context=access or context(),
    )


def step(
    step_id: str,
    ordinal: int,
    *,
    depends_on: tuple[str, ...] = (),
    kind: WorkflowStepKind = WorkflowStepKind.EVIDENCE_QUERY,
    capability_class: WorkflowCapabilityClass = WorkflowCapabilityClass.C1,
    timeout_seconds: int = 30,
) -> WorkflowStepDefinition:
    return WorkflowStepDefinition(
        step_id=step_id,
        ordinal=ordinal,
        title=f"Step {ordinal}",
        kind=kind,
        capability_class=capability_class,
        timeout_seconds=timeout_seconds,
        depends_on=depends_on,
    )


def definition(*steps: WorkflowStepDefinition) -> WorkflowDefinition:
    return WorkflowDefinition(
        definition_id="workflow.test",
        version=1,
        title="Test workflow",
        purpose="Validate a bounded read-only workflow definition.",
        input_schema_version="workflow-input.v1",
        steps=tuple(steps),
    )


@pytest.mark.asyncio
async def test_code_owned_registry_is_stable_versioned_and_audited() -> None:
    service, _, audit = fixture()

    definitions = await service.list_definitions(context=context())

    assert [item.definition_id for item in definitions] == sorted(
        item.definition_id for item in definitions
    )
    assert {item.definition_id for item in definitions} == {
        "workflow.evidence-grounded-query",
        "workflow.scheduled-health-assessment",
        "workflow.technical-report-generation",
    }
    assert all(item.version == 1 and len(item.definition_digest) == 64 for item in definitions)
    assert all(
        step.capability_class in set(WorkflowCapabilityClass) and step.kind in set(WorkflowStepKind)
        for item in definitions
        for step in item.steps
    )
    assert audit.records[-1].result_code == "workflow_definitions_returned"


def test_definition_rejects_missing_duplicate_cyclic_and_unordered_dependencies() -> None:
    with pytest.raises(ValueError, match="missing dependency"):
        definition(step("first", 1, depends_on=("missing",)))

    with pytest.raises(ValueError, match="identifiers must be unique"):
        definition(step("same", 1), step("same", 2))

    with pytest.raises(ValueError, match="dependency cycle"):
        definition(
            step("first", 1, depends_on=("second",)),
            step("second", 2, depends_on=("first",)),
        )

    with pytest.raises(ValueError, match="follow dependency order"):
        definition(step("first", 1, depends_on=("second",)), step("second", 2))

    with pytest.raises(ValueError, match="stable contiguous order"):
        definition(step("first", 2))


def test_definition_rejects_unsupported_kind_capability_timeout_and_duplicate_active_id() -> None:
    with pytest.raises(ValueError, match="unsupported workflow step kind"):
        step("first", 1, kind=cast(WorkflowStepKind, "connector_invocation"))

    with pytest.raises(ValueError, match="limited to C0-C2"):
        step("first", 1, capability_class=cast(WorkflowCapabilityClass, "C3"))

    with pytest.raises(ValueError, match="timeout"):
        step("first", 1, timeout_seconds=3601)

    active = definition(step("first", 1))
    with pytest.raises(ValueError, match="one active version"):
        WorkflowDefinitionRegistry((active, replace(active, version=2)))


@pytest.mark.asyncio
async def test_create_plan_binds_exact_definition_scope_input_and_zero_authority() -> None:
    service, _, audit = fixture()

    plan = await create_plan(service)
    definition_record = code_owned_workflow_registry().get(plan.definition_id, 1)

    assert definition_record is not None
    assert plan.definition_digest == definition_record.definition_digest
    assert plan.scope == SCOPE
    assert plan.target_id == TARGET_ID
    assert plan.target_type == "storage"
    assert plan.creator_subject_id == "subject.operator"
    assert plan.state is WorkflowPlanState.PLANNED
    assert all(step.state is WorkflowPlanStepState.NOT_STARTED for step in plan.steps)
    assert plan.durable is False
    assert plan.safety_notice == NO_EXECUTION_SAFETY_NOTICE
    assert not any(plan.authority.canonical_value().values())
    assert plan.canonical_digest == canonical_digest(plan.digest_payload())
    assert audit.records[-1].result_code == "workflow_plan_authorized"
    assert dict(audit.records[-1].target_metadata)["durable"] == "false"


@pytest.mark.asyncio
async def test_canonical_inputs_and_exact_replay_produce_one_immutable_plan() -> None:
    service, _, audit = fixture()

    first = await create_plan(
        service,
        inputs={"question": "health", "options": {"fresh": True, "limit": 5}},
    )
    replay = await create_plan(
        service,
        access=context(requested_at=NOW + timedelta(minutes=1)),
        inputs={"options": {"limit": 5, "fresh": True}, "question": "health"},
    )

    assert replay == first
    assert [record.result_code for record in audit.records] == [
        "workflow_plan_authorized",
        "workflow_plan_replayed",
    ]
    with pytest.raises(FrozenInstanceError):
        first.target_id = "asset.storage.changed"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_changed_idempotency_content_is_rejected_without_second_plan() -> None:
    service, _, audit = fixture()
    await create_plan(service)

    with pytest.raises(WorkflowPlanningError) as reused:
        await create_plan(service, inputs={"question": "changed"})

    assert reused.value.code == "workflow_idempotency_conflict"
    assert len(await service.list_plans(context=context())) == 1
    assert "workflow_idempotency_conflict" in [record.result_code for record in audit.records]


@pytest.mark.asyncio
async def test_concurrent_exact_requests_converge_on_one_plan() -> None:
    service, _, _ = fixture()

    first, second = await asyncio.gather(create_plan(service), create_plan(service))

    assert first == second
    assert len(await service.list_plans(context=context())) == 1


@pytest.mark.asyncio
async def test_human_scope_target_and_definition_boundaries_fail_closed() -> None:
    service, _, _ = fixture()

    with pytest.raises(WorkflowPlanningError) as machine:
        await create_plan(service, access=context(actor_type="service"))
    assert machine.value.code == "workflow_human_required"

    with pytest.raises(WorkflowPlanningError) as target:
        await create_plan(service, target_id="asset.storage.lab.unknown")
    assert target.value.code == "workflow_target_unavailable"

    with pytest.raises(WorkflowPlanningError) as unavailable:
        await create_plan(service, definition_id="workflow.unknown")
    assert unavailable.value.code == "workflow_definition_unavailable"

    with pytest.raises(WorkflowPlanningError) as version:
        await create_plan(service, definition_version=2)
    assert version.value.code == "workflow_definition_unavailable"


@pytest.mark.asyncio
async def test_get_and_list_never_disclose_foreign_scope_or_target() -> None:
    service, _, _ = fixture()
    plan = await create_plan(service)
    foreign_scope = WorkflowScope("organization.foreign", "environment.development", "site.local")

    for access in (
        context(scope=foreign_scope),
        context(targets=frozenset({"asset.storage.lab.secondary"})),
    ):
        with pytest.raises(WorkflowPlanningError) as denied:
            await service.get_plan(plan_id=plan.plan_id, context=access)
        assert denied.value.code == "workflow_plan_not_found"
        assert await service.list_plans(context=access) == ()

    other_human = context(subject_id="subject.reader")
    assert await service.get_plan(plan_id=plan.plan_id, context=other_human) == plan


@pytest.mark.asyncio
async def test_audit_failure_blocks_creation_and_reads_before_return() -> None:
    audit = CollectingAuditSink(fail=True)
    service, repository, _ = fixture(audit=audit)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await create_plan(service)
    assert (
        await repository.list_scoped(
            scope=SCOPE,
            authorized_target_ids=frozenset({TARGET_ID}),
            limit=10,
        )
        == ()
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.list_definitions(context=context())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.list_plans(context=context())


@pytest.mark.asyncio
async def test_unavailable_repository_fails_closed_instead_of_falling_back_to_memory() -> None:
    service = WorkflowPlanningService(
        registry=code_owned_workflow_registry(),
        repository=UnavailableWorkflowPlanRepository(),
        audit_sink=CollectingAuditSink(),
    )

    assert service.durable is False
    with pytest.raises(WorkflowPlanningError) as unavailable:
        await create_plan(service)
    assert unavailable.value.code == "workflow_repository_unavailable"

    with pytest.raises(WorkflowPlanningError) as listed:
        await service.list_plans(context=context())
    assert listed.value.code == "workflow_repository_unavailable"


def test_plan_authority_and_non_planned_states_cannot_be_forged() -> None:
    with pytest.raises(ValueError, match="cannot grant operational authority"):
        WorkflowPlanAuthority(worker_dispatch_authorized=True)


@pytest.mark.asyncio
async def test_invalid_input_payloads_are_rejected_before_persistence() -> None:
    service, repository, _ = fixture()

    for payload, expected_code in (
        ({"not_json": object()}, "workflow_inputs_invalid"),
        ({"not_finite": float("nan")}, "workflow_inputs_invalid"),
        ({"too_large": "x" * 17_000}, "workflow_inputs_too_large"),
    ):
        with pytest.raises(WorkflowPlanningError) as invalid:
            await create_plan(service, inputs=payload, key=f"workflow-{expected_code}-0001")
        assert invalid.value.code == expected_code

    assert (
        await repository.list_scoped(
            scope=SCOPE,
            authorized_target_ids=frozenset({TARGET_ID}),
            limit=10,
        )
        == ()
    )
