from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
    WorkflowPhysicalTransportCredentialBinderContext,
    WorkflowTransportCredentialAssignmentBindingError,
    WorkflowTransportCredentialAssignmentBindingIdempotencyRecord,
    WorkflowTransportCredentialAssignmentBindingRequest,
    WorkflowTransportCredentialAssignmentBindingResult,
    WorkflowTransportCredentialAssignmentBindingStatus,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportCredentialAssignmentSnapshotState,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingPolicy,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingState,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_assignment_binding_policy,
)

NOW = datetime(2026, 8, 15, 17, 0, tzinfo=UTC)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")


class ZeroAuthority:
    def canonical_value(self) -> dict[str, bool]:
        return {"operational_authorized": False}


class Evidence:
    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)
        self.seal()

    def __getattr__(self, name: str) -> Any:
        return self.__dict__[name]

    def __setattr__(self, name: str, value: Any) -> None:
        self.__dict__[name] = value

    def digest_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        for name, value in self.__dict__.items():
            if name == "canonical_digest":
                continue
            if isinstance(value, WorkflowScope):
                payload[name] = value.canonical_value()
            elif isinstance(value, StrEnum):
                payload[name] = value.value
            elif isinstance(value, ZeroAuthority):
                payload[name] = value.canonical_value()
            else:
                payload[name] = value
        return payload

    def seal(self) -> None:
        self.canonical_digest = canonical_digest(self.digest_payload())


def evidence_chain(
    *,
    generation: int = 1,
    rotation_epoch: int = 1,
) -> tuple[
    WorkflowEventPhysicalTransportRouteBinding,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportCredentialAssignmentSnapshot,
]:
    authority = ZeroAuthority()
    route = Evidence(
        snapshot_id="event-physical-transport-route-snapshot.primary",
        route_id="transport-route.workflow-events.primary",
        route_revision="7",
        source_route_digest="1" * 64,
        credential_requirement_profile_id="credential-requirement.workflow-publisher",
        credential_requirement_profile_version="7.0",
        credential_requirement_profile_digest="2" * 64,
        authentication_mechanism_class="mutual-tls",
        principal_class="service-workload",
        scope=SCOPE,
        state=EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED,
        authority=authority,
    )
    route_binding = Evidence(
        binding_id="workflow-event-physical-transport-route-binding.primary",
        transport_route_snapshot_id=route.snapshot_id,
        transport_route_snapshot_digest=route.canonical_digest,
        scope=SCOPE,
        state=WorkflowEventPhysicalTransportRouteBindingState.BOUND,
        authority=authority,
    )
    assignment = Evidence(
        snapshot_id=(
            f"event-physical-transport-credential-assignment-snapshot.generation-{generation}"
        ),
        route_snapshot_id=route.snapshot_id,
        route_id=route.route_id,
        route_revision=route.route_revision,
        source_route_digest=route.source_route_digest,
        credential_requirement_profile_id=route.credential_requirement_profile_id,
        credential_requirement_profile_version=route.credential_requirement_profile_version,
        credential_requirement_profile_digest=route.credential_requirement_profile_digest,
        authentication_mechanism_class=route.authentication_mechanism_class,
        principal_class=route.principal_class,
        privilege_class="read-only",
        credential_generation=generation,
        rotation_epoch=rotation_epoch,
        scope=SCOPE,
        state=EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED,
        authority=authority,
    )
    return (
        cast(WorkflowEventPhysicalTransportRouteBinding, route_binding),
        cast(EventPhysicalTransportRouteSnapshot, route),
        cast(EventPhysicalTransportCredentialAssignmentSnapshot, assignment),
    )


