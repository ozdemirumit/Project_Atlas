from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
    WorkflowTransportCredentialAssignmentRegistryContext,
    WorkflowTransportCredentialAssignmentSnapshotError,
    WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord,
    WorkflowTransportCredentialAssignmentSnapshotRequest,
    WorkflowTransportCredentialAssignmentSnapshotResult,
    WorkflowTransportCredentialAssignmentSnapshotService,
    WorkflowTransportCredentialAssignmentSnapshotStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRoute,
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportCredentialAssignmentSnapshotAuthority,
    EventPhysicalTransportCredentialAssignmentSnapshotState,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotAuthority,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowScope,
    canonical_digest,
)

NOW = datetime.now(UTC)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")


class CollectingAuditSink:
    def __init__(self, *, fail_kind: str | None = None) -> None:
        self.records: list[AuditRecord] = []
        self.fail_kind = fail_kind

    async def record(self, event: AuditRecord) -> None:
        if self.fail_kind is not None and event.event_type.endswith(f".{self.fail_kind}"):
            raise RuntimeError("audit unavailable")
        self.records.append(event)


class InMemoryCredentialAssignmentRegistry:
    def __init__(self, *assignments: DeploymentPhysicalTransportCredentialAssignment) -> None:
        self.assignments = {
            (assignment.assignment_id, assignment.assignment_revision): assignment
            for assignment in assignments
        }
        self.read_count = 0

    @property
    def durable(self) -> bool:
        return True

    async def get_active_credential_assignment(
        self,
        *,
        assignment_id: str,
        assignment_revision: str,
    ) -> DeploymentPhysicalTransportCredentialAssignment | None:
        self.read_count += 1
        return self.assignments.get((assignment_id, assignment_revision))


