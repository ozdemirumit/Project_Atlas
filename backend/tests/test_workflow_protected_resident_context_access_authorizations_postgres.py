from __future__ import annotations

import asyncio
import inspect
import os
import re
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
    WorkflowProtectedResidentContextAccessAuthorizationClaimModel,
    WorkflowProtectedResidentContextAccessAuthorizationLeaseModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260816_0139_workflow_protected_resident_context_access_authorization.py"
)
POLICY_DIGEST = "51141a6f2a3bbc6e61a3d95f76088325ec5f04e7246a05d334365dc941a83555"


def test_migration_is_append_only_guarded_non_colliding_and_exactly_lined() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260816_0139"' in source
    assert 'down_revision: str | None = "20260816_0138"' in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "refusing guarded downgrade" in source
    assert "fk_wf_rc_access_auth_result_lineage" in source
    assert "fk_wf_rc_access_auth_attempt_lineage" in source
    assert "fk_wf_rc_access_auth_claim_lineage" in source
    assert "uq_wf_rc_access_auth_scope_idem" in source
    assert "INTERVAL '1 second'" in source
    assert POLICY_DIGEST in source
    assert "protected_resident_context_access_authority_granted" in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_orm_matches_migration_authority_lineage_and_lifetime_contract() -> None:
    lease = cast(Table, WorkflowProtectedResidentContextAccessAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedResidentContextAccessAuthorizationClaimModel.__table__)
    checks = " ".join(
        str(constraint.sqltext)
        for table in (lease, claim)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "protected_resident_context_access_authority_granted" in checks
    assert "NOT target_context_capsule_handoff_authority_granted" in checks
    assert "NOT target_context_capsule_opening_authority_granted" in checks
    assert "NOT protected_artifact_access_authority_granted" in checks
    assert "NOT network_access_authority_granted" in checks
    assert "NOT execution_authority_granted" in checks
    assert "NOT infrastructure_mutation_authority_granted" in checks
    assert "INTERVAL '1 second'" in checks
    assert POLICY_DIGEST in checks
    assert "701153578261c45c3f1faa89f75b4a3f7003126683ddb895c0346aac0f9148e7" in checks
    lease_names = {constraint.name for constraint in lease.constraints}
    assert {
        "fk_wf_rc_access_auth_result_lineage",
        "fk_wf_rc_access_auth_attempt_lineage",
        "fk_wf_rc_access_auth_claim_lineage",
        "uq_wf_rc_access_auth_lease_result",
        "uq_wf_rc_access_auth_lease_context",
    } <= lease_names
    assert "uq_wf_rc_access_auth_scope_idem" in {
        constraint.name for constraint in claim.constraints
    }
    result = cast(Table, WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel.__table__)
    attempt = cast(
        Table, WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel.__table__
    )
    opening_claim = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel.__table__,
    )
    assert "uq_wf_tctx_caps_open_result_access_auth_lineage" in {
        constraint.name for constraint in result.constraints
    }
    assert "uq_wf_tctx_caps_open_attempt_access_auth_lineage" in {
        constraint.name for constraint in attempt.constraints
    }
    assert "uq_wf_tctx_caps_open_claim_access_auth_lineage" in {
        constraint.name for constraint in opening_claim.constraints
    }


def test_repository_uses_upstream_first_locks_two_db_times_and_no_attestor_io() -> None:
    lock = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_resident_context_access_authorization_sources
    )
    ordered = (
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationClaimModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel",
        "WorkflowProtectedResidentContextAccessAuthorizationLeaseModel",
        "WorkflowProtectedResidentContextAccessAuthorizationClaimModel",
    )
    positions = [lock.index(name) for name in ordered]
    assert positions == sorted(positions)
    assert lock.count("clock_timestamp") == 2
    assert "with_for_update" in lock
    authorize = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.authorize_protected_resident_context_access
    )
    assert "attest_resident_context_lifecycle" not in authorize
    assert "session.commit" in authorize
    assert "IntegrityError" in authorize
    assert "_protected_resident_context_access_replay" in authorize
    assert '"authorization_lease_id"' in authorize
    assert '"access_authorization_lease_id"' not in authorize
    assert '"protected_resident_context_access_authority_granted"' in authorize
    assert "authorization_audit_digest" in authorize
    hydrate = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._resident_context_access_lease_from_row
    )
    assert '"valid_until"' in hydrate


