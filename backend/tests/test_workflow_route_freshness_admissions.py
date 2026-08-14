from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionError,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionService,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus,
    WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthority,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_route_freshness_policy,
)

NOW = datetime(2026, 8, 14, 18, 0, tzinfo=UTC)
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
            elif isinstance(value, datetime):
                payload[name] = value.isoformat()
            elif isinstance(value, ZeroAuthority):
                payload[name] = value.canonical_value()
            else:
                payload[name] = value
        return payload

    def seal(self) -> None:
        self.canonical_digest = canonical_digest(self.digest_payload())


class CollectingAuditSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.records.append(event)


def route_chain() -> tuple[Evidence, Evidence]:
    route = Evidence(
        snapshot_id="transport-route-snapshot.0001",
        route_id="transport-route.workflow-events.primary",
        route_revision="23",
        route_set_id="transport-route-set.workflow-events",
        route_set_revision="11",
        selection_epoch_id="transport-route-selection-epoch.2026-08-14",
        selection_epoch_revision="4",
        source_route_digest="1" * 64,
        scope=SCOPE,
        captured_at=NOW - timedelta(seconds=2),
        state=EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED,
        authority=ZeroAuthority(),
    )
    binding = Evidence(
        binding_id="workflow-event-physical-transport-route-binding.0001",
        transport_route_snapshot_id=route.snapshot_id,
        transport_route_snapshot_digest=route.canonical_digest,
        scope=SCOPE,
        binder_subject_id="service.workflow-physical-route-binder",
        bound_at=NOW - timedelta(seconds=1),
        state=WorkflowEventPhysicalTransportRouteBindingState.BOUND,
        authority=ZeroAuthority(),
    )
    return binding, route


def selection_head(**changes: object) -> DeploymentEventTransportRouteSelectionHead:
    values: dict[str, object] = {
        "head_id": "transport-route-selection-head.workflow-events.0001",
        "generation": 7,
        "route_set_id": "transport-route-set.workflow-events",
        "route_set_revision": "11",
        "selection_epoch_id": "transport-route-selection-epoch.2026-08-14",
        "selection_epoch_revision": "4",
        "selected_route_id": "transport-route.workflow-events.primary",
        "selected_route_revision": "23",
        "selected_route_digest": "1" * 64,
        "fencing_token_digest": "2" * 64,
        "selection_active": True,
        "selection_eligible": True,
        "selection_suspended": False,
        "selection_withdrawn": False,
        "selection_superseded": False,
        "scope": SCOPE,
        "current": True,
    }
    values.update(changes)
    return DeploymentEventTransportRouteSelectionHead(
        **cast(Any, values),
        canonical_digest=canonical_digest(
            {
                "current": values["current"],
                "fencing_token_digest": values["fencing_token_digest"],
                "generation": values["generation"],
                "head_id": values["head_id"],
                "route_set_id": values["route_set_id"],
                "route_set_revision": values["route_set_revision"],
                "scope": cast(WorkflowScope, values["scope"]).canonical_value(),
                "selection_active": values["selection_active"],
                "selection_eligible": values["selection_eligible"],
                "selection_superseded": values["selection_superseded"],
                "selection_suspended": values["selection_suspended"],
                "selection_withdrawn": values["selection_withdrawn"],
                "selected_route_digest": values["selected_route_digest"],
                "selected_route_id": values["selected_route_id"],
                "selected_route_revision": values["selected_route_revision"],
                "selection_epoch_id": values["selection_epoch_id"],
                "selection_epoch_revision": values["selection_epoch_revision"],
            }
        ),
    )


