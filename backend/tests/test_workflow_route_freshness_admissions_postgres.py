from __future__ import annotations

import asyncio
import inspect
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

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

from atlas.core.persistence.models import (
    DeploymentEventTransportRouteSelectionHeadHistoryModel,
    DeploymentEventTransportRouteSelectionHeadModel,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionError,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionService,
    WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    EventPhysicalTransportRouteSnapshot,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_route_freshness_policy,
)


def _selection_head(
    route: EventPhysicalTransportRouteSnapshot,
    *,
    generation: int = 1,
    fencing_token_digest: str = "7" * 64,
) -> DeploymentEventTransportRouteSelectionHead:
    values: dict[str, object] = {
        "head_id": f"transport-route-selection-head.{route.route_set_id}",
        "generation": generation,
        "route_set_id": route.route_set_id,
        "route_set_revision": route.route_set_revision,
        "selection_epoch_id": route.selection_epoch_id,
        "selection_epoch_revision": route.selection_epoch_revision,
        "selected_route_id": route.route_id,
        "selected_route_revision": route.route_revision,
        "selected_route_digest": route.source_route_digest,
        "fencing_token_digest": fencing_token_digest,
        "selection_active": True,
        "selection_eligible": True,
        "selection_suspended": False,
        "selection_withdrawn": False,
        "selection_superseded": False,
        "scope": route.scope,
        "current": True,
    }
    payload = {
        key: value.canonical_value() if isinstance(value, WorkflowScope) else value
        for key, value in values.items()
    }
    return DeploymentEventTransportRouteSelectionHead(
        **cast(Any, values),
        canonical_digest=canonical_digest(payload),
    )


def _context(
    scope: WorkflowScope, requested_at: datetime
) -> WorkflowPhysicalTransportRouteFreshnessAdmitterContext:
    return WorkflowPhysicalTransportRouteFreshnessAdmitterContext(
        subject_id="service.workflow-physical-route-freshness-admitter",
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
        scope=scope,
        correlation_id="correlation.route-freshness-postgres.0001",
        decision_id="decision.route-freshness-postgres.0001",
        requested_at=requested_at,
    )


async def _reset_freshness_rows(
    engine: AsyncEngine,
    *,
    binding_id: str,
    head_id: str,
) -> None:
    statements = (
        "DELETE FROM workflow_event_route_freshness_admission_claims "
        "WHERE physical_transport_route_binding_id = :binding_id",
        "DELETE FROM workflow_event_physical_transport_route_freshness_admissions "
        "WHERE physical_transport_route_binding_id = :binding_id",
        "DELETE FROM deployment_event_transport_route_selection_head_history "
        "WHERE head_id = :head_id",
        "DELETE FROM deployment_event_transport_route_selection_heads WHERE head_id = :head_id",
    )
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for statement in statements:
            await connection.execute(
                text(statement),
                {"binding_id": binding_id, "head_id": head_id},
            )


def test_schema_separates_mutable_head_and_append_only_admission_evidence() -> None:
    head_table = cast(Table, DeploymentEventTransportRouteSelectionHeadModel.__table__)
    history_table = cast(
        Table,
        DeploymentEventTransportRouteSelectionHeadHistoryModel.__table__,
    )
    admission_table = cast(
        Table,
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.__table__,
    )
    claim_table = cast(
        Table,
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel.__table__,
    )
    assert "fencing_token_digest" in head_table.columns
    assert "current_selection_head_fencing_token_digest" in admission_table.columns
    assert "current_selection_head_fencing_token_digest" in claim_table.columns
    assert "generation" in history_table.columns
    head_unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in head_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("organization_id", "environment_id", "site_id", "route_set_id") in (head_unique_columns)
    forbidden = {
        "endpoint",
        "url",
        "hostname",
        "credential",
        "secret",
        "readiness_result",
        "provider_message",
        "publication_attempt",
        "delivery_receipt",
    }
    names = (
        set(head_table.columns.keys())
        | set(history_table.columns.keys())
        | set(admission_table.columns.keys())
        | set(claim_table.columns.keys())
    )
    assert not forbidden & names


def test_repository_locks_binding_route_and_head_before_atomic_insert() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.admit_physical_transport_route_freshness
    )
    lock = source.index("_lock_route_freshness_sources")
    evidence = source.index("_route_freshness_admission_evidence_matches", lock)
    observed = source.index("observed_at", evidence)
    admission_add = source.index("session.add(self._route_freshness_admission_model", observed)
    admission_flush = source.index("await session.flush()", admission_add)
    claim_add = source.index("session.add(self._route_freshness_admission_claim_model")
    commit = source.index("await session.commit()", claim_add)
    assert lock < evidence < observed < admission_add < admission_flush < claim_add < commit

    lock_source = inspect.getsource(PostgreSQLWorkflowPlanRepository._lock_route_freshness_sources)
    positions = [
        lock_source.index("binding_row ="),
        lock_source.index("route_row ="),
        lock_source.index("head_rows ="),
    ]
    assert positions == sorted(positions)
    assert lock_source.count(".with_for_update()") == 3


