from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
    WorkflowTransportRouteRegistryContext,
    WorkflowTransportRouteSnapshotError,
    WorkflowTransportRouteSnapshotIdempotencyRecord,
    WorkflowTransportRouteSnapshotRequest,
    WorkflowTransportRouteSnapshotResult,
    WorkflowTransportRouteSnapshotService,
    WorkflowTransportRouteSnapshotStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRoute,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotAuthority,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowScope,
    canonical_digest,
)

NOW = datetime(2026, 8, 14, 14, 0, tzinfo=UTC)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")


class CollectingAuditSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.records.append(event)


class InMemoryTransportRouteRegistry:
    def __init__(self, *routes: DeploymentEventTransportRoute) -> None:
        self.routes = {(route.route_id, route.route_revision): route for route in routes}
        self.read_count = 0

    @property
    def durable(self) -> bool:
        return True

    async def get_active_transport_route(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> DeploymentEventTransportRoute | None:
        self.read_count += 1
        return self.routes.get((route_id, route_revision))


class InMemoryTransportRouteSnapshotRepository:
    def __init__(self, audit: CollectingAuditSink) -> None:
        self.audit = audit
        self.snapshots: dict[tuple[str, str], EventPhysicalTransportRouteSnapshot] = {}
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowTransportRouteSnapshotIdempotencyRecord,
        ] = {}
        self.pre_persistence_audit: AuditRecord | None = None

    @property
    def durable(self) -> bool:
        return True

    async def get_transport_route_snapshot(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> EventPhysicalTransportRouteSnapshot | None:
        return self.snapshots.get((route_id, route_revision))

    async def get_transport_route_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportRouteSnapshotIdempotencyRecord | None:
        return self.requests.get((scope, snapshotter_subject_id, idempotency_key))

    async def snapshot_transport_route(
        self, request: WorkflowTransportRouteSnapshotRequest
    ) -> WorkflowTransportRouteSnapshotResult:
        self.pre_persistence_audit = self.audit.records[-1] if self.audit.records else None
        claim_key = (request.scope, request.snapshotter_subject_id, request.idempotency_key)
        prior = self.requests.get(claim_key)
        if prior is not None:
            status = (
                WorkflowTransportRouteSnapshotStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowTransportRouteSnapshotStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowTransportRouteSnapshotResult(status, prior.snapshot)
        source_key = (
            request.expected_source_route_id,
            request.expected_source_route_revision,
        )
        current = self.snapshots.get(source_key)
        if current is not None:
            return WorkflowTransportRouteSnapshotResult(
                WorkflowTransportRouteSnapshotStatus.ALREADY_SNAPSHOTTED,
                current,
            )
        if request.candidate.source_route_digest != request.expected_source_route_digest:
            return WorkflowTransportRouteSnapshotResult(
                WorkflowTransportRouteSnapshotStatus.SOURCE_CONFLICT,
                None,
            )
        self.snapshots[source_key] = request.candidate
        self.requests[claim_key] = WorkflowTransportRouteSnapshotIdempotencyRecord(
            request.request_fingerprint, request.candidate
        )
        return WorkflowTransportRouteSnapshotResult(
            WorkflowTransportRouteSnapshotStatus.SNAPSHOTTED,
            request.candidate,
        )


def route_fixture(
    *,
    route_id: str = "transport-route.workflow-events.primary",
    revision: str = "7",
    scope: WorkflowScope = SCOPE,
    active: bool = True,
    minimum_tls_version: str = "1.3",
    proxy_mode: str = "prohibited",
) -> DeploymentEventTransportRoute:
    values: dict[str, object] = {
        "route_id": route_id,
        "route_revision": revision,
        "route_set_id": "transport-route-set.workflow-events",
        "route_set_revision": "11",
        "selection_epoch_id": "selection-epoch.workflow-events",
        "selection_epoch_revision": "6",
        "deployment_release_id": "atlas-release.2026.08.14",
        "deployment_profile": "lab",
        "scope": scope,
        "transport_profile_id": "transport-profile.workflow-events.primary",
        "transport_profile_revision": "17",
        "transport_resource_id": "transport-resource.workflow-events.primary",
        "transport_resource_digest": "1" * 64,
        "transport_implementation_id": "transport.nats-jetstream",
        "transport_implementation_version": "2.11",
        "adapter_contract_id": "adapter-contract.workflow-events",
        "adapter_contract_version": "1.0",
        "adapter_contract_digest": "2" * 64,
        "route_kind": "message-broker",
        "endpoint_set_id": "endpoint-set.workflow-events.primary",
        "endpoint_set_revision": "4",
        "destination_id": "destination.workflow-dispatch.internal",
        "destination_revision": "9",
        "routing_contract_id": "routing-contract.workflow-run",
        "routing_contract_revision": "3",
        "private_route_descriptor_commitment": "6" * 64,
        "transport_security_policy_id": "security-policy.workflow-events",
        "transport_security_policy_version": "2.0",
        "transport_security_policy_digest": "3" * 64,
        "minimum_tls_version": minimum_tls_version,
        "server_authentication_required": True,
        "client_authentication_required": False,
        "plaintext_fallback_prohibited": True,
        "network_policy_id": "network-policy.workflow-events.restricted",
        "network_policy_version": "5.0",
        "network_policy_digest": "4" * 64,
        "source_zone_class": "zone.workload-internal",
        "destination_zone_class": "zone.event-backbone-internal",
        "restricted_network_enforced": True,
        "public_egress_prohibited": True,
        "proxy_mode": proxy_mode,
        "credential_requirement_profile_id": "credential-requirement.workflow-publisher",
        "credential_requirement_profile_version": "7.0",
        "credential_requirement_profile_digest": "5" * 64,
        "authentication_mechanism_class": "workload-token",
        "principal_class": "service-workload",
        "active": active,
    }
    digest_payload = {
        key: value.canonical_value() if isinstance(value, WorkflowScope) else value
        for key, value in values.items()
    }
    return DeploymentEventTransportRoute(
        **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
    )


def registry_context(
    *,
    subject_id: str = "service.workflow-transport-route-registry",
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
    scope: WorkflowScope = SCOPE,
    requested_at: datetime = NOW,
) -> WorkflowTransportRouteRegistryContext:
    return WorkflowTransportRouteRegistryContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        correlation_id="correlation.transport-route.0001",
        decision_id="decision.transport-route.0001",
        requested_at=requested_at,
    )


def service_fixture(
    *routes: DeploymentEventTransportRoute,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowTransportRouteSnapshotService,
    InMemoryTransportRouteRegistry,
    InMemoryTransportRouteSnapshotRepository,
    CollectingAuditSink,
]:
    sink = audit or CollectingAuditSink()
    registry = InMemoryTransportRouteRegistry(*routes)
    repository = InMemoryTransportRouteSnapshotRepository(sink)
    service = WorkflowTransportRouteSnapshotService(
        transport_route_registry=registry,
        snapshot_repository=repository,
        audit_sink=sink,
    )
    return service, registry, repository, sink


async def register(
    service: WorkflowTransportRouteSnapshotService,
    route: DeploymentEventTransportRoute,
    *,
    idempotency_key: str = "transport-route-snapshot-0001",
    context: WorkflowTransportRouteRegistryContext | None = None,
    **changes: object,
) -> EventPhysicalTransportRouteSnapshot:
    values: dict[str, object] = {
        "route_id": route.route_id,
        "route_revision": route.route_revision,
        "source_route_digest": route.canonical_digest,
        "idempotency_key": idempotency_key,
        "context": context or registry_context(),
    }
    values.update(changes)
    return await service.register(**cast(Any, values))


@pytest.mark.asyncio
async def test_captures_exact_route_and_security_requirements_with_zero_authority() -> None:
    route = route_fixture()
    service, registry, repository, audit = service_fixture(route)

    snapshot = await register(service, route)

    assert service.durable is True
    assert registry.read_count == 1
    assert repository.snapshots[(route.route_id, route.route_revision)] == snapshot
    assert snapshot.source_route_digest == route.canonical_digest
    assert snapshot.endpoint_set_id == route.endpoint_set_id
    assert snapshot.destination_id == route.destination_id
    assert snapshot.routing_contract_id == route.routing_contract_id
    assert snapshot.minimum_tls_version == "1.3"
    assert snapshot.plaintext_fallback_prohibited is True
    assert snapshot.restricted_network_enforced is True
    assert snapshot.public_egress_prohibited is True
    assert snapshot.credential_requirement_profile_id == (route.credential_requirement_profile_id)
    assert snapshot.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
    assert snapshot.canonical_digest == canonical_digest(snapshot.digest_payload())
    assert not any(snapshot.authority.canonical_value().values())
    assert snapshot.grants_route_selection_authority is False
    assert snapshot.grants_route_binding_authority is False
    assert snapshot.grants_endpoint_resolution_authority is False
    assert snapshot.grants_credential_access_authority is False
    assert snapshot.grants_network_access_authority is False
    assert snapshot.grants_readiness_probe_authority is False
    assert snapshot.grants_publication_authority is False
    assert snapshot.grants_delivery_authority is False
    assert snapshot.grants_dispatch_authority is False
    assert snapshot.grants_execution_authority is False

    authorization = repository.pre_persistence_audit
    assert authorization is not None
    assert authorization.event_type == "atlas.workflow.transport-route-snapshot.authorization"
    assert authorization.outcome == "authorized"
    assert authorization.result_code == ("workflow_transport_route_snapshot_persistence_authorized")
    assert "snapshotted" not in authorization.result_code
    assert "succeeded" not in authorization.event_type
    assert audit.records == [authorization]

    assert set(inspect.signature(service.register).parameters) == {
        "route_id",
        "route_revision",
        "source_route_digest",
        "idempotency_key",
        "context",
    }


@pytest.mark.asyncio
async def test_exact_replay_changed_request_and_competing_identity_fail_closed() -> None:
    first_route = route_fixture()
    second_route = route_fixture(route_id="transport-route.workflow-events.secondary", revision="2")
    service, _, repository, audit = service_fixture(first_route, second_route)
    first = await register(service, first_route)
    replay = await register(
        service,
        first_route,
        context=registry_context(requested_at=NOW + timedelta(seconds=10)),
    )
    assert replay == first
    assert audit.records[-1].result_code == "workflow_transport_route_snapshot_replayed"

    with pytest.raises(WorkflowTransportRouteSnapshotError) as changed:
        await register(service, second_route)
    assert changed.value.code == "workflow_transport_route_snapshot_idempotency_conflict"

    with pytest.raises(WorkflowTransportRouteSnapshotError) as competing:
        await register(
            service,
            first_route,
            idempotency_key="transport-route-snapshot-secondary",
            context=registry_context(
                subject_id="service.workflow-transport-route-registry.secondary"
            ),
        )
    assert competing.value.code == "workflow_transport_route_snapshot_competing_identity"
    assert len(repository.snapshots) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context",
    [
        registry_context(
            subject_id="user.operator",
            actor_type="human",
            authentication_method="password",
            audience="audience.browser",
        ),
        registry_context(audience="audience.workflow-transport-profile-registry"),
    ],
)
async def test_only_dedicated_route_registry_workload_can_create(
    context: WorkflowTransportRouteRegistryContext,
) -> None:
    route = route_fixture()
    service, registry, repository, _ = service_fixture(route)
    with pytest.raises(WorkflowTransportRouteSnapshotError) as denied:
        await register(service, route, context=context)
    assert denied.value.code == "workflow_transport_route_snapshot_registry_identity_required"
    assert registry.read_count == 0
    assert repository.snapshots == {}


