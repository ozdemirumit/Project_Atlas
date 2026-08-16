from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Table, text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedResidentContextAccessAttemptModel,
    WorkflowProtectedResidentContextAccessConsumptionClaimModel,
    WorkflowProtectedResidentContextAccessResultModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260816_0140_workflow_protected_resident_context_access_consumption.py"
)


def test_migration_is_linear_append_only_guarded_and_has_exact_lineage() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260816_0140"' in source
    assert 'down_revision: str | None = "20260816_0139"' in source
    assert source.count("op.create_table(") == 3
    assert "uq_wf_rc_access_auth_consume_lineage" in source
    assert "fk_wf_rc_access_consume_lease_lineage" in source
    assert "fk_wf_rc_access_attempt_claim_lineage" in source
    assert "fk_wf_rc_access_result_attempt_lineage" in source
    assert "uq_wf_rc_access_consume_lease" in source
    assert "uq_wf_rc_access_consume_context" in source
    assert source.count("BEFORE UPDATE OR DELETE") == 1
    assert "trg_wf_rc_access_consume_append_only" in source
    assert "trg_wf_rc_access_attempt_append_only" in source
    assert "trg_wf_rc_access_result_append_only" in source
    assert (
        "refusing guarded downgrade: resident-context access consumption evidence exists" in source
    )


def test_orm_contract_has_composite_lineage_profiles_windows_and_twenty_zero_authorities() -> None:
    claim = cast(Table, WorkflowProtectedResidentContextAccessConsumptionClaimModel.__table__)
    attempt = cast(Table, WorkflowProtectedResidentContextAccessAttemptModel.__table__)
    result = cast(Table, WorkflowProtectedResidentContextAccessResultModel.__table__)

    assert claim.name == "workflow_event_resident_context_access_consumption_claims"
    assert attempt.name == "workflow_event_resident_context_access_attempts"
    assert result.name == "workflow_event_resident_context_access_results"
    assert "fk_wf_rc_access_consume_lease_lineage" in {
        item.name for item in claim.foreign_key_constraints
    }
    assert "fk_wf_rc_access_attempt_claim_lineage" in {
        item.name for item in attempt.foreign_key_constraints
    }
    assert "fk_wf_rc_access_result_attempt_lineage" in {
        item.name for item in result.foreign_key_constraints
    }
    claim_checks = " ".join(
        str(item.sqltext) for item in claim.constraints if hasattr(item, "sqltext")
    )
    attempt_checks = " ".join(
        str(item.sqltext) for item in attempt.constraints if hasattr(item, "sqltext")
    )
    result_checks = " ".join(
        str(item.sqltext) for item in result.constraints if hasattr(item, "sqltext")
    )
    for checks in (claim_checks, attempt_checks, result_checks):
        assert checks.count("authority_granted") == 20
        assert "NOT protected_resident_context_access_authority_granted" in checks
        assert "NOT infrastructure_mutation_authority_granted" in checks
    assert "irreversible_consumption_acknowledged" in claim_checks
    assert "protected_runtime_handle_is_bearer_capability" in result_checks
    assert "access_deadline <= authorization_lease_valid_until" in attempt_checks
    assert "readiness_attestation_valid_until" in attempt_checks
    assert "contract.workflow-protected-resident-context-accessor" in attempt_checks
    assert "profile.workflow-protected-resident-context-runtime-handle" in attempt_checks
    assert "handle_established_in_protected_boundary" in result_checks
    assert "resident_context_access_failed" in result_checks
    assert "access_outcome_uncertain" in result_checks


def test_repository_orders_replay_locks_two_clocks_and_atomic_claim_attempt_commit() -> None:
    claim_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.claim_protected_resident_context_access_consumption
    )
    lock = claim_source.index("_lock_protected_resident_context_access_consumption_sources")
    validation = claim_source.index(
        "_protected_resident_context_access_consumption_request_is_valid", lock
    )
    second_clock = claim_source.index("clock_timestamp", validation)
    second_validation = claim_source.index(
        "_protected_resident_context_access_consumption_request_is_valid", second_clock
    )
    claim_add = claim_source.index(
        "_protected_resident_context_access_consumption_claim_model", second_validation
    )
    claim_flush = claim_source.index("session.flush", claim_add)
    attempt_add = claim_source.index(
        "_protected_resident_context_access_attempt_model", claim_flush
    )
    attempt_flush = claim_source.index("session.flush", attempt_add)
    commit = claim_source.index("session.commit", attempt_flush)

    assert lock < validation < second_clock < second_validation
    assert second_validation < claim_add < claim_flush < attempt_add < attempt_flush < commit
    assert "required_precommit_audit" not in claim_source
    assert "Memory" not in claim_source
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_resident_context_access_consumption_sources
    )
    for model in (
        "WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel",
        "WorkflowProtectedResidentContextAccessAuthorizationLeaseModel",
        "WorkflowProtectedResidentContextAccessAuthorizationClaimModel",
        "WorkflowProtectedResidentContextAccessConsumptionClaimModel",
        "WorkflowProtectedResidentContextAccessAttemptModel",
        "WorkflowProtectedResidentContextAccessResultModel",
    ):
        assert model in lock_source
    assert "with_for_update" in lock_source


def test_replay_path_is_durable_and_does_not_call_external_attestors_or_accessor() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.lookup_protected_resident_context_access_consumption_replay
    )
    source += inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_resident_context_access_consumption_replay_from_rows
    )
    assert "WorkflowProtectedResidentContextAccessConsumptionClaimModel" in source
    assert "WorkflowProtectedResidentContextAccessAttemptModel" in source
    assert "WorkflowProtectedResidentContextAccessResultModel" in source
    assert "offline_signature_verifier" not in source
    assert "accessor" not in source.lower().replace(
        "protected_resident_context_access", "protected_resident_context"
    )


@pytest.mark.asyncio
async def test_live_postgres_contract_and_append_only_triggers_when_configured() -> None:
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
                            "AND tablename IN (:claim, :attempt, :result)"
                        ),
                        {
                            "claim": "workflow_event_resident_context_access_consumption_claims",
                            "attempt": "workflow_event_resident_context_access_attempts",
                            "result": "workflow_event_resident_context_access_results",
                        },
                    )
                ).scalars()
            )
            assert tables == {
                "workflow_event_resident_context_access_consumption_claims",
                "workflow_event_resident_context_access_attempts",
                "workflow_event_resident_context_access_results",
            }
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_rc_access_consume_append_only', "
                            "'trg_wf_rc_access_attempt_append_only', "
                            "'trg_wf_rc_access_result_append_only')"
                        )
                    )
                ).scalars()
            )
            assert triggers == {
                "trg_wf_rc_access_consume_append_only",
                "trg_wf_rc_access_attempt_append_only",
                "trg_wf_rc_access_result_append_only",
            }
    finally:
        await engine.dispose()
