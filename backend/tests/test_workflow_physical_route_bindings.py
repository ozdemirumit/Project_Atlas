from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
    WorkflowEventPhysicalTransportRouteBindingError,
    WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord,
    WorkflowEventPhysicalTransportRouteBindingRequest,
    WorkflowEventPhysicalTransportRouteBindingResult,
    WorkflowEventPhysicalTransportRouteBindingService,
    WorkflowEventPhysicalTransportRouteBindingStatus,
    WorkflowPhysicalTransportRouteBinderContext,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportProfileSnapshotState,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowEventLogicalChannelBindingState,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteBindingAuthority,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowEventTransportCompatibilityAdmissionState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_route_binding_policy,
)

NOW = datetime(2026, 8, 14, 16, 0, tzinfo=UTC)
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


class CollectingAuditSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail:
            raise RuntimeError("audit unavailable")
        self.records.append(event)


def evidence_chain() -> tuple[Evidence, Evidence, Evidence, Evidence]:
    authority = ZeroAuthority()
    logical = Evidence(
        binding_id="logical-binding.0001",
        scope=SCOPE,
        state=WorkflowEventLogicalChannelBindingState.BOUND,
        authority=authority,
    )
    profile = Evidence(
        snapshot_id="transport-profile-snapshot.0001",
        transport_profile_id="transport-profile.workflow-events.primary",
        transport_profile_revision="17",
        transport_resource_id="transport-resource.workflow-events.primary",
        transport_resource_digest="1" * 64,
        transport_implementation_id="transport.nats-jetstream",
        transport_implementation_version="2.11",
        adapter_contract_id="adapter-contract.workflow-events",
        adapter_contract_version="1.0",
        adapter_contract_digest="2" * 64,
        deployment_release_id="atlas-release.2026.08.14",
        deployment_profile="lab",
        transport_encryption_required=True,
        restricted_network_supported=True,
        scope=SCOPE,
        state=EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED,
        authority=authority,
    )
    admission = Evidence(
        compatibility_admission_id="compatibility-admission.0001",
        logical_channel_binding_id=logical.binding_id,
        logical_channel_binding_digest=logical.canonical_digest,
        transport_profile_snapshot_id=profile.snapshot_id,
        transport_profile_snapshot_digest=profile.canonical_digest,
        transport_profile_id=profile.transport_profile_id,
        transport_profile_revision=profile.transport_profile_revision,
        scope=SCOPE,
        state=WorkflowEventTransportCompatibilityAdmissionState.ADMITTED,
        authority=authority,
    )
    route = Evidence(
        snapshot_id="transport-route-snapshot.0001",
        transport_profile_id=profile.transport_profile_id,
        transport_profile_revision=profile.transport_profile_revision,
        transport_resource_id=profile.transport_resource_id,
        transport_resource_digest=profile.transport_resource_digest,
        transport_implementation_id=profile.transport_implementation_id,
        transport_implementation_version=profile.transport_implementation_version,
        adapter_contract_id=profile.adapter_contract_id,
        adapter_contract_version=profile.adapter_contract_version,
        adapter_contract_digest=profile.adapter_contract_digest,
        deployment_release_id=profile.deployment_release_id,
        deployment_profile=profile.deployment_profile,
        minimum_tls_version="1.3",
        server_authentication_required=True,
        plaintext_fallback_prohibited=True,
        restricted_network_enforced=True,
        public_egress_prohibited=True,
        proxy_mode="prohibited",
        scope=SCOPE,
        state=EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED,
        authority=authority,
    )
    return logical, admission, profile, route


