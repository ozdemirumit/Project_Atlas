from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import (
    CheckConstraint,
    Constraint,
    ForeignKeyConstraint,
    Index,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportTargetContextAccessConsumptionClaimModel,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttemptModel,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.domain import WorkflowScope

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260815_0133_workflow_target_context_artifact_opening.py"
)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
AUTHORITY_COLUMNS = (
    "route_selection_authority_granted",
    "route_binding_authority_granted",
    "endpoint_resolution_authority_granted",
    "protected_artifact_access_authority_granted",
    "credential_selection_authority_granted",
    "credential_assignment_binding_authority_granted",
    "credential_access_authority_granted",
    "credential_brokerage_authority_granted",
    "credential_resolution_authority_granted",
    "credential_delivery_authority_granted",
    "network_access_authority_granted",
    "readiness_probe_authority_granted",
    "publication_authority_granted",
    "delivery_authority_granted",
    "dispatch_authority_granted",
    "execution_authority_granted",
    "infrastructure_mutation_authority_granted",
)


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _constraint(table: Table, name: str) -> Constraint:
    return next(constraint for constraint in table.constraints if constraint.name == name)


def test_schema_is_append_only_single_use_and_zero_authority() -> None:
    claim = cast(
        Table,
        WorkflowEventPhysicalTransportTargetContextAccessConsumptionClaimModel.__table__,
    )
    attempt = cast(
        Table,
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttemptModel.__table__,
    )
    result = cast(
        Table,
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultModel.__table__,
    )
    assert claim.name == "workflow_event_tctx_access_consumption_claims"
    assert attempt.name == "workflow_event_tctx_artifact_opening_attempts"
    assert result.name == "workflow_event_tctx_artifact_opening_results"
    assert {
        ("idempotency_scope_id", "idempotency_key"),
        ("authorization_lease_id",),
        ("attempt_id",),
        ("opening_id",),
        ("canonical_digest",),
        (
            "claim_id",
            "authorization_lease_id",
            "attempt_id",
            "opening_id",
            "target_context_binding_id",
            "organization_id",
            "environment_id",
            "site_id",
        ),
    } <= _unique_columns(claim)
    assert {
        ("opening_id",),
        ("consumption_claim_id",),
        ("authorization_lease_id",),
        ("canonical_digest",),
        (
            "attempt_id",
            "consumption_claim_id",
            "authorization_lease_id",
            "opening_id",
            "target_context_binding_id",
            "organization_id",
            "environment_id",
            "site_id",
        ),
    } <= _unique_columns(attempt)
    assert {
        "request_nonce_digest",
        "opener_contract_id",
        "opener_attestor_id",
    } <= set(attempt.columns.keys())
    assert {
        ("attempt_id",),
        ("consumption_claim_id",),
        ("authorization_lease_id",),
        ("canonical_digest",),
    } <= _unique_columns(result)
    attempt_lineage = cast(
        ForeignKeyConstraint,
        _constraint(attempt, "fk_wf_tctx_open_attempt_claim_lineage"),
    )
    assert tuple(element.parent.name for element in attempt_lineage.elements) == (
        "consumption_claim_id",
        "authorization_lease_id",
        "attempt_id",
        "opening_id",
        "target_context_binding_id",
        "organization_id",
        "environment_id",
        "site_id",
    )
    assert tuple(element.target_fullname for element in attempt_lineage.elements) == (
        "workflow_event_tctx_access_consumption_claims.claim_id",
        "workflow_event_tctx_access_consumption_claims.authorization_lease_id",
        "workflow_event_tctx_access_consumption_claims.attempt_id",
        "workflow_event_tctx_access_consumption_claims.opening_id",
        "workflow_event_tctx_access_consumption_claims.target_context_binding_id",
        "workflow_event_tctx_access_consumption_claims.organization_id",
        "workflow_event_tctx_access_consumption_claims.environment_id",
        "workflow_event_tctx_access_consumption_claims.site_id",
    )
    result_lineage = cast(
        ForeignKeyConstraint,
        _constraint(result, "fk_wf_tctx_open_result_attempt_lineage"),
    )
    assert tuple(element.parent.name for element in result_lineage.elements) == (
        "attempt_id",
        "consumption_claim_id",
        "authorization_lease_id",
        "opening_id",
        "target_context_binding_id",
        "organization_id",
        "environment_id",
        "site_id",
    )
    assert {
        "consumption_authorization_audit_digest",
        "consumption_authorization_audit_payload",
    } <= set(claim.columns.keys())
    claim_checks = "\n".join(
        str(constraint.sqltext)
        for constraint in claim.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "consumption_authorization_audit_digest ~ '^[0-9a-f]{64}$'" in claim_checks
    assert "consumption_authorization_audit_payload <> '{}'::jsonb" in claim_checks
    for table in (claim, attempt, result):
        assert set(AUTHORITY_COLUMNS) <= set(table.columns.keys())
        checks = "\n".join(
            str(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        )
        assert all(f"NOT {column}" in checks for column in AUTHORITY_COLUMNS)
        schema_items: tuple[Constraint | Index, ...] = (*table.constraints, *table.indexes)
        assert all(len(item.name) <= 63 for item in schema_items if isinstance(item.name, str))


def test_migration_is_linear_reversible_and_registers_three_immutable_tables() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260815_0133"' in migration
    assert 'down_revision: str | None = "20260815_0132"' in migration
    for table, trigger in (
        (
            "workflow_event_tctx_access_consumption_claims",
            "trg_wf_tctx_open_claims_append_only",
        ),
        (
            "workflow_event_tctx_artifact_opening_attempts",
            "trg_wf_tctx_open_attempts_append_only",
        ),
        (
            "workflow_event_tctx_artifact_opening_results",
            "trg_wf_tctx_open_results_append_only",
        ),
    ):
        assert table in migration
        assert trigger in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "op.drop_table(RESULT_TABLE)" in migration
    assert "op.drop_table(ATTEMPT_TABLE)" in migration
    assert "op.drop_table(CLAIM_TABLE)" in migration
    assert "refusing to downgrade target-context artifact opening audit schema" in migration
    assert "consumption_authorization_audit_digest" in migration
    assert "consumption_authorization_audit_payload" in migration
    assert "fk_wf_tctx_open_attempt_claim_lineage" in migration
    assert "fk_wf_tctx_open_result_attempt_lineage" in migration


def _migration_module() -> Any:
    spec = importlib.util.spec_from_file_location("imp210_schema_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_downgrade_guard_covers_every_audit_table_before_destructive_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _migration_module()
    executed: list[str] = []
    dropped: list[str] = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: executed.append(str(statement)))
    monkeypatch.setattr(migration.op, "drop_table", dropped.append)

    migration.downgrade()

    assert executed[0] == migration.DOWNGRADE_EMPTY_GUARD_SQL
    assert all(
        f"SELECT 1 FROM {table_name} LIMIT 1" in executed[0]
        for table_name in (migration.RESULT_TABLE, migration.ATTEMPT_TABLE, migration.CLAIM_TABLE)
    )
    assert "append-only tables contain evidence" in executed[0]
    assert "ERRCODE = '55000'" in executed[0]
    assert dropped == [migration.RESULT_TABLE, migration.ATTEMPT_TABLE, migration.CLAIM_TABLE]
    assert any("DROP FUNCTION" in statement for statement in executed)


def test_repository_commits_claim_and_attempt_after_two_complete_revalidations() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.claim_target_context_artifact_opening
    )
    lock = source.index("_lock_target_context_access_sources")
    lease = source.index("lease_row =", lock)
    replay = source.index("_target_context_artifact_opening_replay", lease)
    first_validate = source.index("_target_context_artifact_opening_request_is_valid", replay)
    first_evidence = source.index(
        "_target_context_artifact_opening_evidence_matches", first_validate
    )
    assert "required_precommit_audit" not in source
    second_clock = source.index("clock_timestamp", first_evidence)
    second_validate = source.index(
        "_target_context_artifact_opening_request_is_valid", second_clock
    )
    second_evidence = source.index(
        "_target_context_artifact_opening_evidence_matches", second_validate
    )
    claim_build = source.index("_target_context_artifact_opening_claim(", second_evidence)
    attempt_build = source.index("_target_context_artifact_opening_attempt(", claim_build)
    claim_add = source.index("_target_context_artifact_opening_claim_model", attempt_build)
    flush = source.index("await session.flush()", claim_add)
    attempt_add = source.index("_target_context_artifact_opening_attempt_model", flush)
    commit = source.index("await session.commit()", attempt_add)
    assert (
        lock
        < lease
        < replay
        < first_validate
        < first_evidence
        < second_clock
        < second_validate
        < second_evidence
        < claim_build
        < attempt_build
        < claim_add
        < flush
        < attempt_add
        < commit
    )
    claim_model_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._target_context_artifact_opening_claim_model
    )
    assert "consumption_authorization_audit_digest" in claim_model_source
    assert "consumption_authorization_audit_payload" in claim_model_source


