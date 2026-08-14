from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WorkflowAccessContext,
    WorkflowOrchestrationLeaseService,
    WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord,
    WorkflowOutboxPublicationLeaseAcquireRequest,
    WorkflowOutboxPublicationLeaseAcquireResult,
    WorkflowOutboxPublicationLeaseAcquireStatus,
    WorkflowOutboxPublicationLeaseError,
    WorkflowOutboxPublicationLeaseMutationRequest,
    WorkflowOutboxPublicationLeaseMutationResult,
    WorkflowOutboxPublicationLeaseMutationStatus,
    WorkflowOutboxPublicationLeaseService,
    WorkflowOutboxPublisherContext,
    WorkflowPlanningService,
    WorkflowWorkerContext,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowOutboxPublicationLeaseState,
    WorkflowPlanAuthority,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_registry,
)

NOW = datetime(2026, 8, 14, 17, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.development", "site.local")
TARGET_ID = "asset.storage.lab.primary"
PUBLISHER_ID = "service.workflow-outbox-publisher-01"


class CollectingAuditSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail:
            raise RuntimeError("publication lease audit unavailable")
        self.records.append(event)


class InMemoryPublicationLeaseRepository:
    def __init__(self, outbox: WorkflowDispatchOutboxEntry) -> None:
        self.outbox = outbox
        self.current: WorkflowOutboxPublicationLease | None = None
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord,
        ] = {}

    @property
    def durable(self) -> bool:
        return True

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        return self.outbox if self.outbox.outbox_entry_id == outbox_entry_id else None

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        if self.current is None or self.current.outbox_entry_id != outbox_entry_id:
            return None
        return self.current

    async def get_publication_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord | None:
        return self.requests.get((scope, publisher_subject_id, idempotency_key))

    async def acquire_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseAcquireRequest
    ) -> WorkflowOutboxPublicationLeaseAcquireResult:
        key = (
            request.candidate.scope,
            request.candidate.publisher_subject_id,
            request.idempotency_key,
        )
        prior = self.requests.get(key)
        if prior is not None:
            status = (
                WorkflowOutboxPublicationLeaseAcquireStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowOutboxPublicationLeaseAcquireStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowOutboxPublicationLeaseAcquireResult(status, prior.lease)
        if request.expected_outbox_entry_digest != self.outbox.canonical_digest:
            return WorkflowOutboxPublicationLeaseAcquireResult(
                WorkflowOutboxPublicationLeaseAcquireStatus.EVIDENCE_CONFLICT, self.current
            )
        if self.current is not None:
            if (
                self.current.effective_state(requested_at=request.requested_at)
                is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            ):
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED, self.current
                )
            if (
                request.expected_current_lease_digest != self.current.canonical_digest
                or request.expected_current_publication_fencing_token
                != self.current.publication_fencing_token
            ):
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.EVIDENCE_CONFLICT,
                    self.current,
                )
        elif (
            request.expected_current_lease_digest is not None
            or request.expected_current_publication_fencing_token is not None
        ):
            return WorkflowOutboxPublicationLeaseAcquireResult(
                WorkflowOutboxPublicationLeaseAcquireStatus.EVIDENCE_CONFLICT, None
            )
        self.current = request.candidate
        self.requests[key] = WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord(
            request.request_fingerprint, request.candidate
        )
        return WorkflowOutboxPublicationLeaseAcquireResult(
            WorkflowOutboxPublicationLeaseAcquireStatus.ACQUIRED, request.candidate
        )

    async def heartbeat_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return self._mutate(request)

    async def release_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return self._mutate(request)

    def _mutate(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        if self.current is None:
            return WorkflowOutboxPublicationLeaseMutationResult(
                WorkflowOutboxPublicationLeaseMutationStatus.NOT_FOUND, None
            )
        if (
            request.expected_outbox_entry_digest != self.outbox.canonical_digest
            or request.expected_orchestration_lease_id != self.current.orchestration_lease_id
            or request.expected_orchestration_lease_digest
            != self.current.orchestration_lease_digest
            or request.expected_orchestration_fencing_token
            != self.current.orchestration_fencing_token
        ):
            return WorkflowOutboxPublicationLeaseMutationResult(
                WorkflowOutboxPublicationLeaseMutationStatus.EVIDENCE_CONFLICT,
                self.current,
            )
        if (
            request.expected_publication_lease_id != self.current.publication_lease_id
            or request.expected_publication_lease_digest != self.current.canonical_digest
            or request.expected_publication_fencing_token != self.current.publication_fencing_token
            or request.publisher_subject_id != self.current.publisher_subject_id
            or self.current.effective_state(requested_at=request.requested_at)
            is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
        ):
            return WorkflowOutboxPublicationLeaseMutationResult(
                WorkflowOutboxPublicationLeaseMutationStatus.LEASE_CONFLICT, self.current
            )
        self.current = request.updated_lease
        return WorkflowOutboxPublicationLeaseMutationResult(
            WorkflowOutboxPublicationLeaseMutationStatus.UPDATED, self.current
        )


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


def worker_context(*, requested_at: datetime) -> WorkflowWorkerContext:
    return WorkflowWorkerContext(
        subject_id="service.workflow-worker-01",
        actor_type="service",
        authentication_method="workload_token",
        credential_audience="audience.workflow-worker",
        scope=SCOPE,
        authorized_target_ids=frozenset({TARGET_ID}),
        correlation_id="correlation.worker",
        decision_id="decision.worker",
        requested_at=requested_at,
    )


def publisher_context(
    *,
    subject_id: str = PUBLISHER_ID,
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    requested_at: datetime = NOW + timedelta(seconds=3),
    targets: frozenset[str] = frozenset({TARGET_ID}),
) -> WorkflowOutboxPublisherContext:
    return WorkflowOutboxPublisherContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=SCOPE,
        authorized_target_ids=targets,
        correlation_id=f"correlation.{subject_id}",
        decision_id=f"decision.{subject_id}",
        requested_at=requested_at,
    )


