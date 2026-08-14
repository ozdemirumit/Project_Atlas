from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
    WorkflowTransportProfileRegistryContext,
    WorkflowTransportProfileSnapshotError,
    WorkflowTransportProfileSnapshotIdempotencyRecord,
    WorkflowTransportProfileSnapshotRequest,
    WorkflowTransportProfileSnapshotResult,
    WorkflowTransportProfileSnapshotService,
    WorkflowTransportProfileSnapshotStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportProfile,
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportProfileSnapshotAuthority,
    EventPhysicalTransportProfileSnapshotState,
    WorkflowScope,
    canonical_digest,
)

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")


class CollectingAuditSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.records.append(event)


class InMemoryTransportProfileRegistry:
    def __init__(self, *profiles: DeploymentEventTransportProfile) -> None:
        self.profiles = {
            (profile.transport_profile_id, profile.transport_profile_revision): profile
            for profile in profiles
        }
        self.read_count = 0

    @property
    def durable(self) -> bool:
        return True

    async def get_active_transport_profile(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
    ) -> DeploymentEventTransportProfile | None:
        self.read_count += 1
        return self.profiles.get((transport_profile_id, transport_profile_revision))


class InMemoryTransportProfileSnapshotRepository:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, str], EventPhysicalTransportProfileSnapshot] = {}
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowTransportProfileSnapshotIdempotencyRecord,
        ] = {}

    @property
    def durable(self) -> bool:
        return True

    async def get_transport_profile_snapshot(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
    ) -> EventPhysicalTransportProfileSnapshot | None:
        return self.snapshots.get((transport_profile_id, transport_profile_revision))

    async def get_transport_profile_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportProfileSnapshotIdempotencyRecord | None:
        return self.requests.get((scope, snapshotter_subject_id, idempotency_key))

    async def snapshot_transport_profile(
        self, request: WorkflowTransportProfileSnapshotRequest
    ) -> WorkflowTransportProfileSnapshotResult:
        claim_key = (
            request.scope,
            request.snapshotter_subject_id,
            request.idempotency_key,
        )
        prior = self.requests.get(claim_key)
        if prior is not None:
            status = (
                WorkflowTransportProfileSnapshotStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowTransportProfileSnapshotStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowTransportProfileSnapshotResult(status, prior.snapshot)
        source_key = (
            request.expected_source_profile_id,
            request.expected_source_profile_revision,
        )
        current = self.snapshots.get(source_key)
        if current is not None:
            return WorkflowTransportProfileSnapshotResult(
                WorkflowTransportProfileSnapshotStatus.ALREADY_SNAPSHOTTED,
                current,
            )
        self.snapshots[source_key] = request.candidate
        self.requests[claim_key] = WorkflowTransportProfileSnapshotIdempotencyRecord(
            request.request_fingerprint, request.candidate
        )
        return WorkflowTransportProfileSnapshotResult(
            WorkflowTransportProfileSnapshotStatus.SNAPSHOTTED,
            request.candidate,
        )


def profile_fixture(
    *,
    profile_id: str = "transport-profile.workflow-events.primary",
    revision: str = "17",
    scope: WorkflowScope = SCOPE,
    active: bool = True,
    implementation: str = "transport.nats-jetstream",
    maximum_message_byte_count: int = 1_048_576,
) -> DeploymentEventTransportProfile:
    values: dict[str, object] = {
        "transport_profile_id": profile_id,
        "transport_profile_revision": revision,
        "deployment_release_id": "atlas-release.2026.08.14",
        "deployment_profile": "lab",
        "scope": scope,
        "transport_resource_id": "transport-resource.workflow-events.primary",
        "transport_resource_digest": "1" * 64,
        "transport_implementation_id": implementation,
        "transport_implementation_version": "2.11",
        "adapter_contract_id": "adapter-contract.workflow-events",
        "adapter_contract_version": "1.0",
        "adapter_contract_digest": "2" * 64,
        "supported_event_contracts": (
            "WorkflowStepDispatchRequested|1.0|"
            "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
        ),
        "supported_classifications": ("internal",),
        "supported_representations": ("canonical-json",),
        "supported_encodings": ("utf-8",),
        "supported_delivery_semantics": ("at-least-once",),
        "durable_delivery_supported": True,
        "supported_ordering_key_kinds": ("workflow-run",),
        "supported_retention_classes": ("workflow-operational",),
        "maximum_message_byte_count": maximum_message_byte_count,
        "transport_encryption_required": True,
        "restricted_network_supported": True,
        "active": active,
    }
    digest_payload = {
        key: value.canonical_value() if isinstance(value, WorkflowScope) else value
        for key, value in values.items()
    }
    return DeploymentEventTransportProfile(
        **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
    )


def registry_context(
    *,
    subject_id: str = "service.workflow-transport-profile-registry",
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
    scope: WorkflowScope = SCOPE,
    requested_at: datetime = NOW,
) -> WorkflowTransportProfileRegistryContext:
    return WorkflowTransportProfileRegistryContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        correlation_id="correlation.transport-profile.0001",
        decision_id="decision.transport-profile.0001",
        requested_at=requested_at,
    )


