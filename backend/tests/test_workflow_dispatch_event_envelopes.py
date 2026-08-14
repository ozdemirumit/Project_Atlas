from __future__ import annotations

from dataclasses import fields, replace
from datetime import timedelta
from typing import Any, cast

import pytest
from test_workflow_outbox_publication_leases import (
    NOW,
    CollectingAuditSink,
    InMemoryPublicationLeaseRepository,
    acquire,
    human_context,
    publisher_context,
    worker_context,
)
from test_workflow_outbox_publication_leases import (
    fixture as publication_fixture,
)

from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowDispatchEventEnvelopeError,
    WorkflowDispatchEventEnvelopePrepareIdempotencyRecord,
    WorkflowDispatchEventEnvelopePrepareRequest,
    WorkflowDispatchEventEnvelopePrepareResult,
    WorkflowDispatchEventEnvelopePrepareStatus,
    WorkflowDispatchEventEnvelopeService,
    WorkflowOrchestrationLeaseService,
    WorkflowOutboxPublicationLeaseService,
    WorkflowPlanningService,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchEventEnvelopeState,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_registry,
)


class InMemoryEventEnvelopeRepository:
    def __init__(self, publication_repository: InMemoryPublicationLeaseRepository) -> None:
        self.publication_repository = publication_repository
        self.current: WorkflowDispatchEventEnvelope | None = None
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowDispatchEventEnvelopePrepareIdempotencyRecord,
        ] = {}

    @property
    def durable(self) -> bool:
        return True

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        return await self.publication_repository.get_outbox_entry_by_id(
            outbox_entry_id=outbox_entry_id
        )

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        return await self.publication_repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )

    async def get_dispatch_event_envelope_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchEventEnvelope | None:
        if self.current is None or self.current.payload.outbox_entry_id != outbox_entry_id:
            return None
        return self.current

    async def get_dispatch_event_envelope_prepare_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchEventEnvelopePrepareIdempotencyRecord | None:
        return self.requests.get((scope, publisher_subject_id, idempotency_key))

    async def prepare_dispatch_event_envelope(
        self, request: WorkflowDispatchEventEnvelopePrepareRequest
    ) -> WorkflowDispatchEventEnvelopePrepareResult:
        key = (
            request.candidate.payload.scope,
            request.publisher_subject_id,
            request.idempotency_key,
        )
        prior = self.requests.get(key)
        if prior is not None:
            status = (
                WorkflowDispatchEventEnvelopePrepareStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowDispatchEventEnvelopePrepareStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowDispatchEventEnvelopePrepareResult(status, prior.envelope)
        if self.current is not None:
            return WorkflowDispatchEventEnvelopePrepareResult(
                WorkflowDispatchEventEnvelopePrepareStatus.ALREADY_PREPARED, self.current
            )
        self.current = request.candidate
        self.requests[key] = WorkflowDispatchEventEnvelopePrepareIdempotencyRecord(
            request.request_fingerprint, request.candidate
        )
        return WorkflowDispatchEventEnvelopePrepareResult(
            WorkflowDispatchEventEnvelopePrepareStatus.PREPARED, request.candidate
        )


async def envelope_fixture(
    *, audit: CollectingAuditSink | None = None
) -> tuple[
    WorkflowDispatchEventEnvelopeService,
    InMemoryEventEnvelopeRepository,
    WorkflowOutboxPublicationLeaseService,
    InMemoryPublicationLeaseRepository,
    InMemoryWorkflowPlanRepository,
    WorkflowDispatchOutboxEntry,
    WorkflowOrchestrationLease,
    CollectingAuditSink,
]:
    (
        publication_service,
        publication_repository,
        plan_repository,
        sink,
        outbox,
        lease,
    ) = await publication_fixture(audit=audit)
    await acquire(publication_service, outbox)
    repository = InMemoryEventEnvelopeRepository(publication_repository)
    service = WorkflowDispatchEventEnvelopeService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        event_envelope_repository=repository,
        audit_sink=sink,
    )
    return (
        service,
        repository,
        publication_service,
        publication_repository,
        plan_repository,
        outbox,
        lease,
        sink,
    )