def outbox_entry(
    plan: WorkflowRunPlan, lease: WorkflowOrchestrationLease
) -> WorkflowDispatchOutboxEntry:
    payload = {
        "admitted_at": (NOW + timedelta(seconds=2)).isoformat(),
        "attempt_digest": "5" * 64,
        "attempt_id": "workflow-attempt.fixture",
        "attempt_number": 1,
        "authority": WorkflowPlanAuthority().canonical_value(),
        "dispatch_intent_digest": "4" * 64,
        "dispatch_intent_id": "workflow-dispatch-intent.fixture",
        "fencing_token": lease.fencing_token,
        "lease_digest": lease.canonical_digest,
        "lease_id": lease.lease_id,
        "outbox_entry_id": "workflow-dispatch-outbox.fixture",
        "plan_digest": plan.canonical_digest,
        "plan_id": plan.plan_id,
        "run_digest": "2" * 64,
        "run_id": "workflow-run.fixture",
        "scope": plan.scope.canonical_value(),
        "state": WorkflowDispatchOutboxState.PENDING_PUBLICATION.value,
        "step_id": "collect-evidence",
        "step_run_digest": "3" * 64,
        "step_run_id": "workflow-step-run.fixture",
        "target_id": plan.target_id,
        "target_type": plan.target_type,
        "worker_subject_id": lease.worker_subject_id,
    }
    return WorkflowDispatchOutboxEntry(
        outbox_entry_id="workflow-dispatch-outbox.fixture",
        dispatch_intent_id="workflow-dispatch-intent.fixture",
        dispatch_intent_digest="4" * 64,
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        run_id="workflow-run.fixture",
        run_digest="2" * 64,
        step_run_id="workflow-step-run.fixture",
        step_run_digest="3" * 64,
        step_id="collect-evidence",
        attempt_id="workflow-attempt.fixture",
        attempt_digest="5" * 64,
        attempt_number=1,
        scope=plan.scope,
        target_id=plan.target_id,
        target_type=plan.target_type,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token,
        worker_subject_id=lease.worker_subject_id,
        admitted_at=NOW + timedelta(seconds=2),
        state=WorkflowDispatchOutboxState.PENDING_PUBLICATION,
        authority=WorkflowPlanAuthority(),
        canonical_digest=canonical_digest(payload),
    )