class InMemoryRouteSnapshotReader:
    def __init__(self, *routes: EventPhysicalTransportRouteSnapshot) -> None:
        self.routes = {(route.route_id, route.route_revision): route for route in routes}
        self.read_count = 0

    @property
    def durable(self) -> bool:
        return True

    async def get_transport_route_snapshot(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> EventPhysicalTransportRouteSnapshot | None:
        self.read_count += 1
        return self.routes.get((route_id, route_revision))


class InMemoryCredentialAssignmentSnapshotRepository:
    def __init__(self, audit: CollectingAuditSink) -> None:
        self.audit = audit
        self.snapshots: dict[
            tuple[str, str], EventPhysicalTransportCredentialAssignmentSnapshot
        ] = {}
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord,
        ] = {}
        self.events_before_write: tuple[str, ...] = ()

    @property
    def durable(self) -> bool:
        return True

    async def get_credential_assignment_snapshot(
        self,
        *,
        assignment_id: str,
        assignment_revision: str,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot | None:
        return self.snapshots.get((assignment_id, assignment_revision))

    async def list_credential_assignment_snapshots(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[EventPhysicalTransportCredentialAssignmentSnapshot, ...]:
        return tuple(
            sorted(
                (snapshot for snapshot in self.snapshots.values() if snapshot.scope == scope),
                key=lambda value: (value.assignment_id, value.assignment_revision),
            )[:limit]
        )

    async def get_credential_assignment_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord | None:
        return self.requests.get((scope, snapshotter_subject_id, idempotency_key))

    async def snapshot_credential_assignment(
        self,
        request: WorkflowTransportCredentialAssignmentSnapshotRequest,
    ) -> WorkflowTransportCredentialAssignmentSnapshotResult:
        claim_key = (request.scope, request.snapshotter_subject_id, request.idempotency_key)
        prior = self.requests.get(claim_key)
        if prior is not None:
            status = (
                WorkflowTransportCredentialAssignmentSnapshotStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowTransportCredentialAssignmentSnapshotStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowTransportCredentialAssignmentSnapshotResult(status, prior.snapshot)
        source_key = (
            request.expected_source_assignment_id,
            request.expected_source_assignment_revision,
        )
        current = self.snapshots.get(source_key)
        if current is not None:
            return WorkflowTransportCredentialAssignmentSnapshotResult(
                WorkflowTransportCredentialAssignmentSnapshotStatus.ALREADY_SNAPSHOTTED,
                current,
            )
        if request.candidate.source_assignment_digest != request.expected_source_assignment_digest:
            return WorkflowTransportCredentialAssignmentSnapshotResult(
                WorkflowTransportCredentialAssignmentSnapshotStatus.SOURCE_CONFLICT,
                None,
            )
        self.events_before_write = tuple(record.event_type for record in self.audit.records)
        await request.required_precommit_audit()
        self.snapshots[source_key] = request.candidate
        self.requests[claim_key] = WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord(
            request.request_fingerprint, request.candidate
        )
        return WorkflowTransportCredentialAssignmentSnapshotResult(
            WorkflowTransportCredentialAssignmentSnapshotStatus.SNAPSHOTTED,
            request.candidate,
        )


def route_fixture() -> EventPhysicalTransportRouteSnapshot:
    route_values: dict[str, object] = {
        "route_id": "transport-route.workflow-events.primary",
        "route_revision": "7",
        "route_set_id": "transport-route-set.workflow-events",
        "route_set_revision": "11",
        "selection_epoch_id": "selection-epoch.workflow-events",
        "selection_epoch_revision": "6",
        "deployment_release_id": "atlas-release.2026.08.15",
        "deployment_profile": "lab",
        "scope": SCOPE,
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
        "minimum_tls_version": "1.3",
        "server_authentication_required": True,
        "client_authentication_required": True,
        "plaintext_fallback_prohibited": True,
        "network_policy_id": "network-policy.workflow-events.restricted",
        "network_policy_version": "5.0",
        "network_policy_digest": "4" * 64,
        "source_zone_class": "zone.workload-internal",
        "destination_zone_class": "zone.event-backbone-internal",
        "restricted_network_enforced": True,
        "public_egress_prohibited": True,
        "proxy_mode": "prohibited",
        "credential_requirement_profile_id": "credential-requirement.workflow-publisher",
        "credential_requirement_profile_version": "7.0",
        "credential_requirement_profile_digest": "5" * 64,
        "authentication_mechanism_class": "mutual-tls",
        "principal_class": "service-workload",
        "active": True,
    }
    route_payload = {
        key: value.canonical_value() if isinstance(value, WorkflowScope) else value
        for key, value in route_values.items()
    }
    route = DeploymentEventTransportRoute(
        **cast(Any, route_values), canonical_digest=canonical_digest(route_payload)
    )
    authority = EventPhysicalTransportRouteSnapshotAuthority()
    snapshot_values: dict[str, object] = {
        field.name: getattr(route, field.name)
        for field in fields(EventPhysicalTransportRouteSnapshot)
        if hasattr(route, field.name) and field.name != "canonical_digest"
    }
    snapshot_values.update(
        {
            "snapshot_id": "event-physical-transport-route-snapshot.test-primary",
            "source_route_digest": route.canonical_digest,
            "snapshotter_subject_id": "service.workflow-transport-route-registry",
            "captured_at": NOW - timedelta(days=1),
            "state": EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED,
            "authority": authority,
        }
    )
    digest_payload = {
        key: value.canonical_value()
        if isinstance(value, (WorkflowScope, EventPhysicalTransportRouteSnapshotAuthority))
        else value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if isinstance(value, EventPhysicalTransportRouteSnapshotState)
        else value
        for key, value in snapshot_values.items()
    }
    return EventPhysicalTransportRouteSnapshot(
        **cast(Any, snapshot_values), canonical_digest=canonical_digest(digest_payload)
    )


def assignment_fixture(
    *,
    assignment_id: str = "credential-assignment.workflow-events.primary",
    assignment_revision: str = "13",
    scope: WorkflowScope = SCOPE,
    route: EventPhysicalTransportRouteSnapshot | None = None,
    active: bool = True,
    revoked: bool = False,
    credential_generation: int = 23,
    rotation_epoch: int = 8,
    activated_at: datetime = NOW - timedelta(days=10),
    expires_at: datetime = NOW + timedelta(days=20),
) -> DeploymentPhysicalTransportCredentialAssignment:
    compatible_route = route or route_fixture()
    values: dict[str, object] = {
        "assignment_id": assignment_id,
        "assignment_revision": assignment_revision,
        "scope": scope,
        "route_id": compatible_route.route_id,
        "route_revision": compatible_route.route_revision,
        "source_route_digest": compatible_route.source_route_digest,
        "credential_requirement_profile_id": (compatible_route.credential_requirement_profile_id),
        "credential_requirement_profile_version": (
            compatible_route.credential_requirement_profile_version
        ),
        "credential_requirement_profile_digest": (
            compatible_route.credential_requirement_profile_digest
        ),
        "credential_profile_id": "credential-profile.workflow-publisher.primary",
        "credential_profile_version": "9",
        "credential_profile_digest": "7" * 64,
        "authentication_mechanism_class": compatible_route.authentication_mechanism_class,
        "principal_class": compatible_route.principal_class,
        "privilege_class": "read-only",
        "target_scope_commitment": "8" * 64,
        "credential_generation": credential_generation,
        "rotation_epoch": rotation_epoch,
        "activated_at": activated_at,
        "expires_at": expires_at,
        "revoked": revoked,
        "active": active,
        "broker_policy_id": "broker-policy.workflow-events",
        "broker_policy_version": "3",
        "broker_policy_digest": "9" * 64,
    }
    payload = {
        key: value.canonical_value()
        if isinstance(value, WorkflowScope)
        else value.isoformat()
        if isinstance(value, datetime)
        else value
        for key, value in values.items()
    }
    return DeploymentPhysicalTransportCredentialAssignment(
        **cast(Any, values), canonical_digest=canonical_digest(payload)
    )


def registry_context(
    *,
    subject_id: str = WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,
    scope: WorkflowScope = SCOPE,
    requested_at: datetime = NOW,
) -> WorkflowTransportCredentialAssignmentRegistryContext:
    return WorkflowTransportCredentialAssignmentRegistryContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        correlation_id="correlation.credential-assignment.0001",
        decision_id="decision.credential-assignment.0001",
        requested_at=requested_at,
    )


def service_fixture(
    assignment: DeploymentPhysicalTransportCredentialAssignment,
    route: EventPhysicalTransportRouteSnapshot,
    *,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowTransportCredentialAssignmentSnapshotService,
    InMemoryCredentialAssignmentRegistry,
    InMemoryRouteSnapshotReader,
    InMemoryCredentialAssignmentSnapshotRepository,
    CollectingAuditSink,
]:
    sink = audit or CollectingAuditSink()
    registry = InMemoryCredentialAssignmentRegistry(assignment)
    routes = InMemoryRouteSnapshotReader(route)
    repository = InMemoryCredentialAssignmentSnapshotRepository(sink)
    service = WorkflowTransportCredentialAssignmentSnapshotService(
        credential_assignment_registry=registry,
        route_snapshot_reader=routes,
        snapshot_repository=repository,
        audit_sink=sink,
    )
    return service, registry, routes, repository, sink


async def register(
    service: WorkflowTransportCredentialAssignmentSnapshotService,
    assignment: DeploymentPhysicalTransportCredentialAssignment,
    **changes: object,
) -> EventPhysicalTransportCredentialAssignmentSnapshot:
    values: dict[str, object] = {
        "assignment_id": assignment.assignment_id,
        "assignment_revision": assignment.assignment_revision,
        "source_assignment_digest": assignment.canonical_digest,
        "idempotency_key": "credential-assignment-snapshot-0001",
        "context": registry_context(),
    }
    values.update(changes)
    return await service.register(**cast(Any, values))


@pytest.mark.asyncio
async def test_captures_compatible_assignment_with_zero_authority_and_required_audit() -> None:
    route = route_fixture()
    assignment = assignment_fixture(route=route)
    service, registry, routes, repository, audit = service_fixture(assignment, route)

    snapshot = await register(service, assignment)

    assert service.durable is True
    assert registry.read_count == 1
    assert routes.read_count == 1
    assert repository.snapshots[(assignment.assignment_id, assignment.assignment_revision)] == (
        snapshot
    )
    assert snapshot.route_snapshot_id == route.snapshot_id
    assert snapshot.source_assignment_digest == assignment.canonical_digest
    assert snapshot.credential_generation == 23
    assert snapshot.rotation_epoch == 8
    assert snapshot.source_non_revoked is True
    assert snapshot.state is EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED
    assert snapshot.canonical_digest == canonical_digest(snapshot.digest_payload())
    assert not any(snapshot.authority.canonical_value().values())
    assert all(
        not getattr(snapshot, name)
        for name in (
            "grants_endpoint_resolution_authority",
            "grants_credential_access_authority",
            "grants_network_access_authority",
            "grants_readiness_probe_authority",
            "grants_publication_authority",
            "grants_delivery_authority",
            "grants_dispatch_authority",
            "grants_execution_authority",
        )
    )
    assert repository.events_before_write == (
        "atlas.workflow.transport-credential-assignment-snapshot.intent",
    )
    assert [record.event_type.rsplit(".", 1)[-1] for record in audit.records] == [
        "intent",
        "commit-authorization",
        "completion",
    ]
    metadata = dict(audit.records[-1].target_metadata)
    assert metadata["credential_access_authority"] == "false"
    assert "credential_profile_id" not in metadata
    assert "broker_policy_id" not in metadata
    assert set(inspect.signature(service.register).parameters) == {
        "assignment_id",
        "assignment_revision",
        "source_assignment_digest",
        "idempotency_key",
        "context",
    }


@pytest.mark.asyncio
async def test_exact_replay_and_changed_idempotent_request_fail_closed() -> None:
    route = route_fixture()
    assignment = assignment_fixture(route=route)
    service, registry, routes, repository, audit = service_fixture(assignment, route)
    first = await register(service, assignment)
    registry.assignments.clear()
    routes.routes.clear()
    replay = await register(
        service,
        assignment,
        context=registry_context(requested_at=NOW + timedelta(seconds=1)),
    )
    assert replay == first
    assert len(repository.snapshots) == 1
    assert registry.read_count == 1
    assert routes.read_count == 1
    assert audit.records[-1].result_code == (
        "workflow_transport_credential_assignment_snapshot_replayed"
    )

    claim_key = (
        SCOPE,
        WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
        "credential-assignment-snapshot-0001",
    )
    repository.requests[claim_key] = WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord(
        "f" * 64, first
    )
    with pytest.raises(WorkflowTransportCredentialAssignmentSnapshotError) as conflict:
        await register(service, assignment)
    assert conflict.value.code == (
        "workflow_transport_credential_assignment_snapshot_idempotency_conflict"
    )


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
        registry_context(subject_id="service.another-registry"),
        registry_context(audience="audience.workflow-transport-route-registry"),
    ],
)
async def test_only_exact_registry_workload_can_create(
    context: WorkflowTransportCredentialAssignmentRegistryContext,
) -> None:
    route = route_fixture()
    assignment = assignment_fixture(route=route)
    service, registry, routes, repository, _ = service_fixture(assignment, route)
    with pytest.raises(WorkflowTransportCredentialAssignmentSnapshotError) as denied:
        await register(service, assignment, context=context)
    assert denied.value.code == (
        "workflow_transport_credential_assignment_snapshot_registry_identity_required"
    )
    assert registry.read_count == 0
    assert routes.read_count == 0
    assert repository.snapshots == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "assignment",
    [
        assignment_fixture(active=False),
        assignment_fixture(revoked=True),
        assignment_fixture(expires_at=NOW),
        assignment_fixture(activated_at=NOW + timedelta(seconds=1)),
        assignment_fixture(scope=WorkflowScope("org-atlas", "environment-lab", "site-ankara")),
    ],
)
async def test_inactive_expired_revoked_future_and_wrong_scope_sources_fail_closed(
    assignment: DeploymentPhysicalTransportCredentialAssignment,
) -> None:
    route = route_fixture()
    service, _, _, repository, _ = service_fixture(assignment, route)
    with pytest.raises(WorkflowTransportCredentialAssignmentSnapshotError) as denied:
        await register(service, assignment)
    assert denied.value.code == (
        "workflow_transport_credential_assignment_snapshot_source_conflict"
    )
    assert repository.snapshots == {}


