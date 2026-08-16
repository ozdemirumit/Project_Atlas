from __future__ import annotations

import asyncio
import inspect
import os
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import Boolean, Table, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptModel,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationClaimModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.domain import (
    WorkflowScope,
    code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260816_0137_workflow_target_context_capsule_opening_authorization_lease.py"
)
SCOPE = WorkflowScope("organization.development", "environment.test", "site.local")


def test_migration_is_append_only_guarded_and_has_composite_lineage() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260816_0137"' in source
    assert 'down_revision: str | None = "20260816_0136"' in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "refusing guarded downgrade" in source
    assert "fk_wf_tctx_open_auth_result_lineage" in source
    assert "fk_wf_tctx_open_auth_attempt_lineage" in source
    assert "fk_wf_tctx_open_auth_claim_lease" in source
    assert "uq_wf_tctx_handoff_result_open_auth_lineage" in source
    assert "uq_wf_tctx_handoff_attempt_open_auth_lineage" in source
    assert "uq_wf_tctx_open_auth_claim_lineage" in source
    assert "uq_wf_tctx_open_auth_result" in source
    assert "uq_wf_tctx_open_auth_receipt" in source
    assert "uq_wf_tctx_open_auth_capsule" in source
    assert "interval '1 second'" in source
    assert "source_reuse_authority_terminated" not in source
    assert "service.workflow-protected-transport-target-context-capsule-consumer" in source
    assert "boundary.workflow-protected-target-context-capsule-consumer" in source


def test_orm_contract_has_one_true_authority_and_exact_lineage_constraints() -> None:
    lease_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel.__table__,
    )
    claim_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationClaimModel.__table__,
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
    assert "service.workflow-protected-transport-target-context-capsule-consumer" in checks
    assert "boundary.workflow-protected-target-context-capsule-consumer" in checks
    names = {constraint.name for constraint in lease_table.constraints}
    assert "fk_wf_tctx_open_auth_result_lineage" in names
    assert "fk_wf_tctx_open_auth_attempt_lineage" in names
    assert "uq_wf_tctx_open_auth_result" in names
    assert "uq_wf_tctx_open_auth_receipt" in names
    assert "uq_wf_tctx_open_auth_capsule" in names
    assert "uq_wf_tctx_open_auth_claim_lineage" in names
    assert "fk_wf_tctx_open_auth_claim_lease" in {
        constraint.name for constraint in claim_table.constraints
    }
    assert "uq_wf_tctx_open_auth_scope_idem" in {
        constraint.name for constraint in claim_table.constraints
    }
    handoff_result_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel.__table__,
    )
    assert "uq_wf_tctx_handoff_result_lineage" in {
        constraint.name for constraint in handoff_result_table.constraints
    }
    assert "uq_wf_tctx_handoff_result_open_auth_lineage" in {
        constraint.name for constraint in handoff_result_table.constraints
    }
    handoff_attempt_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptModel.__table__,
    )
    assert "uq_wf_tctx_handoff_attempt_open_auth_lineage" in {
        constraint.name for constraint in handoff_attempt_table.constraints
    }


