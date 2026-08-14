from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from test_workflow_route_freshness_admissions import (
    NOW,
    SCOPE,
    CollectingAuditSink,
    Evidence,
    admit,
    selection_head,
)
from test_workflow_route_freshness_admissions import (
    service_fixture as freshness_service_fixture,
)

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRepository,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus,
    WorkflowPhysicalTransportEndpointResolverContext,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseEffectiveState,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy,
)

LEASE_NOW = NOW + timedelta(seconds=5)


def _lease_from_request(
    request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    *,
    issued_at: datetime,
) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease:
    values: dict[str, object] = {
        "authorization_lease_id": request.authorization_lease_id,
        "freshness_admission_id": request.expected_freshness_admission_id,
        "freshness_admission_digest": request.expected_freshness_admission_digest,
        "physical_transport_route_binding_id": (
            request.expected_physical_transport_route_binding_id
        ),
        "physical_transport_route_binding_digest": (
            request.expected_physical_transport_route_binding_digest
        ),
        "transport_route_snapshot_id": request.expected_transport_route_snapshot_id,
        "transport_route_snapshot_digest": request.expected_transport_route_snapshot_digest,
        "current_selection_head_id": request.expected_current_selection_head_id,
        "current_selection_head_digest": request.expected_current_selection_head_digest,
        "current_selection_head_generation": request.expected_current_selection_head_generation,
        "current_selection_head_fencing_token_digest": (
            request.expected_current_selection_head_fencing_token_digest
        ),
        "route_set_id": request.expected_route_set_id,
        "route_set_revision": request.expected_route_set_revision,
        "selection_epoch_id": request.expected_selection_epoch_id,
        "selection_epoch_revision": request.expected_selection_epoch_revision,
        "selected_route_id": request.expected_selected_route_id,
        "selected_route_revision": request.expected_selected_route_revision,
        "selected_route_digest": request.expected_selected_route_digest,
        "selection_active": request.expected_selection_active,
        "selection_eligible": request.expected_selection_eligible,
        "selection_suspended": request.expected_selection_suspended,
        "selection_withdrawn": request.expected_selection_withdrawn,
        "selection_superseded": request.expected_selection_superseded,
        "policy_id": request.expected_policy_id,
        "policy_version": request.expected_policy_version,
        "policy_digest": request.expected_policy_digest,
        "scope": request.scope,
        "resolver_subject_id": request.resolver_subject_id,
        "issued_at": issued_at,
        "valid_until": issued_at + timedelta(seconds=request.expected_validity_window_seconds),
        "state": (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "authority": (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority()
        ),
    }
    payload = {
        key: value.canonical_value()
        if isinstance(
            value,
            (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority,
                WorkflowScope,
            ),
        )
        else value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if isinstance(
            value,
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState,
        )
        else value
        for key, value in values.items()
    }
    return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease(
        **cast(Any, values), canonical_digest=canonical_digest(payload)
    )


class InMemoryEndpointResolutionAuthorizationRepository:
    def __init__(
        self,
        *,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        binding: Evidence,
        route: Evidence,
        head: DeploymentEventTransportRouteSelectionHead,
        audit: CollectingAuditSink,
    ) -> None:
        self.admission = admission
        self.binding = binding
        self.route = route
        self.head = head
        self.audit = audit
        self.now = LEASE_NOW
        self.leases: dict[
            str, WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease
        ] = {}
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord,
        ] = {}
        self.last_request: (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest | None
        ) = None
        self.pre_persistence_audit: AuditRecord | None = None
        self.head_before_authorize: DeploymentEventTransportRouteSelectionHead | None = None

    @property
    def durable(self) -> bool:
        return True

    async def get_authoritative_time(self) -> datetime:
        return self.now

    async def get_route_freshness_admission_by_id(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission | None:
        if self.admission.freshness_admission_id == freshness_admission_id:
            return self.admission
        return None

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

    async def get_endpoint_resolution_authorization_lease(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None:
        return self.leases.get(freshness_admission_id)

    async def list_endpoint_resolution_authorization_leases(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease, ...]:
        return tuple(lease for lease in self.leases.values() if lease.scope == scope)[:limit]

    async def get_endpoint_resolution_authorization_lease_request(
        self,
        *,
        scope: WorkflowScope,
        resolver_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord | None:
        return self.requests.get((scope, resolver_subject_id, idempotency_key))

    async def authorize_endpoint_resolution(
        self,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult:
        self.pre_persistence_audit = self.audit.records[-1] if self.audit.records else None
        self.last_request = request
        if self.head_before_authorize is not None:
            self.head = self.head_before_authorize

        claim_key = (request.scope, request.resolver_subject_id, request.idempotency_key)
        prior = self.requests.get(claim_key)
        if prior is not None:
            status = (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.REPLAY
                if prior.request_fingerprint == request.request_fingerprint
                else (
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus
                ).IDEMPOTENCY_CONFLICT
            )
            return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                status,
                prior.lease,
            )

        current = self.leases.get(request.expected_freshness_admission_id)
        if current is not None:
            return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
                current,
            )

        policy = (
            code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy()
        )
        expected = (
            request.expected_freshness_admission_id,
            request.expected_freshness_admission_digest,
            request.expected_freshness_admission_valid_until,
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
            request.expected_policy_id,
            request.expected_policy_version,
            request.expected_policy_digest,
            request.expected_validity_window_seconds,
            request.scope,
        )
        actual = (
            self.admission.freshness_admission_id,
            self.admission.canonical_digest,
            self.admission.valid_until,
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
            policy.policy_id,
            policy.policy_version,
            policy.canonical_digest,
            policy.validity_window_seconds,
            self.admission.scope,
        )
        if (
            expected != actual
            or self.now + timedelta(seconds=policy.validity_window_seconds)
            > self.admission.valid_until
        ):
            return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                None,
            )

        lease = _lease_from_request(request, issued_at=self.now)
        self.leases[self.admission.freshness_admission_id] = lease
        self.requests[claim_key] = (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord(
                request.request_fingerprint,
                lease,
            )
        )
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.AUTHORIZED,
            lease,
        )


