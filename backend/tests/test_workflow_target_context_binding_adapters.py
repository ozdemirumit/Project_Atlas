from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application.target_context_binding_ports import (
    WorkflowEventPhysicalTransportTargetContextBindingError,
    WorkflowEventPhysicalTransportTargetContextBindingRequest,
    WorkflowEventPhysicalTransportTargetContextBindingStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_target_context_binding_policy,
)

NOW = datetime.now(UTC)
SCOPE = WorkflowScope("organization.atlas", "environment.test", "site.istanbul")
OTHER_SCOPE = WorkflowScope("organization.atlas", "environment.test", "site.ankara")


def evidence(
    *,
    endpoint_materialization_id: str = "endpoint-materialization.primary",
    credential_materialization_id: str = "credential-materialization.primary",
) -> tuple[Any, Any, Any, Any, Any, Any]:
    route_binding = SimpleNamespace(
        binding_id="physical-route-binding.primary",
        canonical_digest="1" * 64,
    )
    route_snapshot = SimpleNamespace(
        snapshot_id="transport-route-snapshot.primary",
        canonical_digest="2" * 64,
        destination_id="destination.primary",
        destination_revision="revision.1",
        endpoint_set_id="endpoint-set.primary",
        endpoint_set_revision="revision.1",
        routing_contract_id="routing-contract.primary",
        routing_contract_revision="revision.1",
        scope=SCOPE,
    )
    endpoint_result = SimpleNamespace(
        materialization_id=endpoint_materialization_id,
        canonical_digest="3" * 64,
        resolver_subject_id="service.endpoint-resolver",
        usable_until=NOW + timedelta(minutes=5),
    )
    credential_binding = SimpleNamespace(
        binding_id="credential-assignment-binding.primary",
        canonical_digest="4" * 64,
    )
    credential_snapshot = SimpleNamespace(
        snapshot_id="credential-assignment-snapshot.primary",
        canonical_digest="5" * 64,
    )
    credential_result = SimpleNamespace(
        materialization_id=credential_materialization_id,
        canonical_digest="6" * 64,
        accessor_subject_id="service.credential-accessor",
        usable_until=NOW + timedelta(minutes=4),
    )
    return cast(
        tuple[Any, Any, Any, Any, Any, Any],
        (
            route_binding,
            route_snapshot,
            endpoint_result,
            credential_binding,
            credential_snapshot,
            credential_result,
        ),
    )


def request(
    *,
    idempotency_key: str = "target-context-primary",
    request_fingerprint: str = "a" * 64,
    endpoint_materialization_id: str = "endpoint-materialization.primary",
    endpoint_materialization_digest: str = "3" * 64,
    credential_materialization_id: str = "credential-materialization.primary",
    credential_materialization_digest: str = "6" * 64,
    audit: Any = None,
) -> WorkflowEventPhysicalTransportTargetContextBindingRequest:
    policy = code_owned_workflow_event_physical_transport_target_context_binding_policy()

    async def successful_audit() -> None:
        return None

    return WorkflowEventPhysicalTransportTargetContextBindingRequest(
        expected_endpoint_materialization_id=endpoint_materialization_id,
        expected_endpoint_materialization_digest=endpoint_materialization_digest,
        expected_credential_materialization_id=credential_materialization_id,
        expected_credential_materialization_digest=credential_materialization_digest,
        expected_policy_id=policy.policy_id,
        expected_policy_version=policy.policy_version,
        expected_policy_digest=policy.canonical_digest,
        scope=SCOPE,
        binder_subject_id="service.target-context-binder",
        requested_at=NOW,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        required_precommit_audit=audit or successful_audit,
    )


def install_evidence(
    repository: InMemoryWorkflowPlanRepository,
    source_evidence: tuple[Any, Any, Any, Any, Any, Any],
) -> None:
    repository.__dict__["_target_context_binding_source_evidence"] = (
        lambda *, request, observed_at: source_evidence
    )


