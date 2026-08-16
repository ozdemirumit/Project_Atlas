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
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.domain import (
    WorkflowScope,
    code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy,
    code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260816_0138_workflow_target_context_capsule_opening_consumption.py"
)
SCOPE = WorkflowScope("organization.development", "environment.test", "site.local")


def test_migration_is_linear_append_only_guarded_and_has_composite_lineage() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260816_0138"' in source
    assert 'down_revision: str | None = "20260816_0137"' in source
    assert source.count("op.create_table(") == 3
    assert source.count("BEFORE UPDATE OR DELETE") == 1
    assert "trg_wf_tctx_open_consume_append_only" in source
    assert "trg_wf_tctx_open_attempt_append_only" in source
    assert "trg_wf_tctx_open_result_append_only" in source
    assert "refusing guarded downgrade: capsule opening evidence exists" in source
    assert "fk_wf_tctx_open_consume_lease_lineage" in source
    assert "fk_wf_tctx_open_attempt_claim_lineage" in source
    assert "fk_wf_tctx_open_result_attempt_lineage" in source
    assert "uq_wf_tctx_open_auth_consume_lineage" in source
    assert "uq_wf_tctx_open_consume_lease" in source
    assert "uq_wf_tctx_open_consume_handoff" in source
    assert "uq_wf_tctx_open_consume_receipt" in source
    assert "uq_wf_tctx_open_consume_capsule" in source
    assert source.count("_authority_granted") >= 19


def test_orm_contract_has_exact_identity_acknowledgements_and_zero_authority() -> None:
    claim_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel.__table__,
    )
    attempt_table = cast(
        Table, WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel.__table__
    )
    result_table = cast(
        Table, WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel.__table__
    )
    claim_checks = " ".join(
        str(constraint.sqltext)
        for constraint in claim_table.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "service.workflow-protected-transport-target-context-capsule-consumer" in claim_checks
    assert "contract.workflow-protected-transport-target-context-capsule-consumer" in claim_checks
    assert "irreversible_consumption_acknowledged" in claim_checks
    assert "uncertain_outcome_requires_new_authorization_acknowledged" in claim_checks
    assert "NOT target_context_capsule_opening_authority_granted" in claim_checks
    assert "NOT target_context_capsule_handoff_authority_granted" in claim_checks
    assert "NOT infrastructure_mutation_authority_granted" in claim_checks
    assert "fk_wf_tctx_open_consume_lease_lineage" in {
        constraint.name for constraint in claim_table.foreign_key_constraints
    }
    assert "fk_wf_tctx_open_attempt_claim_lineage" in {
        constraint.name for constraint in attempt_table.foreign_key_constraints
    }
    assert "fk_wf_tctx_open_result_attempt_lineage" in {
        constraint.name for constraint in result_table.foreign_key_constraints
    }


def test_repository_claim_orders_locks_audit_second_db_time_and_atomic_commit() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.claim_target_context_capsule_opening
    )
    lock = source.index("_lock_target_context_capsule_opening_sources")
    evidence = source.index("_target_context_capsule_opening_claim_is_valid", lock)
    claim_add = source.index("_target_context_capsule_opening_consumption_claim_model", evidence)
    first_flush = source.index("session.flush", claim_add)
    attempt_add = source.index("_target_context_capsule_opening_attempt_model", first_flush)
    second_flush = source.index("session.flush", attempt_add)
    audit = source.index("required_precommit_audit", second_flush)
    second_clock = source.index("clock_timestamp", audit)
    second_evidence = source.index("_target_context_capsule_opening_claim_is_valid", second_clock)
    commit = source.index("session.commit", second_evidence)

    assert lock < evidence < claim_add < first_flush < attempt_add < second_flush
    assert second_flush < audit < second_clock < second_evidence < commit
    assert "PRECOMMIT_AUDIT_FAILED" in source
    assert "Memory" not in source
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_target_context_capsule_opening_sources
    )
    lock_source += inspect.getsource(
        PostgreSQLWorkflowPlanRepository._load_target_context_capsule_opening_consumption_claims
    )
    for model_name in (
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaimModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel",
        "WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel",
    ):
        assert model_name in lock_source
    assert "_lock_target_context_capsule_consumer_binding_sources" in lock_source
    assert "with_for_update" in lock_source