class CollectingAuditSink:
    def __init__(self, *, fail_kind: str | None = None, fail_all: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail_kind = fail_kind
        self.fail_all = fail_all

    async def record(self, event: AuditRecord) -> None:
        if self.fail_all or (
            self.fail_kind is not None and event.event_type.endswith(f".{self.fail_kind}")
        ):
            raise RuntimeError("audit unavailable")
        self.records.append(event)


class InMemoryBindingRepository:
    def __init__(
        self,
        route_binding: WorkflowEventPhysicalTransportRouteBinding,
        route: EventPhysicalTransportRouteSnapshot,
        *assignments: EventPhysicalTransportCredentialAssignmentSnapshot,
        audit: CollectingAuditSink,
    ) -> None:
        self.route_bindings = {route_binding.binding_id: route_binding}
        self.routes = {route.snapshot_id: route}
        self.assignments = {assignment.snapshot_id: assignment for assignment in assignments}
        self.bindings: dict[
            tuple[str, str],
            WorkflowEventPhysicalTransportCredentialAssignmentBinding,
        ] = {}
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowTransportCredentialAssignmentBindingIdempotencyRecord,
        ] = {}
        self.audit = audit
        self.source_read_count = 0
        self.events_before_write: tuple[str, ...] = ()

    @property
    def durable(self) -> bool:
        return True

    async def get_physical_transport_route_binding_by_id(
        self,
        *,
        binding_id: str,
    ) -> WorkflowEventPhysicalTransportRouteBinding | None:
        self.source_read_count += 1
        return self.route_bindings.get(binding_id)

    async def get_transport_route_snapshot_by_id(
        self,
        *,
        snapshot_id: str,
    ) -> EventPhysicalTransportRouteSnapshot | None:
        self.source_read_count += 1
        return self.routes.get(snapshot_id)

    async def get_credential_assignment_snapshot_by_id(
        self,
        *,
        snapshot_id: str,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot | None:
        self.source_read_count += 1
        return self.assignments.get(snapshot_id)

    async def get_credential_assignment_binding(
        self,
        *,
        physical_transport_route_binding_id: str,
        credential_assignment_snapshot_id: str,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding | None:
        return self.bindings.get(
            (physical_transport_route_binding_id, credential_assignment_snapshot_id)
        )

    async def list_credential_assignment_bindings(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAssignmentBinding, ...]:
        return tuple(
            sorted(
                (binding for binding in self.bindings.values() if binding.scope == scope),
                key=lambda value: value.binding_id,
            )[:limit]
        )

    async def get_credential_assignment_binding_request(
        self,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportCredentialAssignmentBindingIdempotencyRecord | None:
        return self.requests.get((scope, binder_subject_id, idempotency_key))

    async def bind_credential_assignment(
        self,
        request: WorkflowTransportCredentialAssignmentBindingRequest,
    ) -> WorkflowTransportCredentialAssignmentBindingResult:
        claim_key = (request.scope, request.binder_subject_id, request.idempotency_key)
        prior = self.requests.get(claim_key)
        if prior is not None:
            status = (
                WorkflowTransportCredentialAssignmentBindingStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowTransportCredentialAssignmentBindingStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowTransportCredentialAssignmentBindingResult(status, prior.binding)
        pair = (
            request.expected_physical_transport_route_binding_id,
            request.expected_credential_assignment_snapshot_id,
        )
        current = self.bindings.get(pair)
        if current is not None:
            return WorkflowTransportCredentialAssignmentBindingResult(
                WorkflowTransportCredentialAssignmentBindingStatus.ALREADY_BOUND,
                current,
            )
        source_digests = (
            self.route_bindings[
                request.expected_physical_transport_route_binding_id
            ].canonical_digest,
            self.routes[request.expected_transport_route_snapshot_id].canonical_digest,
            self.assignments[request.expected_credential_assignment_snapshot_id].canonical_digest,
        )
        if source_digests != (
            request.expected_physical_transport_route_binding_digest,
            request.expected_transport_route_snapshot_digest,
            request.expected_credential_assignment_snapshot_digest,
        ):
            return WorkflowTransportCredentialAssignmentBindingResult(
                WorkflowTransportCredentialAssignmentBindingStatus.EVIDENCE_CONFLICT,
                None,
            )
        try:
            await request.required_precommit_audit()
        except Exception:
            return WorkflowTransportCredentialAssignmentBindingResult(
                WorkflowTransportCredentialAssignmentBindingStatus.PRECOMMIT_AUDIT_FAILED,
                None,
            )
        self.events_before_write = tuple(record.event_type for record in self.audit.records)
        self.bindings[pair] = request.candidate
        self.requests[claim_key] = WorkflowTransportCredentialAssignmentBindingIdempotencyRecord(
            request.request_fingerprint,
            request.candidate,
        )
        return WorkflowTransportCredentialAssignmentBindingResult(
            WorkflowTransportCredentialAssignmentBindingStatus.BOUND,
            request.candidate,
        )


def context(
    *,
    subject_id: str = "service.workflow-physical-transport-credential-binder",
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE,
) -> WorkflowPhysicalTransportCredentialBinderContext:
    return WorkflowPhysicalTransportCredentialBinderContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=SCOPE,
        correlation_id="correlation.imp-204",
        decision_id="decision.imp-204",
        requested_at=NOW,
    )


def service_fixture(
    *,
    audit: CollectingAuditSink | None = None,
    assignments: tuple[EventPhysicalTransportCredentialAssignmentSnapshot, ...] | None = None,
) -> tuple[
    WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
    InMemoryBindingRepository,
    WorkflowEventPhysicalTransportRouteBinding,
    EventPhysicalTransportRouteSnapshot,
    tuple[EventPhysicalTransportCredentialAssignmentSnapshot, ...],
    CollectingAuditSink,
]:
    route_binding, route, first = evidence_chain()
    selected = assignments or (first,)
    sink = audit or CollectingAuditSink()
    repository = InMemoryBindingRepository(
        route_binding,
        route,
        *selected,
        audit=sink,
    )
    return (
        WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
            binding_repository=repository,
            audit_sink=sink,
        ),
        repository,
        route_binding,
        route,
        selected,
        sink,
    )


async def bind(
    service: WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
    route_binding: WorkflowEventPhysicalTransportRouteBinding,
    assignment: EventPhysicalTransportCredentialAssignmentSnapshot,
    *,
    idempotency_key: str = "credential-binding-request-0001",
    binder_context: WorkflowPhysicalTransportCredentialBinderContext | None = None,
) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding:
    policy = service.policy
    return await service.bind(
        physical_transport_route_binding_id=route_binding.binding_id,
        physical_transport_route_binding_digest=route_binding.canonical_digest,
        credential_assignment_snapshot_id=assignment.snapshot_id,
        credential_assignment_snapshot_digest=assignment.canonical_digest,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_digest=policy.canonical_digest,
        idempotency_key=idempotency_key,
        context=binder_context or context(),
    )


@pytest.mark.asyncio
async def test_binding_is_minimized_zero_authority_and_audited_around_commit() -> None:
    service, repository, route_binding, route, assignments, audit = service_fixture()

    binding = await bind(service, route_binding, assignments[0])

    assert binding.state is WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND
    assert binding.transport_route_snapshot_id == route.snapshot_id
    assert not any(binding.authority.canonical_value().values())
    assert canonical_digest(binding.digest_payload()) == binding.canonical_digest
    assert repository.events_before_write[-2:] == (
        "atlas.workflow.physical-transport-credential-assignment-binding.intent",
        "atlas.workflow.physical-transport-credential-assignment-binding.commit-authorization",
    )
    assert audit.records[-1].event_type.endswith(".completion")
    field_names = {field.name for field in fields(type(binding))}
    forbidden = {
        "secret",
        "password",
        "token",
        "key",
        "certificate",
        "endpoint",
        "artifact",
        "target_scope_commitment",
        "broker_policy_id",
        "credential_profile_id",
    }
    assert field_names.isdisjoint(forbidden)
    assert all(
        value == "false"
        for key, value in audit.records[-1].target_metadata
        if key.endswith("authority")
    )


@pytest.mark.asyncio
async def test_exact_replay_uses_history_before_removed_sources() -> None:
    service, repository, route_binding, _, assignments, audit = service_fixture()
    first = await bind(service, route_binding, assignments[0])
    repository.route_bindings.clear()
    repository.routes.clear()
    repository.assignments.clear()
    reads_before_replay = repository.source_read_count

    replay = await bind(service, route_binding, assignments[0])

    assert replay == first
    assert repository.source_read_count == reads_before_replay
    assert audit.records[-1].event_type.endswith(".replay")
    metadata = dict(audit.records[-1].target_metadata)
    assert metadata["physical_transport_route_binding_id"] == route_binding.binding_id
    assert metadata["credential_assignment_snapshot_id"] == assignments[0].snapshot_id


@pytest.mark.asyncio
async def test_exact_replay_survives_code_owned_policy_rotation() -> None:
    service, repository, route_binding, _, assignments, audit = service_fixture()
    original_policy = service.policy
    first = await bind(service, route_binding, assignments[0])
    rotated_values = {
        **original_policy.digest_payload(),
        "policy_version": "2.0",
    }
    rotated_policy = WorkflowEventPhysicalTransportCredentialAssignmentBindingPolicy(
        **cast(Any, rotated_values),
        canonical_digest=canonical_digest(rotated_values),
    )
    rotated_service = WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
        binding_repository=repository,
        audit_sink=audit,
        policy=rotated_policy,
    )
    repository.route_bindings.clear()
    repository.routes.clear()
    repository.assignments.clear()
    reads_before_replay = repository.source_read_count

    replay = await rotated_service.bind(
        physical_transport_route_binding_id=route_binding.binding_id,
        physical_transport_route_binding_digest=route_binding.canonical_digest,
        credential_assignment_snapshot_id=assignments[0].snapshot_id,
        credential_assignment_snapshot_digest=assignments[0].canonical_digest,
        policy_id=original_policy.policy_id,
        policy_version=original_policy.policy_version,
        policy_digest=original_policy.canonical_digest,
        idempotency_key="credential-binding-request-0001",
        context=context(),
    )

    assert replay == first
    assert replay.policy_digest == original_policy.canonical_digest
    assert repository.source_read_count == reads_before_replay
    assert audit.records[-1].event_type.endswith(".replay")


@pytest.mark.asyncio
async def test_same_route_binding_accepts_multiple_historical_assignment_snapshots() -> None:
    route_binding, route, first = evidence_chain(generation=1, rotation_epoch=1)
    _, _, second = evidence_chain(generation=2, rotation_epoch=2)
    audit = CollectingAuditSink()
    repository = InMemoryBindingRepository(route_binding, route, first, second, audit=audit)
    service = WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
        binding_repository=repository,
        audit_sink=audit,
    )

    first_binding = await bind(service, route_binding, first, idempotency_key="binding-gen-0001")
    second_binding = await bind(service, route_binding, second, idempotency_key="binding-gen-0002")

    assert first_binding.binding_id != second_binding.binding_id
    assert len(repository.bindings) == 2


