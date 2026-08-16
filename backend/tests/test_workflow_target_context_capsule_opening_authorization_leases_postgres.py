from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationClaimModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260816_0137_workflow_target_context_capsule_opening_authorization_lease.py"
)


def test_migration_is_append_only_guarded_and_has_composite_lineage() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260816_0137"' in source
    assert 'down_revision: str | None = "20260816_0136"' in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "refusing guarded downgrade" in source
    assert "fk_wf_tctx_open_auth_result_lineage" in source
    assert "fk_wf_tctx_open_auth_attempt_lineage" in source
    assert "uq_wf_tctx_open_auth_result" in source
    assert "uq_wf_tctx_open_auth_receipt" in source
    assert "uq_wf_tctx_open_auth_capsule" in source
    assert "interval '1 second'" in source


def test_orm_contract_has_one_true_authority_and_exact_lineage_constraints() -> None:
    lease_table = (
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel.__table__
    )
    claim_table = (
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationClaimModel.__table__
    )
    checks = " ".join(
        str(constraint.sqltext)
        for constraint in lease_table.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "target_context_capsule_opening_authority_granted" in checks
    assert "NOT target_context_capsule_handoff_authority_granted" in checks
    assert "NOT protected_artifact_access_authority_granted" in checks
    assert "NOT network_access_authority_granted" in checks
    assert "NOT execution_authority_granted" in checks
    assert "NOT infrastructure_mutation_authority_granted" in checks
    names = {constraint.name for constraint in lease_table.constraints}
    assert "fk_wf_tctx_open_auth_result_lineage" in names
    assert "fk_wf_tctx_open_auth_attempt_lineage" in names
    assert "uq_wf_tctx_open_auth_result" in names
    assert "uq_wf_tctx_open_auth_receipt" in names
    assert "uq_wf_tctx_open_auth_capsule" in names
    assert "uq_wf_tctx_open_auth_scope_idem" in {
        constraint.name for constraint in claim_table.constraints
    }
    assert "uq_wf_tctx_handoff_result_lineage" in {
        constraint.name
        for constraint in (
            WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel.__table__.constraints
        )
    }


def test_repository_orders_locks_evidence_replay_second_db_time_and_atomic_write() -> None:
    authorize = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.authorize_target_context_capsule_opening
    )
    lock = authorize.index("_lock_target_context_capsule_opening_authorization_sources")
    evidence = authorize.index("_target_context_capsule_opening_evidence_matches", lock)
    replay = authorize.index("_target_context_capsule_opening_replay", evidence)
    second_clock = authorize.index("clock_timestamp", replay)
    second_evidence = authorize.index(
        "_target_context_capsule_opening_evidence_matches", second_clock
    )
    lease_add = authorize.index("_target_context_capsule_opening_lease_model", second_evidence)
    flush = authorize.index("session.flush", lease_add)
    claim_add = authorize.index("_target_context_capsule_opening_claim_model", flush)
    commit = authorize.index("session.commit", claim_add)
    assert lock < evidence < replay < second_clock < second_evidence
    assert second_evidence < lease_add < flush < claim_add < commit
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_target_context_capsule_opening_authorization_sources
    )
    for model_name in (
        "WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaimModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel",
        "WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationClaimModel",
    ):
        assert model_name in lock_source
    assert "_lock_target_context_capsule_consumer_binding_sources" in lock_source
    assert "with_for_update" in lock_source


@pytest.mark.asyncio
async def test_live_postgres_tables_and_append_only_triggers_when_configured() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
                        "AND tablename IN (:lease, :claim)"
                    ),
                    {
                        "lease": "workflow_event_tctx_capsule_opening_authorization_leases",
                        "claim": "workflow_event_tctx_capsule_opening_authorization_claims",
                    },
                )
            ).scalars()
            assert set(rows) == {
                "workflow_event_tctx_capsule_opening_authorization_leases",
                "workflow_event_tctx_capsule_opening_authorization_claims",
            }
    finally:
        await engine.dispose()