@pytest.mark.asyncio
async def test_live_postgres_constraints_concurrency_lineage_append_only_and_claim_only_when_configured() -> (  # noqa: E501
    None
):
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    try:
        await _assert_installed_contract(engine)
        lease_table = cast(
            Table,
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel.__table__,
        )
        claim_table = cast(
            Table,
            WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel.__table__,
        )
        attempt_table = cast(
            Table, WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel.__table__
        )
        result_table = cast(
            Table, WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel.__table__
        )
        seed = uuid4().hex
        lease = _live_lease_values(seed=seed, table=lease_table)
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(lease_table.insert(), lease)

        first = _live_claim_values(seed=f"{seed}a", table=claim_table, lease=lease)
        second = {
            **_live_claim_values(seed=f"{seed}b", table=claim_table, lease=lease),
            "authorization_lease_id": first["authorization_lease_id"],
            "handoff_id": first["handoff_id"],
            "consumer_receipt_id": first["consumer_receipt_id"],
            "sealed_capsule_id": first["sealed_capsule_id"],
        }

        async def insert(values: dict[str, object]) -> BaseException | None:
            try:
                async with engine.begin() as connection:
                    await connection.execute(claim_table.insert(), values)
            except BaseException as error:  # pragma: no cover - asserted below
                return error
            return None

        outcomes = await asyncio.wait_for(asyncio.gather(insert(first), insert(second)), timeout=15)
        assert sum(outcome is None for outcome in outcomes) == 1
        assert sum(isinstance(outcome, IntegrityError) for outcome in outcomes) == 1
        winner = first if outcomes[0] is None else second

        for field, unsafe_value in (
            ("consumer_subject_id", "service.workflow-unrelated"),
            ("consumer_contract_id", "contract.workflow-unrelated"),
        ):
            unsafe = {
                **_live_claim_values(seed=f"{seed}{field}", table=claim_table, lease=lease),
                "authorization_lease_id": f"lease.{seed}.{field}",
                "handoff_id": f"handoff.{seed}.{field}",
                "consumer_receipt_id": f"receipt.{seed}.{field}",
                "sealed_capsule_id": f"capsule.{seed}.{field}",
                field: unsafe_value,
            }
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(text("SET LOCAL session_replication_role = replica"))
                    await connection.execute(claim_table.insert(), unsafe)

        attempt = _live_attempt_values(seed=seed, table=attempt_table, claim=winner, lease=lease)
        mismatched = {**attempt, "authorization_lease_digest": _live_digest(seed, "mismatch")}
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(attempt_table.insert(), mismatched)

        async with engine.begin() as connection:
            await connection.execute(attempt_table.insert(), attempt)

        async with engine.connect() as connection:
            durable_claim = await connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_tctx_capsule_opening_consumption_claims "
                    "WHERE claim_id = :claim_id"
                ),
                {"claim_id": winner["claim_id"]},
            )
            durable_attempt = await connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_tctx_capsule_opening_attempts "
                    "WHERE attempt_id = :attempt_id"
                ),
                {"attempt_id": attempt["attempt_id"]},
            )
            no_result = await connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_tctx_capsule_opening_results "
                    "WHERE opening_id = :opening_id"
                ),
                {"opening_id": attempt["opening_id"]},
            )
        assert (durable_claim, durable_attempt, no_result) == (1, 1, 0)

        result = _live_uncertain_result_values(
            seed=seed,
            table=result_table,
            claim=winner,
            attempt=attempt,
        )
        async with engine.begin() as connection:
            await connection.execute(result_table.insert(), result)

        for table, key, row_value in (
            (claim_table, "claim_id", winner["claim_id"]),
            (attempt_table, "attempt_id", attempt["attempt_id"]),
            (result_table, "opening_id", result["opening_id"]),
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(
                        table.update()
                        .where(table.c[key] == row_value)
                        .values(payload={"changed": True})
                    )
    finally:
        await engine.dispose()


async def _assert_installed_contract(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        tables = set(
            (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
                        "AND tablename IN (:claim, :attempt, :result)"
                    ),
                    {
                        "claim": "workflow_event_tctx_capsule_opening_consumption_claims",
                        "attempt": "workflow_event_tctx_capsule_opening_attempts",
                        "result": "workflow_event_tctx_capsule_opening_results",
                    },
                )
            ).scalars()
        )
        assert tables == {
            "workflow_event_tctx_capsule_opening_consumption_claims",
            "workflow_event_tctx_capsule_opening_attempts",
            "workflow_event_tctx_capsule_opening_results",
        }
        constraints = set(
            (
                await connection.execute(
                    text(
                        "SELECT conname FROM pg_constraint WHERE conname IN "
                        "('ck_wf_tctx_open_consume_contract', "
                        "'ck_wf_tctx_open_consume_ack', "
                        "'ck_wf_tctx_open_consume_authority', "
                        "'uq_wf_tctx_open_consume_lease', "
                        "'fk_wf_tctx_open_attempt_claim_lineage', "
                        "'fk_wf_tctx_open_result_attempt_lineage')"
                    )
                )
            ).scalars()
        )
        assert constraints == {
            "ck_wf_tctx_open_consume_contract",
            "ck_wf_tctx_open_consume_ack",
            "ck_wf_tctx_open_consume_authority",
            "uq_wf_tctx_open_consume_lease",
            "fk_wf_tctx_open_attempt_claim_lineage",
            "fk_wf_tctx_open_result_attempt_lineage",
        }
        triggers = set(
            (
                await connection.execute(
                    text(
                        "SELECT tgname FROM pg_trigger WHERE tgname IN "
                        "('trg_wf_tctx_open_consume_append_only', "
                        "'trg_wf_tctx_open_attempt_append_only', "
                        "'trg_wf_tctx_open_result_append_only')"
                    )
                )
            ).scalars()
        )
        assert triggers == {
            "trg_wf_tctx_open_consume_append_only",
            "trg_wf_tctx_open_attempt_append_only",
            "trg_wf_tctx_open_result_append_only",
        }


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
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    lineage = {
        "authorization_lease_id": lease["authorization_lease_id"],
        "authorization_lease_digest": lease["canonical_digest"],
        "handoff_id": lease["handoff_id"],
        "handoff_result_digest": lease["handoff_result_digest"],
        "handoff_attempt_id": lease["attempt_id"],
        "handoff_attempt_digest": lease["attempt_digest"],
        "handoff_consumption_claim_id": lease["consumption_claim_id"],
        "handoff_consumption_claim_digest": lease["consumption_claim_digest"],
        "consumer_binding_id": lease["consumer_binding_id"],
        "consumer_binding_digest": lease["consumer_binding_digest"],
        "sealed_capsule_id": lease["sealed_capsule_id"],
        "sealed_capsule_digest": lease["sealed_capsule_digest"],
        "consumer_receipt_id": lease["consumer_receipt_id"],
        "consumer_receipt_digest": lease["receipt_digest"],
    }
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in lineage:
            values[name] = lineage[name]
        elif hasattr(policy, name):
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