class InMemoryFreshnessAdmissionRepository:
    def __init__(
        self,
        binding: Evidence,
        route: Evidence,
        head: DeploymentEventTransportRouteSelectionHead,
        *,
        audit: CollectingAuditSink,
    ) -> None:
        self.binding = binding
        self.route = route
        self.head = head
        self.audit = audit
        self.admissions: dict[str, WorkflowEventPhysicalTransportRouteFreshnessAdmission] = {}
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord,
        ] = {}
        self.pre_persistence_audit: AuditRecord | None = None
        self.last_request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest | None = (
            None
        )
        self.head_before_admit: DeploymentEventTransportRouteSelectionHead | None = None
        self.synchronized_heads: tuple[DeploymentEventTransportRouteSelectionHead, ...] = ()

    @property
    def durable(self) -> bool:
        return True

    async def synchronize_route_selection_heads(
        self, heads: tuple[DeploymentEventTransportRouteSelectionHead, ...]
    ) -> None:
        self.synchronized_heads = heads

    async def get_physical_transport_route_binding_by_id(self, *, binding_id: str) -> Any:
        return self.binding if self.binding.binding_id == binding_id else None

    async def get_transport_route_snapshot_by_id(self, *, snapshot_id: str) -> Any:
        return self.route if self.route.snapshot_id == snapshot_id else None

    async def get_current_route_selection_head(
        self, *, scope: WorkflowScope, route_set_id: str
    ) -> DeploymentEventTransportRouteSelectionHead | None:
        if self.head.scope == scope and self.head.route_set_id == route_set_id:
            return self.head
        return None

    async def get_route_freshness_admission(
        self, *, physical_transport_route_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission | None:
        return self.admissions.get(physical_transport_route_binding_id)

    async def list_route_freshness_admissions(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportRouteFreshnessAdmission, ...]:
        return tuple(item for item in self.admissions.values() if item.scope == scope)[:limit]

    async def get_route_freshness_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord | None:
        return self.requests.get((scope, admitter_subject_id, idempotency_key))

    async def admit_physical_transport_route_freshness(
        self, request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult:
        self.pre_persistence_audit = self.audit.records[-1] if self.audit.records else None
        self.last_request = request
        if self.head_before_admit is not None:
            self.head = self.head_before_admit
        claim_key = (request.scope, request.admitter_subject_id, request.idempotency_key)
        prior = self.requests.get(claim_key)
        if prior is not None:
            status = (
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else (
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.IDEMPOTENCY_CONFLICT
                )
            )
            return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                status, prior.admission
            )
        current = self.admissions.get(request.expected_physical_transport_route_binding_id)
        if current is not None:
            return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.ALREADY_ADMITTED,
                current,
            )
        expected = (
            request.expected_physical_transport_route_binding_id,
            request.expected_physical_transport_route_binding_digest,
            request.expected_transport_route_snapshot_id,
            request.expected_transport_route_snapshot_digest,
            request.expected_current_selection_head_id,
            request.expected_current_selection_head_digest,
            request.expected_current_selection_head_generation,
            request.expected_current_selection_head_fencing_token_digest,
            request.expected_route_set_id,
            request.expected_route_set_revision,
            request.expected_selection_epoch_id,
            request.expected_selection_epoch_revision,
            request.expected_selected_route_id,
            request.expected_selected_route_revision,
            request.expected_selected_route_digest,
            request.expected_selection_active,
            request.expected_selection_eligible,
            request.expected_selection_suspended,
            request.expected_selection_withdrawn,
            request.expected_selection_superseded,
        )
        actual = (
            self.binding.binding_id,
            self.binding.canonical_digest,
            self.route.snapshot_id,
            self.route.canonical_digest,
            self.head.head_id,
            self.head.canonical_digest,
            self.head.generation,
            self.head.fencing_token_digest,
            self.head.route_set_id,
            self.head.route_set_revision,
            self.head.selection_epoch_id,
            self.head.selection_epoch_revision,
            self.head.selected_route_id,
            self.head.selected_route_revision,
            self.head.selected_route_digest,
            self.head.selection_active,
            self.head.selection_eligible,
            self.head.selection_suspended,
            self.head.selection_withdrawn,
            self.head.selection_superseded,
        )
        if expected != actual:
            return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                None,
            )
        self.admissions[self.binding.binding_id] = request.candidate
        self.requests[claim_key] = (
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord(
                request.request_fingerprint, request.candidate
            )
        )
        return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.ADMITTED_CURRENT,
            request.candidate,
        )


def admitter_context(
    *,
    subject_id: str = "service.workflow-physical-route-freshness-admitter",
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
    scope: WorkflowScope = SCOPE,
    requested_at: datetime = NOW,
) -> WorkflowPhysicalTransportRouteFreshnessAdmitterContext:
    return WorkflowPhysicalTransportRouteFreshnessAdmitterContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        correlation_id="correlation.route-freshness.0001",
        decision_id="decision.route-freshness.0001",
        requested_at=requested_at,
    )


def service_fixture(
    *, audit: CollectingAuditSink | None = None
) -> tuple[
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionService,
    InMemoryFreshnessAdmissionRepository,
    CollectingAuditSink,
    tuple[Evidence, Evidence],
]:
    binding, route = route_chain()
    sink = audit or CollectingAuditSink()
    repository = InMemoryFreshnessAdmissionRepository(binding, route, selection_head(), audit=sink)
    service = WorkflowEventPhysicalTransportRouteFreshnessAdmissionService(
        admission_repository=cast(Any, repository), audit_sink=sink
    )
    return service, repository, sink, (binding, route)