def test_attempt_inventory_is_scoped_ordered_and_integrity_checked() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.list_target_context_artifact_opening_attempts
    )
    assert "organization_id" in source
    assert "environment_id" in source
    assert "site_id" in source
    assert "started_at.desc()" in source
    assert "_target_context_artifact_opening_attempt_from_row" in source
    assert InMemoryWorkflowPlanRepository().durable is False
    assert UnavailableWorkflowPlanRepository().durable is False


def test_result_writer_and_replay_lookup_use_non_conflicting_scoped_access() -> None:
    writer = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.record_target_context_artifact_opening_result
    )
    lease_lock = writer.index("lease_row =")
    claim_lock = writer.index("claim_row =", lease_lock)
    attempt_lock = writer.index("attempt_row =", claim_lock)
    result_lock = writer.index("existing =", attempt_lock)
    assert lease_lock < claim_lock < attempt_lock < result_lock
    assert all(
        ".with_for_update()" in section
        for section in (
            writer[lease_lock:claim_lock],
            writer[claim_lock:attempt_lock],
            writer[attempt_lock:result_lock],
        )
    )

    lookup = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.lookup_target_context_artifact_opening_replay
    )
    assert ".with_for_update()" not in lookup
    assert "idempotency_digest" in lookup
    assert "organization_id" in lookup
    assert "environment_id" in lookup
    assert "site_id" in lookup
    assert "accessor_subject_id" in lookup
    assert "_target_context_artifact_opening_audit_matches" in lookup

    replay = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._target_context_artifact_opening_replay
    )
    assert "_target_context_artifact_opening_audit_matches" in replay

    audit = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._target_context_artifact_opening_expected_audit_payload
    )
    for field in (
        "credential_audience",
        "policy_digest",
        "idempotency_digest",
        "request_fingerprint",
        "irreversible_consumption_acknowledged",
        "uncertain_outcome_requires_new_authorization_acknowledged",
    ):
        assert field in audit


