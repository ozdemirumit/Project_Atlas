from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timedelta
from hashlib import sha256

import pytest
from test_workflow_event_transport_admissions import (
    InMemoryTransportAdmissionRepository,
    admission_fixture,
    admit,
)
from test_workflow_outbox_publication_leases import (
    NOW,
    CollectingAuditSink,
    publisher_context,
    worker_context,
)

from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowEventByteArtifactError,
    WorkflowEventByteArtifactIdempotencyRecord,
    WorkflowEventByteArtifactRequest,
    WorkflowEventByteArtifactResult,
    WorkflowEventByteArtifactService,
    WorkflowEventByteArtifactStatus,
    WorkflowOrchestrationLeaseService,
    WorkflowOutboxPublicationLeaseService,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchOutboxEntry,
    WorkflowEventByteArtifact,
    WorkflowEventTransportAdmission,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowScope,
    canonical_digest,
    canonical_json_bytes,
)


class InMemoryByteArtifactRepository:
    def __init__(self, admission_repository: InMemoryTransportAdmissionRepository) -> None:
        self.admission_repository = admission_repository
        self.current: WorkflowEventByteArtifact | None = None
        self.requests: dict[
            tuple[WorkflowScope, str, str], WorkflowEventByteArtifactIdempotencyRecord
        ] = {}

    @property
    def durable(self) -> bool:
        return True

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        return await self.admission_repository.get_outbox_entry_by_id(
            outbox_entry_id=outbox_entry_id
        )

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        return await self.admission_repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )

    async def get_dispatch_event_envelope_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchEventEnvelope | None:
        return await self.admission_repository.get_dispatch_event_envelope_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None:
        return await self.admission_repository.get_event_transport_admission_by_event_id(
            event_id=event_id
        )

    async def get_event_byte_artifact_by_admission_id(
        self, *, admission_id: str
    ) -> WorkflowEventByteArtifact | None:
        if self.current is None or self.current.admission_id != admission_id:
            return None
        return self.current

    async def get_event_byte_artifact_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventByteArtifactIdempotencyRecord | None:
        return self.requests.get((scope, publisher_subject_id, idempotency_key))

    async def materialize_event_byte_artifact(
        self, request: WorkflowEventByteArtifactRequest
    ) -> WorkflowEventByteArtifactResult:
        key = (
            request.candidate.scope,
            request.publisher_subject_id,
            request.idempotency_key,
        )
        prior = self.requests.get(key)
        if prior is not None:
            status = (
                WorkflowEventByteArtifactStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowEventByteArtifactStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowEventByteArtifactResult(status, prior.artifact)
        if self.current is not None:
            return WorkflowEventByteArtifactResult(
                WorkflowEventByteArtifactStatus.ALREADY_MATERIALIZED,
                self.current,
            )
        self.current = request.candidate
        self.requests[key] = WorkflowEventByteArtifactIdempotencyRecord(
            request.request_fingerprint,
            request.candidate,
        )
        return WorkflowEventByteArtifactResult(
            WorkflowEventByteArtifactStatus.MATERIALIZED,
            request.candidate,
        )


async def artifact_fixture(
    *, audit: CollectingAuditSink | None = None
) -> tuple[
    WorkflowEventByteArtifactService,
    InMemoryByteArtifactRepository,
    WorkflowOutboxPublicationLeaseService,
    InMemoryWorkflowPlanRepository,
    WorkflowDispatchOutboxEntry,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowDispatchEventEnvelope,
    WorkflowEventTransportAdmission,
    CollectingAuditSink,
]:
    (
        admission_service,
        admission_repository,
        publication_service,
        _,
        plan_repository,
        outbox,
        orchestration_lease,
        publication_lease,
        envelope,
        sink,
    ) = await admission_fixture(audit=audit)
    admission = await admit(
        admission_service,
        outbox,
        publication_lease,
        envelope,
    )
    repository = InMemoryByteArtifactRepository(admission_repository)
    service = WorkflowEventByteArtifactService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        byte_artifact_repository=repository,
        audit_sink=sink,
    )
    return (
        service,
        repository,
        publication_service,
        plan_repository,
        outbox,
        orchestration_lease,
        publication_lease,
        envelope,
        admission,
        sink,
    )


