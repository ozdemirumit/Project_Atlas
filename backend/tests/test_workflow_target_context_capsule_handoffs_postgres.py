from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from inspect import getsource
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import Boolean, Table, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from test_workflow_target_context_capsule_handoffs import make_attempt

from atlas.core.persistence.models import (
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptModel,
    WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaimModel,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.target_context_capsule_handoff_adapters import (
    DeterministicSyntheticWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter,
)
from atlas.modules.workflows.application import (
    WorkflowProtectedTransportTargetContextCapsuleHandoffError,
)
from atlas.modules.workflows.domain import (
    WorkflowScope,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260816_0136_workflow_target_context_capsule_handoff_consumption.py"
)
SCOPE = WorkflowScope("organization.development", "environment.test", "site.local")


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


@pytest.mark.asyncio
async def test_live_postgres_constraints_concurrency_and_append_only_when_configured() -> None:
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
                            "claim": "workflow_event_tctx_capsule_handoff_consumption_claims",
                            "attempt": "workflow_event_tctx_capsule_handoff_attempts",
                            "result": "workflow_event_tctx_capsule_handoff_results",
                        },
                    )
                ).scalars()
            )
            assert tables == {
                "workflow_event_tctx_capsule_handoff_consumption_claims",
                "workflow_event_tctx_capsule_handoff_attempts",
                "workflow_event_tctx_capsule_handoff_results",
            }
            constraints = set(
                (
                    await connection.execute(
                        text(
                            "SELECT conname FROM pg_constraint WHERE conname IN "
                            "('ck_wf_tctx_handoff_consume_contract', "
                            "'ck_wf_tctx_handoff_consume_ack', "
                            "'ck_wf_tctx_handoff_consume_authority', "
                            "'uq_wf_tctx_handoff_consume_lease', "
                            "'fk_wf_tctx_handoff_result_attempt_lineage')"
                        )
                    )
                ).scalars()
            )
            assert constraints == {
                "ck_wf_tctx_handoff_consume_contract",
                "ck_wf_tctx_handoff_consume_ack",
                "ck_wf_tctx_handoff_consume_authority",
                "uq_wf_tctx_handoff_consume_lease",
                "fk_wf_tctx_handoff_result_attempt_lineage",
            }
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_tctx_handoff_consume_append_only', "
                            "'trg_wf_tctx_handoff_attempt_append_only', "
                            "'trg_wf_tctx_handoff_result_append_only')"
                        )
                    )
                ).scalars()
            )
            assert triggers == {
                "trg_wf_tctx_handoff_consume_append_only",
                "trg_wf_tctx_handoff_attempt_append_only",
                "trg_wf_tctx_handoff_result_append_only",
            }

        claim_table = cast(
            Table,
            WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaimModel.__table__,
        )
        seed = uuid4().hex
        first = _live_claim_values(seed=f"{seed}a", table=claim_table)
        second = {
            **_live_claim_values(seed=f"{seed}b", table=claim_table),
            "authorization_lease_id": first["authorization_lease_id"],
        }

        async def insert(values: dict[str, object]) -> BaseException | None:
            try:
                async with engine.begin() as connection:
                    await connection.execute(text("SET LOCAL session_replication_role = replica"))
                    await connection.execute(claim_table.insert(), values)
            except BaseException as error:  # pragma: no cover - asserted below
                return error
            return None

        outcomes = await asyncio.wait_for(asyncio.gather(insert(first), insert(second)), timeout=15)
        assert sum(outcome is None for outcome in outcomes) == 1
        assert sum(isinstance(outcome, IntegrityError) for outcome in outcomes) == 1
        winner = first if outcomes[0] is None else second

        unsafe = {
            **_live_claim_values(seed=f"{seed}unsafe", table=claim_table),
            "consumer_subject_id": "service.workflow-unrelated",
        }
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(text("SET LOCAL session_replication_role = replica"))
                await connection.execute(claim_table.insert(), unsafe)

        with pytest.raises(DBAPIError):
            async with engine.begin() as connection:
                await connection.execute(
                    claim_table.update()
                    .where(claim_table.c.claim_id == winner["claim_id"])
                    .values(payload={"changed": True})
                )
    finally:
        await engine.dispose()


def _live_digest(seed: str, name: str) -> str:
    return sha256(f"{seed}:{name}".encode()).hexdigest()


def _live_claim_values(*, seed: str, table: Table) -> dict[str, object]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()
    )
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if hasattr(policy, name):
            values[name] = getattr(policy, name)
        elif name in {
            "irreversible_consumption_acknowledged",
            "uncertain_outcome_requires_new_authorization_acknowledged",
        }:
            values[name] = True
        elif isinstance(column.type, Boolean):
            values[name] = False
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name == "claimed_at":
            values[name] = datetime.now(UTC)
        elif name.endswith("_payload") or name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name in {
            "idempotency_scope_id",
            "request_fingerprint",
            "canonical_digest",
        }:
            values[name] = _live_digest(seed, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values
