from __future__ import annotations

from dataclasses import fields
from datetime import timedelta

import pytest
from test_workflow_event_logical_channel_bindings import bind, binding_fixture
from test_workflow_outbox_publication_leases import NOW, CollectingAuditSink
from test_workflow_transport_profile_snapshots import (
    profile_fixture,
    register,
    registry_context,
)
from test_workflow_transport_profile_snapshots import (
    service_fixture as profile_service_fixture,
)

from atlas.modules.workflows.application import (
    WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
    WorkflowEventTransportCompatibilityAdmissionError,
    WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord,
    WorkflowEventTransportCompatibilityAdmissionRequest,
    WorkflowEventTransportCompatibilityAdmissionResult,
    WorkflowEventTransportCompatibilityAdmissionService,
    WorkflowEventTransportCompatibilityAdmissionStatus,
    WorkflowTransportCompatibilityAdmitterContext,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportProfileSnapshot,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowEventTransportCompatibilityAdmissionAuthority,
    WorkflowEventTransportCompatibilityAdmissionState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_transport_compatibility_policy,
)


class InMemoryTransportCompatibilityAdmissionRepository:
    def __init__(
        self,
        binding: WorkflowEventLogicalChannelBinding,
        *snapshots: EventPhysicalTransportProfileSnapshot,
    ) -> None:
        self.bindings = {binding.binding_id: binding}
        self.snapshots = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
        self.admissions: dict[
            tuple[str, str, str], WorkflowEventTransportCompatibilityAdmission
        ] = {}
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord,
        ] = {}

    @property
    def durable(self) -> bool:
        return True

    async def get_event_logical_channel_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        return self.bindings.get(binding_id)

    async def get_transport_profile_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportProfileSnapshot | None:
        return self.snapshots.get(snapshot_id)

    async def get_transport_compatibility_admission(
        self,
        *,
        logical_channel_binding_id: str,
        transport_profile_snapshot_id: str,
        policy_digest: str,
    ) -> WorkflowEventTransportCompatibilityAdmission | None:
        return self.admissions.get(
            (logical_channel_binding_id, transport_profile_snapshot_id, policy_digest)
        )

    async def list_transport_compatibility_admissions_by_binding(
        self, *, logical_channel_binding_id: str
    ) -> tuple[WorkflowEventTransportCompatibilityAdmission, ...]:
        return tuple(
            admission
            for admission in self.admissions.values()
            if admission.logical_channel_binding_id == logical_channel_binding_id
        )

    async def get_transport_compatibility_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord | None:
        return self.requests.get((scope, admitter_subject_id, idempotency_key))

    async def admit_transport_compatibility(
        self, request: WorkflowEventTransportCompatibilityAdmissionRequest
    ) -> WorkflowEventTransportCompatibilityAdmissionResult:
        claim_key = (request.scope, request.admitter_subject_id, request.idempotency_key)
        prior = self.requests.get(claim_key)
        if prior is not None:
            status = (
                WorkflowEventTransportCompatibilityAdmissionStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowEventTransportCompatibilityAdmissionStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowEventTransportCompatibilityAdmissionResult(status, prior.admission)
        source_key = (
            request.expected_logical_channel_binding_id,
            request.expected_transport_profile_snapshot_id,
            request.expected_policy_digest,
        )
        current = self.admissions.get(source_key)
        if current is not None:
            return WorkflowEventTransportCompatibilityAdmissionResult(
                WorkflowEventTransportCompatibilityAdmissionStatus.ALREADY_ADMITTED,
                current,
            )
        binding = self.bindings.get(request.expected_logical_channel_binding_id)
        snapshot = self.snapshots.get(request.expected_transport_profile_snapshot_id)
        if (
            binding is None
            or binding.canonical_digest != request.expected_logical_channel_binding_digest
            or snapshot is None
            or snapshot.canonical_digest != request.expected_transport_profile_snapshot_digest
        ):
            return WorkflowEventTransportCompatibilityAdmissionResult(
                WorkflowEventTransportCompatibilityAdmissionStatus.EVIDENCE_CONFLICT,
                None,
            )
        self.admissions[source_key] = request.candidate
        self.requests[claim_key] = WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord(
            request.request_fingerprint, request.candidate
        )
        return WorkflowEventTransportCompatibilityAdmissionResult(
            WorkflowEventTransportCompatibilityAdmissionStatus.ADMITTED,
            request.candidate,
        )


def admitter_context(
    *,
    scope: WorkflowScope,
    subject_id: str = "service.workflow-transport-compatibility-admitter",
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
) -> WorkflowTransportCompatibilityAdmitterContext:
    return WorkflowTransportCompatibilityAdmitterContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        correlation_id="correlation.transport-compatibility.0001",
        decision_id="decision.transport-compatibility.0001",
        requested_at=NOW + timedelta(seconds=20),
    )