class InMemoryBindingRepository:
    def __init__(
        self,
        logical: Evidence,
        admission: Evidence,
        profile: Evidence,
        *routes: Evidence,
        audit: CollectingAuditSink,
    ) -> None:
        self.logical = logical
        self.admission = admission
        self.profile = profile
        self.routes = {route.snapshot_id: route for route in routes}
        self.audit = audit
        self.bindings: dict[str, WorkflowEventPhysicalTransportRouteBinding] = {}
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord,
        ] = {}
        self.pre_persistence_audit: AuditRecord | None = None

    @property
    def durable(self) -> bool:
        return True

    async def get_event_logical_channel_binding_by_id(self, *, binding_id: str) -> Any:
        return self.logical if self.logical.binding_id == binding_id else None

    async def get_transport_compatibility_admission_by_id(self, *, admission_id: str) -> Any:
        return self.admission if self.admission.compatibility_admission_id == admission_id else None

    async def get_transport_profile_snapshot_by_id(self, *, snapshot_id: str) -> Any:
        return self.profile if self.profile.snapshot_id == snapshot_id else None

    async def get_transport_route_snapshot_by_id(self, *, snapshot_id: str) -> Any:
        return self.routes.get(snapshot_id)

    async def get_physical_transport_route_binding(
        self, *, logical_channel_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None:
        return self.bindings.get(logical_channel_binding_id)

    async def get_physical_transport_route_binding_request(
        self,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord | None:
        return self.requests.get((scope, binder_subject_id, idempotency_key))

    async def bind_physical_transport_route(
        self, request: WorkflowEventPhysicalTransportRouteBindingRequest
    ) -> WorkflowEventPhysicalTransportRouteBindingResult:
        self.pre_persistence_audit = self.audit.records[-1] if self.audit.records else None
        claim_key = (request.scope, request.binder_subject_id, request.idempotency_key)
        prior = self.requests.get(claim_key)
        if prior is not None:
            status = (
                WorkflowEventPhysicalTransportRouteBindingStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else WorkflowEventPhysicalTransportRouteBindingStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowEventPhysicalTransportRouteBindingResult(status, prior.binding)
        current = self.bindings.get(request.expected_logical_channel_binding_id)
        if current is not None:
            return WorkflowEventPhysicalTransportRouteBindingResult(
                WorkflowEventPhysicalTransportRouteBindingStatus.ALREADY_BOUND, current
            )
        expected = (
            request.expected_logical_channel_binding_digest,
            request.expected_transport_compatibility_admission_digest,
            request.expected_transport_profile_snapshot_digest,
            request.expected_transport_route_snapshot_digest,
        )
        actual = (
            self.logical.canonical_digest,
            self.admission.canonical_digest,
            self.profile.canonical_digest,
            self.routes[request.expected_transport_route_snapshot_id].canonical_digest,
        )
        if expected != actual:
            return WorkflowEventPhysicalTransportRouteBindingResult(
                WorkflowEventPhysicalTransportRouteBindingStatus.EVIDENCE_CONFLICT, None
            )
        self.bindings[request.expected_logical_channel_binding_id] = request.candidate
        self.requests[claim_key] = WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord(
            request.request_fingerprint, request.candidate
        )
        return WorkflowEventPhysicalTransportRouteBindingResult(
            WorkflowEventPhysicalTransportRouteBindingStatus.BOUND, request.candidate
        )


def binder_context(
    *,
    subject_id: str = "service.workflow-physical-transport-route-binder",
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
    requested_at: datetime = NOW,
) -> WorkflowPhysicalTransportRouteBinderContext:
    return WorkflowPhysicalTransportRouteBinderContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=SCOPE,
        correlation_id="correlation.physical-route-binding.0001",
        decision_id="decision.physical-route-binding.0001",
        requested_at=requested_at,
    )


def service_fixture(
    *, audit: CollectingAuditSink | None = None
) -> tuple[
    WorkflowEventPhysicalTransportRouteBindingService,
    InMemoryBindingRepository,
    CollectingAuditSink,
    tuple[Evidence, Evidence, Evidence, Evidence],
]:
    chain = evidence_chain()
    sink = audit or CollectingAuditSink()
    repository = InMemoryBindingRepository(*chain, audit=sink)
    service = WorkflowEventPhysicalTransportRouteBindingService(
        binding_repository=cast(Any, repository), audit_sink=sink
    )
    return service, repository, sink, chain


async def bind(
    service: WorkflowEventPhysicalTransportRouteBindingService,
    chain: tuple[Evidence, Evidence, Evidence, Evidence],
    *,
    idempotency_key: str = "physical-route-binding-0001",
    context: WorkflowPhysicalTransportRouteBinderContext | None = None,
    **changes: object,
) -> WorkflowEventPhysicalTransportRouteBinding:
    logical, admission, profile, route = chain
    policy = service.policy
    values: dict[str, object] = {
        "logical_channel_binding_id": logical.binding_id,
        "logical_channel_binding_digest": logical.canonical_digest,
        "transport_compatibility_admission_id": admission.compatibility_admission_id,
        "transport_compatibility_admission_digest": admission.canonical_digest,
        "transport_profile_snapshot_id": profile.snapshot_id,
        "transport_profile_snapshot_digest": profile.canonical_digest,
        "transport_route_snapshot_id": route.snapshot_id,
        "transport_route_snapshot_digest": route.canonical_digest,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "idempotency_key": idempotency_key,
        "context": context or binder_context(),
    }
    values.update(changes)
    return await service.bind(**cast(Any, values))


@pytest.mark.asyncio
async def test_binds_exact_chain_with_zero_authority_and_authorization_only_audit() -> None:
    service, repository, audit, chain = service_fixture()

    result = await bind(service, chain)

    logical, admission, profile, route = chain
    assert service.durable is True
    assert result.logical_channel_binding_digest == logical.canonical_digest
    assert result.transport_compatibility_admission_digest == admission.canonical_digest
    assert result.transport_profile_snapshot_digest == profile.canonical_digest
    assert result.transport_route_snapshot_digest == route.canonical_digest
    assert result.state is WorkflowEventPhysicalTransportRouteBindingState.BOUND
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
    authorization = repository.pre_persistence_audit
    assert authorization is not None
    assert authorization.event_type.endswith(".authorization")
    assert authorization.outcome == "authorized"
    assert authorization.result_code.endswith("_persistence_authorized")
    assert "succeeded" not in authorization.event_type
    assert audit.records == [authorization]


@pytest.mark.asyncio
async def test_exact_replay_changed_request_and_competing_identity_fail_closed() -> None:
    service, repository, audit, chain = service_fixture()
    first = await bind(service, chain)
    replay = await bind(
        service, chain, context=binder_context(requested_at=NOW + timedelta(seconds=5))
    )
    assert replay == first
    assert audit.records[-1].event_type.endswith(".replay")

    with pytest.raises(WorkflowEventPhysicalTransportRouteBindingError) as changed:
        await bind(service, chain, policy_digest="f" * 64)
    assert changed.value.code == "workflow_physical_transport_route_binding_policy_conflict"

    repository.requests.clear()
    with pytest.raises(WorkflowEventPhysicalTransportRouteBindingError) as competing:
        await bind(
            service,
            chain,
            idempotency_key="physical-route-binding-0002",
            context=binder_context(subject_id="service.workflow-route-binder.secondary"),
        )
    assert competing.value.code == "workflow_physical_transport_route_binding_competing_identity"


@pytest.mark.asyncio
async def test_chain_drift_scope_authority_and_insecure_route_fail_closed() -> None:
    service, repository, _, chain = service_fixture()
    logical, admission, profile, route = chain

    route.adapter_contract_digest = "9" * 64
    route.seal()
    with pytest.raises(WorkflowEventPhysicalTransportRouteBindingError) as mismatch:
        await bind(service, chain)
    assert mismatch.value.code == "workflow_physical_transport_route_binding_evidence_conflict"
    assert repository.bindings == {}

    route.adapter_contract_digest = profile.adapter_contract_digest
    route.minimum_tls_version = "1.2"
    route.seal()
    with pytest.raises(WorkflowEventPhysicalTransportRouteBindingError) as insecure:
        await bind(service, chain)
    assert insecure.value.code == "workflow_physical_transport_route_binding_evidence_conflict"

    route.minimum_tls_version = "1.3"
    route.seal()
    logical.scope = WorkflowScope("org-atlas", "environment-lab", "site-ankara")
    logical.seal()
    admission.logical_channel_binding_digest = logical.canonical_digest
    admission.seal()
    with pytest.raises(WorkflowEventPhysicalTransportRouteBindingError) as wrong_scope:
        await bind(service, chain)
    assert wrong_scope.value.code == "workflow_physical_transport_route_binding_evidence_conflict"


@pytest.mark.asyncio
async def test_missing_and_cross_scope_evidence_share_one_non_enumerating_failure() -> None:
    service, repository, _, chain = service_fixture()
    repository.routes.clear()
    with pytest.raises(WorkflowEventPhysicalTransportRouteBindingError) as missing:
        await bind(service, chain)
    assert missing.value.code == "workflow_physical_transport_route_binding_evidence_conflict"

    service, repository, _, chain = service_fixture()
    chain[0].scope = WorkflowScope("org-atlas", "environment-lab", "site-ankara")
    chain[0].seal()
    with pytest.raises(WorkflowEventPhysicalTransportRouteBindingError) as cross_scope:
        await bind(service, chain)
    assert cross_scope.value.code == missing.value.code


@pytest.mark.asyncio
async def test_binder_identity_and_audit_failure_create_no_binding() -> None:
    service, repository, _, chain = service_fixture()
    with pytest.raises(WorkflowEventPhysicalTransportRouteBindingError) as identity:
        await bind(
            service,
            chain,
            context=binder_context(
                subject_id="user.operator",
                actor_type="human",
                authentication_method="password",
                audience="audience.browser",
            ),
        )
    assert identity.value.code.endswith("_binder_identity_required")
    assert repository.bindings == {}

    failing = CollectingAuditSink(fail=True)
    service, repository, _, chain = service_fixture(audit=failing)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await bind(service, chain)
    assert repository.bindings == {}
    assert repository.requests == {}


def test_policy_model_and_public_surface_are_immutable_and_minimized() -> None:
    policy = code_owned_workflow_event_physical_transport_route_binding_policy()
    assert policy.minimum_tls_version == "1.3"
    assert policy.canonical_digest == canonical_digest(policy.digest_payload())
    with pytest.raises(ValueError, match="cannot grant operational authority"):
        WorkflowEventPhysicalTransportRouteBindingAuthority(network_access_authorized=True)

    service, _, _, chain = service_fixture()
    logical, admission, profile, route = chain
    binding = service._build_binding(
        logical=cast(Any, logical),
        admission=cast(Any, admission),
        profile=cast(Any, profile),
        route=cast(Any, route),
        binder_subject_id="service.workflow-physical-transport-route-binder",
        bound_at=NOW,
    )
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(binding, transport_route_snapshot_digest="a" * 64)

    names = {field.name for field in fields(WorkflowEventPhysicalTransportRouteBinding)}
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
        "private_route_descriptor_commitment",
        "credential",
        "secret_reference",
        "resolved_endpoint",
        "network_result",
        "readiness_result",
        "provider_message_id",
        "publication_attempt",
        "delivery_receipt",
        "worker_instruction",
    }
    assert forbidden.isdisjoint(names)
    assert set(inspect.signature(service.bind).parameters) == {
        "logical_channel_binding_id",
        "logical_channel_binding_digest",
        "transport_compatibility_admission_id",
        "transport_compatibility_admission_digest",
        "transport_profile_snapshot_id",
        "transport_profile_snapshot_digest",
        "transport_route_snapshot_id",
        "transport_route_snapshot_digest",
        "policy_id",
        "policy_version",
        "policy_digest",
        "idempotency_key",
        "context",
    }