async def fixture(
    *, audit: CollectingAuditSink | None = None
) -> tuple[
    WorkflowOutboxPublicationLeaseService,
    InMemoryPublicationLeaseRepository,
    InMemoryWorkflowPlanRepository,
    CollectingAuditSink,
    WorkflowDispatchOutboxEntry,
    WorkflowOrchestrationLease,
]:
    plan_repository = InMemoryWorkflowPlanRepository()
    sink = audit or CollectingAuditSink()
    plan = await WorkflowPlanningService(
        registry=code_owned_workflow_registry(),
        repository=plan_repository,
        audit_sink=sink,
    ).create_plan(
        definition_id="workflow.evidence-grounded-query",
        definition_version=1,
        target_id=TARGET_ID,
        inputs={"question": "health"},
        idempotency_key="publication-lease-plan-0001",
        context=human_context(),
    )
    lease = await WorkflowOrchestrationLeaseService(
        plan_repository=plan_repository,
        lease_repository=plan_repository,
        audit_sink=sink,
    ).acquire(
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        lease_seconds=300,
        idempotency_key="publication-orchestration-lease-0001",
        context=worker_context(requested_at=NOW + timedelta(seconds=1)),
    )
    outbox = outbox_entry(plan, lease)
    publication_repository = InMemoryPublicationLeaseRepository(outbox)
    service = WorkflowOutboxPublicationLeaseService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        publication_lease_repository=publication_repository,
        audit_sink=sink,
    )
    return service, publication_repository, plan_repository, sink, outbox, lease


async def acquire(
    service: WorkflowOutboxPublicationLeaseService,
    outbox: WorkflowDispatchOutboxEntry,
    *,
    context: WorkflowOutboxPublisherContext | None = None,
    key: str = "publication-lease-acquire-0001",
    seconds: int = 60,
) -> WorkflowOutboxPublicationLease:
    return await service.acquire(
        outbox_entry_id=outbox.outbox_entry_id,
        outbox_entry_digest=outbox.canonical_digest,
        lease_seconds=seconds,
        idempotency_key=key,
        context=context or publisher_context(),
    )


@pytest.mark.asyncio
async def test_acquire_binds_complete_lineage_fence_and_zero_authority() -> None:
    service, _, _, audit, outbox, orchestration_lease = await fixture()

    lease = await acquire(service, outbox)

    assert service.durable is True
    assert lease.outbox_entry_id == outbox.outbox_entry_id
    assert lease.outbox_entry_digest == outbox.canonical_digest
    assert lease.dispatch_intent_id == outbox.dispatch_intent_id
    assert lease.dispatch_intent_digest == outbox.dispatch_intent_digest
    assert lease.plan_id == outbox.plan_id
    assert lease.plan_digest == outbox.plan_digest
    assert lease.run_id == outbox.run_id
    assert lease.run_digest == outbox.run_digest
    assert lease.step_run_id == outbox.step_run_id
    assert lease.step_run_digest == outbox.step_run_digest
    assert lease.step_id == outbox.step_id
    assert lease.attempt_id == outbox.attempt_id
    assert lease.attempt_digest == outbox.attempt_digest
    assert lease.attempt_number == outbox.attempt_number
    assert lease.scope == outbox.scope
    assert lease.target_id == outbox.target_id
    assert lease.target_type == outbox.target_type
    assert lease.orchestration_lease_id == orchestration_lease.lease_id
    assert lease.orchestration_lease_digest == orchestration_lease.canonical_digest
    assert lease.orchestration_fencing_token == orchestration_lease.fencing_token
    assert lease.publisher_subject_id == PUBLISHER_ID
    assert lease.publication_fencing_token == 1
    assert lease.state is WorkflowOutboxPublicationLeaseState.ACTIVE
    assert lease.canonical_digest == canonical_digest(lease.digest_payload())
    assert not any(lease.authority.canonical_value().values())
    assert lease.grants_publication_authority is False
    assert lease.grants_delivery_authority is False
    assert lease.grants_dispatch_authority is False
    assert lease.grants_execution_authority is False
    assert audit.records[-1].result_code == "workflow_outbox_publication_lease_acquired"
    metadata = dict(audit.records[-1].target_metadata)
    assert metadata["publication_authority"] == "false"
    assert metadata["delivery_authority"] == "false"
    assert metadata["dispatch_authority"] == "false"
    assert metadata["execution_authority"] == "false"


@pytest.mark.asyncio
async def test_exact_acquisition_replays_and_changed_request_conflicts() -> None:
    service, _, _, audit, outbox, _ = await fixture()
    first = await acquire(service, outbox)
    replay = await acquire(
        service,
        outbox,
        context=publisher_context(requested_at=NOW + timedelta(seconds=10)),
    )
    assert replay == first
    assert audit.records[-1].result_code.endswith("acquisition_replayed")

    with pytest.raises(WorkflowOutboxPublicationLeaseError) as conflict:
        await acquire(
            service,
            outbox,
            context=publisher_context(requested_at=NOW + timedelta(seconds=11)),
            seconds=90,
        )
    assert conflict.value.code == "workflow_outbox_publication_lease_idempotency_conflict"
    assert audit.records[-1].outcome == "denied"


