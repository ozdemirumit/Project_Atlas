from __future__ import annotations

import inspect
import os
import re
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeContextUseAttemptModel,
    WorkflowProtectedRuntimeContextUseClaimModel,
    WorkflowProtectedRuntimeContextUseResultModel,
    WorkflowProtectedRuntimeStartAuthorizationClaimModel,
    WorkflowProtectedRuntimeStartAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    code_owned_workflow_protected_runtime_start_authorization_policy,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260817_0146_workflow_protected_runtime_start_authorization.py"
)


def _checks(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def test_migration_is_linear_append_only_guarded_and_non_colliding() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    policy = code_owned_workflow_protected_runtime_start_authorization_policy()

    assert 'revision: str = "20260817_0146"' in source
    assert 'down_revision: str | None = "20260817_0145"' in source
    assert source.count("op.create_table(") == 2
    assert "workflow_event_runtime_start_auth_claims" in source
    assert "workflow_event_runtime_start_auth_leases" in source
    assert "workflow_protected_runtime_context_use_results" in source
    assert "workflow_protected_runtime_context_use_attempts" in source
    assert "workflow_protected_runtime_context_use_claims" in source
    assert "fk_wf_rtstart_{prefix}_use_result" in source
    assert "fk_wf_rtstart_{prefix}_use_attempt" in source
    assert "fk_wf_rtstart_{prefix}_use_claim" in source
    assert "uq_wf_rtctx_use_result_start_source" in source
    assert "uq_wf_rtctx_use_attempt_start_source" in source
    assert "uq_wf_rtctx_use_claim_start_source" in source
    assert "INTERVAL '1 second'" in source
    assert "use_count_pre = 0 AND use_count_post = 1" in source
    assert "context_used_once_in_protected_boundary" in source
    assert "context_terminal_non_reusable" in source
    assert "protected_runtime_start_authority_granted" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "trg_wf_rtstart_auth_lease_append_only" in source
    assert "trg_wf_rtstart_auth_claim_append_only" in source
    assert (
        "refusing guarded downgrade: protected runtime-start authorization evidence exists"
        in source
    )
    assert policy.canonical_digest in source
    assert policy.source_policy_digest in source
    assert policy.runtime_start_profile_digest in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_orm_binds_exact_adr172_lineage_and_one_winner_constraints() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeStartAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeStartAuthorizationClaimModel.__table__)

    assert lease.name == "workflow_event_runtime_start_auth_leases"
    assert claim.name == "workflow_event_runtime_start_auth_claims"
    required = {
        "use_result_id",
        "use_result_digest",
        "use_id",
        "use_attempt_id",
        "use_attempt_digest",
        "use_claim_id",
        "use_claim_digest",
        "use_receipt_digest",
        "authorization_consumption_result_id",
        "authorization_consumption_result_digest",
        "runtime_slot_pre_generation",
        "runtime_slot_post_generation",
        "use_count_pre",
        "use_count_post",
    }
    assert required <= set(lease.c.keys())
    assert required <= set(claim.c.keys())
    assert {
        "uq_wf_rtstart_auth_lease_use_result",
        "uq_wf_rtstart_auth_lease_slot",
        "uq_wf_rtstart_auth_lease_claim",
    } <= {constraint.name for constraint in lease.constraints}
    assert {
        "uq_wf_rtstart_auth_claim_use_result",
        "uq_wf_rtstart_auth_claim_slot",
        "uq_wf_rtstart_auth_scope_idem",
    } <= {constraint.name for constraint in claim.constraints}
    lease_claim = next(
        constraint
        for constraint in lease.foreign_key_constraints
        if constraint.name == "fk_wf_rtstart_auth_lease_claim"
    )
    claim_lease = next(
        constraint
        for constraint in claim.foreign_key_constraints
        if constraint.name == "fk_wf_rtstart_auth_claim_lease"
    )
    assert lease_claim.deferrable is True and lease_claim.initially == "DEFERRED"
    assert claim_lease.deferrable is True and claim_lease.initially == "DEFERRED"


def test_orm_composite_foreign_keys_bind_result_attempt_and_claim_digests() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeStartAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeStartAuthorizationClaimModel.__table__)
    parents = (
        (
            cast(Table, WorkflowProtectedRuntimeContextUseResultModel.__table__),
            "fk_wf_rtstart_lease_use_result",
            "fk_wf_rtstart_claim_use_result",
            ("use_result_id", "use_result_digest"),
        ),
        (
            cast(Table, WorkflowProtectedRuntimeContextUseAttemptModel.__table__),
            "fk_wf_rtstart_lease_use_attempt",
            "fk_wf_rtstart_claim_use_attempt",
            ("use_attempt_id", "use_attempt_digest"),
        ),
        (
            cast(Table, WorkflowProtectedRuntimeContextUseClaimModel.__table__),
            "fk_wf_rtstart_lease_use_claim",
            "fk_wf_rtstart_claim_use_claim",
            ("use_claim_id", "use_claim_digest"),
        ),
    )
    for parent, lease_name, claim_name, leading in parents:
        for child, expected_name in ((lease, lease_name), (claim, claim_name)):
            constraint = next(
                item for item in child.foreign_key_constraints if item.name == expected_name
            )
            local = tuple(element.parent.name for element in constraint.elements)
            assert local[:2] == leading
            assert all(element.column.table is parent for element in constraint.elements)
        assert any(isinstance(item, UniqueConstraint) for item in parent.constraints)