def _live_attempt_values(
    *,
    seed: str,
    table: Table,
    claim: dict[str, object],
    lease: dict[str, object],
) -> dict[str, object]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    started_at = cast(datetime, lease["issued_at"])
    deadline = started_at + timedelta(milliseconds=500)
    lineage = {
        "attempt_id": claim["attempt_id"],
        "opening_id": claim["opening_id"],
        "consumption_claim_id": claim["claim_id"],
        "consumption_claim_digest": claim["canonical_digest"],
        "authorization_lease_id": claim["authorization_lease_id"],
        "authorization_lease_digest": claim["authorization_lease_digest"],
        "consumer_binding_id": claim["consumer_binding_id"],
        "consumer_binding_digest": claim["consumer_binding_digest"],
        "sealed_capsule_id": claim["sealed_capsule_id"],
        "sealed_capsule_digest": claim["sealed_capsule_digest"],
        "consumer_receipt_id": claim["consumer_receipt_id"],
        "consumer_receipt_digest": claim["consumer_receipt_digest"],
    }
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in lineage:
            values[name] = lineage[name]
        elif hasattr(policy, name):
            values[name] = getattr(policy, name)
        elif name == "state":
            values[name] = "started"
        elif name == "started_at":
            values[name] = started_at
        elif name == "opening_deadline":
            values[name] = deadline
        elif name == "lease_valid_until":
            values[name] = lease["valid_until"]
        elif name in {"custody_attestation_valid_until", "openability_attestation_valid_until"}:
            values[name] = cast(datetime, lease["valid_until"]) + timedelta(seconds=1)
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


def _live_uncertain_result_values(
    *,
    seed: str,
    table: Table,
    claim: dict[str, object],
    attempt: dict[str, object],
) -> dict[str, object]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    lineage = {
        "opening_id": attempt["opening_id"],
        "attempt_id": attempt["attempt_id"],
        "attempt_digest": attempt["canonical_digest"],
        "consumption_claim_id": claim["claim_id"],
        "consumption_claim_digest": claim["canonical_digest"],
        "authorization_lease_id": claim["authorization_lease_id"],
        "authorization_lease_digest": claim["authorization_lease_digest"],
        "consumer_binding_id": claim["consumer_binding_id"],
        "consumer_binding_digest": claim["consumer_binding_digest"],
        "sealed_capsule_id": claim["sealed_capsule_id"],
        "sealed_capsule_digest": claim["sealed_capsule_digest"],
        "consumer_receipt_id": claim["consumer_receipt_id"],
        "consumer_receipt_digest": claim["consumer_receipt_digest"],
    }
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in lineage:
            values[name] = lineage[name]
        elif hasattr(policy, name):
            values[name] = getattr(policy, name)
        elif name == "state" or name == "failure_class":
            values[name] = "opening_outcome_uncertain"
        elif name in {"opening_deadline", "recorded_at"}:
            values[name] = attempt["opening_deadline"]
        elif name in {
            "opening_receipt_digest",
            "opening_receipt_payload",
            "protected_resident_context_id",
            "protected_resident_context_digest",
            "completed_at",
        }:
            values[name] = None
        elif isinstance(column.type, Boolean):
            values[name] = False
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name == "canonical_digest":
            values[name] = _live_digest(seed, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values
