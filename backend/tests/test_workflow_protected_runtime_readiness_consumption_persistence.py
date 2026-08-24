from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel,
    WorkflowProtectedRuntimeReadinessConsumptionAttemptModel,
    WorkflowProtectedRuntimeReadinessConsumptionClaimModel,
    WorkflowProtectedRuntimeReadinessConsumptionResultModel,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "20260817_0149_workflow_protected_runtime_readiness_consumption.py"
)

AUTHORITY_COLUMNS = {
    "endpoint_resolution_authorized",
    "route_selection_authorized",
    "route_binding_authorized",
    "credential_selection_authorized",
    "credential_assignment_binding_authorized",
    "credential_access_authorized",
    "credential_brokerage_authorized",
    "credential_resolution_authorized",
    "protected_artifact_access_authorized",
    "credential_delivery_authorized",
    "network_access_authorized",
    "readiness_probe_authorized",
    "publication_authorized",
    "delivery_authorized",
    "dispatch_authorized",
    "execution_authorized",
    "infrastructure_mutation_authorized",
    "target_context_capsule_handoff_authorized",
    "target_context_capsule_opening_authorized",
    "protected_resident_context_access_authority_granted",
    "protected_runtime_context_injection_authority_granted",
    "runtime_use_authorized",
    "runtime_start_authorized",
    "runtime_resume_authorized",
    "connector_activity_authorized",
    "protected_runtime_context_use_authority_granted",
    "protected_runtime_start_authority_granted",
    "protected_runtime_readiness_authority_granted",
}


def _checks(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _constraint_names(table: Table) -> set[str]:
    return {constraint.name for constraint in table.constraints if isinstance(constraint.name, str)}


def test_migration_is_linear_three_table_append_only_and_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260817_0149"' in source
    assert 'down_revision: str | None = "20260817_0148"' in source
    assert source.count("op.create_table(") == 3
    for table in (
        "workflow_event_runtime_readiness_consumption_claims",
        "workflow_event_runtime_readiness_consumption_attempts",
        "workflow_event_runtime_readiness_consumption_results",
    ):
        assert table in source
    assert "workflow_event_runtime_readiness_coordination_heads" not in source
    assert source.count("BEFORE UPDATE OR DELETE") == 1
    assert source.count("BEFORE TRUNCATE") == 1
    for suffix in ("claim", "attempt", "result"):
        assert f"trg_wf_rtready_cons_{suffix}_append_only" in source
        assert f"trg_wf_rtready_cons_{suffix}_no_truncate" in source
    assert "CREATE CONSTRAINT TRIGGER trg_wf_rtready_cons_final_window" in source
    assert "DEFERRABLE INITIALLY DEFERRED" in source
    assert "readiness claim and attempt must commit atomically" in source
    assert "clock_timestamp() + INTERVAL '100 milliseconds'" in source
    assert (
        "refusing guarded downgrade: protected runtime-readiness consumption evidence exists"
        in source
    )
    assert source.index("op.drop_table(RESULT_TABLE)") < source.index(
        'op.drop_constraint("uq_wf_rtready_auth_lease_consume"'
    )
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_models_bind_exact_lease_claim_attempt_and_result_cardinality() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeReadinessConsumptionClaimModel.__table__)
    attempt = cast(Table, WorkflowProtectedRuntimeReadinessConsumptionAttemptModel.__table__)
    result = cast(Table, WorkflowProtectedRuntimeReadinessConsumptionResultModel.__table__)

    assert claim.name == "workflow_event_runtime_readiness_consumption_claims"
    assert attempt.name == "workflow_event_runtime_readiness_consumption_attempts"
    assert result.name == "workflow_event_runtime_readiness_consumption_results"
    assert {
        "uq_wf_rtready_auth_lease_identity",
        "uq_wf_rtready_auth_lease_consume",
        "uq_wf_rtready_auth_lease_consume_outcome",
    } <= _constraint_names(lease)
    assert {
        "uq_wf_rtready_cons_claim_lease",
        "uq_wf_rtready_cons_claim_consumption",
        "uq_wf_rtready_cons_claim_attempt",
        "uq_wf_rtready_cons_claim_tenant_idem",
    } <= _constraint_names(claim)
    assert {
        "uq_wf_rtready_cons_attempt_claim",
        "uq_wf_rtready_cons_attempt_consumption",
        "uq_wf_rtready_cons_attempt_lease",
    } <= _constraint_names(attempt)
    assert {
        "uq_wf_rtready_cons_result_attempt",
        "uq_wf_rtready_cons_result_claim",
        "uq_wf_rtready_cons_result_consumption",
        "uq_wf_rtready_cons_result_lease",
    } <= _constraint_names(result)
    for table, prefix in (
        (claim, "claim"),
        (attempt, "attempt"),
        (result, "result"),
    ):
        foreign_keys = {
            constraint.name
            for constraint in table.foreign_key_constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }
        assert f"fk_wf_rtready_cons_{prefix}_lease" in foreign_keys
        assert f"fk_wf_rtready_cons_{prefix}_outcome" in foreign_keys
        assert f"fk_wf_rtready_cons_{prefix}_auth_claim" in foreign_keys
    assert "fk_wf_rtready_cons_attempt_claim" in {
        item.name for item in attempt.foreign_key_constraints
    }
    assert "fk_wf_rtready_cons_result_attempt" in {
        item.name for item in result.foreign_key_constraints
    }


