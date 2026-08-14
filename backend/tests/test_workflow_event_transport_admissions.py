from __future__ import annotations

from dataclasses import fields, replace
from datetime import timedelta
from typing import Any, cast

import pytest
from test_workflow_dispatch_event_envelopes import (
    InMemoryEventEnvelopeRepository,
    envelope_fixture,
    prepare,
)
from test_workflow_outbox_publication_leases import (
    NOW,
    CollectingAuditSink,
    InMemoryPublicationLeaseRepository,
    publisher_context,
    worker_context,
)

from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowEventTransportAdmissionError,
    WorkflowEventTransportAdmissionIdempotencyRecord,
    WorkflowEventTransportAdmissionRequest,
    WorkflowEventTransportAdmissionResult,
    WorkflowEventTransportAdmissionService,
    WorkflowEventTransportAdmissionStatus,
    WorkflowOrchestrationLeaseService,
    WorkflowOutboxPublicationLeaseService,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchOutboxEntry,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionPolicy,
    WorkflowEventTransportAdmissionState,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowScope,
    canonical_digest,
    canonical_json_byte_count,
    code_owned_workflow_event_transport_admission_policy,
)


class InMemoryTransportAdmissionRepository:
    def __init__(
        self,
        publication_repository: InMemoryPublicationLeaseRepository,
        envelope_repository: InMemoryEventEnvelopeRepository,
    ) -> None:
        self.publication_repository = publication_repository
        self.envelope_repository = envelope_repository
        self.current: WorkflowEventTransportAdmission | None = None
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventTransportAdmissionIdempotencyRecord,
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
        return await self.envelope_repository.get_dispatch_event_envelope_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None:
        if self.current is None or self.current.event_id != event_id:
            return None
        return self.current

    async def get_event_transport_admission_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportAdmissionIdempotencyRecord | None:
        return self.requests.get((scope, publisher_subject_id, idempotency_key))

    async def admit_event_transport(
        self, request: WorkflowEventTransportAdmissionRequest
    ) -> WorkflowEventTransportAdmissionResult:
        key = (
            request.candidate.scope,
            request.publisher_subject_id,
            request.idempotency_key,
        )
        prior = self.requests.get(key)
        if prior is not None:
            status = (
                WorkflowEventTransportAdmissionStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowEventTransportAdmissionStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowEventTransportAdmissionResult(status, prior.admission)
        if self.current is not None:
            return WorkflowEventTransportAdmissionResult(
                WorkflowEventTransportAdmissionStatus.ALREADY_ADMITTED,
                self.current,
            )
        self.current = request.candidate
        self.requests[key] = WorkflowEventTransportAdmissionIdempotencyRecord(
            request.request_fingerprint,
            request.candidate,
        )
        return WorkflowEventTransportAdmissionResult(
            WorkflowEventTransportAdmissionStatus.ADMITTED,
            request.candidate,
        )


async def admission_fixture(
    *,
    audit: CollectingAuditSink | None = None,
    policy: WorkflowEventTransportAdmissionPolicy | None = None,
) -> tuple[
    WorkflowEventTransportAdmissionService,
    InMemoryTransportAdmissionRepository,
    WorkflowOutboxPublicationLeaseService,
    InMemoryPublicationLeaseRepository,
    InMemoryWorkflowPlanRepository,
    WorkflowDispatchOutboxEntry,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowDispatchEventEnvelope,
    CollectingAuditSink,
]:
    (
        envelope_service,
        envelope_repository,
        publication_service,
        publication_repository,
        plan_repository,
        outbox,
        lease,
        sink,
    ) = await envelope_fixture(audit=audit)
    publication_lease = publication_repository.current
    assert publication_lease is not None
    envelope = await prepare(envelope_service, outbox, publication_lease)
    repository = InMemoryTransportAdmissionRepository(
        publication_repository,
        envelope_repository,
    )
    service = WorkflowEventTransportAdmissionService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        transport_admission_repository=repository,
        audit_sink=sink,
        policy=policy,
    )
    return (
        service,
        repository,
        publication_service,
        publication_repository,
        plan_repository,
        outbox,
        lease,
        publication_lease,
        envelope,
        sink,
    )


async def admit(
    service: WorkflowEventTransportAdmissionService,
    outbox: WorkflowDispatchOutboxEntry,
    publication_lease: WorkflowOutboxPublicationLease,
    envelope: WorkflowDispatchEventEnvelope,
    **changes: object,
) -> WorkflowEventTransportAdmission:
    policy = service.policy
    values: dict[str, object] = {
        "outbox_entry_id": outbox.outbox_entry_id,
        "outbox_entry_digest": outbox.canonical_digest,
        "event_id": envelope.event_id,
        "event_digest": envelope.canonical_digest,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "publication_lease_id": publication_lease.publication_lease_id,
        "publication_lease_digest": publication_lease.canonical_digest,
        "publication_fencing_token": publication_lease.publication_fencing_token,
        "idempotency_key": "workflow-transport-admission-0001",
        "context": publisher_context(requested_at=NOW + timedelta(seconds=5)),
    }
    values.update(changes)
    return await service.admit(**cast(Any, values))