@pytest.mark.asyncio
async def test_active_contention_and_expired_or_released_takeover_increment_fencing() -> None:
    service, repository, _, _, outbox, _ = await fixture()
    first = await acquire(service, outbox, seconds=30)
    with pytest.raises(WorkflowOutboxPublicationLeaseError) as contended:
        await acquire(
            service,
            outbox,
            context=publisher_context(
                subject_id="service.workflow-outbox-publisher-02",
                requested_at=NOW + timedelta(seconds=4),
            ),
            key="publication-lease-acquire-0002",
        )
    assert contended.value.code == "workflow_outbox_publication_lease_contended"

    expired_takeover = await acquire(
        service,
        outbox,
        context=publisher_context(
            subject_id="service.workflow-outbox-publisher-02",
            requested_at=first.expires_at,
        ),
        key="publication-lease-acquire-0003",
    )
    assert expired_takeover.publication_fencing_token == 2

    released = await service.release(
        outbox_entry_id=outbox.outbox_entry_id,
        outbox_entry_digest=outbox.canonical_digest,
        publication_lease_id=expired_takeover.publication_lease_id,
        publication_lease_digest=expired_takeover.canonical_digest,
        publication_fencing_token=expired_takeover.publication_fencing_token,
        context=publisher_context(
            subject_id=expired_takeover.publisher_subject_id,
            requested_at=first.expires_at + timedelta(seconds=1),
        ),
    )
    assert released.state is WorkflowOutboxPublicationLeaseState.RELEASED
    assert repository.current == released
    released_takeover = await acquire(
        service,
        outbox,
        context=publisher_context(
            subject_id="service.workflow-outbox-publisher-03",
            requested_at=first.expires_at + timedelta(seconds=2),
        ),
        key="publication-lease-acquire-0004",
    )
    assert released_takeover.publication_fencing_token == 3


@pytest.mark.asyncio
async def test_heartbeat_and_release_require_exact_current_digest_fence_and_subject() -> None:
    service, _, _, audit, outbox, _ = await fixture()
    lease = await acquire(service, outbox)
    heartbeat_context = publisher_context(requested_at=NOW + timedelta(seconds=20))
    heartbeated = await service.heartbeat(
        outbox_entry_id=outbox.outbox_entry_id,
        outbox_entry_digest=outbox.canonical_digest,
        publication_lease_id=lease.publication_lease_id,
        publication_lease_digest=lease.canonical_digest,
        publication_fencing_token=lease.publication_fencing_token,
        lease_seconds=90,
        context=heartbeat_context,
    )
    assert heartbeated.last_heartbeat_at == heartbeat_context.requested_at
    assert heartbeated.expires_at == heartbeat_context.requested_at + timedelta(seconds=90)
    assert heartbeated.publication_fencing_token == lease.publication_fencing_token

    for subject_id, digest, fence in (
        ("service.workflow-outbox-publisher-02", heartbeated.canonical_digest, 1),
        (PUBLISHER_ID, "0" * 64, 1),
        (PUBLISHER_ID, heartbeated.canonical_digest, 2),
    ):
        with pytest.raises(WorkflowOutboxPublicationLeaseError) as stale:
            await service.release(
                outbox_entry_id=outbox.outbox_entry_id,
                outbox_entry_digest=outbox.canonical_digest,
                publication_lease_id=heartbeated.publication_lease_id,
                publication_lease_digest=digest,
                publication_fencing_token=fence,
                context=publisher_context(
                    subject_id=subject_id,
                    requested_at=NOW + timedelta(seconds=21),
                ),
            )
        assert stale.value.code == "workflow_outbox_publication_lease_conflict"
        assert audit.records[-1].outcome == "denied"