async def source_fixture(
    *,
    profile_revision: str = "17",
    maximum_message_byte_count: int = 1_048_576,
    durable_delivery_supported: bool = True,
) -> tuple[WorkflowEventLogicalChannelBinding, EventPhysicalTransportProfileSnapshot]:
    (
        binding_service,
        _,
        _,
        _,
        outbox,
        _,
        lease,
        transport_admission,
        artifact,
        _,
    ) = await binding_fixture()
    binding = await bind(
        binding_service,
        outbox,
        lease,
        transport_admission,
        artifact,
    )
    profile = profile_fixture(
        profile_id=f"transport-profile.workflow-events.{profile_revision}",
        revision=profile_revision,
        scope=binding.scope,
        maximum_message_byte_count=maximum_message_byte_count,
    )
    if not durable_delivery_supported:
        values = profile.digest_payload() | {"durable_delivery_supported": False}
        object.__setattr__(profile, "durable_delivery_supported", False)
        object.__setattr__(profile, "canonical_digest", canonical_digest(values))
    profile_service, _, _, _ = profile_service_fixture(profile)
    snapshot = await register(
        profile_service,
        profile,
        context=registry_context(
            scope=binding.scope,
            requested_at=NOW + timedelta(seconds=15),
        ),
        idempotency_key=f"transport-profile-snapshot-{profile_revision}",
    )
    return binding, snapshot


def service_fixture(
    binding: WorkflowEventLogicalChannelBinding,
    *snapshots: EventPhysicalTransportProfileSnapshot,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowEventTransportCompatibilityAdmissionService,
    InMemoryTransportCompatibilityAdmissionRepository,
    CollectingAuditSink,
]:
    sink = audit or CollectingAuditSink()
    repository = InMemoryTransportCompatibilityAdmissionRepository(binding, *snapshots)
    return (
        WorkflowEventTransportCompatibilityAdmissionService(
            admission_repository=repository,
            audit_sink=sink,
        ),
        repository,
        sink,
    )


async def admit(
    service: WorkflowEventTransportCompatibilityAdmissionService,
    binding: WorkflowEventLogicalChannelBinding,
    snapshot: EventPhysicalTransportProfileSnapshot,
    *,
    idempotency_key: str = "transport-compatibility-admission-0001",
    context: WorkflowTransportCompatibilityAdmitterContext | None = None,
) -> WorkflowEventTransportCompatibilityAdmission:
    policy = service.policy
    return await service.admit(
        logical_channel_binding_id=binding.binding_id,
        logical_channel_binding_digest=binding.canonical_digest,
        transport_profile_snapshot_id=snapshot.snapshot_id,
        transport_profile_snapshot_digest=snapshot.canonical_digest,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_digest=policy.canonical_digest,
        idempotency_key=idempotency_key,
        context=context or admitter_context(scope=binding.scope),
    )