async def materialize(
    service: WorkflowEventByteArtifactService,
    outbox: WorkflowDispatchOutboxEntry,
    publication_lease: WorkflowOutboxPublicationLease,
    envelope: WorkflowDispatchEventEnvelope,
    admission: WorkflowEventTransportAdmission,
    *,
    idempotency_key: str = "workflow-event-byte-artifact-0001",
    context_time: datetime = NOW + timedelta(seconds=8),
) -> WorkflowEventByteArtifact:
    return await service.materialize(
        outbox_entry_id=outbox.outbox_entry_id,
        outbox_entry_digest=outbox.canonical_digest,
        event_id=envelope.event_id,
        event_digest=envelope.canonical_digest,
        admission_id=admission.admission_id,
        admission_digest=admission.canonical_digest,
        policy_id=admission.policy_id,
        policy_version=admission.policy_version,
        policy_digest=admission.policy_digest,
        publication_lease_id=publication_lease.publication_lease_id,
        publication_lease_digest=publication_lease.canonical_digest,
        publication_fencing_token=publication_lease.publication_fencing_token,
        idempotency_key=idempotency_key,
        context=publisher_context(requested_at=context_time),
    )


@pytest.mark.asyncio
async def test_materializes_exact_deterministic_bytes_with_minimized_public_evidence() -> None:
    (
        service,
        repository,
        _,
        _,
        outbox,
        _,
        lease,
        envelope,
        admission,
        audit,
    ) = await artifact_fixture()

    artifact = await materialize(service, outbox, lease, envelope, admission)
    expected_bytes = canonical_json_bytes(envelope.canonical_value())

    assert service.durable is True
    assert repository.current == artifact
    assert artifact.canonical_bytes == expected_bytes
    assert artifact.canonical_byte_count == len(expected_bytes) == admission.canonical_byte_count
    assert artifact.content_sha256 == sha256(expected_bytes).hexdigest()
    assert artifact.admission_id == admission.admission_id
    assert artifact.admission_digest == admission.canonical_digest
    assert artifact.policy_digest == admission.policy_digest
    assert artifact.event_digest == envelope.canonical_digest
    assert artifact.outbox_entry_digest == outbox.canonical_digest
    assert artifact.publication_lease_id == lease.publication_lease_id
    assert artifact.canonical_digest == canonical_digest(artifact.digest_payload())
    assert "canonical_bytes" not in artifact.canonical_value()
    assert expected_bytes not in artifact.canonical_value().values()
    assert not any(artifact.authority.canonical_value().values())
    assert artifact.grants_publication_authority is False
    assert artifact.grants_delivery_authority is False
    assert artifact.grants_dispatch_authority is False
    assert artifact.grants_execution_authority is False
    assert audit.records[-1].result_code == "workflow_event_byte_artifact_materialized"


@pytest.mark.asyncio
async def test_exact_replay_is_stable_and_changed_request_fails_closed() -> None:
    (
        service,
        repository,
        _,
        _,
        outbox,
        _,
        lease,
        envelope,
        admission,
        audit,
    ) = await artifact_fixture()
    first = await materialize(service, outbox, lease, envelope, admission)
    replay = await materialize(
        service,
        outbox,
        lease,
        envelope,
        admission,
        context_time=NOW + timedelta(seconds=9),
    )
    assert replay == first
    assert audit.records[-1].result_code == "workflow_event_byte_artifact_replayed"

    key = (outbox.scope, lease.publisher_subject_id, "workflow-event-byte-artifact-0001")
    prior = repository.requests[key]
    repository.requests[key] = WorkflowEventByteArtifactIdempotencyRecord("f" * 64, prior.artifact)
    with pytest.raises(WorkflowEventByteArtifactError) as conflict:
        await materialize(service, outbox, lease, envelope, admission)
    assert conflict.value.code == "workflow_event_byte_artifact_idempotency_conflict"


