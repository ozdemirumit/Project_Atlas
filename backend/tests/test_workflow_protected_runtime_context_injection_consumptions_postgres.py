from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Table, text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeContextInjectionAttemptModel,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseModel,
    WorkflowProtectedRuntimeContextInjectionConsumptionClaimModel,
    WorkflowProtectedRuntimeContextInjectionResultModel,
    WorkflowProtectedRuntimeContextInjectionSlotHeadModel,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260816_0142_workflow_protected_runtime_context_injection_consumption.py"
)


def _checks(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    )


def test_migration_is_linear_guarded_append_only_and_non_colliding() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260816_0142"' in source
    assert 'down_revision: str | None = "20260816_0141"' in source
    assert source.count("op.create_table(") == 4
    assert "uq_wf_rtctx_inj_auth_consume_lineage" in source
    assert "fk_wf_rtctx_inj_consume_auth_lease" in source
    assert "fk_wf_rtctx_inj_attempt_claim_lineage" in source
    assert "fk_wf_rtctx_inj_result_attempt_lineage" in source
    assert source.count("deferrable=True") == 3
    assert source.count('initially="DEFERRED"') == 3
    assert "trg_wf_rtctx_inj_consume_append_only" in source
    assert "trg_wf_rtctx_inj_attempt_append_only" in source
    assert "trg_wf_rtctx_inj_result_append_only" in source
    assert "trg_wf_rtctx_inj_slot_head_append_only" not in source
    assert source.count("BEFORE UPDATE OR DELETE") == 1
    assert (
        "refusing guarded downgrade: runtime-context injection consumption evidence exists"
        in source
    )
    assert "slot_generation <> 0 OR slot_state <> 'empty_inert'" in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_orm_models_match_exact_slot_and_append_only_evidence_contract() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseModel.__table__)
    head = cast(Table, WorkflowProtectedRuntimeContextInjectionSlotHeadModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeContextInjectionConsumptionClaimModel.__table__)
    attempt = cast(Table, WorkflowProtectedRuntimeContextInjectionAttemptModel.__table__)
    result = cast(Table, WorkflowProtectedRuntimeContextInjectionResultModel.__table__)

    assert head.name == "workflow_protected_runtime_context_injection_slot_heads"
    assert claim.name == "workflow_event_runtime_context_injection_consumption_claims"
    assert attempt.name == "workflow_event_runtime_context_injection_attempts"
    assert result.name == "workflow_event_runtime_context_injection_results"
    assert "uq_wf_rtctx_inj_auth_consume_lineage" in {
        constraint.name for constraint in lease.constraints
    }
    assert "fk_wf_rtctx_inj_consume_auth_lease" in {
        constraint.name for constraint in claim.foreign_key_constraints
    }
    assert "fk_wf_rtctx_inj_attempt_claim_lineage" in {
        constraint.name for constraint in attempt.foreign_key_constraints
    }
    assert "fk_wf_rtctx_inj_result_attempt_lineage" in {
        constraint.name for constraint in result.foreign_key_constraints
    }
    for table in (claim, attempt, result):
        assert all(foreign_key.column.table is not head for foreign_key in table.foreign_keys)
    assert [column.name for column in head.primary_key.columns] == [
        "destination_deployment_id",
        "runtime_slot_commitment",
    ]
    assert any(
        index.name == "ix_wf_rtctx_inj_slot_head_lock" and index.unique for index in head.indexes
    )
    head_checks = _checks(head)
    assert "slot_generation >= 0" in head_checks
    assert "empty_inert" in head_checks
    assert "inert_context_present" in head_checks
    assert "outcome_uncertain" in head_checks
    assert "payload = jsonb_build_object" in head_checks


def test_claim_enforces_single_winners_consumption_and_zero_authority() -> None:
    claim = cast(Table, WorkflowProtectedRuntimeContextInjectionConsumptionClaimModel.__table__)
    names = {constraint.name for constraint in claim.constraints}
    assert {
        "uq_wf_rtctx_inj_consume_lease",
        "uq_wf_rtctx_inj_consume_handle",
        "uq_wf_rtctx_inj_consume_slot_generation",
        "uq_wf_rtctx_inj_consume_operation",
        "uq_wf_rtctx_inj_consume_attempt",
        "uq_wf_rtctx_inj_consume_scope_idem",
    } <= names
    checks = _checks(claim)
    assert "irreversible_consumption_acknowledged" in checks
    assert "uncertain_outcome_requires_new_authorization_acknowledged" in checks
    assert "runtime_slot_pre_generation >= 0" in checks
    assert "claimed_at < authorization_lease_valid_until" in checks
    assert checks.count("authority_granted") == 21
    assert "NOT runtime_use_authorized" in checks
    assert "NOT protected_runtime_context_injection_authority_granted" in checks
    assert "NOT network_access_authority_granted" in checks
    assert "NOT execution_authority_granted" in checks
    assert "NOT infrastructure_mutation_authority_granted" in checks
    authorization_fk = next(
        constraint
        for constraint in claim.foreign_key_constraints
        if constraint.name == "fk_wf_rtctx_inj_consume_auth_lease"
    )
    assert authorization_fk.deferrable is True
    assert authorization_fk.initially == "DEFERRED"


