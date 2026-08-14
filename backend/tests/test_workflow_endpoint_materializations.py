from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from test_workflow_endpoint_resolution_authorization_leases import (
    LEASE_NOW,
    authorize,
    resolver_context,
)
from test_workflow_endpoint_resolution_authorization_leases import (
    service_fixture as authorization_service_fixture,
)
from test_workflow_route_freshness_admissions import CollectingAuditSink

from atlas.modules.workflows.adapters import (
    SyntheticWorkflowPhysicalTransportEndpointMaterializer,
    UnavailableWorkflowPhysicalTransportEndpointMaterializer,
)
from atlas.modules.workflows.application import (
    WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
    WorkflowEventPhysicalTransportEndpointMaterializationClaimResult,
    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus,
    WorkflowEventPhysicalTransportEndpointMaterializationError,
    WorkflowEventPhysicalTransportEndpointMaterializationResultRequest,
    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus,
    WorkflowEventPhysicalTransportEndpointMaterializationResultWrite,
    WorkflowEventPhysicalTransportEndpointMaterializationService,
    WorkflowEventPhysicalTransportEndpointMaterializationUncertainError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportEndpointMaterializationAttempt,
    WorkflowEventPhysicalTransportEndpointMaterializationAttemptState,
    WorkflowEventPhysicalTransportEndpointMaterializationAuthority,
    WorkflowEventPhysicalTransportEndpointMaterializationFailureClass,
    WorkflowEventPhysicalTransportEndpointMaterializationInstruction,
    WorkflowEventPhysicalTransportEndpointMaterializationReceipt,
    WorkflowEventPhysicalTransportEndpointMaterializationResult,
    WorkflowEventPhysicalTransportEndpointMaterializationResultState,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_endpoint_materialization_policy,
)

MATERIALIZATION_NOW = LEASE_NOW + timedelta(seconds=1)


class SelectiveAuditSink(CollectingAuditSink):
    def __init__(self, *, fail_suffix: str) -> None:
        super().__init__()
        self.fail_suffix = fail_suffix

    async def record(self, event: Any) -> None:
        if event.event_type.endswith(self.fail_suffix):
            raise RuntimeError("audit unavailable")
        await super().record(event)