def test_opening_revalidates_complete_materialization_chains_and_terminal_lineage() -> None:
    locker = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_target_context_materialization_chains
    )
    for model_name in (
        "WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel",
        "WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel",
        "WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel",
        "WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel",
        "WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel",
        "WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel",
        "WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel",
        "WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel",
    ):
        assert model_name in locker
    assert ".with_for_update()" in locker

    matcher = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._target_context_artifact_opening_evidence_matches
    )
    assert "_target_context_binding_evidence" in matcher
    assert "require_live_overlap=True" in matcher

    lineage = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._target_context_artifact_opening_lineage_matches
    )
    for field in (
        "attempt_digest",
        "consumption_claim_digest",
        "authorization_lease_digest",
        "target_context_binding_digest",
        "target_context_commitment",
        "accessor_subject_id",
        "policy_digest",
        "started_at",
        "completed_at",
        "usable_until",
    ):
        assert field in lineage

    attempt_reader = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._target_context_artifact_opening_attempt_from_row
    )
    for field in (
        "request_nonce_digest",
        "policy_id",
        "policy_version",
        "policy_digest",
        "required_opener_contract_id",
        "required_opener_attestor_id",
    ):
        assert field in attempt_reader


async def _live_engine() -> AsyncEngine:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    return create_async_engine(database_url, pool_pre_ping=True)


@pytest.mark.asyncio
async def test_live_postgres_opening_schema_and_append_only_triggers_are_installed() -> None:
    engine = await _live_engine()
    try:
        async with engine.connect() as connection:
            tables = set(
                (
                    await connection.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_name IN "
                            "('workflow_event_tctx_access_consumption_claims', "
                            "'workflow_event_tctx_artifact_opening_attempts', "
                            "'workflow_event_tctx_artifact_opening_results')"
                        )
                    )
                ).scalars()
            )
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_tctx_open_claims_append_only', "
                            "'trg_wf_tctx_open_attempts_append_only', "
                            "'trg_wf_tctx_open_results_append_only')"
                        )
                    )
                ).scalars()
            )
        assert tables == {
            "workflow_event_tctx_access_consumption_claims",
            "workflow_event_tctx_artifact_opening_attempts",
            "workflow_event_tctx_artifact_opening_results",
        }
        assert triggers == {
            "trg_wf_tctx_open_claims_append_only",
            "trg_wf_tctx_open_attempts_append_only",
            "trg_wf_tctx_open_results_append_only",
        }
    finally:
        await engine.dispose()