def test_code_owned_compatibility_policy_is_exact_and_deterministic() -> None:
    first = code_owned_workflow_event_transport_compatibility_policy()
    second = code_owned_workflow_event_transport_compatibility_policy()
    assert first == second
    assert first.policy_id == "policy.workflow-event-transport-compatibility"
    assert first.policy_version == "1.0"
    assert first.event_type == "WorkflowStepDispatchRequested"
    assert first.data_classification == "internal"
    assert first.representation_name == "canonical-json"
    assert first.encoding == "utf-8"
    assert first.delivery_semantics == "at-least-once"
    assert first.durability_required is True
    assert first.ordering_key_kind == "workflow-run"
    assert first.retention_class == "workflow-operational"
    assert first.maximum_logical_byte_count == 65_536
    assert first.canonical_digest == canonical_digest(first.digest_payload())


@pytest.mark.asyncio
async def test_admits_exact_contracts_deterministically_with_zero_authority() -> None:
    binding, snapshot = await source_fixture()
    service, repository, audit = service_fixture(binding, snapshot)
    admission = await admit(service, binding, snapshot)

    assert service.durable is True
    assert admission.logical_channel_binding_id == binding.binding_id
    assert admission.logical_channel_binding_digest == binding.canonical_digest
    assert admission.transport_profile_snapshot_id == snapshot.snapshot_id
    assert admission.transport_profile_snapshot_digest == snapshot.canonical_digest
    assert admission.transport_profile_id == snapshot.transport_profile_id
    assert admission.artifact_byte_count == binding.canonical_byte_count
    assert admission.state is WorkflowEventTransportCompatibilityAdmissionState.ADMITTED
    assert admission.canonical_digest == canonical_digest(admission.digest_payload())
    assert not any(admission.authority.canonical_value().values())
    assert admission.grants_route_selection_authority is False
    assert admission.grants_route_binding_authority is False
    assert admission.grants_credential_access_authority is False
    assert admission.grants_publication_authority is False
    assert admission.grants_delivery_authority is False
    assert admission.grants_dispatch_authority is False
    assert admission.grants_execution_authority is False
    assert len(repository.admissions) == 1
    assert audit.records[-1].result_code == (
        "workflow_transport_compatibility_admission_authorized"
    )


@pytest.mark.asyncio
async def test_exact_replay_changed_key_and_competing_identity_fail_closed() -> None:
    binding, first_snapshot = await source_fixture()
    _, second_snapshot = await source_fixture(profile_revision="18")
    service, repository, audit = service_fixture(binding, first_snapshot, second_snapshot)
    first = await admit(service, binding, first_snapshot)
    replay = await admit(service, binding, first_snapshot)
    assert replay == first
    assert audit.records[-1].result_code == ("workflow_transport_compatibility_admission_replayed")

    with pytest.raises(WorkflowEventTransportCompatibilityAdmissionError) as changed:
        await admit(service, binding, second_snapshot)
    assert changed.value.code == "workflow_transport_compatibility_idempotency_conflict"

    other = admitter_context(
        scope=binding.scope,
        subject_id="service.workflow-transport-compatibility-admitter-secondary",
    )
    with pytest.raises(WorkflowEventTransportCompatibilityAdmissionError) as competing:
        await admit(
            service,
            binding,
            first_snapshot,
            idempotency_key="transport-compatibility-admission-secondary",
            context=other,
        )
    assert competing.value.code == "workflow_transport_compatibility_competing_identity"
    assert len(repository.admissions) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actor_type", "authentication_method", "audience"),
    [
        ("human", "password", "audience.browser"),
        ("service", "workload_token", "audience.workflow-outbox-publisher"),
        ("service", "workload_token", "audience.workflow-transport-profile-registry"),
    ],
)
async def test_only_dedicated_admitter_workload_can_create(
    actor_type: str, authentication_method: str, audience: str
) -> None:
    binding, snapshot = await source_fixture()
    service, repository, _ = service_fixture(binding, snapshot)
    context = admitter_context(
        scope=binding.scope,
        actor_type=actor_type,
        authentication_method=authentication_method,
        audience=audience,
    )
    with pytest.raises(WorkflowEventTransportCompatibilityAdmissionError) as denied:
        await admit(service, binding, snapshot, context=context)
    assert denied.value.code == "workflow_transport_compatibility_admitter_identity_required"
    assert repository.admissions == {}
    assert repository.requests == {}