def test_orm_enforces_one_second_lease_only_authority_and_zero_existing_authority() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeStartAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeStartAuthorizationClaimModel.__table__)
    lease_checks = _checks(lease)
    claim_checks = _checks(claim)

    assert "INTERVAL '1 second'" in lease_checks
    assert "single_use" in lease_checks
    assert "NOT renewable" in lease_checks
    assert "NOT transferable" in lease_checks
    assert "NOT lease_is_bearer_capability" in lease_checks
    assert "protected_runtime_start_authority_granted" in lease_checks
    assert "NOT protected_runtime_start_authority_granted" in claim_checks
    for forbidden in (
        "runtime_use_authorized",
        "runtime_start_authorized",
        "runtime_resume_authorized",
        "connector_activity_authorized",
        "network_access_authorized",
        "readiness_probe_authorized",
        "publication_authorized",
        "delivery_authorized",
        "dispatch_authorized",
        "execution_authorized",
        "infrastructure_mutation_authorized",
        "protected_runtime_context_use_authority_granted",
    ):
        assert f"NOT {forbidden}" in lease_checks
        assert f"NOT {forbidden}" in claim_checks


def test_repository_uses_two_database_times_terminal_slot_and_future_consumption_gate() -> None:
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_runtime_start_authorization_rows
    )
    authorize_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.authorize_protected_runtime_start
    )
    evidence_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_start_evidence_matches
    )
    presentation_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.list_protected_runtime_start_authorization_presentations
    )
    consumed_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_start_consumed_ids
    )

    assert lock_source.count("clock_timestamp") == 2
    assert "with_for_update" in lock_source
    assert lock_source.index("use_claim =") < lock_source.index("use_attempt =")
    assert lock_source.index("use_attempt =") < lock_source.index("use_result =")
    assert "context_used_terminal" in evidence_source
    assert "runtime_slot_post_generation" in evidence_source
    assert "destination_fencing_token_digest" in evidence_source
    assert "validate_workflow_protected_runtime_start_authorization_request" in evidence_source
    assert "except IntegrityError" in authorize_source
    assert "_protected_runtime_start_replay" in authorize_source
    assert "to_regclass" in consumed_source
    assert "workflow_event_runtime_start_auth_consumption_claims" in consumed_source
    assert "_protected_runtime_start_consumed_ids" in presentation_source
    for forbidden in ("executor", "connector", "mcp", "network", "process_manager"):
        assert forbidden not in authorize_source.lower()


@pytest.mark.asyncio
async def test_live_postgres_tables_constraints_and_append_only_triggers_when_configured() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                tables = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT tablename FROM pg_tables "
                                "WHERE schemaname = current_schema() "
                                "AND tablename IN (:lease, :claim)"
                            ),
                            {
                                "lease": "workflow_event_runtime_start_auth_leases",
                                "claim": "workflow_event_runtime_start_auth_claims",
                            },
                        )
                    ).scalars()
                )
                assert tables == {
                    "workflow_event_runtime_start_auth_leases",
                    "workflow_event_runtime_start_auth_claims",
                }
                triggers = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT tgname FROM pg_trigger WHERE tgname IN "
                                "('trg_wf_rtstart_auth_lease_append_only', "
                                "'trg_wf_rtstart_auth_claim_append_only')"
                            )
                        )
                    ).scalars()
                )
                assert triggers == {
                    "trg_wf_rtstart_auth_lease_append_only",
                    "trg_wf_rtstart_auth_claim_append_only",
                }
                constraints = " ".join(
                    (
                        await connection.execute(
                            text(
                                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                                "WHERE conrelid IN "
                                "('workflow_event_runtime_start_auth_leases'::regclass, "
                                "'workflow_event_runtime_start_auth_claims'::regclass)"
                            )
                        )
                    ).scalars()
                )
                assert "context_used_once_in_protected_boundary" in constraints
                assert "context_terminal_non_reusable" in constraints
                assert "use_count_pre = 0" in constraints
                assert "use_count_post = 1" in constraints
                assert "1 second" in constraints

                await connection.execute(text("CREATE TEMP TABLE rtstart_append_probe (id int)"))
                await connection.execute(
                    text(
                        "CREATE TRIGGER rtstart_append_probe_trigger "
                        "BEFORE UPDATE OR DELETE ON rtstart_append_probe "
                        "FOR EACH ROW EXECUTE FUNCTION reject_wf_rtstart_auth_mutation()"
                    )
                )
                await connection.execute(text("INSERT INTO rtstart_append_probe VALUES (1)"))
                with pytest.raises(Exception, match="append-only"):
                    await connection.execute(text("UPDATE rtstart_append_probe SET id = 2"))
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