@pytest.mark.asyncio
async def test_route_requirement_mechanism_and_source_digest_mismatch_fail_closed() -> None:
    route = route_fixture()
    assignment = assignment_fixture(route=route)
    incompatible_route = route
    object.__setattr__(
        incompatible_route,
        "credential_requirement_profile_id",
        "credential-requirement.other",
    )
    object.__setattr__(
        incompatible_route,
        "canonical_digest",
        canonical_digest(incompatible_route.digest_payload()),
    )
    service, _, _, repository, _ = service_fixture(assignment, incompatible_route)
    with pytest.raises(WorkflowTransportCredentialAssignmentSnapshotError) as denied:
        await register(service, assignment)
    assert denied.value.code == (
        "workflow_transport_credential_assignment_snapshot_route_incompatible"
    )
    assert repository.snapshots == {}


@pytest.mark.asyncio
async def test_intent_or_precommit_audit_failure_creates_no_state() -> None:
    route = route_fixture()
    assignment = assignment_fixture(route=route)
    for fail_kind in ("intent", "commit-authorization"):
        audit = CollectingAuditSink(fail_kind=fail_kind)
        service, _, _, repository, _ = service_fixture(assignment, route, audit=audit)
        with pytest.raises((RuntimeError, WorkflowTransportCredentialAssignmentSnapshotError)):
            await register(service, assignment)
        assert repository.snapshots == {}
        assert repository.requests == {}