async def admit(
    service: WorkflowEventPhysicalTransportRouteFreshnessAdmissionService,
    chain: tuple[Evidence, Evidence],
    *,
    idempotency_key: str = "route-freshness-admission-0001",
    context: WorkflowPhysicalTransportRouteFreshnessAdmitterContext | None = None,
    **changes: object,
) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission:
    binding, _ = chain
    values: dict[str, object] = {
        "physical_transport_route_binding_id": binding.binding_id,
        "physical_transport_route_binding_digest": binding.canonical_digest,
        "policy_id": service.policy.policy_id,
        "policy_version": service.policy.policy_version,
        "idempotency_key": idempotency_key,
        "context": context or admitter_context(),
    }
    values.update(changes)
    return await service.admit(**cast(Any, values))


@pytest.mark.asyncio
async def test_admits_exact_current_chain_with_bounded_lifetime_and_zero_authority() -> None:
    service, repository, audit, chain = service_fixture()

    result = await admit(service, chain)

    binding, route = chain
    assert service.durable is True
    assert result.physical_transport_route_binding_id == binding.binding_id
    assert result.transport_route_snapshot_id == route.snapshot_id
    assert result.current_selection_head_id == repository.head.head_id
    assert result.current_selection_head_generation == repository.head.generation
    assert (
        result.current_selection_head_fencing_token_digest == repository.head.fencing_token_digest
    )
    assert result.valid_until == NOW + timedelta(seconds=60)
    assert (
        result.state is WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT
    )
    assert result.canonical_digest == canonical_digest(result.digest_payload())
    assert not any(result.authority.canonical_value().values())
    assert not any(
        (
            result.grants_endpoint_resolution_authority,
            result.grants_route_selection_authority,
            result.grants_route_binding_authority,
            result.grants_credential_access_authority,
            result.grants_network_access_authority,
            result.grants_readiness_probe_authority,
            result.grants_publication_authority,
            result.grants_delivery_authority,
            result.grants_dispatch_authority,
            result.grants_execution_authority,
        )
    )
    request = repository.last_request
    assert request is not None
    assert request.expected_current_selection_head_digest == repository.head.canonical_digest
    assert request.expected_current_selection_head_generation == repository.head.generation
    assert (
        request.expected_current_selection_head_fencing_token_digest
        == repository.head.fencing_token_digest
    )
    authorization = repository.pre_persistence_audit
    assert authorization is not None
    assert authorization.event_type.endswith(".authorization")
    assert authorization.outcome == "authorized"
    assert audit.records == [authorization]


@pytest.mark.asyncio
async def test_exact_replay_requires_unexpired_unchanged_head_and_fence() -> None:
    service, repository, audit, chain = service_fixture()
    first = await admit(service, chain)

    replay = await admit(
        service, chain, context=admitter_context(requested_at=NOW + timedelta(seconds=59))
    )
    assert replay == first
    assert audit.records[-1].event_type.endswith(".replay")

    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as expired:
        await admit(
            service, chain, context=admitter_context(requested_at=NOW + timedelta(seconds=60))
        )
    assert expired.value.code.endswith("_admission_not_current")

    repository.head = selection_head(
        head_id="transport-route-selection-head.workflow-events.0002",
        generation=8,
        fencing_token_digest="3" * 64,
    )
    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as advanced:
        await admit(
            service, chain, context=admitter_context(requested_at=NOW + timedelta(seconds=30))
        )
    assert advanced.value.code.endswith("_admission_not_current")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("selection_active", False),
        ("selection_eligible", False),
        ("selection_suspended", True),
        ("selection_withdrawn", True),
        ("selection_superseded", True),
    ),
)
async def test_unsafe_current_selection_state_fails_closed(field: str, value: bool) -> None:
    service, repository, _, chain = service_fixture()
    repository.head = selection_head(**{field: value})

    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as denied:
        await admit(service, chain)

    assert denied.value.code.endswith("_evidence_conflict")
    assert repository.admissions == {}


@pytest.mark.asyncio
async def test_route_chain_drift_missing_and_cross_scope_share_evidence_failure() -> None:
    service, repository, _, chain = service_fixture()
    repository.route.source_route_digest = "9" * 64
    repository.route.seal()
    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as drift:
        await admit(service, chain)
    assert drift.value.code.endswith("_evidence_conflict")

    service, repository, _, chain = service_fixture()
    repository.route.snapshot_id = "transport-route-snapshot.missing"
    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as missing:
        await admit(service, chain)
    assert missing.value.code == drift.value.code

    service, repository, _, chain = service_fixture()
    repository.binding.scope = WorkflowScope("org-atlas", "environment-lab", "site-ankara")
    repository.binding.seal()
    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as scoped:
        await admit(service, chain)
    assert scoped.value.code == drift.value.code