@pytest.mark.asyncio
async def test_memory_binding_is_atomic_replay_safe_scope_bounded_and_source_unique() -> None:
    repository = InMemoryWorkflowPlanRepository()
    source_evidence = evidence()
    install_evidence(repository, source_evidence)

    created = await repository.bind_target_context(request())
    replay = await repository.bind_target_context(request())
    changed_replay = await repository.bind_target_context(request(request_fingerprint="b" * 64))
    competing_pair = await repository.bind_target_context(
        request(idempotency_key="target-context-competing")
    )

    assert created.status is WorkflowEventPhysicalTransportTargetContextBindingStatus.BOUND
    assert created.binding is not None
    assert replay.status is WorkflowEventPhysicalTransportTargetContextBindingStatus.REPLAY
    assert replay.binding is created.binding
    assert (
        changed_replay.status
        is WorkflowEventPhysicalTransportTargetContextBindingStatus.IDEMPOTENCY_CONFLICT
    )
    assert (
        competing_pair.status
        is WorkflowEventPhysicalTransportTargetContextBindingStatus.ALREADY_BOUND
    )
    assert await repository.list_target_context_bindings(scope=SCOPE) == (created.binding,)
    assert await repository.list_target_context_bindings(scope=OTHER_SCOPE) == ()
    assert not any(created.binding.authority.canonical_value().values())
    assert created.binding.joint_usable_until == NOW + timedelta(minutes=4)

    policy = code_owned_workflow_event_physical_transport_target_context_binding_policy()
    route_binding, route_snapshot, endpoint_result, credential_binding, snapshot, result = (
        source_evidence
    )
    assert created.binding.target_context_commitment == canonical_digest(
        {
            "credential_assignment_snapshot_digest": snapshot.canonical_digest,
            "credential_assignment_snapshot_id": snapshot.snapshot_id,
            "credential_materialization_digest": result.canonical_digest,
            "credential_materialization_id": result.materialization_id,
            "destination_id": route_snapshot.destination_id,
            "destination_revision": route_snapshot.destination_revision,
            "endpoint_materialization_digest": endpoint_result.canonical_digest,
            "endpoint_materialization_id": endpoint_result.materialization_id,
            "endpoint_set_id": route_snapshot.endpoint_set_id,
            "endpoint_set_revision": route_snapshot.endpoint_set_revision,
            "physical_transport_credential_assignment_binding_digest": (
                credential_binding.canonical_digest
            ),
            "physical_transport_credential_assignment_binding_id": credential_binding.binding_id,
            "physical_transport_route_binding_digest": route_binding.canonical_digest,
            "physical_transport_route_binding_id": route_binding.binding_id,
            "routing_contract_id": route_snapshot.routing_contract_id,
            "routing_contract_revision": route_snapshot.routing_contract_revision,
            "scope": SCOPE.canonical_value(),
            "target_context_schema_id": policy.target_context_schema_id,
            "target_context_schema_version": policy.target_context_schema_version,
            "transport_route_snapshot_digest": route_snapshot.canonical_digest,
            "transport_route_snapshot_id": route_snapshot.snapshot_id,
        }
    )


@pytest.mark.asyncio
async def test_memory_binding_rolls_back_when_precommit_audit_fails() -> None:
    repository = InMemoryWorkflowPlanRepository()
    install_evidence(repository, evidence())

    async def failed_audit() -> None:
        raise RuntimeError("audit unavailable")

    denied = await repository.bind_target_context(request(audit=failed_audit))
    assert (
        denied.status
        is WorkflowEventPhysicalTransportTargetContextBindingStatus.PRECOMMIT_AUDIT_FAILED
    )
    assert await repository.list_target_context_bindings(scope=SCOPE) == ()

    recovered = await repository.bind_target_context(request())
    assert recovered.status is WorkflowEventPhysicalTransportTargetContextBindingStatus.BOUND


@pytest.mark.asyncio
async def test_memory_binding_fails_closed_without_complete_source_lineage() -> None:
    repository = InMemoryWorkflowPlanRepository()
    audit_called = False

    async def audit() -> None:
        nonlocal audit_called
        audit_called = True

    denied = await repository.bind_target_context(request(audit=audit))

    assert (
        denied.status is WorkflowEventPhysicalTransportTargetContextBindingStatus.EVIDENCE_CONFLICT
    )
    assert denied.binding is None
    assert audit_called is False


@pytest.mark.asyncio
async def test_unavailable_target_context_repository_fails_closed() -> None:
    repository = UnavailableWorkflowPlanRepository()

    assert repository.durable is False
    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as bind_error:
        await repository.bind_target_context(request())
    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as list_error:
        await repository.list_target_context_bindings(scope=SCOPE)

    assert bind_error.value.code == "workflow_target_context_binding_repository_unavailable"
    assert list_error.value.code == "workflow_target_context_binding_repository_unavailable"


@pytest.mark.asyncio
async def test_memory_target_context_inventory_rejects_invalid_limits() -> None:
    repository = InMemoryWorkflowPlanRepository()

    with pytest.raises(ValueError, match="target context binding limit"):
        await repository.list_target_context_bindings(scope=SCOPE, limit=0)
    with pytest.raises(ValueError, match="target context binding limit"):
        await repository.list_target_context_bindings(scope=SCOPE, limit=257)