async def prepare(
    service: WorkflowDispatchEventEnvelopeService,
    outbox: WorkflowDispatchOutboxEntry,
    publication_lease: WorkflowOutboxPublicationLease,
    **changes: object,
) -> WorkflowDispatchEventEnvelope:
    values: dict[str, object] = {
        "outbox_entry_id": outbox.outbox_entry_id,
        "outbox_entry_digest": outbox.canonical_digest,
        "publication_lease_id": publication_lease.publication_lease_id,
        "publication_lease_digest": publication_lease.canonical_digest,
        "publication_fencing_token": publication_lease.publication_fencing_token,
        "idempotency_key": "dispatch-event-envelope-prepare-0001",
        "context": publisher_context(requested_at=NOW + timedelta(seconds=4)),
    }
    values.update(changes)
    return await service.prepare(**cast(Any, values))


@pytest.mark.asyncio
async def test_prepares_canonical_minimized_envelope_with_zero_authority() -> None:
    (
        service,
        repository,
        _,
        publication_repository,
        _,
        outbox,
        lease,
        audit,
    ) = await envelope_fixture()
    publication_lease = publication_repository.current
    assert publication_lease is not None

    envelope = await prepare(service, outbox, publication_lease)

    assert service.durable is True
    assert repository.current == envelope
    assert envelope.event_id.startswith("workflow-dispatch-event.")
    assert envelope.event_type == "WorkflowStepDispatchRequested"
    assert envelope.event_version == "1.0"
    assert envelope.occurred_at == outbox.admitted_at
    assert envelope.recorded_at == envelope.prepared_at == NOW + timedelta(seconds=4)
    assert envelope.subject_id == outbox.attempt_id
    assert envelope.organization_id == outbox.scope.organization_id
    assert envelope.environment_id == outbox.scope.environment_id
    assert envelope.correlation_id == envelope.workflow_id == outbox.run_id
    assert envelope.causation_id == outbox.dispatch_intent_id
    assert envelope.data_classification == "internal"
    assert envelope.schema_uri == "urn:project-atlas:event:workflow-step-dispatch-requested:1.0"
    assert envelope.payload.outbox_entry_id == outbox.outbox_entry_id
    assert envelope.payload.outbox_entry_digest == outbox.canonical_digest
    assert envelope.payload.scope == outbox.scope
    assert envelope.orchestration_lease_id == lease.lease_id
    assert envelope.orchestration_lease_digest == lease.canonical_digest
    assert envelope.orchestration_fencing_token == lease.fencing_token
    assert envelope.publication_lease_id == publication_lease.publication_lease_id
    assert envelope.publication_lease_digest == publication_lease.canonical_digest
    assert envelope.publication_fencing_token == publication_lease.publication_fencing_token
    assert envelope.state is WorkflowDispatchEventEnvelopeState.PREPARED
    assert envelope.extensions == ()
    assert envelope.canonical_digest == canonical_digest(envelope.digest_payload())
    assert not any(envelope.authority.canonical_value().values())
    assert envelope.grants_publication_authority is False
    assert envelope.grants_delivery_authority is False
    assert envelope.grants_dispatch_authority is False
    assert envelope.grants_execution_authority is False
    assert audit.records[-1].result_code == "workflow_dispatch_event_envelope_prepared"