def service_fixture(
    *profiles: DeploymentEventTransportProfile,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowTransportProfileSnapshotService,
    InMemoryTransportProfileRegistry,
    InMemoryTransportProfileSnapshotRepository,
    CollectingAuditSink,
]:
    sink = audit or CollectingAuditSink()
    registry = InMemoryTransportProfileRegistry(*profiles)
    repository = InMemoryTransportProfileSnapshotRepository()
    service = WorkflowTransportProfileSnapshotService(
        transport_profile_registry=registry,
        snapshot_repository=repository,
        audit_sink=sink,
    )
    return service, registry, repository, sink


async def register(
    service: WorkflowTransportProfileSnapshotService,
    profile: DeploymentEventTransportProfile,
    *,
    idempotency_key: str = "transport-profile-snapshot-0001",
    context: WorkflowTransportProfileRegistryContext | None = None,
    **changes: object,
) -> EventPhysicalTransportProfileSnapshot:
    values: dict[str, object] = {
        "transport_profile_id": profile.transport_profile_id,
        "transport_profile_revision": profile.transport_profile_revision,
        "source_profile_digest": profile.canonical_digest,
        "idempotency_key": idempotency_key,
        "context": context or registry_context(),
    }
    values.update(changes)
    return await service.register(**cast(Any, values))


@pytest.mark.asyncio
async def test_captures_server_owned_capabilities_deterministically_with_zero_authority() -> None:
    profile = profile_fixture()
    service, registry, repository, audit = service_fixture(profile)

    snapshot = await register(service, profile)

    assert service.durable is True
    assert registry.read_count == 1
    assert (
        repository.snapshots[(profile.transport_profile_id, profile.transport_profile_revision)]
        == snapshot
    )
    assert snapshot.source_profile_digest == profile.canonical_digest
    assert snapshot.supported_event_contracts == profile.supported_event_contracts
    assert snapshot.maximum_message_byte_count == profile.maximum_message_byte_count
    assert snapshot.state is EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
    assert snapshot.canonical_digest == canonical_digest(snapshot.digest_payload())
    assert not any(snapshot.authority.canonical_value().values())
    assert snapshot.grants_route_selection_authority is False
    assert snapshot.grants_publication_authority is False
    assert snapshot.grants_delivery_authority is False
    assert snapshot.grants_dispatch_authority is False
    assert snapshot.grants_execution_authority is False
    assert audit.records[-1].result_code == "workflow_transport_profile_snapshot_authorized"

    client_parameters = set(inspect.signature(service.register).parameters)
    assert client_parameters == {
        "transport_profile_id",
        "transport_profile_revision",
        "source_profile_digest",
        "idempotency_key",
        "context",
    }