def test_repository_orders_locks_evidence_replay_second_db_time_and_atomic_write() -> None:
    authorize = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.authorize_target_context_capsule_opening
    )
    lock = authorize.index("_lock_target_context_capsule_opening_authorization_sources")
    evidence = authorize.index("_target_context_capsule_opening_evidence_matches", lock)
    replay = authorize.index("_target_context_capsule_opening_replay", evidence)
    precommit_audit = authorize.index("required_precommit_audit", replay)
    second_clock = authorize.index("clock_timestamp", precommit_audit)
    second_evidence = authorize.index(
        "_target_context_capsule_opening_evidence_matches", second_clock
    )
    lease_add = authorize.index("_target_context_capsule_opening_lease_model", second_evidence)
    flush = authorize.index("session.flush", lease_add)
    claim_add = authorize.index("_target_context_capsule_opening_claim_model", flush)
    commit = authorize.index("session.commit", claim_add)
    assert lock < evidence < replay < precommit_audit < second_clock < second_evidence
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
async def test_live_postgres_constraints_concurrency_lineage_and_append_only_when_configured() -> (
    None
):
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
            installed = set(
                (
                    await connection.execute(
                        text(
                            "SELECT conname FROM pg_constraint WHERE conname IN "
                            "('ck_wf_tctx_capsule_open_auth_contract', "
                            "'fk_wf_tctx_open_auth_result_lineage', "
                            "'fk_wf_tctx_open_auth_attempt_lineage', "
                            "'fk_wf_tctx_open_auth_claim_lease', "
                            "'uq_wf_tctx_open_auth_claim_lineage')"
                        )
                    )
                ).scalars()
            )
            assert installed == {
                "ck_wf_tctx_capsule_open_auth_contract",
                "fk_wf_tctx_open_auth_result_lineage",
                "fk_wf_tctx_open_auth_attempt_lineage",
                "fk_wf_tctx_open_auth_claim_lease",
                "uq_wf_tctx_open_auth_claim_lineage",
            }
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_tctx_open_auth_lease_append_only', "
                            "'trg_wf_tctx_open_auth_claim_append_only')"
                        )
                    )
                ).scalars()
            )
            assert triggers == {
                "trg_wf_tctx_open_auth_lease_append_only",
                "trg_wf_tctx_open_auth_claim_append_only",
            }

        lease_table = cast(
            Table,
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel.__table__,
        )
        claim_table = cast(
            Table,
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationClaimModel.__table__,
        )
        seed = uuid4().hex
        first = _live_lease_values(seed=f"{seed}a", table=lease_table)
        second = {
            **_live_lease_values(seed=f"{seed}b", table=lease_table),
            "handoff_id": first["handoff_id"],
            "consumer_receipt_id": first["consumer_receipt_id"],
            "sealed_capsule_id": first["sealed_capsule_id"],
        }

        async def insert(values: dict[str, object]) -> BaseException | None:
            try:
                async with engine.begin() as connection:
                    await connection.execute(text("SET LOCAL session_replication_role = replica"))
                    await connection.execute(lease_table.insert(), values)
            except BaseException as error:  # pragma: no cover - asserted below
                return error
            return None

        outcomes = await asyncio.wait_for(asyncio.gather(insert(first), insert(second)), timeout=15)
        assert sum(outcome is None for outcome in outcomes) == 1
        assert sum(isinstance(outcome, IntegrityError) for outcome in outcomes) == 1
        winner = first if outcomes[0] is None else second

        unsafe = {
            **_live_lease_values(seed=f"{seed}unsafe", table=lease_table),
            "consumer_subject_id": "service.workflow-unrelated",
        }
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(text("SET LOCAL session_replication_role = replica"))
                await connection.execute(lease_table.insert(), unsafe)

        mismatched_claim = _live_claim_values(
            seed=f"{seed}mismatch", table=claim_table, lease=winner
        )
        mismatched_claim["consumer_receipt_id"] = "consumer-receipt.mismatch"
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(claim_table.insert(), mismatched_claim)

        claim = _live_claim_values(seed=seed, table=claim_table, lease=winner)
        async with engine.begin() as connection:
            await connection.execute(claim_table.insert(), claim)

        for table, key, value in (
            (lease_table, "authorization_lease_id", winner["authorization_lease_id"]),
            (claim_table, "claim_id", claim["claim_id"]),
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(
                        table.update()
                        .where(table.c[key] == value)
                        .values(payload={"changed": True})
                    )
    finally:
        await engine.dispose()


def _live_digest(seed: str, name: str) -> str:
    return sha256(f"{seed}:{name}".encode()).hexdigest()


def _live_lease_values(*, seed: str, table: Table) -> dict[str, object]:
    policy = code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy()  # noqa: E501
    now = datetime.now(UTC)
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if hasattr(policy, name):
            values[name] = getattr(policy, name)
        elif name == "state":
            values[name] = "authorized_unconsumed"
        elif name == "issued_at":
            values[name] = now
        elif name == "valid_until":
            values[name] = now + timedelta(seconds=1)
        elif name in {"effective_until", "custody_attestation_valid_until"}:
            values[name] = now + timedelta(seconds=2)
        elif name in {"single_use", "target_context_capsule_opening_authority_granted"}:
            values[name] = True
        elif isinstance(column.type, Boolean):
            values[name] = False
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name.endswith("_payload") or name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name == "canonical_digest":
            values[name] = _live_digest(seed, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values


def _live_claim_values(*, seed: str, table: Table, lease: dict[str, object]) -> dict[str, object]:
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in {
            "authorization_lease_id",
            "handoff_id",
            "consumer_receipt_id",
            "sealed_capsule_id",
            "consumer_subject_id",
            "consumer_audience",
        }:
            values[name] = lease[name]
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name == "claimed_at":
            values[name] = lease["issued_at"]
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