@pytest.mark.asyncio
async def test_scope_tamper_policy_and_insufficient_capabilities_fail_closed() -> None:
    binding, snapshot = await source_fixture()
    service, repository, audit = service_fixture(binding, snapshot)

    wrong_scope = WorkflowScope(
        binding.scope.organization_id,
        binding.scope.environment_id,
        "site.other",
    )
    with pytest.raises(WorkflowEventTransportCompatibilityAdmissionError) as scope_error:
        await admit(service, binding, snapshot, context=admitter_context(scope=wrong_scope))
    assert scope_error.value.code == "workflow_transport_compatibility_evidence_conflict"

    original_digest = binding.canonical_digest
    object.__setattr__(binding, "canonical_digest", "f" * 64)
    with pytest.raises(WorkflowEventTransportCompatibilityAdmissionError) as tamper_error:
        await admit(service, binding, snapshot)
    assert tamper_error.value.code == "workflow_transport_compatibility_evidence_conflict"
    object.__setattr__(binding, "canonical_digest", original_digest)

    with pytest.raises(WorkflowEventTransportCompatibilityAdmissionError) as policy_error:
        await service.admit(
            logical_channel_binding_id=binding.binding_id,
            logical_channel_binding_digest=binding.canonical_digest,
            transport_profile_snapshot_id=snapshot.snapshot_id,
            transport_profile_snapshot_digest=snapshot.canonical_digest,
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            policy_digest="e" * 64,
            idempotency_key="transport-compatibility-policy-conflict",
            context=admitter_context(scope=binding.scope),
        )
    assert policy_error.value.code == "workflow_transport_compatibility_policy_conflict"

    _, small_snapshot = await source_fixture(maximum_message_byte_count=32_768)
    small_service, small_repository, _ = service_fixture(binding, small_snapshot)
    with pytest.raises(WorkflowEventTransportCompatibilityAdmissionError) as size_error:
        await admit(small_service, binding, small_snapshot)
    assert size_error.value.code == "workflow_transport_compatibility_message_size_insufficient"
    assert small_repository.admissions == {}

    _, nondurable_snapshot = await source_fixture(durable_delivery_supported=False)
    durability_service, durability_repository, _ = service_fixture(binding, nondurable_snapshot)
    with pytest.raises(WorkflowEventTransportCompatibilityAdmissionError) as durability_error:
        await admit(durability_service, binding, nondurable_snapshot)
    assert durability_error.value.code == "workflow_transport_compatibility_durability_unsupported"
    assert durability_repository.admissions == {}
    assert repository.admissions == {}
    assert all(record.outcome == "denied" for record in audit.records)


@pytest.mark.asyncio
async def test_audit_failure_creates_no_admission_or_idempotency_claim() -> None:
    binding, snapshot = await source_fixture()
    failing_audit = CollectingAuditSink(fail=True)
    service, repository, _ = service_fixture(binding, snapshot, audit=failing_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await admit(service, binding, snapshot)
    assert repository.admissions == {}
    assert repository.requests == {}


def test_domain_rejects_nonzero_authority_and_exposes_no_route_or_lineage_surface() -> None:
    with pytest.raises(ValueError, match="cannot grant operational authority"):
        WorkflowEventTransportCompatibilityAdmissionAuthority(route_binding_authorized=True)

    forbidden = {
        "artifact_id",
        "event_id",
        "outbox_entry_id",
        "run_id",
        "attempt_id",
        "lease_id",
        "route_id",
        "endpoint",
        "hostname",
        "url",
        "ip_address",
        "namespace",
        "topic",
        "stream",
        "queue",
        "partition",
        "routing_key",
        "credential",
        "secret_reference",
        "vault_path",
        "provider_message_id",
        "publication_attempt",
        "retry",
        "receipt",
        "acknowledgement",
        "offset",
        "network_health",
        "ready",
    }
    names = {field.name for field in fields(WorkflowEventTransportCompatibilityAdmission)}
    assert forbidden.isdisjoint(names)