@pytest.mark.asyncio
async def test_exact_replay_is_stable_and_changed_request_conflicts() -> None:
    first_profile = profile_fixture()
    second_profile = profile_fixture(
        profile_id="transport-profile.workflow-events.secondary", revision="3"
    )
    service, _, _, audit = service_fixture(first_profile, second_profile)
    first = await register(service, first_profile)
    replay = await register(
        service,
        first_profile,
        context=registry_context(requested_at=NOW + timedelta(seconds=10)),
    )
    assert replay == first
    assert audit.records[-1].result_code == "workflow_transport_profile_snapshot_replayed"

    with pytest.raises(WorkflowTransportProfileSnapshotError) as conflict:
        await register(service, second_profile)
    assert conflict.value.code == "workflow_transport_profile_snapshot_idempotency_conflict"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("context", "expected_code"),
    [
        (
            registry_context(
                subject_id="user.operator",
                actor_type="human",
                authentication_method="password",
                audience="audience.browser",
            ),
            "workflow_transport_profile_snapshot_registry_identity_required",
        ),
        (
            registry_context(audience="audience.workflow-outbox-publisher"),
            "workflow_transport_profile_snapshot_registry_identity_required",
        ),
    ],
)
async def test_only_dedicated_registry_workload_can_create(
    context: WorkflowTransportProfileRegistryContext, expected_code: str
) -> None:
    profile = profile_fixture()
    service, registry, repository, _ = service_fixture(profile)
    with pytest.raises(WorkflowTransportProfileSnapshotError) as denied:
        await register(service, profile, context=context)
    assert denied.value.code == expected_code
    assert registry.read_count == 0
    assert repository.snapshots == {}


@pytest.mark.asyncio
async def test_inactive_drifted_and_wrong_scope_sources_fail_closed() -> None:
    inactive = profile_fixture(active=False)
    service, _, repository, _ = service_fixture(inactive)
    with pytest.raises(WorkflowTransportProfileSnapshotError) as inactive_error:
        await register(service, inactive)
    assert inactive_error.value.code == "workflow_transport_profile_snapshot_source_not_active"
    assert repository.snapshots == {}

    profile = profile_fixture()
    service, _, repository, _ = service_fixture(profile)
    with pytest.raises(WorkflowTransportProfileSnapshotError) as drift:
        await register(service, profile, source_profile_digest="f" * 64)
    assert drift.value.code == "workflow_transport_profile_snapshot_source_conflict"
    assert repository.snapshots == {}

    other_scope = WorkflowScope("org-atlas", "environment-lab", "site-ankara")
    wrong_scope = profile_fixture(scope=other_scope)
    service, _, repository, _ = service_fixture(wrong_scope)
    with pytest.raises(WorkflowTransportProfileSnapshotError) as scope_error:
        await register(service, wrong_scope)
    assert scope_error.value.code == "workflow_transport_profile_snapshot_source_conflict"
    assert repository.snapshots == {}


@pytest.mark.asyncio
async def test_audit_failure_prevents_snapshot_and_idempotency_state() -> None:
    profile = profile_fixture()
    service, _, repository, _ = service_fixture(profile, audit=CollectingAuditSink(fail=True))
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await register(service, profile)
    assert repository.snapshots == {}
    assert repository.requests == {}


def test_domain_rejects_overstated_capabilities_and_nonzero_authority() -> None:
    profile = profile_fixture()
    with pytest.raises(ValueError, match="transport_implementation_id is unsupported"):
        profile_fixture(implementation="transport.unapproved")
    with pytest.raises(ValueError, match="supported range"):
        profile_fixture(maximum_message_byte_count=0)
    with pytest.raises(ValueError, match="cannot grant operational authority"):
        EventPhysicalTransportProfileSnapshotAuthority(publication_authorized=True)
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(profile, deployment_release_id="atlas-release.changed")


def test_snapshot_domain_exposes_no_lineage_route_secret_or_network_surface() -> None:
    forbidden = {
        "event_id",
        "artifact_id",
        "logical_channel_binding_id",
        "outbox_entry_id",
        "run_id",
        "attempt_id",
        "lease_id",
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
        "compatible",
        "selected",
        "ready_to_publish",
    }
    names = {field.name for field in fields(EventPhysicalTransportProfileSnapshot)}
    assert forbidden.isdisjoint(names)
