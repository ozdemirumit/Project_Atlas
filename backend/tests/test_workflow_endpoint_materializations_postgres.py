from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Table, UniqueConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel,
    WorkflowEventPhysicalTransportEndpointMaterializationResultModel,
    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowEventPhysicalTransportEndpointMaterializationError,
)
from atlas.modules.workflows.domain import WorkflowScope


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_schema_is_single_use_one_to_one_append_only_and_minimized() -> None:
    claim = cast(
        Table,
        WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel.__table__,
    )
    attempt = cast(
        Table,
        WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel.__table__,
    )
    result = cast(
        Table,
        WorkflowEventPhysicalTransportEndpointMaterializationResultModel.__table__,
    )

    assert ("authorization_lease_id",) in _unique_columns(claim)
    assert ("attempt_id",) in _unique_columns(claim)
    assert ("consumption_claim_id",) in _unique_columns(attempt)
    assert ("authorization_lease_id",) in _unique_columns(attempt)
    assert ("attempt_id",) in _unique_columns(result)
    assert ("consumption_claim_id",) in _unique_columns(result)
    assert ("authorization_lease_id",) in _unique_columns(result)
    assert "consumed_at" not in claim.columns
    assert "state" not in claim.columns

    forbidden = {
        "endpoint",
        "hostname",
        "url",
        "ip_address",
        "port",
        "locator",
        "credential",
        "secret",
        "certificate",
        "private_route_descriptor",
        "provider_payload",
        "provider_message",
    }
    persisted = set(claim.columns) | set(attempt.columns) | set(result.columns)
    assert not forbidden & persisted


def test_claim_transaction_uses_fixed_lock_order_database_time_and_atomic_pair() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.claim_endpoint_materialization)
    lock = source.index("_lock_endpoint_materialization_sources")
    clock = source.index("clock_timestamp", lock)
    replay = source.index("_endpoint_materialization_claim_replay", clock)
    claim_add = source.index("session.add(self._endpoint_materialization_claim_model")
    flush = source.index("await session.flush()", claim_add)
    attempt_add = source.index("session.add(self._endpoint_materialization_attempt_model", flush)
    commit = source.index("await session.commit()", attempt_add)
    assert lock < clock < replay < claim_add < flush < attempt_add < commit
    assert "func.now" not in source

    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_endpoint_materialization_sources
    )
    positions = [
        lock_source.index("binding_row ="),
        lock_source.index("route_row ="),
        lock_source.index("head_rows ="),
        lock_source.index("freshness_row ="),
        lock_source.index("lease_row ="),
    ]
    assert positions == sorted(positions)
    assert lock_source.count(".with_for_update()") == 5


def test_result_insert_relocks_retimes_and_never_updates_evidence() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.record_endpoint_materialization_result
    )
    lock = source.index("_lock_endpoint_materialization_result_sources")
    clock = source.index("clock_timestamp", lock)
    evidence = source.index("_endpoint_materialization_result_evidence_matches", clock)
    add = source.index("session.add(self._endpoint_materialization_result_model", evidence)
    commit = source.index("await session.commit()", add)
    assert lock < clock < evidence < add < commit
    assert "func.now" not in source
    assert "update(" not in source
    assert "delete(" not in source


def test_human_attempt_inventory_is_scope_bounded_and_does_not_join_results() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.list_endpoint_materialization_attempts
    )
    assert "organization_id" in source
    assert "environment_id" in source
    assert "site_id" in source
    assert ".limit(capped)" in source
    assert "MaterializationResultModel" not in source
    assert "protected_artifact" not in source


def test_migration_is_linear_three_table_append_only_evidence() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0125_workflow_endpoint_materialization_consumption.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260814_0125"' in migration
    assert 'down_revision: str | None = "20260814_0124"' in migration
    assert migration.count("op.create_table(") == 3
    assert "uq_wf_endpoint_consume_claim_lease" in migration
    assert "uq_wf_endpoint_mat_attempt_claim" in migration
    assert "uq_wf_endpoint_mat_result_attempt" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "trg_wf_endpoint_consume_claim_append_only" in migration
    assert "trg_wf_endpoint_mat_attempt_append_only" in migration
    assert "trg_wf_endpoint_mat_result_append_only" in migration


@pytest.mark.asyncio
async def test_production_unavailable_adapter_fails_closed_and_memory_is_not_durable() -> None:
    unavailable = UnavailableWorkflowPlanRepository()
    with pytest.raises(WorkflowEventPhysicalTransportEndpointMaterializationError):
        await unavailable.list_endpoint_materialization_attempts(
            scope=WorkflowScope("org", "environment", "site"), limit=10
        )
    assert InMemoryWorkflowPlanRepository().durable is False


@pytest.mark.asyncio
async def test_live_postgres_has_three_append_only_tables_when_dsn_is_configured() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            tables = await connection.execute(
                text(
                    "SELECT to_regclass(name) FROM unnest(ARRAY["
                    "'workflow_event_endpoint_resolution_lease_consumption_claims',"
                    "'workflow_event_endpoint_materialization_attempts',"
                    "'workflow_event_endpoint_materialization_results']) AS name"
                )
            )
            triggers = await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal "
                    "AND tgname IN ('trg_wf_endpoint_consume_claim_append_only', "
                    "'trg_wf_endpoint_mat_attempt_append_only', "
                    "'trg_wf_endpoint_mat_result_append_only')"
                )
            )
        assert all(value is not None for value in tables.scalars())
        assert triggers == 3
    finally:
        await engine.dispose()
