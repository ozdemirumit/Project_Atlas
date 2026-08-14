from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from test_workflow_event_byte_artifacts import (
    InMemoryByteArtifactRepository,
    artifact_fixture,
    materialize,
)
from test_workflow_outbox_publication_leases import (
    NOW,
    CollectingAuditSink,
    publisher_context,
    worker_context,
)

from atlas.modules.workflows.adapters import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowEventLogicalChannelBindingError,
    WorkflowEventLogicalChannelBindingIdempotencyRecord,
    WorkflowEventLogicalChannelBindingRequest,
    WorkflowEventLogicalChannelBindingResult,
    WorkflowEventLogicalChannelBindingService,
    WorkflowEventLogicalChannelBindingStatus,
    WorkflowOrchestrationLeaseService,
    WorkflowOutboxPublicationLeaseService,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchOutboxEntry,
    WorkflowEventByteArtifact,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventLogicalChannelBindingState,
    WorkflowEventLogicalChannelPolicy,
    WorkflowEventTransportAdmission,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_logical_channel_policy,
)


class InMemoryLogicalChannelBindingRepository:
    def __init__(self, byte_repository: InMemoryByteArtifactRepository) -> None:
        self.byte_repository = byte_repository
        self.current: WorkflowEventLogicalChannelBinding | None = None
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventLogicalChannelBindingIdempotencyRecord,
        ] = {}

    @property
    def durable(self) -> bool:
        return True

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        return await self.byte_repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        return await self.byte_repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None:
        return await self.byte_repository.get_event_transport_admission_by_event_id(
            event_id=event_id
        )

    async def get_event_byte_artifact_by_id(
        self, *, artifact_id: str
    ) -> WorkflowEventByteArtifact | None:
        if self.byte_repository.current is None:
            return None
        if self.byte_repository.current.artifact_id != artifact_id:
            return None
        return self.byte_repository.current

    async def get_event_logical_channel_binding_by_artifact_id(
        self, *, artifact_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        if self.current is None or self.current.artifact_id != artifact_id:
            return None
        return self.current

    async def get_event_logical_channel_binding_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventLogicalChannelBindingIdempotencyRecord | None:
        return self.requests.get((scope, publisher_subject_id, idempotency_key))

    async def bind_event_logical_channel(
        self, request: WorkflowEventLogicalChannelBindingRequest
    ) -> WorkflowEventLogicalChannelBindingResult:
        key = (
            request.candidate.scope,
            request.publisher_subject_id,
            request.idempotency_key,
        )
        prior = self.requests.get(key)
        if prior is not None:
            status = (
                WorkflowEventLogicalChannelBindingStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowEventLogicalChannelBindingStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowEventLogicalChannelBindingResult(status, prior.binding)
        if self.current is not None:
            return WorkflowEventLogicalChannelBindingResult(
                WorkflowEventLogicalChannelBindingStatus.ALREADY_BOUND,
                self.current,
            )
        self.current = request.candidate
        self.requests[key] = WorkflowEventLogicalChannelBindingIdempotencyRecord(
            request.request_fingerprint,
            request.candidate,
        )
        return WorkflowEventLogicalChannelBindingResult(
            WorkflowEventLogicalChannelBindingStatus.BOUND,
            request.candidate,
        )


async def binding_fixture(
    *, audit: CollectingAuditSink | None = None
) -> tuple[
    WorkflowEventLogicalChannelBindingService,
    InMemoryLogicalChannelBindingRepository,
    WorkflowOutboxPublicationLeaseService,
    InMemoryWorkflowPlanRepository,
    WorkflowDispatchOutboxEntry,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowEventTransportAdmission,
    WorkflowEventByteArtifact,
    CollectingAuditSink,
]:
    (
        artifact_service,
        byte_repository,
        publication_service,
        plan_repository,
        outbox,
        orchestration_lease,
        publication_lease,
        envelope,
        admission,
        sink,
    ) = await artifact_fixture(audit=audit)
    artifact = await materialize(
        artifact_service,
        outbox,
        publication_lease,
        envelope,
        admission,
    )
    repository = InMemoryLogicalChannelBindingRepository(byte_repository)
    service = WorkflowEventLogicalChannelBindingService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        logical_channel_binding_repository=repository,
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
        admission,
        artifact,
        sink,
    )


async def bind(
    service: WorkflowEventLogicalChannelBindingService,
    outbox: WorkflowDispatchOutboxEntry,
    publication_lease: WorkflowOutboxPublicationLease,
    admission: WorkflowEventTransportAdmission,
    artifact: WorkflowEventByteArtifact,
    *,
    idempotency_key: str = "workflow-logical-channel-binding-0001",
    context_time: datetime = NOW + timedelta(seconds=9),
    **changes: object,
) -> WorkflowEventLogicalChannelBinding:
    policy = service.policy
    values: dict[str, object] = {
        "artifact_id": artifact.artifact_id,
        "artifact_digest": artifact.canonical_digest,
        "content_sha256": artifact.content_sha256,
        "canonical_byte_count": artifact.canonical_byte_count,
        "admission_id": admission.admission_id,
        "admission_digest": admission.canonical_digest,
        "event_id": artifact.event_id,
        "event_digest": artifact.event_digest,
        "outbox_entry_id": outbox.outbox_entry_id,
        "outbox_entry_digest": outbox.canonical_digest,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "logical_channel_id": policy.logical_channel_id,
        "logical_channel_version": policy.logical_channel_version,
        "publication_lease_id": publication_lease.publication_lease_id,
        "publication_lease_digest": publication_lease.canonical_digest,
        "publication_fencing_token": publication_lease.publication_fencing_token,
        "idempotency_key": idempotency_key,
        "context": publisher_context(requested_at=context_time),
    }
    values.update(changes)
    return await service.bind(**cast(Any, values))


def test_code_owned_policy_is_exact_and_deterministic() -> None:
    first = code_owned_workflow_event_logical_channel_policy()
    second = code_owned_workflow_event_logical_channel_policy()

    assert first == second
    assert first.policy_id == "policy.workflow-event-logical-channel"
    assert first.policy_version == "1.0"
    assert first.logical_channel_id == "channel.workflow-dispatch.internal"
    assert first.logical_channel_version == "1.0"
    assert first.allowed_event_types == ("WorkflowStepDispatchRequested",)
    assert first.allowed_event_versions == ("1.0",)
    assert first.allowed_schema_uris == (
        "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
    )
    assert first.allowed_data_classifications == ("internal",)
    assert first.representation_name == "canonical-json"
    assert first.encoding == "utf-8"
    assert first.delivery_semantics == "at-least-once"
    assert first.durability_required is True
    assert first.ordering_key_kind == "workflow-run"
    assert first.retention_class == "workflow-operational"
    assert first.maximum_canonical_byte_count == 65_536
    assert first.canonical_digest == canonical_digest(first.digest_payload())


@pytest.mark.asyncio
async def test_binds_exact_artifact_deterministically_with_zero_authority() -> None:
    (
        service,
        repository,
        _,
        _,
        outbox,
        _,
        lease,
        admission,
        artifact,
        audit,
    ) = await binding_fixture()

    binding = await bind(service, outbox, lease, admission, artifact)

    assert service.durable is True
    assert repository.current == binding
    assert binding.artifact_id == artifact.artifact_id
    assert binding.artifact_digest == artifact.canonical_digest
    assert binding.content_sha256 == artifact.content_sha256
    assert binding.canonical_byte_count == artifact.canonical_byte_count
    assert binding.admission_digest == admission.canonical_digest
    assert binding.event_digest == artifact.event_digest
    assert binding.outbox_entry_digest == outbox.canonical_digest
    assert binding.ordering_key_value == binding.run_id == artifact.run_id
    assert binding.state is WorkflowEventLogicalChannelBindingState.BOUND
    assert binding.canonical_digest == canonical_digest(binding.digest_payload())
    assert not any(binding.authority.canonical_value().values())
    assert binding.grants_publication_authority is False
    assert binding.grants_delivery_authority is False
    assert binding.grants_dispatch_authority is False
    assert binding.grants_execution_authority is False
    assert audit.records[-1].result_code == ("workflow_event_logical_channel_binding_authorized")


@pytest.mark.asyncio
async def test_exact_replay_is_stable_and_changed_request_conflicts() -> None:
    (
        service,
        repository,
        _,
        _,
        outbox,
        _,
        lease,
        admission,
        artifact,
        audit,
    ) = await binding_fixture()
    first = await bind(service, outbox, lease, admission, artifact)
    replay = await bind(
        service,
        outbox,
        lease,
        admission,
        artifact,
        context_time=NOW + timedelta(seconds=10),
    )
    assert replay == first
    assert audit.records[-1].result_code == "workflow_event_logical_channel_binding_replayed"

    key = (artifact.scope, lease.publisher_subject_id, "workflow-logical-channel-binding-0001")
    prior = repository.requests[key]
    repository.requests[key] = WorkflowEventLogicalChannelBindingIdempotencyRecord(
        "f" * 64, prior.binding
    )
    with pytest.raises(WorkflowEventLogicalChannelBindingError) as conflict:
        await bind(service, outbox, lease, admission, artifact)
    assert conflict.value.code == "workflow_event_logical_channel_binding_idempotency_conflict"


@pytest.mark.asyncio
async def test_tampered_artifact_and_policy_mismatch_fail_closed() -> None:
    (
        service,
        repository,
        _,
        _,
        outbox,
        _,
        lease,
        admission,
        artifact,
        audit,
    ) = await binding_fixture()
    tampered_subject = "service.workflow-outbox-publisher-tampered"
    tampered = replace(
        artifact,
        publisher_subject_id=tampered_subject,
        canonical_digest=canonical_digest(
            artifact.digest_payload() | {"publisher_subject_id": tampered_subject}
        ),
    )
    repository.byte_repository.current = tampered
    with pytest.raises(WorkflowEventLogicalChannelBindingError) as artifact_error:
        await bind(
            service,
            outbox,
            lease,
            admission,
            tampered,
        )
    assert artifact_error.value.code == (
        "workflow_event_logical_channel_binding_artifact_scope_violation"
    )
    assert audit.records[-1].result_code == artifact_error.value.code

    service, _, _, _, outbox, _, lease, admission, artifact, audit = await binding_fixture()
    with pytest.raises(WorkflowEventLogicalChannelBindingError) as policy_error:
        await bind(
            service,
            outbox,
            lease,
            admission,
            artifact,
            policy_digest="f" * 64,
        )
    assert policy_error.value.code == "workflow_event_logical_channel_binding_policy_conflict"
    assert audit.records[-1].result_code == policy_error.value.code


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
        admission,
        artifact,
        _,
    ) = await binding_fixture()
    with pytest.raises(WorkflowEventLogicalChannelBindingError) as expired:
        await bind(
            service,
            outbox,
            lease,
            admission,
            artifact,
            context_time=lease.expires_at,
        )
    assert expired.value.code == (
        "workflow_event_logical_channel_binding_publication_lease_conflict"
    )

    released = await publication_service.release(
        outbox_entry_id=outbox.outbox_entry_id,
        outbox_entry_digest=outbox.canonical_digest,
        publication_lease_id=lease.publication_lease_id,
        publication_lease_digest=lease.canonical_digest,
        publication_fencing_token=lease.publication_fencing_token,
        context=publisher_context(requested_at=NOW + timedelta(seconds=9)),
    )
    with pytest.raises(WorkflowEventLogicalChannelBindingError) as released_error:
        await bind(
            service,
            outbox,
            released,
            admission,
            artifact,
            context_time=NOW + timedelta(seconds=10),
        )
    assert released_error.value.code == (
        "workflow_event_logical_channel_binding_publication_lease_conflict"
    )

    (
        service,
        _,
        _,
        plan_repository,
        outbox,
        orchestration,
        lease,
        admission,
        artifact,
        audit,
    ) = await binding_fixture()
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
        context=worker_context(requested_at=NOW + timedelta(seconds=9)),
    )
    with pytest.raises(WorkflowEventLogicalChannelBindingError) as stale:
        await bind(
            service,
            outbox,
            lease,
            admission,
            artifact,
            context_time=NOW + timedelta(seconds=10),
        )
    assert stale.value.code == (
        "workflow_event_logical_channel_binding_orchestration_lease_conflict"
    )