@pytest.mark.asyncio
async def test_exact_pair_cannot_be_rebound_with_another_request_or_identity() -> None:
    service, _, route_binding, _, assignments, _ = service_fixture()
    await bind(service, route_binding, assignments[0])

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as same_subject:
        await bind(
            service,
            route_binding,
            assignments[0],
            idempotency_key="credential-binding-request-0002",
        )
    assert same_subject.value.code.endswith("already_bound")

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as other_subject:
        await bind(
            service,
            route_binding,
            assignments[0],
            idempotency_key="credential-binding-request-0003",
            binder_context=context(subject_id="service.competing-binder"),
        )
    assert other_subject.value.code.endswith("competing_identity")


@pytest.mark.asyncio
async def test_changed_idempotent_request_fails_closed_without_source_reads() -> None:
    route_binding, route, first = evidence_chain(generation=1)
    _, _, second = evidence_chain(generation=2)
    audit = CollectingAuditSink()
    repository = InMemoryBindingRepository(route_binding, route, first, second, audit=audit)
    service = WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
        binding_repository=repository,
        audit_sink=audit,
    )
    await bind(service, route_binding, first)
    reads_before_conflict = repository.source_read_count

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as exc_info:
        await bind(service, route_binding, second)

    assert exc_info.value.code.endswith("idempotency_conflict")
    assert repository.source_read_count == reads_before_conflict