@pytest.mark.asyncio
async def test_inactive_drifted_and_wrong_scope_sources_fail_closed() -> None:
    inactive = route_fixture(active=False)
    service, _, repository, _ = service_fixture(inactive)
    with pytest.raises(WorkflowTransportRouteSnapshotError) as inactive_error:
        await register(service, inactive)
    assert inactive_error.value.code == "workflow_transport_route_snapshot_source_not_active"
    assert repository.snapshots == {}

    route = route_fixture()
    service, _, repository, _ = service_fixture(route)
    with pytest.raises(WorkflowTransportRouteSnapshotError) as drift:
        await register(service, route, source_route_digest="f" * 64)
    assert drift.value.code == "workflow_transport_route_snapshot_source_conflict"
    assert repository.snapshots == {}

    original_digest = route.canonical_digest
    object.__setattr__(route, "canonical_digest", "e" * 64)
    with pytest.raises(WorkflowTransportRouteSnapshotError) as internal_drift:
        await register(service, route, source_route_digest="e" * 64)
    assert internal_drift.value.code == "workflow_transport_route_snapshot_source_conflict"
    object.__setattr__(route, "canonical_digest", original_digest)

    other_scope = WorkflowScope("org-atlas", "environment-lab", "site-ankara")
    wrong_scope = route_fixture(scope=other_scope)
    service, _, repository, _ = service_fixture(wrong_scope)
    with pytest.raises(WorkflowTransportRouteSnapshotError) as scope_error:
        await register(service, wrong_scope)
    assert scope_error.value.code == "workflow_transport_route_snapshot_source_conflict"
    assert repository.snapshots == {}