def policy_with(
    *,
    allowed_event_types: tuple[str, ...] = ("WorkflowStepDispatchRequested",),
    maximum_canonical_byte_count: int = 65_536,
) -> WorkflowEventTransportAdmissionPolicy:
    values = {
        "policy_id": "policy.workflow-event-transport-admission",
        "policy_version": "1.0",
        "allowed_event_types": allowed_event_types,
        "allowed_event_versions": ("1.0",),
        "allowed_schema_uris": ("urn:project-atlas:event:workflow-step-dispatch-requested:1.0",),
        "allowed_data_classifications": ("internal",),
        "representation_name": "canonical-json",
        "encoding": "utf-8",
        "maximum_canonical_byte_count": maximum_canonical_byte_count,
    }
    digest_payload = {
        key: list(value) if isinstance(value, tuple) else value for key, value in values.items()
    }
    return WorkflowEventTransportAdmissionPolicy(
        **cast(Any, values),
        canonical_digest=canonical_digest(digest_payload),
    )


@pytest.mark.asyncio
async def test_admits_exact_envelope_under_code_owned_policy_with_zero_authority() -> None:
    (
        service,
        repository,
        _,
        _,
        _,
        outbox,
        _,
        publication_lease,
        envelope,
        audit,
    ) = await admission_fixture()

    admission = await admit(service, outbox, publication_lease, envelope)

    assert service.durable is True
    assert repository.current == admission
    assert admission.policy_id == "policy.workflow-event-transport-admission"
    assert admission.policy_digest == service.policy.canonical_digest
    assert admission.event_id == envelope.event_id
    assert admission.event_digest == envelope.canonical_digest
    assert admission.canonical_byte_count == canonical_json_byte_count(envelope.canonical_value())
    assert admission.canonical_byte_count <= admission.maximum_canonical_byte_count
    assert admission.representation_name == "canonical-json"
    assert admission.encoding == "utf-8"
    assert admission.state is WorkflowEventTransportAdmissionState.ADMITTED
    assert admission.canonical_digest == canonical_digest(admission.digest_payload())
    assert not any(admission.authority.canonical_value().values())
    assert admission.grants_publication_authority is False
    assert admission.grants_delivery_authority is False
    assert admission.grants_dispatch_authority is False
    assert admission.grants_execution_authority is False
    assert audit.records[-1].result_code == "workflow_event_transport_admitted"


@pytest.mark.asyncio
async def test_exact_replay_is_stable_and_changed_claim_fails_closed() -> None:
    (
        service,
        repository,
        _,
        _,
        _,
        outbox,
        _,
        publication_lease,
        envelope,
        audit,
    ) = await admission_fixture()
    first = await admit(service, outbox, publication_lease, envelope)
    replay = await admit(
        service,
        outbox,
        publication_lease,
        envelope,
        context=publisher_context(requested_at=NOW + timedelta(seconds=6)),
    )
    assert replay == first
    assert audit.records[-1].result_code == "workflow_event_transport_admission_replayed"

    key = (
        outbox.scope,
        publication_lease.publisher_subject_id,
        "workflow-transport-admission-0001",
    )
    prior = repository.requests[key]
    repository.requests[key] = WorkflowEventTransportAdmissionIdempotencyRecord(
        "f" * 64,
        prior.admission,
    )
    with pytest.raises(WorkflowEventTransportAdmissionError) as conflict:
        await admit(service, outbox, publication_lease, envelope)
    assert conflict.value.code == "workflow_event_transport_admission_idempotency_conflict"