@pytest.mark.asyncio
async def test_chain_mismatch_and_human_identity_fail_closed() -> None:
    route_binding, route, assignment = evidence_chain()
    cast(Any, assignment).principal_class = "human-user"
    cast(Any, assignment).seal()
    audit = CollectingAuditSink()
    repository = InMemoryBindingRepository(route_binding, route, assignment, audit=audit)
    service = WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
        binding_repository=repository,
        audit_sink=audit,
    )

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as mismatch:
        await bind(service, route_binding, assignment)
    assert mismatch.value.code.endswith("evidence_conflict")
    assert not repository.bindings

    service, repository, route_binding, _, assignments, _ = service_fixture()
    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as identity:
        await bind(
            service,
            route_binding,
            assignments[0],
            binder_context=context(
                actor_type="human",
                authentication_method="session_cookie",
                audience="atlas-web",
            ),
        )
    assert identity.value.code.endswith("binder_identity_required")
    assert not repository.bindings


@pytest.mark.asyncio
async def test_cross_scope_and_route_source_drift_fail_closed() -> None:
    route_binding, route, assignment = evidence_chain()
    cast(Any, assignment).scope = WorkflowScope(
        "org-atlas",
        "environment-lab",
        "site-ankara",
    )
    cast(Any, assignment).seal()
    audit = CollectingAuditSink()
    repository = InMemoryBindingRepository(route_binding, route, assignment, audit=audit)
    service = WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
        binding_repository=repository,
        audit_sink=audit,
    )

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as cross_scope:
        await bind(service, route_binding, assignment)
    assert cross_scope.value.code.endswith("evidence_conflict")
    assert not repository.bindings

    route_binding, route, assignment = evidence_chain()
    cast(Any, route_binding).transport_route_snapshot_digest = "f" * 64
    cast(Any, route_binding).seal()
    audit = CollectingAuditSink()
    repository = InMemoryBindingRepository(route_binding, route, assignment, audit=audit)
    service = WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
        binding_repository=repository,
        audit_sink=audit,
    )

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as drift:
        await bind(service, route_binding, assignment)
    assert drift.value.code.endswith("evidence_conflict")
    assert not repository.bindings