@pytest.mark.asyncio
async def test_exact_replay_is_stable_and_changed_request_fails_closed() -> None:
    (
        service,
        _,
        publication_service,
        publication_repository,
        _,
        outbox,
        _,
        audit,
    ) = await envelope_fixture()
    publication_lease = publication_repository.current
    assert publication_lease is not None
    first = await prepare(service, outbox, publication_lease)
    replay = await prepare(
        service,
        outbox,
        publication_lease,
        context=publisher_context(requested_at=NOW + timedelta(seconds=5)),
    )
    assert replay == first
    assert audit.records[-1].result_code.endswith("preparation_replayed")

    renewed = await publication_service.heartbeat(
        outbox_entry_id=outbox.outbox_entry_id,
        outbox_entry_digest=outbox.canonical_digest,
        publication_lease_id=publication_lease.publication_lease_id,
        publication_lease_digest=publication_lease.canonical_digest,
        publication_fencing_token=publication_lease.publication_fencing_token,
        lease_seconds=60,
        context=publisher_context(requested_at=NOW + timedelta(seconds=6)),
    )
    with pytest.raises(WorkflowDispatchEventEnvelopeError) as changed:
        await prepare(
            service,
            outbox,
            renewed,
            context=publisher_context(requested_at=NOW + timedelta(seconds=7)),
        )
    assert changed.value.code == "workflow_dispatch_event_envelope_idempotency_conflict"


@pytest.mark.asyncio
async def test_replayed_repository_envelope_revalidates_canonical_context() -> None:
    (
        service,
        repository,
        _,
        publication_repository,
        _,
        outbox,
        _,
        _,
    ) = await envelope_fixture()
    publication_lease = publication_repository.current
    assert publication_lease is not None
    first = await prepare(service, outbox, publication_lease)
    key = (
        outbox.scope,
        publication_lease.publisher_subject_id,
        "dispatch-event-envelope-prepare-0001",
    )
    prior = repository.requests[key]
    tampered_payload = first.digest_payload() | {"producer": "tampered-workflow-producer"}
    tampered = replace(
        first,
        producer="tampered-workflow-producer",
        canonical_digest=canonical_digest(tampered_payload),
    )
    repository.requests[key] = WorkflowDispatchEventEnvelopePrepareIdempotencyRecord(
        prior.request_fingerprint,
        tampered,
    )

    with pytest.raises(WorkflowDispatchEventEnvelopeError) as invalid:
        await prepare(service, outbox, publication_lease)

    assert invalid.value.code == "workflow_dispatch_event_envelope_repository_scope_violation"


@pytest.mark.asyncio
async def test_expired_released_and_competing_publication_identity_fail_closed() -> None:
    (
        service,
        _,
        publication_service,
        publication_repository,
        _,
        outbox,
        _,
        _,
    ) = await envelope_fixture()
    publication_lease = publication_repository.current
    assert publication_lease is not None
    with pytest.raises(WorkflowDispatchEventEnvelopeError) as expired:
        await prepare(
            service,
            outbox,
            publication_lease,
            context=publisher_context(requested_at=publication_lease.expires_at),
        )
    assert expired.value.code == "workflow_dispatch_event_publication_lease_conflict"

    released = await publication_service.release(
        outbox_entry_id=outbox.outbox_entry_id,
        outbox_entry_digest=outbox.canonical_digest,
        publication_lease_id=publication_lease.publication_lease_id,
        publication_lease_digest=publication_lease.canonical_digest,
        publication_fencing_token=publication_lease.publication_fencing_token,
        context=publisher_context(requested_at=NOW + timedelta(seconds=5)),
    )
    with pytest.raises(WorkflowDispatchEventEnvelopeError) as released_error:
        await prepare(
            service,
            outbox,
            released,
            context=publisher_context(requested_at=NOW + timedelta(seconds=6)),
        )
    assert released_error.value.code == "workflow_dispatch_event_publication_lease_conflict"

    service, _, _, publication_repository, _, outbox, _, _ = await envelope_fixture()
    publication_lease = publication_repository.current
    assert publication_lease is not None
    with pytest.raises(WorkflowDispatchEventEnvelopeError) as competing:
        await prepare(
            service,
            outbox,
            publication_lease,
            context=publisher_context(
                subject_id="service.workflow-outbox-publisher-02",
                requested_at=NOW + timedelta(seconds=4),
            ),
        )
    assert competing.value.code == "workflow_dispatch_event_publication_lease_conflict"