def test_models_preserve_complete_runtime_lineage_and_instruction_evidence() -> None:
    tables = tuple(
        cast(Table, model.__table__)
        for model in (
            WorkflowProtectedRuntimeReadinessConsumptionClaimModel,
            WorkflowProtectedRuntimeReadinessConsumptionAttemptModel,
            WorkflowProtectedRuntimeReadinessConsumptionResultModel,
        )
    )
    required = {
        "organization_id",
        "environment_id",
        "site_id",
        "authorization_lease_id",
        "authorization_lease_digest",
        "authorization_claim_id",
        "authorization_claim_digest",
        "start_result_id",
        "start_result_digest",
        "start_consumption_id",
        "start_attempt_id",
        "start_attempt_digest",
        "start_consumption_claim_id",
        "start_consumption_claim_digest",
        "runtime_start_authorization_lease_id",
        "runtime_start_authorization_lease_digest",
        "runtime_start_authorization_claim_id",
        "runtime_start_authorization_claim_digest",
        "use_result_id",
        "use_result_digest",
        "destination_deployment_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_generation",
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "runtime_start_profile_id",
        "runtime_start_profile_version",
        "runtime_start_profile_digest",
        "readiness_profile_id",
        "readiness_profile_version",
        "readiness_profile_digest",
        "protected_operation_reference",
        "start_instruction_digest",
        "starter_receipt_digest",
        "start_result_state",
        "coordination_state",
    }
    for table in tables:
        assert required <= set(table.c.keys())
        assert set(table.c.keys()) >= AUTHORITY_COLUMNS
        checks = _checks(table)
        assert "policy.workflow-protected-runtime-readiness-consumption" in checks
        assert "runtime_started_in_protected_boundary" in checks
        assert "start_attempt_terminal" in checks
        for authority in AUTHORITY_COLUMNS:
            assert f"NOT {authority}" in checks
    attempt = tables[1]
    assert {
        "instruction_digest",
        "instruction_signing_key_id",
        "instruction_signature_algorithm",
        "signed_instruction_envelope_digest",
        "signed_instruction_envelope_payload",
        "invocation_deadline",
    } <= set(attempt.c.keys())


def test_result_constraints_cover_all_terminal_outcomes_and_receipt_rules() -> None:
    result = cast(Table, WorkflowProtectedRuntimeReadinessConsumptionResultModel.__table__)
    checks = _checks(result)

    for state in (
        "runtime_ready_in_protected_boundary",
        "runtime_not_ready_in_protected_boundary",
        "runtime_readiness_failed_without_assessment",
        "runtime_readiness_outcome_uncertain",
    ):
        assert state in checks
    assert "protected_assessor_rejected_without_assessment" in checks
    assert "protected_assessment_failed_without_assessment" in checks
    assert "completed_at < invocation_deadline" in checks
    assert "assessor_receipt_digest IS NOT NULL" in checks
    assert "assessor_receipt_payload IS NOT NULL" in checks
    assert "assessor_receipt_digest IS NULL" in checks
    assert "assessor_receipt_payload IS NULL" in checks
    assert "assessment_performed IS NULL" in checks


def test_alembic_graph_keeps_0149_in_single_0150_lineage() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260824_0156"]
    revision = script.get_revision("20260817_0149")
    assert revision is not None
    assert revision.down_revision == "20260817_0148"
    source = MIGRATION.read_text(encoding="utf-8")
    assert source.count("op.drop_table(") == 3
    for parent_constraint in (
        "uq_wf_rtready_auth_lease_identity",
        "uq_wf_rtready_auth_lease_consume",
        "uq_wf_rtready_auth_lease_consume_outcome",
    ):
        assert f'op.drop_constraint("{parent_constraint}"' in source or parent_constraint in source
    assert "DROP FUNCTION IF EXISTS {FINAL_VALIDATION_FUNCTION}()" in source
    assert "DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()" in source


def test_all_new_constraint_names_fit_postgresql_identifier_limit() -> None:
    tables = (
        cast(Table, WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel.__table__),
        cast(Table, WorkflowProtectedRuntimeReadinessConsumptionClaimModel.__table__),
        cast(Table, WorkflowProtectedRuntimeReadinessConsumptionAttemptModel.__table__),
        cast(Table, WorkflowProtectedRuntimeReadinessConsumptionResultModel.__table__),
    )
    names = {
        constraint.name
        for table in tables
        for constraint in table.constraints
        if isinstance(constraint.name, str)
        and ("rtready_cons" in constraint.name or "lease_consume" in constraint.name)
    }
    assert names
    assert max(map(len, names)) <= 63
    assert all(
        isinstance(item, UniqueConstraint)
        for item in tables[0].constraints
        if item.name
        in {
            "uq_wf_rtready_auth_lease_identity",
            "uq_wf_rtready_auth_lease_consume",
            "uq_wf_rtready_auth_lease_consume_outcome",
        }
    )