@pytest.mark.asyncio
async def test_tampered_artifact_and_admission_fail_closed_with_audit() -> None:
    (
        service,
        repository,
        _,
        _,
        outbox,
        _,
        lease,
        envelope,
        admission,
        audit,
    ) = await artifact_fixture()
    artifact = await materialize(service, outbox, lease, envelope, admission)
    key = (outbox.scope, lease.publisher_subject_id, "workflow-event-byte-artifact-0001")
    altered_bytes = canonical_json_bytes(envelope.canonical_value() | {"tampered": True})
    altered_digest_payload = artifact.digest_payload() | {
        "canonical_byte_count": len(altered_bytes),
        "content_sha256": sha256(altered_bytes).hexdigest(),
    }
    tampered = replace(
        artifact,
        canonical_bytes=altered_bytes,
        canonical_byte_count=len(altered_bytes),
        content_sha256=sha256(altered_bytes).hexdigest(),
        canonical_digest=canonical_digest(altered_digest_payload),
    )
    prior = repository.requests[key]
    repository.requests[key] = WorkflowEventByteArtifactIdempotencyRecord(
        prior.request_fingerprint, tampered
    )
    with pytest.raises(WorkflowEventByteArtifactError) as artifact_error:
        await materialize(service, outbox, lease, envelope, admission)
    assert artifact_error.value.code == "workflow_event_byte_artifact_repository_scope_violation"
    assert audit.records[-1].result_code == artifact_error.value.code

    (
        service,
        repository,
        _,
        _,
        outbox,
        _,
        lease,
        envelope,
        admission,
        audit,
    ) = await artifact_fixture()
    admission_repository = repository.admission_repository
    tampered_admission = replace(
        admission,
        publisher_subject_id="service.workflow-outbox-publisher-tampered",
        canonical_digest=canonical_digest(
            admission.digest_payload()
            | {"publisher_subject_id": "service.workflow-outbox-publisher-tampered"}
        ),
    )
    admission_repository.current = tampered_admission
    with pytest.raises(WorkflowEventByteArtifactError) as admission_error:
        await materialize(service, outbox, lease, envelope, tampered_admission)
    assert admission_error.value.code == "workflow_event_byte_artifact_admission_scope_violation"
    assert audit.records[-1].result_code == admission_error.value.code


@pytest.mark.asyncio
async def test_expired_released_and_stale_leases_fail_closed() -> None:
    (
        service,
        _,
        publication_service,
        _,
        outbox,
        _,
        lease,
        envelope,
        admission,
        _,
    ) = await artifact_fixture()
    with pytest.raises(WorkflowEventByteArtifactError) as expired:
        await materialize(
            service,
            outbox,
            lease,
            envelope,
            admission,
            context_time=lease.expires_at,
        )
    assert expired.value.code == "workflow_event_byte_artifact_publication_lease_conflict"

    released = await publication_service.release(
        outbox_entry_id=outbox.outbox_entry_id,
        outbox_entry_digest=outbox.canonical_digest,
        publication_lease_id=lease.publication_lease_id,
        publication_lease_digest=lease.canonical_digest,
        publication_fencing_token=lease.publication_fencing_token,
        context=publisher_context(requested_at=NOW + timedelta(seconds=7)),
    )
    with pytest.raises(WorkflowEventByteArtifactError) as released_error:
        await materialize(
            service,
            outbox,
            released,
            envelope,
            admission,
            context_time=NOW + timedelta(seconds=8),
        )
    assert released_error.value.code == "workflow_event_byte_artifact_publication_lease_conflict"

    (
        service,
        _,
        _,
        plan_repository,
        outbox,
        orchestration,
        lease,
        envelope,
        admission,
        audit,
    ) = await artifact_fixture()
    await WorkflowOrchestrationLeaseService(
        plan_repository=plan_repository,
        lease_repository=plan_repository,
        audit_sink=audit,
    ).heartbeat(
        plan_id=outbox.plan_id,
        plan_digest=outbox.plan_digest,
        lease_id=orchestration.lease_id,
        lease_digest=orchestration.canonical_digest,
        fencing_token=orchestration.fencing_token,
        lease_seconds=300,
        context=worker_context(requested_at=NOW + timedelta(seconds=7)),
    )
    with pytest.raises(WorkflowEventByteArtifactError) as stale:
        await materialize(service, outbox, lease, envelope, admission)
    assert stale.value.code == "workflow_event_byte_artifact_orchestration_lease_conflict"


@pytest.mark.asyncio
async def test_audit_failure_never_returns_success() -> None:
    (
        _,
        repository,
        _,
        plan_repository,
        outbox,
        _,
        lease,
        envelope,
        admission,
        _,
    ) = await artifact_fixture()
    service = WorkflowEventByteArtifactService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        byte_artifact_repository=repository,
        audit_sink=CollectingAuditSink(fail=True),
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await materialize(service, outbox, lease, envelope, admission)
    assert repository.current is not None


def test_domain_recomputes_integrity_and_exposes_no_transport_surface() -> None:
    forbidden = {
        "broker",
        "provider",
        "endpoint",
        "queue",
        "topic",
        "partition",
        "routing_key",
        "credential",
        "publication_attempt",
        "receipt",
        "delivery_acknowledgement",
        "worker_reservation",
        "execution_result",
    }
    names = {field.name for field in fields(WorkflowEventByteArtifact)}
    assert forbidden.isdisjoint(names)
    assert "canonical_bytes" in names