@pytest.mark.asyncio
async def test_stale_source_lease_cancelled_plan_and_nonpending_outbox_fail_closed() -> None:
    (
        service,
        _,
        _,
        publication_repository,
        plan_repository,
        outbox,
        lease,
        audit,
    ) = await envelope_fixture()
    publication_lease = publication_repository.current
    assert publication_lease is not None
    await WorkflowOrchestrationLeaseService(
        plan_repository=plan_repository,
        lease_repository=plan_repository,
        audit_sink=audit,
    ).heartbeat(
        plan_id=outbox.plan_id,
        plan_digest=outbox.plan_digest,
        lease_id=lease.lease_id,
        lease_digest=lease.canonical_digest,
        fencing_token=lease.fencing_token,
        lease_seconds=300,
        context=worker_context(requested_at=NOW + timedelta(seconds=4)),
    )
    with pytest.raises(WorkflowDispatchEventEnvelopeError) as stale:
        await prepare(
            service,
            outbox,
            publication_lease,
            context=publisher_context(requested_at=NOW + timedelta(seconds=5)),
        )
    assert stale.value.code == "workflow_dispatch_event_orchestration_lease_conflict"

    (
        service,
        _,
        _,
        publication_repository,
        plan_repository,
        outbox,
        _,
        audit,
    ) = await envelope_fixture()
    publication_lease = publication_repository.current
    assert publication_lease is not None
    await WorkflowPlanningService(
        registry=code_owned_workflow_registry(), repository=plan_repository, audit_sink=audit
    ).cancel_plan(
        plan_id=outbox.plan_id,
        reason="The maintenance window was withdrawn.",
        acknowledge_no_external_undo=True,
        idempotency_key="event-envelope-plan-cancel-0001",
        context=human_context(requested_at=NOW + timedelta(seconds=4)),
    )
    with pytest.raises(WorkflowDispatchEventEnvelopeError) as cancelled:
        await prepare(
            service,
            outbox,
            publication_lease,
            context=publisher_context(requested_at=NOW + timedelta(seconds=5)),
        )
    assert cancelled.value.code == "workflow_dispatch_event_plan_conflict"

    service, _, _, publication_repository, _, outbox, _, _ = await envelope_fixture()
    publication_lease = publication_repository.current
    assert publication_lease is not None
    object.__setattr__(outbox, "state", "published")
    with pytest.raises(WorkflowDispatchEventEnvelopeError) as nonpending:
        await prepare(service, outbox, publication_lease)
    assert nonpending.value.code == "workflow_dispatch_event_outbox_conflict"
    object.__setattr__(outbox, "state", WorkflowDispatchOutboxState.PENDING_PUBLICATION)


@pytest.mark.asyncio
async def test_audit_failure_never_returns_success() -> None:
    (
        _,
        repository,
        _,
        publication_repository,
        plan_repository,
        outbox,
        _,
        _,
    ) = await envelope_fixture()
    publication_lease = publication_repository.current
    assert publication_lease is not None
    failing_audit = CollectingAuditSink(fail=True)
    service = WorkflowDispatchEventEnvelopeService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        event_envelope_repository=repository,
        audit_sink=failing_audit,
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await prepare(service, outbox, publication_lease)
    assert repository.current is not None


def test_domain_has_no_transport_or_execution_surface() -> None:
    forbidden = {
        "broker",
        "endpoint",
        "queue",
        "topic",
        "routing_key",
        "partition",
        "credential",
        "wire_serialization",
        "publication_attempt",
        "receipt",
    }
    assert forbidden.isdisjoint(field.name for field in fields(WorkflowDispatchEventEnvelope))