@pytest.mark.asyncio
async def test_audit_failure_prevents_all_binding_state() -> None:
    (
        _,
        repository,
        _,
        plan_repository,
        outbox,
        _,
        lease,
        admission,
        artifact,
        _,
    ) = await binding_fixture()
    service = WorkflowEventLogicalChannelBindingService(
        plan_repository=plan_repository,
        orchestration_lease_repository=plan_repository,
        logical_channel_binding_repository=repository,
        audit_sink=CollectingAuditSink(fail=True),
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await bind(service, outbox, lease, admission, artifact)
    assert repository.current is None
    assert repository.requests == {}


def test_domain_rejects_route_mutation_and_exposes_no_physical_transport_surface() -> None:
    forbidden = {
        "broker",
        "provider",
        "endpoint",
        "namespace",
        "queue",
        "topic",
        "stream",
        "partition",
        "routing_key",
        "credential",
        "secret_reference",
        "network",
        "message",
        "publication_attempt",
        "retry_schedule",
        "receipt",
        "delivery_acknowledgement",
    }
    names = {field.name for field in fields(WorkflowEventLogicalChannelBinding)}
    assert forbidden.isdisjoint(names)

    policy = code_owned_workflow_event_logical_channel_policy()
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        WorkflowEventLogicalChannelPolicy(
            **cast(
                Any,
                {
                    **policy.digest_payload(),
                    "allowed_event_types": policy.allowed_event_types,
                    "allowed_event_versions": policy.allowed_event_versions,
                    "allowed_schema_uris": policy.allowed_schema_uris,
                    "allowed_data_classifications": policy.allowed_data_classifications,
                    "logical_channel_id": "channel.workflow-dispatch.changed",
                    "canonical_digest": policy.canonical_digest,
                },
            )
        )