class InMemoryEndpointMaterializationRepository:
    def __init__(self, *, source: Any, lease: Any) -> None:
        self.admission = source.admission
        self.binding = source.binding
        self.route = source.route
        self.head = source.head
        self.lease = lease
        self.now = MATERIALIZATION_NOW
        self.claims: dict[
            str, WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim
        ] = {}
        self.attempts: dict[str, WorkflowEventPhysicalTransportEndpointMaterializationAttempt] = {}
        self.results: dict[str, WorkflowEventPhysicalTransportEndpointMaterializationResult] = {}
        self.last_request: (
            WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest | None
        ) = None
        self.adapter_call_observed_claim = False
        self.force_result_conflict = False

    @property
    def durable(self) -> bool:
        return True

    async def get_authoritative_time(self) -> datetime:
        return self.now

    async def get_endpoint_resolution_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None:
        return self.lease if self.lease.authorization_lease_id == authorization_lease_id else None

    async def get_route_freshness_admission_by_id(self, *, freshness_admission_id: str) -> Any:
        return (
            self.admission
            if self.admission.freshness_admission_id == freshness_admission_id
            else None
        )

    async def get_physical_transport_route_binding_by_id(self, *, binding_id: str) -> Any:
        return self.binding if self.binding.binding_id == binding_id else None

    async def get_transport_route_snapshot_by_id(self, *, snapshot_id: str) -> Any:
        return self.route if self.route.snapshot_id == snapshot_id else None

    async def get_current_route_selection_head(
        self, *, scope: WorkflowScope, route_set_id: str
    ) -> Any:
        return (
            self.head
            if self.head.scope == scope and self.head.route_set_id == route_set_id
            else None
        )

    async def get_endpoint_materialization_claim_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim | None:
        return self.claims.get(authorization_lease_id)

    async def get_endpoint_materialization_attempt_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationAttempt | None:
        return self.attempts.get(authorization_lease_id)

    async def list_endpoint_materialization_attempts(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportEndpointMaterializationAttempt, ...]:
        return tuple(item for item in self.attempts.values() if item.scope == scope)[:limit]

    async def get_endpoint_materialization_result_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResult | None:
        return self.results.get(authorization_lease_id)

    async def claim_endpoint_materialization(
        self, request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationClaimResult:
        self.last_request = request
        prior = self.claims.get(request.authorization_lease_id)
        if prior is not None:
            exact = (
                prior.request_fingerprint == request.request_fingerprint
                and prior.idempotency_digest == request.idempotency_digest
                and prior.resolver_subject_id == request.resolver_subject_id
            )
            if not exact:
                return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.ALREADY_CONSUMED,
                    prior,
                    self.attempts[request.authorization_lease_id],
                    self.results.get(request.authorization_lease_id),
                )
            result = self.results.get(request.authorization_lease_id)
            return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                (
                    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.REPLAY_COMPLETED
                    if result is not None
                    else (
                        WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus
                    ).CLAIM_ONLY_UNCERTAIN
                ),
                prior,
                self.attempts[request.authorization_lease_id],
                result,
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
            self.lease.route_set_id,
            self.lease.route_set_revision,
            self.lease.selection_epoch_id,
            self.lease.selection_epoch_revision,
            self.lease.selected_route_id,
            self.lease.selected_route_revision,
            self.lease.selected_route_digest,
            self.head.selection_active,
            self.head.selection_eligible,
            self.head.selection_suspended,
            self.head.selection_withdrawn,
            self.head.selection_superseded,
            self.lease.state.value,
            self.lease.authority.endpoint_resolution_authorized,
            request.scope,
            request.resolver_subject_id,
        )
        expected = (
            request.expected_freshness_admission_id,
            request.expected_freshness_admission_digest,
            request.expected_freshness_valid_until,
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
            request.expected_lease_state,
            request.expected_endpoint_resolution_authorized,
            request.scope,
            request.resolver_subject_id,
        )
        policy = code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
        if (
            actual != expected
            or self.now >= min(self.admission.valid_until, self.lease.valid_until)
            or (
                request.expected_materialization_policy_id,
                request.expected_materialization_policy_version,
                request.expected_materialization_policy_digest,
            )
            != (policy.policy_id, policy.policy_version, policy.canonical_digest)
        ):
            return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.EVIDENCE_CONFLICT,
                None,
                None,
                None,
            )
        authority = WorkflowEventPhysicalTransportEndpointMaterializationAuthority()
        claim_values: dict[str, Any] = {
            "claim_id": request.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "freshness_admission_id": request.expected_freshness_admission_id,
            "freshness_admission_digest": request.expected_freshness_admission_digest,
            "attempt_id": request.attempt_id,
            "materialization_id": request.materialization_id,
            "scope": request.scope,
            "resolver_subject_id": request.resolver_subject_id,
            "claimed_at": self.now,
            "request_fingerprint": request.request_fingerprint,
            "idempotency_digest": request.idempotency_digest,
            "authority": authority,
        }
        claim_payload = {
            **claim_values,
            "scope": request.scope.canonical_value(),
            "claimed_at": self.now.isoformat(),
            "authority": authority.canonical_value(),
        }
        claim = WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim(
            **cast(Any, claim_values), canonical_digest=canonical_digest(claim_payload)
        )
        attempt_values: dict[str, Any] = {
            "attempt_id": request.attempt_id,
            "materialization_id": request.materialization_id,
            "consumption_claim_id": request.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "freshness_admission_id": request.expected_freshness_admission_id,
            "freshness_admission_digest": request.expected_freshness_admission_digest,
            "physical_transport_route_binding_id": (
                request.expected_physical_transport_route_binding_id
            ),
            "physical_transport_route_binding_digest": (
                request.expected_physical_transport_route_binding_digest
            ),
            "transport_route_snapshot_id": request.expected_transport_route_snapshot_id,
            "transport_route_snapshot_digest": (request.expected_transport_route_snapshot_digest),
            "current_selection_head_id": request.expected_current_selection_head_id,
            "current_selection_head_digest": request.expected_current_selection_head_digest,
            "current_selection_head_generation": (
                request.expected_current_selection_head_generation
            ),
            "current_selection_head_fencing_token_digest": (
                request.expected_current_selection_head_fencing_token_digest
            ),
            "scope": request.scope,
            "resolver_subject_id": request.resolver_subject_id,
            "policy_id": request.expected_materialization_policy_id,
            "policy_version": request.expected_materialization_policy_version,
            "policy_digest": request.expected_materialization_policy_digest,
            "started_at": self.now,
            "freshness_valid_until": request.expected_freshness_valid_until,
            "lease_valid_until": self.lease.valid_until,
            "state": (
                WorkflowEventPhysicalTransportEndpointMaterializationAttemptState.MATERIALIZATION_STARTED
            ),
            "authority": authority,
        }
        attempt_payload = {
            **attempt_values,
            "scope": request.scope.canonical_value(),
            "started_at": self.now.isoformat(),
            "freshness_valid_until": request.expected_freshness_valid_until.isoformat(),
            "lease_valid_until": self.lease.valid_until.isoformat(),
            "state": attempt_values["state"].value,
            "authority": authority.canonical_value(),
        }
        attempt = WorkflowEventPhysicalTransportEndpointMaterializationAttempt(
            **cast(Any, attempt_values), canonical_digest=canonical_digest(attempt_payload)
        )
        self.claims[request.authorization_lease_id] = claim
        self.attempts[request.authorization_lease_id] = attempt
        return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
            WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.CLAIMED,
            claim,
            attempt,
            None,
        )

    async def record_endpoint_materialization_result(
        self, request: WorkflowEventPhysicalTransportEndpointMaterializationResultRequest
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResultWrite:
        if self.force_result_conflict:
            return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.CONFLICT,
                None,
            )
        prior = self.results.get(request.result.authorization_lease_id)
        if prior is not None:
            return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                (
                    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.REPLAY
                    if prior.canonical_digest == request.result.canonical_digest
                    else WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.CONFLICT
                ),
                prior,
            )
        claim = self.claims[request.result.authorization_lease_id]
        attempt = self.attempts[request.result.authorization_lease_id]
        if (
            claim.canonical_digest != request.expected_claim_digest
            or attempt.canonical_digest != request.expected_attempt_digest
        ):
            return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.CONFLICT,
                None,
            )
        self.results[request.result.authorization_lease_id] = request.result
        return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
            WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.RECORDED,
            request.result,
        )