@pytest.mark.asyncio
async def test_completion_audit_failure_preserves_committed_snapshot_for_safe_replay() -> None:
    route = route_fixture()
    assignment = assignment_fixture(route=route)
    audit = CollectingAuditSink(fail_kind="completion")
    service, registry, routes, repository, _ = service_fixture(assignment, route, audit=audit)

    with pytest.raises(WorkflowTransportCredentialAssignmentSnapshotError) as uncertain:
        await register(service, assignment)
    assert uncertain.value.code == (
        "workflow_transport_credential_assignment_snapshot_completion_audit_outcome_uncertain"
    )
    assert len(repository.snapshots) == 1
    assert len(repository.requests) == 1

    audit.fail_kind = None
    registry.assignments.clear()
    routes.routes.clear()
    replay = await register(
        service,
        assignment,
        context=registry_context(requested_at=NOW + timedelta(seconds=1)),
    )
    assert replay == next(iter(repository.snapshots.values()))
    assert audit.records[-1].result_code == (
        "workflow_transport_credential_assignment_snapshot_replayed"
    )


def test_domain_rejects_privilege_escalation_authority_and_secret_surface() -> None:
    route = route_fixture()
    with pytest.raises(ValueError, match="least privilege"):
        assignment = assignment_fixture(route=route)
        replace(assignment, privilege_class="administrator")
    with pytest.raises(ValueError, match="cannot grant operational authority"):
        EventPhysicalTransportCredentialAssignmentSnapshotAuthority(
            credential_access_authorized=True
        )

    assignment_fields = {
        field.name for field in fields(DeploymentPhysicalTransportCredentialAssignment)
    }
    snapshot_fields = {
        field.name for field in fields(EventPhysicalTransportCredentialAssignmentSnapshot)
    }
    forbidden = {
        "password",
        "token",
        "secret",
        "secret_reference",
        "vault_path",
        "secret_store",
        "username",
        "private_key",
        "certificate",
        "endpoint",
        "hostname",
        "url",
        "ip_address",
        "workflow_id",
        "materialization_id",
        "protected_artifact_id",
    }
    assert forbidden.isdisjoint(assignment_fields)
    assert forbidden.isdisjoint(snapshot_fields)
