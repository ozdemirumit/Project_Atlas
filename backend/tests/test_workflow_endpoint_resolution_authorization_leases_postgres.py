from __future__ import annotations

import asyncio
import inspect
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from test_workflow_physical_transport_route_bindings_postgres import (
    _integration_request as physical_binding_request,
)
from test_workflow_physical_transport_route_bindings_postgres import (
    _integration_sources,
    _reset_integration_rows,
    _seed_integration_sources,
)
from test_workflow_route_freshness_admissions import CollectingAuditSink
from test_workflow_route_freshness_admissions_postgres import (
    _context as freshness_context,
)
from test_workflow_route_freshness_admissions_postgres import (
    _reset_freshness_rows,
    _selection_head,
)

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionService,
    WorkflowPhysicalTransportEndpointResolverContext,
)
from atlas.modules.workflows.domain import (
    WorkflowScope,
    code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy,
    code_owned_workflow_event_physical_transport_route_freshness_policy,
)


def _resolver_context(
    scope: WorkflowScope,
    requested_at: datetime,
) -> WorkflowPhysicalTransportEndpointResolverContext:
    return WorkflowPhysicalTransportEndpointResolverContext(
        subject_id="service.workflow-physical-transport-endpoint-resolver",
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
        scope=scope,
        correlation_id="correlation.endpoint-resolution-authorization-postgres.0001",
        decision_id="decision.endpoint-resolution-authorization-postgres.0001",
        requested_at=requested_at,
    )


async def _reset_endpoint_resolution_authorization_rows(
    engine: AsyncEngine,
    *,
    freshness_admission_id: str,
) -> None:
    statements = (
        "DELETE FROM workflow_event_endpoint_resolution_authorization_lease_claims "
        "WHERE freshness_admission_id = :freshness_admission_id",
        "DELETE FROM workflow_event_endpoint_resolution_authorization_leases "
        "WHERE freshness_admission_id = :freshness_admission_id",
    )
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for statement in statements:
            await connection.execute(
                text(statement),
                {"freshness_admission_id": freshness_admission_id},
            )


def test_schema_keeps_lease_and_acquisition_claim_immutable_and_minimized() -> None:
    lease_table = cast(
        Table,
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.__table__,
    )
    claim_table = cast(
        Table,
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel.__table__,
    )
    lease_unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in lease_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    claim_unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in claim_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("freshness_admission_id",) in lease_unique_columns
    assert ("authorization_lease_id",) in claim_unique_columns
    assert ("idempotency_scope_id", "idempotency_key") in claim_unique_columns
    assert "endpoint_resolution_authority_granted" in lease_table.columns
    forbidden = {
        "endpoint",
        "url",
        "hostname",
        "ip_address",
        "port",
        "topic",
        "stream",
        "queue",
        "locator",
        "credential_reference",
        "secret_reference",
        "certificate",
        "provider_message",
        "consumed_at",
    }
    assert not forbidden & (set(lease_table.columns.keys()) | set(claim_table.columns.keys()))


def test_repository_locks_binding_route_head_and_freshness_before_atomic_insert() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.authorize_endpoint_resolution)
    lock = source.index("_lock_endpoint_resolution_authorization_sources")
    evidence = source.index("_endpoint_resolution_authorization_evidence_matches", lock)
    observed = source.index("observed_at", lock)
    lease_add = source.index("session.add(self._endpoint_resolution_authorization_lease_model")
    lease_flush = source.index("await session.flush()", lease_add)
    claim_add = source.index("_endpoint_resolution_authorization_lease_claim_model", lease_flush)
    commit = source.index("await session.commit()", claim_add)
    assert lock < observed < evidence < lease_add < lease_flush < claim_add < commit

    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_endpoint_resolution_authorization_sources
    )
    positions = [
        lock_source.index("binding_row ="),
        lock_source.index("route_row ="),
        lock_source.index("head_rows ="),
        lock_source.index("freshness_row ="),
    ]
    assert positions == sorted(positions)
    assert lock_source.count(".with_for_update()") == 4