@pytest.mark.asyncio
async def test_required_pre_persistence_audit_failure_creates_no_state() -> None:
    route = route_fixture()
    failing_audit = CollectingAuditSink(fail=True)
    service, _, repository, _ = service_fixture(route, audit=failing_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await register(service, route)
    assert repository.snapshots == {}
    assert repository.requests == {}


def test_domain_rejects_insecure_requirements_and_nonzero_authority() -> None:
    route = route_fixture()
    with pytest.raises(ValueError, match="minimum TLS version is unsupported"):
        route_fixture(minimum_tls_version="1.0")
    with pytest.raises(ValueError, match="proxy mode is unsupported"):
        route_fixture(proxy_mode="caller-supplied")
    with pytest.raises(ValueError, match="cannot grant operational authority"):
        EventPhysicalTransportRouteSnapshotAuthority(network_access_authorized=True)
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(route, endpoint_set_revision="changed")


def test_route_snapshot_exposes_only_opaque_references_and_no_operational_surface() -> None:
    required = {
        "route_set_id",
        "route_set_revision",
        "selection_epoch_id",
        "selection_epoch_revision",
        "endpoint_set_id",
        "endpoint_set_revision",
        "destination_id",
        "destination_revision",
        "routing_contract_id",
        "routing_contract_revision",
        "private_route_descriptor_commitment",
        "transport_security_policy_id",
        "transport_security_policy_digest",
        "network_policy_id",
        "network_policy_digest",
        "source_zone_class",
        "destination_zone_class",
        "credential_requirement_profile_id",
        "credential_requirement_profile_version",
        "credential_requirement_profile_digest",
    }
    forbidden = {
        "endpoint_set_digest",
        "destination_digest",
        "routing_contract_digest",
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
        "credential_assignment_id",
        "credential_id",
        "secret_reference",
        "vault_path",
        "certificate_reference",
        "network_health",
        "ready",
        "provider_message_id",
        "publication_attempt",
        "receipt",
        "acknowledgement",
        "offset",
        "workflow_compatibility_admission_id",
        "logical_channel_binding_id",
    }
    names = {field.name for field in fields(EventPhysicalTransportRouteSnapshot)}
    assert required.issubset(names)
    assert forbidden.isdisjoint(names)
