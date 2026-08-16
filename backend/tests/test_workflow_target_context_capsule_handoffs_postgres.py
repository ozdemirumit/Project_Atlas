from __future__ import annotations

from datetime import UTC, datetime, timedelta
from inspect import getsource
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Table
from test_workflow_target_context_capsule_handoffs import make_attempt

from atlas.core.persistence.models import (
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptModel,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.target_context_capsule_handoff_adapters import (
    DeterministicSyntheticWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter,
)
from atlas.modules.workflows.application import (
    WorkflowProtectedTransportTargetContextCapsuleHandoffError,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260816_0136_workflow_target_context_capsule_handoff_consumption.py"
)


def test_migration_is_linear_append_only_and_binds_result_lineage() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260816_0136"' in migration
    assert 'down_revision: str | None = "20260816_0135"' in migration
    assert migration.count("op.create_table(") == 3
    assert migration.count("BEFORE UPDATE OR DELETE") == 1
    assert "trg_wf_tctx_handoff_consume_append_only" in migration
    assert "trg_wf_tctx_handoff_attempt_append_only" in migration
    assert "trg_wf_tctx_handoff_result_append_only" in migration
    assert "DOWNGRADE_EMPTY_GUARD_SQL" in migration
    assert "uq_wf_tctx_handoff_attempt_lineage" in migration
    assert "fk_wf_tctx_handoff_result_attempt_lineage" in migration
    assert "fk_wf_tctx_handoff_result_claim" in migration
    assert migration.count("_authority_granted") >= 18


def test_orm_metadata_enforces_attempt_and_claim_result_lineage() -> None:
    attempt_table = cast(
        Table, WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptModel.__table__
    )
    result_table = cast(
        Table, WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel.__table__
    )
    attempt_constraints = {constraint.name for constraint in attempt_table.constraints}
    result_foreign_keys = {constraint.name for constraint in result_table.foreign_key_constraints}

    assert "uq_wf_tctx_handoff_attempt_lineage" in attempt_constraints
    assert "fk_wf_tctx_handoff_result_attempt_lineage" in result_foreign_keys
    assert "fk_wf_tctx_handoff_result_claim" in result_foreign_keys


def test_claim_rechecks_database_time_immediately_before_commit() -> None:
    source = getsource(PostgreSQLWorkflowPlanRepository.claim_target_context_capsule_handoff)

    assert source.count("func.clock_timestamp()") >= 2
    assert "precommit_at >= deadline" in source
    assert source.index("precommit_at >= deadline") < source.index("await session.commit()")


@pytest.mark.asyncio
async def test_synthetic_adapter_requires_explicit_test_enablement() -> None:
    now = datetime.now(UTC)
    attempt = make_attempt(started_at=now, handoff_deadline=now + timedelta(seconds=1))
    adapter = DeterministicSyntheticWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter(
        clock=lambda: now
    )

    assert adapter.available is False
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffError,
        match="target_context_capsule_handoff_synthetic_adapter_disabled",
    ):
        await adapter.handoff_sealed_capsule(attempt)  # type: ignore[arg-type]
