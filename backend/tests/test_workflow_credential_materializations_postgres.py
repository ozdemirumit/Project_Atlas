from __future__ import annotations

import asyncio
import inspect
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from test_workflow_credential_access_authorization_leases_postgres import (
    _context,
    _reset_authorization_rows,
)
from test_workflow_route_freshness_admissions import CollectingAuditSink
from test_workflow_transport_credential_assignment_bindings_postgres import (
    _request as credential_binding_request,
)
from test_workflow_transport_credential_assignment_bindings_postgres import (
    _seed_live_sources as seed_binding_sources,
)
from test_workflow_transport_credential_assignment_freshness_admissions_postgres import (
    _admission_request,
    _head,
    _reset_live,
)

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel,
    WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel,
    WorkflowEventPhysicalTransportCredentialMaterializationResultModel,
)
from atlas.modules.workflows.adapters.credential_materialization_synthetic import (
    SyntheticWorkflowPhysicalTransportCredentialMaterializer,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
    WorkflowEventPhysicalTransportCredentialMaterializationError,
    WorkflowEventPhysicalTransportCredentialMaterializationService,
    WorkflowEventPhysicalTransportCredentialMaterializationUncertainError,
)
from atlas.modules.workflows.domain import (
    WorkflowScope,
    code_owned_workflow_event_physical_transport_credential_access_authorization_policy,
    code_owned_workflow_event_physical_transport_credential_materialization_policy,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260815_0130_workflow_credential_materialization_consumption.py"
)


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_schema_is_single_use_append_only_minimized_and_zero_authority() -> None:
    claim = cast(
        Table,
        WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel.__table__,
    )
    attempt = cast(
        Table,
        WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel.__table__,
    )
    result = cast(
        Table,
        WorkflowEventPhysicalTransportCredentialMaterializationResultModel.__table__,
    )
    assert ("authorization_lease_id",) in _unique_columns(claim)
    assert ("attempt_id",) in _unique_columns(claim)
    assert ("consumption_claim_id",) in _unique_columns(attempt)
    assert ("authorization_lease_id",) in _unique_columns(attempt)
    assert ("attempt_id",) in _unique_columns(result)
    assert ("consumption_claim_id",) in _unique_columns(result)
    assert ("authorization_lease_id",) in _unique_columns(result)

    forbidden = {
        "username",
        "password",
        "token",
        "private_key",
        "secret",
        "vault_path",
        "secret_reference",
        "provider_payload",
        "provider_handle",
        "endpoint",
        "hostname",
        "url",
        "ip_address",
        "port",
        "command",
        "environment_variable",
    }
    assert not forbidden & (set(claim.columns) | set(attempt.columns) | set(result.columns))
    for table in (claim, attempt, result):
        authority_columns = {
            column.name for column in table.columns if column.name.endswith("_authority_granted")
        }
        checks = "\n".join(
            str(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        )
        assert len(authority_columns) == 17
        assert all(f"NOT {name}" in checks for name in authority_columns)


def test_claim_uses_exact_lock_order_db_time_and_atomic_claim_attempt_pair() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.claim_credential_materialization)
    lock = source.index("_lock_credential_materialization_sources")
    clock = source.index("clock_timestamp", lock)
    replay = source.index("_credential_materialization_claim_replay", clock)
    evidence = source.index("_credential_materialization_evidence_matches", replay)
    claim_add = source.index("_credential_materialization_claim_model", evidence)
    flush = source.index("await session.flush()", claim_add)
    attempt_add = source.index("_credential_materialization_attempt_model", flush)
    commit = source.index("await session.commit()", attempt_add)
    assert lock < clock < replay < evidence < claim_add < flush < attempt_add < commit
    assert "func.now" not in source

    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_credential_materialization_sources
    )
    positions = [
        lock_source.index("binding_row ="),
        lock_source.index("snapshot_row ="),
        lock_source.index("pg_advisory_xact_lock"),
        lock_source.index("assignment_rows ="),
        lock_source.index("freshness_row ="),
        lock_source.index("lease_row ="),
    ]
    assert positions == sorted(positions)
    assert lock_source.count(".with_for_update()") == 5
    assert "clock_timestamp" not in lock_source
    assert "issued_at <= observed_at < lease.valid_until" in inspect.getsource(
        PostgreSQLWorkflowPlanRepository._credential_materialization_evidence_matches
    )


def test_result_relocks_retimes_appends_and_never_reopens_claim() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.record_credential_materialization_result
    )
    lock = source.index("_lock_credential_materialization_result_sources")
    clock = source.index("clock_timestamp", lock)
    evidence = source.index("_credential_materialization_result_evidence_matches", clock)
    add = source.index("_credential_materialization_result_model", evidence)
    commit = source.index("await session.commit()", add)
    assert lock < clock < evidence < add < commit
    assert "func.now" not in source
    assert "update(" not in source
    assert "delete(" not in source


def test_migration_is_linear_three_table_append_only_evidence() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260815_0130"' in migration
    assert 'down_revision: str | None = "20260815_0129"' in migration
    assert migration.count("op.create_table(") == 3
    assert "uq_wf_credential_consume_claim_lease" in migration
    assert "uq_wf_credential_mat_attempt_claim" in migration
    assert "uq_wf_credential_mat_result_attempt" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "trg_wf_credential_consume_claim_append_only" in migration
    assert "trg_wf_credential_mat_attempt_append_only" in migration
    assert "trg_wf_credential_mat_result_append_only" in migration
    assert migration.count("_authority_granted") >= 17
    for forbidden in (
        "vault_path",
        "secret_reference",
        "provider_handle",
        "endpoint_url",
        "raw_credential",
    ):
        assert forbidden not in migration