def test_migration_is_linear_bounded_and_append_only() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0124_workflow_endpoint_resolution_authorization_leases.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260814_0124"' in migration
    assert 'down_revision: str | None = "20260814_0123"' in migration
    assert "valid_until = issued_at + INTERVAL '15 seconds'" in migration
    assert "uq_wf_endpoint_res_lease_freshness" in migration
    assert "uq_wf_endpoint_res_claim_scope_idem" in migration
    assert "trg_wf_endpoint_res_lease_append_only" in migration
    assert "trg_wf_endpoint_res_claim_append_only" in migration
    assert "reject_endpoint_resolution_authorization_mutation" in migration


@pytest.mark.asyncio
async def test_unavailable_production_adapter_fails_closed() -> None:
    repository = UnavailableWorkflowPlanRepository()
    with pytest.raises(WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError):
        await repository.get_authoritative_time()


@pytest.mark.asyncio
async def test_live_postgres_serializes_replay_and_rejects_mutation() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    binding_request = physical_binding_request()
    route = _integration_sources()[3]
    head = _selection_head(route)
    repository = PostgreSQLWorkflowPlanRepository(engine=engine)
    freshness_admission_id = "freshness-admission.endpoint-resolution-postgres"
    try:
        await _reset_endpoint_resolution_authorization_rows(
            engine,
            freshness_admission_id=freshness_admission_id,
        )
        await _reset_freshness_rows(
            engine,
            binding_id=binding_request.candidate.binding_id,
            head_id=head.head_id,
        )
        await _reset_integration_rows(engine, binding_request)
        await _seed_integration_sources(engine, binding_request)
        bound = await repository.bind_physical_transport_route(binding_request)
        assert bound.binding == binding_request.candidate
        await repository.synchronize_route_selection_heads((head,))

        freshness_service = WorkflowEventPhysicalTransportRouteFreshnessAdmissionService(
            admission_repository=repository,
            audit_sink=CollectingAuditSink(),
        )
        freshness_policy = code_owned_workflow_event_physical_transport_route_freshness_policy()
        requested_at = datetime.now(UTC)
        admission = await freshness_service.admit(
            physical_transport_route_binding_id=binding_request.candidate.binding_id,
            physical_transport_route_binding_digest=binding_request.candidate.canonical_digest,
            policy_id=freshness_policy.policy_id,
            policy_version=freshness_policy.policy_version,
            idempotency_key="endpoint-resolution-postgres-freshness-0001",
            context=freshness_context(binding_request.scope, requested_at),
        )
        freshness_admission_id = admission.freshness_admission_id

        service = WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService(
            authorization_repository=repository,
            audit_sink=CollectingAuditSink(),
        )
        policy = (
            code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy()
        )

        async def authorize() -> object:
            return await service.authorize(
                freshness_admission_id=admission.freshness_admission_id,
                freshness_admission_digest=admission.canonical_digest,
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                idempotency_key="endpoint-resolution-authorization-postgres-0001",
                context=_resolver_context(binding_request.scope, requested_at),
            )

        first, second = await asyncio.gather(authorize(), authorize())
        assert first == second

        async with engine.connect() as connection:
            lease_count = await connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM workflow_event_endpoint_resolution_authorization_leases "
                    "WHERE freshness_admission_id = :freshness_admission_id"
                ),
                {"freshness_admission_id": admission.freshness_admission_id},
            )
            claim_count = await connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM workflow_event_endpoint_resolution_authorization_lease_claims "
                    "WHERE freshness_admission_id = :freshness_admission_id"
                ),
                {"freshness_admission_id": admission.freshness_admission_id},
            )
        assert lease_count == claim_count == 1

        mutations = (
            "UPDATE workflow_event_endpoint_resolution_authorization_leases "
            "SET state = state WHERE freshness_admission_id = :freshness_admission_id",
            "DELETE FROM workflow_event_endpoint_resolution_authorization_lease_claims "
            "WHERE freshness_admission_id = :freshness_admission_id",
        )
        for statement in mutations:
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(statement),
                        {"freshness_admission_id": admission.freshness_admission_id},
                    )
    finally:
        await _reset_endpoint_resolution_authorization_rows(
            engine,
            freshness_admission_id=freshness_admission_id,
        )
        await _reset_freshness_rows(
            engine,
            binding_id=binding_request.candidate.binding_id,
            head_id=head.head_id,
        )
        await _reset_integration_rows(engine, binding_request)
        await engine.dispose()