def test_migration_is_linear_and_enforces_fenced_history_and_append_only_rows() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0123_workflow_route_freshness_admissions.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260814_0123"' in migration
    assert 'down_revision: str | None = "20260814_0122"' in migration
    assert "trg_deployment_route_head_sync" in migration
    assert "trg_deployment_route_head_history" in migration
    assert "generation must increase" in migration
    assert "fencing token must change" in migration
    assert "trg_route_head_history_append_only" in migration
    assert "trg_route_fresh_admission_append_only" in migration
    assert "trg_route_fresh_claim_append_only" in migration


@pytest.mark.asyncio
async def test_unavailable_production_adapter_fails_closed() -> None:
    repository = UnavailableWorkflowPlanRepository()
    route = _integration_sources()[3]
    with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError):
        await repository.synchronize_route_selection_heads((_selection_head(route),))


@pytest.mark.asyncio
async def test_live_postgres_serializes_replay_and_fences_superseded_admission() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    binding_request = physical_binding_request()
    route = _integration_sources()[3]
    head = _selection_head(route)
    try:
        await _reset_freshness_rows(
            engine,
            binding_id=binding_request.candidate.binding_id,
            head_id=head.head_id,
        )
        await _reset_integration_rows(engine, binding_request)
        await _seed_integration_sources(engine, binding_request)
        repository = PostgreSQLWorkflowPlanRepository(engine=engine)
        bound = await repository.bind_physical_transport_route(binding_request)
        assert bound.binding == binding_request.candidate
        await repository.synchronize_route_selection_heads((head,))

        service = WorkflowEventPhysicalTransportRouteFreshnessAdmissionService(
            admission_repository=repository,
            audit_sink=CollectingAuditSink(),
        )
        policy = code_owned_workflow_event_physical_transport_route_freshness_policy()
        requested_at = datetime.now(UTC)

        async def admit() -> object:
            return await service.admit(
                physical_transport_route_binding_id=binding_request.candidate.binding_id,
                physical_transport_route_binding_digest=(
                    binding_request.candidate.canonical_digest
                ),
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                idempotency_key="route-freshness-postgres-integration-0001",
                context=_context(binding_request.scope, requested_at),
            )

        first, second = await asyncio.gather(admit(), admit())
        assert first == second

        advanced = _selection_head(
            route,
            generation=2,
            fencing_token_digest="8" * 64,
        )
        await repository.synchronize_route_selection_heads((advanced,))
        with pytest.raises(WorkflowEventPhysicalTransportRouteFreshnessAdmissionError) as error:
            await service.admit(
                physical_transport_route_binding_id=binding_request.candidate.binding_id,
                physical_transport_route_binding_digest=(
                    binding_request.candidate.canonical_digest
                ),
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                idempotency_key="route-freshness-postgres-integration-0001",
                context=_context(binding_request.scope, requested_at + timedelta(seconds=1)),
            )
        assert error.value.code.endswith("_not_current")

        async with engine.connect() as connection:
            admission_count = await connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM workflow_event_physical_transport_route_freshness_admissions "
                    "WHERE physical_transport_route_binding_id = :binding_id"
                ),
                {"binding_id": binding_request.candidate.binding_id},
            )
            claim_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_route_freshness_admission_claims "
                    "WHERE physical_transport_route_binding_id = :binding_id"
                ),
                {"binding_id": binding_request.candidate.binding_id},
            )
            history_count = await connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM deployment_event_transport_route_selection_head_history "
                    "WHERE head_id = :head_id"
                ),
                {"head_id": head.head_id},
            )
        assert admission_count == claim_count == 1
        assert history_count == 2

        mutations = (
            (
                "UPDATE workflow_event_physical_transport_route_freshness_admissions "
                "SET state = state WHERE physical_transport_route_binding_id = :binding_id",
                {"binding_id": binding_request.candidate.binding_id},
            ),
            (
                "DELETE FROM workflow_event_route_freshness_admission_claims "
                "WHERE physical_transport_route_binding_id = :binding_id",
                {"binding_id": binding_request.candidate.binding_id},
            ),
            (
                "UPDATE deployment_event_transport_route_selection_head_history "
                "SET generation = generation WHERE head_id = :head_id",
                {"head_id": head.head_id},
            ),
            (
                "UPDATE deployment_event_transport_route_selection_heads "
                "SET generation = generation WHERE head_id = :head_id",
                {"head_id": head.head_id},
            ),
        )
        for statement, parameters in mutations:
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(text(statement), parameters)
    finally:
        await _reset_freshness_rows(
            engine,
            binding_id=binding_request.candidate.binding_id,
            head_id=head.head_id,
        )
        await _reset_integration_rows(engine, binding_request)
        await engine.dispose()
