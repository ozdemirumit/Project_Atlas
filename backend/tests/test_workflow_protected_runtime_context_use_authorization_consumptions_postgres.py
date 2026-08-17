from __future__ import annotations

import inspect
import os
import re
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Table, UniqueConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaimModel,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResultModel,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_consumption_domain import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority,
    code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260817_0144_workflow_protected_runtime_context_use_authorization_consumption.py"
)


def _checks(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    )


def test_migration_is_linear_two_record_append_only_and_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    policy = code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()

    assert 'revision: str = "20260817_0144"' in source
    assert 'down_revision: str | None = "20260816_0143"' in source
    assert source.count("op.create_table(") == 2
    assert "workflow_event_runtime_context_use_auth_consumption_claims" in source
    assert "workflow_event_runtime_context_use_auth_consumption_results" in source
    assert "attempt" not in " ".join(
        line for line in source.splitlines() if "TABLE" in line and "=" in line
    )
    assert "clock_timestamp" not in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "trg_wf_rtctx_use_consume_claim_append_only" in source
    assert "trg_wf_rtctx_use_consume_result_append_only" in source
    assert "refusing guarded downgrade" in source
    assert "consumption evidence exists" in source
    assert policy.canonical_digest in source
    assert policy.source_policy_digest in source
    assert "claimed_at < source_lease_valid_until" in source
    assert "claimed_at < source_lease_effective_until" in source
    assert "claimed_at < injected_context_usable_until" in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_orm_binds_exact_adr170_lineage_and_terminal_result() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeContextUseAuthorizationLeaseModel.__table__)
    claim = cast(
        Table,
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaimModel.__table__,
    )
    result = cast(
        Table,
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResultModel.__table__,
    )

    assert claim.name == "workflow_event_runtime_context_use_auth_consumption_claims"
    assert result.name == "workflow_event_runtime_context_use_auth_consumption_results"
    assert {
        "uq_wf_rtctx_use_auth_lease_id_digest",
        "uq_wf_rtctx_use_auth_lease_claim_line",
        "uq_wf_rtctx_use_auth_lease_result_line",
        "uq_wf_rtctx_use_auth_lease_slot_line",
        "uq_wf_rtctx_use_auth_lease_window_line",
        "uq_wf_rtctx_use_auth_lease_scope_policy",
    } <= {constraint.name for constraint in lease.constraints}
    assert {
        "fk_wf_rtctx_use_consume_claim_lease_digest",
        "fk_wf_rtctx_use_consume_claim_lease_claim",
        "fk_wf_rtctx_use_consume_claim_auth_claim",
        "fk_wf_rtctx_use_consume_claim_result",
        "fk_wf_rtctx_use_consume_claim_slot",
        "fk_wf_rtctx_use_consume_claim_window",
        "fk_wf_rtctx_use_consume_claim_scope_policy",
    } == {constraint.name for constraint in claim.foreign_key_constraints}
    assert {
        "fk_wf_rtctx_use_consume_result_claim",
        "fk_wf_rtctx_use_consume_result_identity",
        "fk_wf_rtctx_use_consume_result_policy",
    } == {constraint.name for constraint in result.foreign_key_constraints}
    assert {
        "authorization_lease_digest",
        "authorization_claim_digest",
        "injection_result_digest",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_post_generation",
        "source_lease_valid_until",
        "source_lease_effective_until",
        "injected_context_usable_until",
    } <= set(claim.c.keys())


def test_orm_enforces_single_winner_terminal_zero_authority_contract() -> None:
    claim = cast(
        Table,
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaimModel.__table__,
    )
    result = cast(
        Table,
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResultModel.__table__,
    )
    claim_checks = _checks(claim)
    result_checks = _checks(result)
    authority_names = tuple(
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority()
        .canonical_value()
        .keys()
    )

    assert "irreversible_consumption_acknowledged" in claim_checks
    assert "authorization_consumed_without_runtime_use" in result_checks
    assert "authorization_lease_consumed" in result_checks
    assert "historical_result_only" in result_checks
    for name in authority_names:
        assert f"NOT {name}" in claim_checks
        assert f"NOT {name}" in result_checks
    for effect in (
        "context_accessed",
        "context_used",
        "runtime_started",
        "runtime_resumed",
        "network_activity_performed",
        "connector_activity_performed",
        "readiness_probe_performed",
        "publication_performed",
        "delivery_performed",
        "dispatch_performed",
        "execution_performed",
        "infrastructure_mutation_performed",
        "renewal_created",
        "transfer_created",
        "replacement_created",
        "retry_created",
    ):
        assert f"NOT {effect}" in result_checks
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == ("authorization_lease_id",)
        for constraint in claim.constraints
    )