def resolver_context(
    *,
    subject_id: str = "service.workflow-physical-transport-endpoint-resolver",
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
    scope: WorkflowScope = SCOPE,
) -> WorkflowPhysicalTransportEndpointResolverContext:
    return WorkflowPhysicalTransportEndpointResolverContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        correlation_id="correlation.endpoint-resolution-authorization.0001",
        decision_id="decision.endpoint-resolution-authorization.0001",
        requested_at=LEASE_NOW,
    )


async def service_fixture(
    *,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService,
    InMemoryEndpointResolutionAuthorizationRepository,
    CollectingAuditSink,
]:
    freshness_service, freshness_repository, _, chain = freshness_service_fixture()
    admission = await admit(freshness_service, chain)
    binding, route = chain
    sink = audit or CollectingAuditSink()
    repository = InMemoryEndpointResolutionAuthorizationRepository(
        admission=admission,
        binding=binding,
        route=route,
        head=freshness_repository.head,
        audit=sink,
    )
    service = WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService(
        authorization_repository=cast(Any, repository),
        audit_sink=sink,
    )
    return service, repository, sink


async def authorize(
    service: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService,
    repository: InMemoryEndpointResolutionAuthorizationRepository,
    *,
    idempotency_key: str = "endpoint-resolution-authorization-0001",
    context: WorkflowPhysicalTransportEndpointResolverContext | None = None,
    **changes: object,
) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease:
    values: dict[str, object] = {
        "freshness_admission_id": repository.admission.freshness_admission_id,
        "freshness_admission_digest": repository.admission.canonical_digest,
        "policy_id": service.policy.policy_id,
        "policy_version": service.policy.policy_version,
        "idempotency_key": idempotency_key,
        "context": context or resolver_context(),
    }
    values.update(changes)
    return await service.authorize(**cast(Any, values))