@pytest.mark.asyncio
async def test_unavailable_adapter_fails_closed_and_memory_is_not_durable() -> None:
    unavailable = UnavailableWorkflowPlanRepository()
    with pytest.raises(WorkflowEventPhysicalTransportCredentialMaterializationError):
        await unavailable.list_credential_materialization_attempts(
            scope=WorkflowScope("org-atlas", "environment-lab", "site-istanbul"), limit=10
        )
    assert InMemoryWorkflowPlanRepository().durable is False


async def _reset_materialization_rows(engine: AsyncEngine, *, authorization_lease_id: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for table in (
            "workflow_event_credential_materialization_results",
            "workflow_event_credential_materialization_attempts",
            "workflow_event_credential_access_lease_consumption_claims",
        ):
            await connection.execute(
                text(f"DELETE FROM {table} WHERE authorization_lease_id = :lease_id"),
                {"lease_id": authorization_lease_id},
            )


@pytest.mark.asyncio
async def test_live_postgres_serializes_single_use_and_rejects_mutation() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    requested_at = datetime.now(UTC)
    binding_request, route, snapshot = credential_binding_request(
        bound_at=requested_at - timedelta(seconds=2),
        idempotency_key="credential-binding-for-materialization-pg-0001",
        fingerprint="d" * 64,
    )
    binding = binding_request.candidate
    head = _head(route, snapshot)
    freshness_request = _admission_request(
        binding,
        snapshot,
        head,
        requested_at=requested_at,
        idempotency_key="credential-freshness-for-materialization-pg-0001",
    )
    freshness_id = freshness_request.candidate.freshness_admission_id
    engine = create_async_engine(database_url, pool_pre_ping=True)
    lease_id = ""
    try:
        await _reset_authorization_rows(engine, freshness_admission_id=freshness_id)
        await _reset_live(engine, binding_request, assignment_id=head.assignment_id)
        await seed_binding_sources(engine, route=route, assignments=(snapshot,))
        repository = PostgreSQLWorkflowPlanRepository(engine=engine)
        await repository.synchronize_credential_assignments((head,))
        bound = await repository.bind_credential_assignment(binding_request)
        assert bound.binding == binding
        admitted = await repository.admit_credential_assignment_freshness(freshness_request)
        admission = admitted.admission
        assert admission is not None

        authorization_service = (
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService(
                authorization_repository=repository,
                audit_sink=CollectingAuditSink(),
            )
        )
        authorization_policy = (
            code_owned_workflow_event_physical_transport_credential_access_authorization_policy()
        )
        lease = await authorization_service.authorize(
            freshness_admission_id=admission.freshness_admission_id,
            freshness_admission_digest=admission.canonical_digest,
            policy_id=authorization_policy.policy_id,
            policy_version=authorization_policy.policy_version,
            idempotency_key="credential-access-for-materialization-pg-0001",
            context=_context(binding.scope, datetime.now(UTC)),
        )
        lease_id = lease.authorization_lease_id
        materializer = SyntheticWorkflowPhysicalTransportCredentialMaterializer()
        materialization_service = WorkflowEventPhysicalTransportCredentialMaterializationService(
            repository=repository,
            materializer=materializer,
            audit_sink=CollectingAuditSink(),
        )
        materialization_policy = (
            code_owned_workflow_event_physical_transport_credential_materialization_policy()
        )

        async def materialize() -> object:
            return await materialization_service.materialize(
                authorization_lease_id=lease.authorization_lease_id,
                authorization_lease_digest=lease.canonical_digest,
                materialization_policy_id=materialization_policy.policy_id,
                materialization_policy_version=materialization_policy.policy_version,
                irreversible_consumption_acknowledged=True,
                uncertain_outcome_requires_new_authorization_acknowledged=True,
                idempotency_key="credential-materialization-postgres-0001",
                context=_context(binding.scope, datetime.now(UTC)),
            )

        outcomes = await asyncio.gather(materialize(), materialize(), return_exceptions=True)
        successful = [value for value in outcomes if not isinstance(value, BaseException)]
        uncertain = [
            value
            for value in outcomes
            if isinstance(
                value, WorkflowEventPhysicalTransportCredentialMaterializationUncertainError
            )
        ]
        assert successful
        assert len(successful) + len(uncertain) == 2
        assert len(materializer.calls) == 1

        async with engine.connect() as connection:
            counts = []
            for table in (
                "workflow_event_credential_access_lease_consumption_claims",
                "workflow_event_credential_materialization_attempts",
                "workflow_event_credential_materialization_results",
            ):
                counts.append(
                    await connection.scalar(
                        text(f"SELECT count(*) FROM {table} WHERE authorization_lease_id = :id"),
                        {"id": lease_id},
                    )
                )
        assert counts == [1, 1, 1]

        for statement in (
            "UPDATE workflow_event_credential_access_lease_consumption_claims "
            "SET claimed_at = claimed_at WHERE authorization_lease_id = :id",
            "DELETE FROM workflow_event_credential_materialization_attempts "
            "WHERE authorization_lease_id = :id",
            "UPDATE workflow_event_credential_materialization_results "
            "SET state = state WHERE authorization_lease_id = :id",
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(text(statement), {"id": lease_id})
    finally:
        if lease_id:
            await _reset_materialization_rows(engine, authorization_lease_id=lease_id)
        await _reset_authorization_rows(engine, freshness_admission_id=freshness_id)
        await _reset_live(engine, binding_request, assignment_id=head.assignment_id)
        await engine.dispose()