def test_repository_uses_canonical_locks_atomic_append_replay_and_exists_projection() -> None:
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_runtime_context_use_authorization_consumption_rows
    )
    consume_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.consume_protected_runtime_context_use_authorization
    )
    source_status = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_context_use_authorization_consumption_source_status
    )
    replay_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.lookup_protected_runtime_context_use_authorization_consumption_replay
    )
    projection_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_context_use_consumed_expression
    )

    assert lock_source.count("clock_timestamp") == 2
    assert lock_source.index("injection_authorization_lease =") < lock_source.index(
        "injection_consumption_claim ="
    )
    assert lock_source.index("injection_consumption_claim =") < lock_source.index(
        "injection_attempt ="
    )
    assert lock_source.index("injection_attempt =") < lock_source.index("injection_result =")
    assert lock_source.index("injection_result =") < lock_source.index("destination_head =")
    assert lock_source.index("destination_head =") < lock_source.index("slot_statement =")
    assert lock_source.index("slot_statement =") < lock_source.index(
        "\n        authorization_lease = cast("
    )
    assert lock_source.index("\n        authorization_lease = cast(") < lock_source.index(
        "\n        authorization_claim = cast("
    )
    assert "with_for_update" in lock_source
    assert "session.add(" in consume_source
    assert consume_source.count("session.add(") == 2
    assert consume_source.index("await session.flush()") < consume_source.index(
        "await session.commit()"
    )
    assert "except IntegrityError" in consume_source
    assert "lookup_protected_runtime_context_use_authorization_consumption_replay" in consume_source
    assert "adapter" not in consume_source.lower()
    assert "network" not in consume_source.lower()
    assert "runtime_start" not in consume_source.lower()
    assert "select(claim_model, result_model)" in replay_source
    assert "full=True" in replay_source
    assert replay_source.count("session.execute(") == 1
    assert "exists().where(" in projection_source
    assert "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaimModel" in (
        projection_source
    )
    assert "lease.issued_at" in source_status
    assert "locked.first_observed_at" in source_status
    assert "locked.observed_at" in source_status


def test_schema_discloses_no_context_locator_endpoint_credential_or_secret() -> None:
    tables = (
        cast(
            Table,
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaimModel.__table__,
        ),
        cast(
            Table,
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResultModel.__table__,
        ),
    )
    forbidden = {
        "raw_context",
        "runtime_payload",
        "runtime_slot_locator",
        "protected_operation_reference",
        "endpoint",
        "credential",
        "secret",
        "bearer_token",
        "attempt_id",
        "receipt",
    }
    for table in tables:
        assert forbidden.isdisjoint(table.c.keys())


@pytest.mark.asyncio
async def test_live_postgres_tables_constraints_and_append_only_triggers_when_configured() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            tables = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
                            "AND tablename IN (:claim, :result)"
                        ),
                        {
                            "claim": ("workflow_event_runtime_context_use_auth_consumption_claims"),
                            "result": (
                                "workflow_event_runtime_context_use_auth_consumption_results"
                            ),
                        },
                    )
                ).scalars()
            )
            assert tables == {
                "workflow_event_runtime_context_use_auth_consumption_claims",
                "workflow_event_runtime_context_use_auth_consumption_results",
            }
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_rtctx_use_consume_claim_append_only', "
                            "'trg_wf_rtctx_use_consume_result_append_only')"
                        )
                    )
                ).scalars()
            )
            assert triggers == {
                "trg_wf_rtctx_use_consume_claim_append_only",
                "trg_wf_rtctx_use_consume_result_append_only",
            }
            unique_claim_lease = await connection.scalar(
                text(
                    "SELECT COUNT(*) FROM pg_constraint WHERE conname = "
                    "'uq_wf_rtctx_use_consume_claim_lease' AND contype = 'u'"
                )
            )
            assert unique_claim_lease == 1
    finally:
        await engine.dispose()