@pytest.mark.asyncio
async def test_repository_revalidation_rejects_head_movement_after_prevalidation() -> None:
    service, repository, _, chain = service_fixture()
    repository.head_before_admit = selection_head(
        head_id="transport-route-selection-head.workflow-events.0002",
        generation=8,
        fencing_token_digest="3" * 64,
    )

    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as moved:
        await admit(service, chain)

    assert moved.value.code.endswith("_evidence_conflict")
    assert repository.admissions == {}
    assert repository.requests == {}


@pytest.mark.asyncio
async def test_idempotency_competing_identity_and_audit_failure_fail_closed() -> None:
    service, repository, _, chain = service_fixture()
    first = await admit(service, chain)
    claim_key = (SCOPE, first.admitter_subject_id, "route-freshness-admission-0001")
    repository.requests[claim_key] = (
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord("f" * 64, first)
    )
    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as changed:
        await admit(service, chain)
    assert changed.value.code.endswith("_idempotency_conflict")

    repository.requests.clear()
    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as competing:
        await admit(
            service,
            chain,
            idempotency_key="route-freshness-admission-0002",
            context=admitter_context(subject_id="service.route-freshness.secondary"),
        )
    assert competing.value.code.endswith("_competing_identity")

    failing = CollectingAuditSink(fail=True)
    service, repository, _, chain = service_fixture(audit=failing)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await admit(service, chain)
    assert repository.admissions == {}
    assert repository.requests == {}


@pytest.mark.asyncio
async def test_only_dedicated_workload_audience_can_admit() -> None:
    service, repository, _, chain = service_fixture()

    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as denied:
        await admit(
            service,
            chain,
            context=admitter_context(
                subject_id="user.operator",
                actor_type="human",
                authentication_method="password",
                audience="audience.browser",
            ),
        )

    assert denied.value.code.endswith("_admitter_identity_required")
    assert repository.admissions == {}


@pytest.mark.asyncio
async def test_policy_and_malformed_binding_evidence_fail_before_source_use() -> None:
    service, repository, _, chain = service_fixture()
    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as policy:
        await admit(service, chain, policy_version="2.0")
    assert policy.value.code.endswith("_policy_conflict")

    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as digest:
        await admit(service, chain, physical_transport_route_binding_digest="not-a-digest")
    assert digest.value.code.endswith("_physical_route_binding_digest_invalid")
    assert repository.admissions == {}


def test_models_policy_and_public_create_surface_are_minimized() -> None:
    policy = code_owned_workflow_event_physical_transport_route_freshness_policy()
    assert policy.policy_id == "policy.workflow-event-physical-transport-route-freshness"
    assert policy.validity_window_seconds == 60
    assert policy.unique_current_head_required is True
    assert policy.monotonic_generation_required is True
    assert policy.canonical_digest == canonical_digest(policy.digest_payload())

    head = selection_head()
    assert head.canonical_digest == canonical_digest(head.digest_payload())
    assert "route_snapshot_id" not in {field.name for field in fields(type(head))}
    assert "route_snapshot_digest" not in {field.name for field in fields(type(head))}
    with pytest.raises(ValueError, match="generation must be positive"):
        selection_head(generation=0)
    with pytest.raises(ValueError, match="must be current"):
        selection_head(current=False)
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(head, fencing_token_digest="a" * 64)
    with pytest.raises(ValueError, match="cannot grant operational authority"):
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthority(
            endpoint_resolution_authorized=True
        )

    service, _, _, chain = service_fixture()
    binding, route = chain
    admission = service._build_admission(
        binding=cast(Any, binding),
        route=cast(Any, route),
        head=head,
        admitter_subject_id="service.workflow-physical-route-freshness-admitter",
        evaluated_at=NOW,
    )
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(admission, current_selection_head_fencing_token_digest="a" * 64)

    forbidden = {
        "endpoint",
        "hostname",
        "url",
        "ip_address",
        "topic",
        "stream",
        "queue",
        "partition",
        "routing_key",
        "credential",
        "secret_reference",
        "fencing_token",
        "resolved_endpoint",
        "network_result",
        "readiness_result",
        "provider_message_id",
        "publication_attempt",
        "delivery_receipt",
    }
    assert forbidden.isdisjoint({field.name for field in fields(type(head))})
    assert forbidden.isdisjoint({field.name for field in fields(type(admission))})
    request_fields = {
        field.name for field in fields(WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest)
    }
    assert forbidden.isdisjoint(request_fields)
    assert set(inspect.signature(service.admit).parameters) == {
        "physical_transport_route_binding_id",
        "physical_transport_route_binding_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    assert "synchronize_route_selection_heads" in dir(
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository
    )
    assert "list_route_freshness_admissions" in dir(
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionRepository
    )
    assert "synchronize_route_selection_heads" not in dir(service)