class ObservingSyntheticMaterializer(SyntheticWorkflowPhysicalTransportEndpointMaterializer):
    def __init__(
        self, repository: InMemoryEndpointMaterializationRepository, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.repository = repository

    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportEndpointMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationReceipt:
        self.repository.adapter_call_observed_claim = (
            instruction.authorization_lease_id in self.repository.claims
        )
        return await super().materialize(instruction)


class ExplodingMaterializer(ObservingSyntheticMaterializer):
    async def materialize(
        self, instruction: WorkflowEventPhysicalTransportEndpointMaterializationInstruction
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationReceipt:
        self.repository.adapter_call_observed_claim = (
            instruction.authorization_lease_id in self.repository.claims
        )
        self.calls.append(instruction)
        raise RuntimeError("synthetic protected boundary lost")


async def fixture(
    *,
    materializer_factory: Any = ObservingSyntheticMaterializer,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowEventPhysicalTransportEndpointMaterializationService,
    InMemoryEndpointMaterializationRepository,
    Any,
    CollectingAuditSink,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
]:
    sink = audit or CollectingAuditSink()
    authorization_service, authorization_repository, _ = await authorization_service_fixture(
        audit=sink
    )
    lease = await authorize(authorization_service, authorization_repository)
    route = authorization_repository.route
    route.__dict__.update(
        endpoint_set_id="endpoint-set.workflow-events.primary",
        endpoint_set_revision="9",
        destination_id="destination.workflow-events",
        destination_revision="5",
        routing_contract_id="routing-contract.workflow-events",
        routing_contract_revision="3",
        private_route_descriptor_commitment="3" * 64,
    )
    repository = InMemoryEndpointMaterializationRepository(
        source=authorization_repository,
        lease=lease,
    )
    materializer = materializer_factory(repository, clock=lambda: MATERIALIZATION_NOW)
    service = WorkflowEventPhysicalTransportEndpointMaterializationService(
        repository=cast(Any, repository), materializer=materializer, audit_sink=sink
    )
    return service, repository, materializer, sink, lease


async def materialize(
    service: WorkflowEventPhysicalTransportEndpointMaterializationService,
    lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    **changes: Any,
) -> WorkflowEventPhysicalTransportEndpointMaterializationResult:
    policy = code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
    values = {
        "authorization_lease_id": lease.authorization_lease_id,
        "authorization_lease_digest": lease.canonical_digest,
        "materialization_policy_id": policy.policy_id,
        "materialization_policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "endpoint-materialization-0001",
        "context": resolver_context(),
    }
    values.update(changes)
    return await service.materialize(**cast(Any, values))


@pytest.mark.asyncio
async def test_claims_before_materializer_and_records_minimized_success() -> None:
    service, repository, materializer, audit, lease = await fixture()

    result = await materialize(service, lease)

    assert service.repository is repository
    assert service.durable is True
    assert repository.adapter_call_observed_claim is True
    assert len(materializer.calls) == 1
    assert result.state is (
        WorkflowEventPhysicalTransportEndpointMaterializationResultState.MATERIALIZED_PROTECTED
    )
    assert not any(result.authority.canonical_value().values())
    assert len(result.authority.canonical_value()) == 10
    assert await repository.list_endpoint_materialization_attempts(scope=lease.scope, limit=10) == (
        repository.attempts[lease.authorization_lease_id],
    )
    assert [record.event_type.rsplit(".", 1)[-1] for record in audit.records[-3:]] == [
        "requested",
        "claimed",
        "completed",
    ]
    assert not {
        "hostname",
        "url",
        "ip_address",
        "port",
        "credential",
        "secret",
        "provider_payload",
    } & set(vars(type(result)).keys())


@pytest.mark.asyncio
async def test_exact_completed_replay_returns_same_result_without_adapter_retry() -> None:
    service, _, materializer, _, lease = await fixture()
    first = await materialize(service, lease)

    second = await materialize(service, lease)

    assert second == first
    assert len(materializer.calls) == 1


@pytest.mark.asyncio
async def test_claim_only_is_uncertain_and_never_retried() -> None:
    service, repository, materializer, _, lease = await fixture(
        materializer_factory=ExplodingMaterializer
    )

    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointMaterializationUncertainError,
        match="endpoint_materialization_outcome_uncertain",
    ):
        await materialize(service, lease)
    assert lease.authorization_lease_id in repository.claims
    assert lease.authorization_lease_id not in repository.results

    with pytest.raises(WorkflowEventPhysicalTransportEndpointMaterializationUncertainError):
        await materialize(service, lease)
    assert len(materializer.calls) == 1


@pytest.mark.asyncio
async def test_known_failure_is_append_only_result_with_no_artifact() -> None:
    def failed(
        repository: InMemoryEndpointMaterializationRepository, **kwargs: Any
    ) -> ObservingSyntheticMaterializer:
        return ObservingSyntheticMaterializer(
            repository,
            failure_class=(
                WorkflowEventPhysicalTransportEndpointMaterializationFailureClass.ENDPOINT_SET_INVALID
            ),
            **kwargs,
        )

    service, repository, _, _, lease = await fixture(materializer_factory=failed)

    result = await materialize(service, lease)

    assert result.state is (
        WorkflowEventPhysicalTransportEndpointMaterializationResultState.MATERIALIZATION_FAILED
    )
    assert result.protected_artifact_id is None
    assert result.protected_artifact_revoked is True
    assert repository.results[lease.authorization_lease_id] == result


@pytest.mark.asyncio
async def test_unavailable_materializer_fails_before_consumption() -> None:
    authorization_service, authorization_repository, audit = await authorization_service_fixture()
    lease = await authorize(authorization_service, authorization_repository)
    repository = InMemoryEndpointMaterializationRepository(
        source=authorization_repository, lease=lease
    )
    service = WorkflowEventPhysicalTransportEndpointMaterializationService(
        repository=cast(Any, repository),
        materializer=UnavailableWorkflowPhysicalTransportEndpointMaterializer(),
        audit_sink=audit,
    )

    with pytest.raises(
        WorkflowEventPhysicalTransportEndpointMaterializationError,
        match="endpoint_materialization_trusted_materializer_unavailable",
    ):
        await materialize(service, lease)
    assert repository.claims == {}


@pytest.mark.asyncio
async def test_wrong_audience_subject_or_missing_ack_fails_before_claim() -> None:
    service, repository, _, _, lease = await fixture()

    for changes in (
        {"context": resolver_context(audience="audience.other")},
        {"context": resolver_context(subject_id="service.other-resolver")},
        {"irreversible_consumption_acknowledged": False},
        {"uncertain_outcome_requires_new_authorization_acknowledged": False},
    ):
        with pytest.raises(WorkflowEventPhysicalTransportEndpointMaterializationError):
            await materialize(service, lease, **changes)
    assert repository.claims == {}


@pytest.mark.asyncio
async def test_late_receipt_and_result_conflict_remain_consumed_and_uncertain() -> None:
    service, repository, materializer, _, lease = await fixture()
    materializer._clock = lambda: lease.valid_until

    with pytest.raises(WorkflowEventPhysicalTransportEndpointMaterializationUncertainError):
        await materialize(service, lease)
    assert lease.authorization_lease_id in repository.claims
    assert lease.authorization_lease_id not in repository.results

    service2, repository2, _, _, lease2 = await fixture()
    repository2.force_result_conflict = True
    with pytest.raises(WorkflowEventPhysicalTransportEndpointMaterializationUncertainError):
        await materialize(service2, lease2)
    assert lease2.authorization_lease_id in repository2.claims


@pytest.mark.asyncio
async def test_audit_failure_respects_the_point_of_no_return() -> None:
    requested_audit = SelectiveAuditSink(fail_suffix=".requested")
    service, repository, _, _, lease = await fixture(audit=requested_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await materialize(service, lease)
    assert repository.claims == {}

    claimed_audit = SelectiveAuditSink(fail_suffix=".claimed")
    service, repository, materializer, _, lease = await fixture(audit=claimed_audit)
    with pytest.raises(WorkflowEventPhysicalTransportEndpointMaterializationUncertainError):
        await materialize(service, lease)
    assert lease.authorization_lease_id in repository.claims
    assert materializer.calls == []

    completion_audit = SelectiveAuditSink(fail_suffix=".completed")
    service, repository, materializer, _, lease = await fixture(audit=completion_audit)
    with pytest.raises(WorkflowEventPhysicalTransportEndpointMaterializationUncertainError):
        await materialize(service, lease)
    assert lease.authorization_lease_id in repository.claims
    assert lease.authorization_lease_id not in repository.results
    assert len(materializer.calls) == 1


def test_public_contract_exposes_no_coordinate_or_consumption_api() -> None:
    parameters = inspect.signature(
        WorkflowEventPhysicalTransportEndpointMaterializationService.materialize
    ).parameters
    assert set(parameters) == {
        "self",
        "authorization_lease_id",
        "authorization_lease_digest",
        "materialization_policy_id",
        "materialization_policy_version",
        "irreversible_consumption_acknowledged",
        "uncertain_outcome_requires_new_authorization_acknowledged",
        "idempotency_key",
        "context",
    }
    assert not hasattr(
        WorkflowEventPhysicalTransportEndpointMaterializationService,
        "consume",
    )