@pytest.mark.asyncio
async def test_live_postgres_winner_lineage_deadline_fence_lifecycle_and_append_only() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    lease_table = cast(
        Table, WorkflowProtectedResidentContextAccessAuthorizationLeaseModel.__table__
    )
    claim_table = cast(
        Table, WorkflowProtectedResidentContextAccessAuthorizationClaimModel.__table__
    )
    seed = uuid4().hex
    first = _live_values(seed=f"{seed}a", table=lease_table)
    second = {
        **_live_values(seed=f"{seed}b", table=lease_table),
        "opening_id": first["opening_id"],
        "protected_resident_context_id": first["protected_resident_context_id"],
    }

    async def insert_replica(values: dict[str, object]) -> BaseException | None:
        try:
            async with engine.begin() as connection:
                await connection.execute(text("SET LOCAL session_replication_role = replica"))
                await connection.execute(lease_table.insert(), values)
        except BaseException as error:  # pragma: no cover - asserted below
            return error
        return None

    try:
        outcomes = await asyncio.wait_for(
            asyncio.gather(insert_replica(first), insert_replica(second)), timeout=15
        )
        assert sum(outcome is None for outcome in outcomes) == 1
        assert sum(isinstance(outcome, IntegrityError) for outcome in outcomes) == 1
        winner = first if outcomes[0] is None else second

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    lease_table.insert(), _live_values(seed=seed, table=lease_table)
                )

        for name, value in (
            ("opening_deadline", winner["opening_completed_at"]),
            ("destination_generation", 2),
            ("resident_context_unconsumed", False),
        ):
            unsafe = {**_live_values(seed=f"{seed}{name}", table=lease_table), name: value}
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(text("SET LOCAL session_replication_role = replica"))
                    await connection.execute(lease_table.insert(), unsafe)

        claim = _live_values(seed=seed, table=claim_table)
        claim["access_authorization_lease_id"] = winner["access_authorization_lease_id"]
        claim["opening_id"] = winner["opening_id"]
        claim["protected_resident_context_id"] = winner["protected_resident_context_id"]
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(claim_table.insert(), claim)

        for table, key, value in (
            (lease_table, "access_authorization_lease_id", winner["access_authorization_lease_id"]),
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


def _digest(seed: str, name: str) -> str:
    return sha256(f"{seed}:{name}".encode()).hexdigest()


def _live_values(*, seed: str, table: Table) -> dict[str, object]:
    now = datetime.now(UTC)
    created = now - timedelta(seconds=1)
    values: dict[str, object] = {}
    true_names = {
        "single_use",
        "resident_context_present",
        "resident_context_unexpired",
        "resident_context_unrevoked",
        "resident_context_undestroyed",
        "resident_context_unconsumed",
        "capsule_opened_in_protected_boundary",
        "target_context_pair_verified",
        "opening_outcome_known",
        "protected_source_closed",
        "source_capsule_zeroized",
        "protected_resident_context_access_authority_granted",
    }
    for column in table.columns:
        name = column.name
        if name in true_names and table is lease_table_for(table):
            values[name] = True
        elif isinstance(column.type, Boolean):
            values[name] = name in true_names and name not in {
                "protected_resident_context_access_authority_granted"
            }
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = {
                "organization_id": "organization.development",
                "environment_id": "environment.test",
                "site_id": "site.local",
            }[name]
        elif name == "consumer_subject_id":
            values[name] = "service.workflow-protected-transport-target-context-capsule-consumer"
        elif name == "consumer_audience":
            values[name] = "audience.workflow-protected-transport-target-context-capsule-consumer"
        elif name == "consumer_contract_id":
            values[name] = "contract.workflow-protected-transport-target-context-capsule-consumer"
        elif name == "consumer_contract_version" or name == "policy_version":
            values[name] = "1.0"
        elif name == "purpose_id":
            values[name] = "purpose.workflow-protected-resident-context-access-evaluation"
        elif name == "policy_id":
            values[name] = "policy.workflow-protected-resident-context-access-authorization"
        elif name == "policy_digest":
            values[name] = POLICY_DIGEST
        elif name == "destination_boundary_id":
            values[name] = "boundary.workflow-protected-target-context-capsule-consumer"
        elif name == "destination_deployment_id":
            values[name] = "deployment.workflow-protected-target-context-capsule-consumer"
        elif name == "destination_generation":
            values[name] = 1
        elif name == "destination_fencing_token_digest":
            values[name] = "701153578261c45c3f1faa89f75b4a3f7003126683ddb895c0346aac0f9148e7"
        elif name == "lifecycle_attestor_id":
            values[name] = "attestor.workflow-protected-resident-context-lifecycle"
        elif name == "lifecycle_attestor_version":
            values[name] = "1.0"
        elif name == "lifecycle_signing_key_id":
            values[name] = "key.workflow-protected-target-context-capsule-opening-receipt.v1"
        elif name == "opening_result_state":
            values[name] = "opened_in_protected_consumer_boundary"
        elif name in {"opening_completed_at", "protected_resident_context_created_at"}:
            values[name] = created
        elif name == "opening_deadline":
            values[name] = now + timedelta(seconds=5)
        elif name == "protected_resident_context_usable_until":
            values[name] = created + timedelta(seconds=20)
        elif name == "issued_at" or name == "claimed_at":
            values[name] = now
        elif name in {"valid_until", "effective_until"}:
            values[name] = now + timedelta(milliseconds=500)
        elif name == "lifecycle_attestation_valid_until":
            values[name] = now + timedelta(seconds=2)
        elif name == "state":
            values[name] = "authorized_unconsumed"
        elif name.endswith("_payload") or name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name in {
            "canonical_digest",
            "idempotency_scope_id",
            "idempotency_key",
        }:
            values[name] = _digest(seed, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values


def lease_table_for(table: Table) -> Table:
    del table
    return cast(Table, WorkflowProtectedResidentContextAccessAuthorizationLeaseModel.__table__)