@pytest.mark.asyncio
async def test_authorizes_exact_chain_for_15_seconds_with_one_true_authority() -> None:
    service, repository, audit = await service_fixture()

    lease = await authorize(service, repository)

    assert service.durable is True
    assert lease.freshness_admission_id == repository.admission.freshness_admission_id
    assert lease.resolver_subject_id == resolver_context().subject_id
    assert lease.issued_at == LEASE_NOW
    assert lease.valid_until == LEASE_NOW + timedelta(seconds=15)
    assert lease.valid_until <= repository.admission.valid_until
    assert (
        lease.state
        is (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState
        ).AUTHORIZED_UNCONSUMED
    )
    assert lease.canonical_digest == canonical_digest(lease.digest_payload())
    assert lease.authority.canonical_value() == {
        "credential_access_authorized": False,
        "delivery_authorized": False,
        "dispatch_authorized": False,
        "endpoint_resolution_authorized": True,
        "execution_authorized": False,
        "network_access_authorized": False,
        "publication_authorized": False,
        "readiness_probe_authorized": False,
        "route_binding_authorized": False,
        "route_selection_authorized": False,
    }
    assert repository.last_request is not None
    assert repository.last_request.resolver_subject_id == lease.resolver_subject_id
    assert repository.last_request.expected_validity_window_seconds == 15
    authorization = repository.pre_persistence_audit
    assert authorization is not None
    assert authorization.event_type.endswith(".authorization")
    assert authorization.outcome == "authorized"
    assert ("endpoint_resolution_authority", "true") in authorization.target_metadata
    assert audit.records == [authorization]


@pytest.mark.asyncio
async def test_exact_replay_requires_active_lease_freshness_and_current_head() -> None:
    service, repository, audit = await service_fixture()
    first = await authorize(service, repository)

    repository.now = LEASE_NOW + timedelta(seconds=14)
    replay = await authorize(service, repository)
    assert replay == first
    assert audit.records[-1].event_type.endswith(".replay")

    repository.now = LEASE_NOW + timedelta(seconds=15)
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as expired:
        await authorize(service, repository)
    assert expired.value.code.endswith("_repository_scope_violation")

    repository.now = LEASE_NOW + timedelta(seconds=10)
    repository.head = selection_head(
        head_id="transport-route-selection-head.workflow-events.0002",
        generation=8,
        fencing_token_digest="3" * 64,
    )
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as advanced:
        await authorize(service, repository)
    assert advanced.value.code.endswith("_evidence_conflict")


@pytest.mark.asyncio
async def test_requires_the_complete_15_second_freshness_window() -> None:
    service, repository, _ = await service_fixture()
    repository.now = repository.admission.valid_until - timedelta(seconds=15)
    lease = await authorize(service, repository)
    assert lease.valid_until == repository.admission.valid_until

    service, repository, _ = await service_fixture()
    repository.now = repository.admission.valid_until - timedelta(
        seconds=14,
        microseconds=999_999,
    )
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as denied:
        await authorize(service, repository)
    assert denied.value.code.endswith("_evidence_conflict")
    assert repository.leases == {}
    assert repository.requests == {}


@pytest.mark.asyncio
async def test_resolver_audience_is_bound_to_self_and_one_lease_per_admission() -> None:
    service, repository, _ = await service_fixture()
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as human:
        await authorize(
            service,
            repository,
            context=resolver_context(
                subject_id="user.operator",
                actor_type="human",
                authentication_method="password",
                audience="audience.browser",
            ),
        )
    assert human.value.code.endswith("_resolver_identity_required")

    first = await authorize(service, repository)
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as competing:
        await authorize(
            service,
            repository,
            idempotency_key="endpoint-resolution-authorization-0002",
            context=resolver_context(subject_id="service.endpoint-resolver.secondary"),
        )
    assert competing.value.code.endswith("_competing_identity")

    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as duplicate:
        await authorize(
            service,
            repository,
            idempotency_key="endpoint-resolution-authorization-0003",
        )
    assert duplicate.value.code.endswith("_already_authorized")
    assert tuple(repository.leases.values()) == (first,)


@pytest.mark.asyncio
async def test_source_drift_scope_and_unsafe_head_fail_with_normalized_evidence_error() -> None:
    service, repository, _ = await service_fixture()
    repository.route.source_route_digest = "9" * 64
    repository.route.seal()
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as drift:
        await authorize(service, repository)
    assert drift.value.code.endswith("_evidence_conflict")

    service, repository, _ = await service_fixture()
    repository.binding.scope = WorkflowScope("org-atlas", "environment-lab", "site-ankara")
    repository.binding.seal()
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as scoped:
        await authorize(service, repository)
    assert scoped.value.code == drift.value.code

    service, repository, _ = await service_fixture()
    repository.head = selection_head(selection_suspended=True)
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as suspended:
        await authorize(service, repository)
    assert suspended.value.code == drift.value.code