def test_attempt_binds_fresh_attestations_deadline_instruction_and_exact_slot() -> None:
    attempt = cast(Table, WorkflowProtectedRuntimeContextInjectionAttemptModel.__table__)
    checks = _checks(attempt)
    assert "claimed_at <= lifecycle_attestation_observed_at" in checks
    assert "claimed_at <= slot_readiness_attestation_observed_at" in checks
    assert "started_at < injection_deadline" in checks
    assert "injection_deadline <= authorization_lease_valid_until" in checks
    assert "injection_deadline <= authorization_lease_effective_until" in checks
    assert "injection_deadline <= lifecycle_attestation_valid_until" in checks
    assert "injection_deadline <= slot_readiness_attestation_valid_until" in checks
    assert "key.workflow-protected-runtime-handle-lifecycle.v1" in checks
    assert "key.workflow-protected-runtime-context-slot-readiness.v1" in checks
    assert "key.workflow-protected-runtime-context-injection-receipt.v1" in checks
    assert "jsonb_typeof(lifecycle_attestation_payload) = 'object'" in checks
    assert "jsonb_typeof(slot_readiness_attestation_payload) = 'object'" in checks
    assert {
        "instruction_digest",
        "runtime_slot_commitment",
        "runtime_slot_pre_generation",
        "protected_operation_reference",
        "expected_runtime_slot_post_generation",
    } <= set(attempt.c.keys())
    claim_fk = next(
        constraint
        for constraint in attempt.foreign_key_constraints
        if constraint.name == "fk_wf_rtctx_inj_attempt_claim_lineage"
    )
    assert claim_fk.deferrable is True
    assert claim_fk.initially == "DEFERRED"


def test_result_accepts_only_signed_known_outcomes_or_receipt_free_uncertainty() -> None:
    result = cast(Table, WorkflowProtectedRuntimeContextInjectionResultModel.__table__)
    checks = _checks(result)

    assert "claimed_at <= started_at" in checks
    assert "started_at <= completed_at" in checks
    assert "completed_at <= recorded_at" in checks
    assert "completed_at < injection_deadline" in checks
    assert "recorded_at >= injection_deadline" in checks
    assert "authorization_lease_consumed" in checks
    assert "protected_runtime_handle_consumed" in checks
    assert "injected_into_protected_runtime_slot" in checks
    assert "injection_failed" in checks
    assert "injection_outcome_uncertain" in checks
    assert checks.count("injector_receipt_payload IS NOT NULL") == 2
    assert checks.count("injector_receipt_payload ->> 'canonical_digest'") == 2
    assert checks.count("injector_receipt_digest, FALSE") == 2
    assert checks.count("injector_receipt_payload ->> 'signing_key_id'") == 2
    assert checks.count("injector_receipt_payload ->> 'integrity_signature'") == 2
    assert checks.count("injector_receipt_payload ->> 'instruction_digest'") == 2
    assert checks.count("injector_receipt_payload ->> 'protected_operation_reference'") == 2
    assert "injector_receipt_payload IS NULL" in checks
    assert "runtime_slot_post_generation = runtime_slot_pre_generation + 1" in checks
    assert "runtime_slot_post_generation = runtime_slot_pre_generation" in checks
    assert "runtime_slot_post_generation IS NULL" in checks
    assert "runtime_slot_mutation_performed" in checks
    assert "inert_context_injected" in checks
    assert "temporary_material_zeroized" in checks
    assert result.c.runtime_slot_post_generation.nullable is True
    assert result.c.protected_runtime_handle_consumed.nullable is True
    assert result.c.runtime_slot_mutation_performed.nullable is False
    assert result.c.inert_context_injected.nullable is False
    assert {
        "destination_boundary_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_profile_digest",
    } <= set(result.c.keys())


def test_schema_contains_no_runtime_material_locator_or_operational_authority_fields() -> None:
    tables = (
        cast(Table, WorkflowProtectedRuntimeContextInjectionConsumptionClaimModel.__table__),
        cast(Table, WorkflowProtectedRuntimeContextInjectionAttemptModel.__table__),
        cast(Table, WorkflowProtectedRuntimeContextInjectionResultModel.__table__),
    )
    forbidden_exact = {
        "runtime_handle_material",
        "runtime_handle_locator",
        "runtime_payload",
        "endpoint",
        "credential",
        "secret",
        "bearer_token",
    }
    for table in tables:
        assert forbidden_exact.isdisjoint(table.c.keys())
        assert "handle_lookup_authorized" not in table.c
        assert "handle_retrieval_authorized" not in table.c
        assert "handle_use_authorized" not in table.c
        assert table.c.runtime_use_authorized.nullable is False
        assert "NOT runtime_use_authorized" in _checks(table)


@pytest.mark.asyncio
async def test_live_postgres_tables_triggers_and_mutable_head_when_configured() -> None:
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
                            "AND tablename IN (:head, :claim, :attempt, :result)"
                        ),
                        {
                            "head": "workflow_protected_runtime_context_injection_slot_heads",
                            "claim": "workflow_event_runtime_context_injection_consumption_claims",
                            "attempt": "workflow_event_runtime_context_injection_attempts",
                            "result": "workflow_event_runtime_context_injection_results",
                        },
                    )
                ).scalars()
            )
            assert tables == {
                "workflow_protected_runtime_context_injection_slot_heads",
                "workflow_event_runtime_context_injection_consumption_claims",
                "workflow_event_runtime_context_injection_attempts",
                "workflow_event_runtime_context_injection_results",
            }
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_rtctx_inj_consume_append_only', "
                            "'trg_wf_rtctx_inj_attempt_append_only', "
                            "'trg_wf_rtctx_inj_result_append_only')"
                        )
                    )
                ).scalars()
            )
            assert triggers == {
                "trg_wf_rtctx_inj_consume_append_only",
                "trg_wf_rtctx_inj_attempt_append_only",
                "trg_wf_rtctx_inj_result_append_only",
            }
            slot_head = (
                await connection.execute(
                    text(
                        "SELECT slot_generation, slot_state, current FROM "
                        "workflow_protected_runtime_context_injection_slot_heads"
                    )
                )
            ).one()
            assert slot_head == (0, "empty_inert", True)
    finally:
        await engine.dispose()