def _claim_insert() -> str:
    columns = (
        "claim_id",
        "idempotency_scope_id",
        "idempotency_key",
        "idempotency_digest",
        "request_fingerprint",
        "authorization_lease_id",
        "authorization_lease_digest",
        "target_context_binding_id",
        "target_context_binding_digest",
        "target_context_commitment",
        "attempt_id",
        "opening_id",
        "authorization_evidence_digest",
        "consumption_authorization_audit_digest",
        "organization_id",
        "environment_id",
        "site_id",
        "accessor_subject_id",
        "claimed_at",
        *AUTHORITY_COLUMNS,
        "canonical_digest",
        "payload",
        "authorization_evidence_payload",
        "consumption_authorization_audit_payload",
    )
    values = tuple(
        "CAST(:payload AS jsonb)"
        if column == "payload"
        else "CAST(:evidence AS jsonb)"
        if column == "authorization_evidence_payload"
        else "CAST(:audit AS jsonb)"
        if column == "consumption_authorization_audit_payload"
        else f":{column}"
        for column in columns
    )
    return (
        "INSERT INTO workflow_event_tctx_access_consumption_claims ("
        + ", ".join(columns)
        + ") VALUES ("
        + ", ".join(values)
        + ")"
    )


def _claim_values(*, claim_id: str, lease_id: str, idempotency_key: str) -> dict[str, Any]:
    digest = sha256(claim_id.encode()).hexdigest()
    values: dict[str, Any] = {
        "claim_id": claim_id,
        "idempotency_scope_id": "b" * 64,
        "idempotency_key": idempotency_key,
        "idempotency_digest": "c" * 64,
        "request_fingerprint": "d" * 64,
        "authorization_lease_id": lease_id,
        "authorization_lease_digest": "e" * 64,
        "target_context_binding_id": f"binding.{claim_id}",
        "target_context_binding_digest": "f" * 64,
        "target_context_commitment": "1" * 64,
        "attempt_id": f"attempt.{claim_id}",
        "opening_id": f"opening.{claim_id}",
        "authorization_evidence_digest": "2" * 64,
        "consumption_authorization_audit_digest": "3" * 64,
        "organization_id": SCOPE.organization_id,
        "environment_id": SCOPE.environment_id,
        "site_id": SCOPE.site_id,
        "accessor_subject_id": "service.workflow-protected-transport-context-accessor",
        "claimed_at": "2026-08-16T00:00:00+00:00",
        "canonical_digest": digest,
        "payload": json.dumps({"claim_id": claim_id}),
        "evidence": json.dumps({"lineage": digest}),
        "audit": json.dumps({"audit_event_id": f"audit.{claim_id}"}),
    }
    values.update(dict.fromkeys(AUTHORITY_COLUMNS, False))
    return values


@pytest.mark.asyncio
async def test_live_postgres_single_claim_is_concurrent_and_append_only() -> None:
    engine = await _live_engine()
    seed = uuid4().hex
    lease_id = f"lease.live.{seed}"

    async def insert(number: int) -> bool:
        values = _claim_values(
            claim_id=f"claim.live.{seed}.{number}",
            lease_id=lease_id,
            idempotency_key=f"opening-live-{seed}-{number}",
        )
        try:
            async with engine.begin() as connection:
                await connection.execute(text("SET LOCAL session_replication_role = replica"))
                await connection.execute(text(_claim_insert()), values)
            return True
        except IntegrityError:
            return False

    try:
        outcomes = await asyncio.gather(insert(1), insert(2))
        assert sorted(outcomes) == [False, True]
        with pytest.raises(DBAPIError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE workflow_event_tctx_access_consumption_claims "
                        "SET request_fingerprint = :digest "
                        "WHERE authorization_lease_id = :lease_id"
                    ),
                    {"digest": "9" * 64, "lease_id": lease_id},
                )
        migration = _migration_module()
        with pytest.raises(DBAPIError, match="append-only tables contain evidence"):
            async with engine.begin() as connection:
                await connection.execute(text(migration.DOWNGRADE_EMPTY_GUARD_SQL))
    finally:
        await engine.dispose()