@pytest.mark.asyncio
async def test_tampered_replay_is_rejected_and_audited() -> None:
    (
        service,
        repository,
        _,
        _,
        _,
        outbox,
        _,
        publication_lease,
        envelope,
        audit,
    ) = await admission_fixture()
    first = await admit(service, outbox, publication_lease, envelope)
    key = (
        outbox.scope,
        publication_lease.publisher_subject_id,
        "workflow-transport-admission-0001",
    )
    prior = repository.requests[key]
    tampered_payload = first.digest_payload() | {
        "publisher_subject_id": "service.workflow-outbox-publisher-tampered"
    }
    tampered = replace(
        first,
        publisher_subject_id="service.workflow-outbox-publisher-tampered",
        canonical_digest=canonical_digest(tampered_payload),
    )
    repository.requests[key] = WorkflowEventTransportAdmissionIdempotencyRecord(
        prior.request_fingerprint,
        tampered,
    )

    with pytest.raises(WorkflowEventTransportAdmissionError) as invalid:
        await admit(service, outbox, publication_lease, envelope)

    assert invalid.value.code == "workflow_event_transport_admission_repository_scope_violation"
    assert audit.records[-1].result_code == invalid.value.code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy", "expected_code"),
    (
        (
            policy_with(allowed_event_types=("OtherWorkflowEvent",)),
            "workflow_event_transport_admission_policy_rejected",
        ),
        (
            policy_with(maximum_canonical_byte_count=1),
            "workflow_event_transport_admission_canonical_size_exceeded",
        ),
    ),
)
async def test_unsupported_and_oversized_envelopes_fail_closed_with_audit(
    policy: WorkflowEventTransportAdmissionPolicy,
    expected_code: str,
) -> None:
    (
        service,
        repository,
        _,
        _,
        _,
        outbox,
        _,
        publication_lease,
        envelope,
        audit,
    ) = await admission_fixture(policy=policy)

    with pytest.raises(WorkflowEventTransportAdmissionError) as denied:
        await admit(service, outbox, publication_lease, envelope)

    assert denied.value.code == expected_code
    assert repository.current is None
    assert audit.records[-1].result_code == expected_code


@pytest.mark.asyncio
async def test_expired_released_competing_and_stale_leases_fail_closed() -> None:
    (
        service,
        _,
        publication_service,
        _,
        _,
        outbox,
        _,
        publication_lease,
        envelope,
        _,
    ) = await admission_fixture()
    with pytest.raises(WorkflowEventTransportAdmissionError) as expired:
        await admit(
            service,
            outbox,
            publication_lease,
            envelope,
            context=publisher_context(requested_at=publication_lease.expires_at),
        )
    assert expired.value.code == "workflow_event_transport_admission_publication_lease_conflict"

    released = await publication_service.release(
        outbox_entry_id=outbox.outbox_entry_id,
        outbox_entry_digest=outbox.canonical_digest,
        publication_lease_id=publication_lease.publication_lease_id,
        publication_lease_digest=publication_lease.canonical_digest,
        publication_fencing_token=publication_lease.publication_fencing_token,
        context=publisher_context(requested_at=NOW + timedelta(seconds=5)),
    )
    with pytest.raises(WorkflowEventTransportAdmissionError) as released_error:
        await admit(
            service,
            outbox,
            released,
            envelope,
            context=publisher_context(requested_at=NOW + timedelta(seconds=6)),
        )
    assert released_error.value.code == (
        "workflow_event_transport_admission_publication_lease_conflict"
    )

    service, _, _, _, _, outbox, _, publication_lease, envelope, _ = await admission_fixture()
    with pytest.raises(WorkflowEventTransportAdmissionError) as competing:
        await admit(
            service,
            outbox,
            publication_lease,
            envelope,
            context=publisher_context(
                subject_id="service.workflow-outbox-publisher-02",
                requested_at=NOW + timedelta(seconds=5),
            ),
        )
    assert competing.value.code == ("workflow_event_transport_admission_publication_lease_conflict")

    (
        service,
        _,
        _,
        _,
        plan_repository,
        outbox,
        lease,
        publication_lease,
        envelope,
        audit,
    ) = await admission_fixture()
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
        context=worker_context(requested_at=NOW + timedelta(seconds=5)),
    )
    with pytest.raises(WorkflowEventTransportAdmissionError) as stale:
        await admit(
            service,
            outbox,
            publication_lease,
            envelope,
            context=publisher_context(requested_at=NOW + timedelta(seconds=6)),
        )
    assert stale.value.code == ("workflow_event_transport_admission_orchestration_lease_conflict")


@pytest.mark.asyncio
async def test_audit_failure_never_returns_success() -> None:
    (
        _,
        repository,
        _,
        _,
        plan_repository,
        outbox,
        _,
        publication_lease,
        envelope,
        _,
    ) = await admission_fixture()
    service = WorkflowEventTransportAdmissionService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        transport_admission_repository=repository,
        audit_sink=CollectingAuditSink(fail=True),
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await admit(service, outbox, publication_lease, envelope)

    assert repository.current is not None


def test_domain_has_no_provider_publication_or_execution_surface() -> None:
    forbidden = {
        "broker",
        "provider",
        "endpoint",
        "queue",
        "topic",
        "partition",
        "routing_key",
        "credential",
        "wire_payload",
        "serialized_artifact",
        "publication_attempt",
        "receipt",
    }
    assert forbidden.isdisjoint(field.name for field in fields(WorkflowEventTransportAdmission))
    assert code_owned_workflow_event_transport_admission_policy().representation_name == (
        "canonical-json"
    )