@pytest.mark.asyncio
async def test_changed_or_expired_orchestration_lease_and_cancelled_plan_fail_closed() -> None:
    service, _, plan_repository, audit, outbox, orchestration_lease = await fixture()
    publication_lease = await acquire(service, outbox)
    await WorkflowOrchestrationLeaseService(
        plan_repository=plan_repository,
        lease_repository=plan_repository,
        audit_sink=audit,
    ).heartbeat(
        plan_id=outbox.plan_id,
        plan_digest=outbox.plan_digest,
        lease_id=orchestration_lease.lease_id,
        lease_digest=orchestration_lease.canonical_digest,
        fencing_token=orchestration_lease.fencing_token,
        lease_seconds=300,
        context=worker_context(requested_at=NOW + timedelta(seconds=4)),
    )
    with pytest.raises(WorkflowOutboxPublicationLeaseError) as stale:
        await service.heartbeat(
            outbox_entry_id=outbox.outbox_entry_id,
            outbox_entry_digest=outbox.canonical_digest,
            publication_lease_id=publication_lease.publication_lease_id,
            publication_lease_digest=publication_lease.canonical_digest,
            publication_fencing_token=publication_lease.publication_fencing_token,
            lease_seconds=60,
            context=publisher_context(requested_at=NOW + timedelta(seconds=5)),
        )
    assert stale.value.code == "workflow_outbox_publication_orchestration_lease_conflict"

    service, _, plan_repository, audit, outbox, _ = await fixture()
    await WorkflowPlanningService(
        registry=code_owned_workflow_registry(),
        repository=plan_repository,
        audit_sink=audit,
    ).cancel_plan(
        plan_id=outbox.plan_id,
        reason="The maintenance window was withdrawn.",
        acknowledge_no_external_undo=True,
        idempotency_key="publication-plan-cancel-0001",
        context=human_context(requested_at=NOW + timedelta(seconds=4)),
    )
    with pytest.raises(WorkflowOutboxPublicationLeaseError) as cancelled:
        await acquire(
            service,
            outbox,
            context=publisher_context(requested_at=NOW + timedelta(seconds=5)),
        )
    assert cancelled.value.code == "workflow_outbox_publication_plan_conflict"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actor_type", "method", "audience"),
    (
        ("human", "browser_session", WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
        ("service", "api_token", WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
        ("service", "workload_token", "audience.workflow-worker"),
    ),
)
async def test_only_dedicated_publisher_workload_identity_is_accepted(
    actor_type: str, method: str, audience: str
) -> None:
    service, _, _, audit, outbox, _ = await fixture()
    with pytest.raises(WorkflowOutboxPublicationLeaseError) as rejected:
        await acquire(
            service,
            outbox,
            context=publisher_context(
                actor_type=actor_type,
                authentication_method=method,
                audience=audience,
            ),
        )
    assert rejected.value.code == "workflow_outbox_publisher_identity_required"
    assert audit.records[-1].outcome == "denied"


@pytest.mark.asyncio
async def test_duration_scope_and_outbox_digest_fail_closed_and_are_audited() -> None:
    service, _, _, audit, outbox, _ = await fixture()
    for seconds in (29, 301):
        with pytest.raises(WorkflowOutboxPublicationLeaseError) as invalid:
            await acquire(service, outbox, seconds=seconds)
        assert invalid.value.code == "workflow_outbox_publication_lease_duration_invalid"
        assert audit.records[-1].outcome == "denied"

    with pytest.raises(WorkflowOutboxPublicationLeaseError) as hidden:
        await acquire(service, outbox, context=publisher_context(targets=frozenset()))
    assert hidden.value.code == "workflow_outbox_publication_entry_not_found"

    with pytest.raises(WorkflowOutboxPublicationLeaseError) as changed:
        await service.acquire(
            outbox_entry_id=outbox.outbox_entry_id,
            outbox_entry_digest="0" * 64,
            lease_seconds=60,
            idempotency_key="publication-lease-wrong-digest",
            context=publisher_context(),
        )
    assert changed.value.code == "workflow_outbox_publication_evidence_conflict"


@pytest.mark.asyncio
async def test_audit_failure_never_returns_success() -> None:
    _, repository, plan_repository, _, outbox, _ = await fixture()
    failing_service = WorkflowOutboxPublicationLeaseService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        publication_lease_repository=repository,
        audit_sink=CollectingAuditSink(fail=True),
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await acquire(failing_service, outbox)
    assert repository.current is not None


def test_domain_rejects_wrong_digest_and_forbidden_data_surface() -> None:
    assert {
        "broker",
        "address",
        "topic",
        "routing_key",
        "payload",
        "serialization",
        "published_at",
        "delivered_at",
    }.isdisjoint(WorkflowOutboxPublicationLease.__dataclass_fields__)