@pytest.mark.asyncio
async def test_repository_revalidation_rejects_head_movement_after_preflight() -> None:
    service, repository, _ = await service_fixture()
    repository.head_before_authorize = selection_head(
        head_id="transport-route-selection-head.workflow-events.0002",
        generation=8,
        fencing_token_digest="3" * 64,
    )

    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as moved:
        await authorize(service, repository)

    assert moved.value.code.endswith("_evidence_conflict")
    assert repository.leases == {}
    assert repository.requests == {}


@pytest.mark.asyncio
async def test_idempotency_conflict_and_audit_failure_leave_no_partial_record() -> None:
    service, repository, _ = await service_fixture()
    first = await authorize(service, repository)
    claim_key = (SCOPE, first.resolver_subject_id, "endpoint-resolution-authorization-0001")
    repository.requests[claim_key] = (
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord(
            "f" * 64,
            first,
        )
    )
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as conflict:
        await authorize(service, repository)
    assert conflict.value.code.endswith("_idempotency_conflict")

    failing = CollectingAuditSink(fail=True)
    service, repository, _ = await service_fixture(audit=failing)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await authorize(service, repository)
    assert repository.leases == {}
    assert repository.requests == {}


@pytest.mark.asyncio
async def test_policy_and_malformed_admission_evidence_fail_closed() -> None:
    service, repository, _ = await service_fixture()
    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as policy:
        await authorize(service, repository, policy_version="2.0")
    assert policy.value.code.endswith("_policy_conflict")

    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError
    ) as digest:
        await authorize(service, repository, freshness_admission_digest="not-a-digest")
    assert digest.value.code.endswith("_freshness_admission_digest_invalid")
    assert repository.leases == {}


def test_models_and_public_authorization_surface_are_strict_and_minimized() -> None:
    policy = code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy()
    assert policy.validity_window_seconds == 15
    assert policy.full_freshness_window_required is True
    assert policy.resolver_subject_bound is True
    assert policy.single_use_required is True
    assert policy.canonical_digest == canonical_digest(policy.digest_payload())

    with pytest.raises(ValueError, match="grant only endpoint resolution"):
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority(
            endpoint_resolution_authorized=False
        )
    with pytest.raises(ValueError, match="grant only endpoint resolution"):
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority(
            network_access_authorized=True
        )


@pytest.mark.asyncio
async def test_lease_model_rejects_ttl_drift_and_surface_has_no_runtime_operation() -> None:
    service, repository, _ = await service_fixture()
    lease = await authorize(service, repository)
    assert (
        lease.effective_state(evaluated_at=lease.valid_until - timedelta(microseconds=1))
        is WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseEffectiveState.ACTIVE
    )
    assert (
        lease.effective_state(evaluated_at=lease.valid_until)
        is WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseEffectiveState.EXPIRED
    )
    with pytest.raises(ValueError, match="exact 15-second window"):
        replace(lease, valid_until=lease.valid_until + timedelta(seconds=1))
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(lease, current_selection_head_fencing_token_digest="a" * 64)

    forbidden = {
        "endpoint",
        "hostname",
        "url",
        "ip_address",
        "port",
        "namespace",
        "topic",
        "stream",
        "queue",
        "partition",
        "routing_key",
        "private_route_descriptor",
        "credential",
        "secret",
        "certificate",
        "proxy",
        "network_result",
        "readiness_result",
        "provider_message",
        "publication_attempt",
        "delivery_receipt",
        "consumption_claim",
        "materialization",
    }
    lease_fields = {field.name for field in fields(type(lease))}
    request_fields = {
        field.name
        for field in fields(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest
        )
    }
    assert forbidden.isdisjoint(lease_fields)
    assert forbidden.isdisjoint(request_fields)
    assert set(inspect.signature(service.authorize).parameters) == {
        "freshness_admission_id",
        "freshness_admission_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    assert "consume" not in dir(service)
    assert "materialize" not in dir(service)
    assert "consume_endpoint_resolution_authorization_lease" not in dir(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRepository
    )