@pytest.mark.asyncio
async def test_precommit_audit_failure_does_not_persist() -> None:
    audit = CollectingAuditSink(fail_kind="commit-authorization")
    service, repository, route_binding, _, assignments, _ = service_fixture(audit=audit)

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as exc_info:
        await bind(service, route_binding, assignments[0])

    assert exc_info.value.code.endswith("precommit_audit_failed")
    assert not repository.bindings
    assert not repository.requests


@pytest.mark.asyncio
async def test_complete_audit_outage_is_a_controlled_fail_closed_error() -> None:
    audit = CollectingAuditSink(fail_all=True)
    service, repository, route_binding, _, assignments, _ = service_fixture(audit=audit)

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as intent_failure:
        await bind(service, route_binding, assignments[0])
    assert intent_failure.value.code.endswith("audit_unavailable")
    assert not repository.bindings
    assert not repository.requests

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as denial_failure:
        await bind(
            service,
            route_binding,
            assignments[0],
            binder_context=context(
                actor_type="human",
                authentication_method="session_cookie",
                audience="atlas-web",
            ),
        )
    assert denial_failure.value.code.endswith("audit_unavailable")


@pytest.mark.asyncio
async def test_completion_audit_failure_is_outcome_uncertain_and_replay_recovers() -> None:
    audit = CollectingAuditSink(fail_kind="completion")
    service, repository, route_binding, _, assignments, _ = service_fixture(audit=audit)

    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as exc_info:
        await bind(service, route_binding, assignments[0])
    assert exc_info.value.code.endswith("completion_audit_outcome_uncertain")
    assert len(repository.bindings) == 1
    assert len(repository.requests) == 1

    audit.fail_kind = None
    recovered = await bind(service, route_binding, assignments[0])
    assert recovered == next(iter(repository.bindings.values()))
    assert audit.records[-1].event_type.endswith(".replay")


def test_policy_and_public_request_surface_are_code_owned_and_minimized() -> None:
    policy = code_owned_workflow_event_physical_transport_credential_assignment_binding_policy()
    assert policy.policy_version == "1.0"
    assert policy.required_privilege_class == "read-only"
    assert canonical_digest(policy.digest_payload()) == policy.canonical_digest
    assert not any(
        WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority()
        .canonical_value()
        .values()
    )

    parameters = set(
        inspect.signature(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingService.bind
        ).parameters
    )
    assert parameters == {
        "self",
        "physical_transport_route_binding_id",
        "physical_transport_route_binding_digest",
        "credential_assignment_snapshot_id",
        "credential_assignment_snapshot_digest",
        "policy_id",
        "policy_version",
        "policy_digest",
        "idempotency_key",
        "context",
    }
    request_fields = {
        field.name for field in fields(WorkflowTransportCredentialAssignmentBindingRequest)
    }
    assert not any(
        forbidden in field_name
        for field_name in request_fields
        for forbidden in ("secret", "password", "endpoint", "artifact", "broker", "network")
    )


def test_domain_rejects_nonzero_authority_and_naive_time() -> None:
    with pytest.raises(ValueError, match="cannot grant authority"):
        WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority(
            credential_access_authorized=True
        )

    service, _, route_binding, _, assignments, _ = service_fixture()
    candidate = service._build_binding(
        route_binding=route_binding,
        route=evidence_chain()[1],
        assignment=assignments[0],
        binder_subject_id=context().subject_id,
        bound_at=NOW,
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(
            candidate,
            bound_at=NOW.replace(tzinfo=None),
            canonical_digest="0" * 64,
        )
