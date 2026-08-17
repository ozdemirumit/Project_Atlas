from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeContextUseResultModel,
    WorkflowProtectedRuntimeReadinessAuthorizationClaimModel,
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel,
    WorkflowProtectedRuntimeStartAuthorizationClaimModel,
    WorkflowProtectedRuntimeStartAuthorizationLeaseModel,
    WorkflowProtectedRuntimeStartConsumptionAttemptModel,
    WorkflowProtectedRuntimeStartConsumptionClaimModel,
    WorkflowProtectedRuntimeStartConsumptionResultModel,
    WorkflowProtectedRuntimeStartCoordinationHeadModel,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "20260817_0148_workflow_protected_runtime_readiness_authorization.py"
)


def _checks(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


SCOPE_COLUMNS = ("organization_id", "environment_id", "site_id")


def _constraint_columns(constraint: UniqueConstraint) -> tuple[str, ...]:
    return tuple(column.name for column in constraint.columns)


def test_migration_is_linear_append_only_guarded_and_source_complete() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260817_0148"' in source
    assert 'down_revision: str | None = "20260817_0147"' in source
    assert source.count("op.create_table(") == 2
    assert "workflow_event_runtime_readiness_auth_claims" in source
    assert "workflow_event_runtime_readiness_auth_leases" in source
    for parent in (
        "workflow_event_runtime_start_consumption_results",
        "workflow_event_runtime_start_consumption_attempts",
        "workflow_event_runtime_start_consumption_claims",
        "workflow_event_runtime_start_auth_leases",
        "workflow_event_runtime_start_auth_claims",
        "workflow_event_runtime_start_coordination_heads",
    ):
        assert parent in source
    for suffix in (
        "start_result",
        "start_outcome",
        "start_attempt",
        "start_claim",
        "start_lease",
        "start_auth_claim",
        "started_head",
    ):
        assert f"fk_wf_rtready_{{prefix}}_{suffix}" in source
    assert "uq_wf_rtready_auth_claim_result" in source
    assert "uq_wf_rtready_auth_claim_slot" in source
    assert "uq_wf_rtready_auth_lease_result" in source
    assert "uq_wf_rtready_auth_lease_slot" in source
    assert "uq_wf_rtready_src_use_result_scope" in source
    assert "fk_wf_rtstart_coord_ready_scope" in source
    assert "trg_wf_rtstart_coord_ready_scope" in source
    assert "readiness_attestation_valid_until " in source
    assert "<= readiness_attestation_observed_at + INTERVAL '1 second'" in source
    assert "valid_until = effective_until" in source
    assert "valid_until <= effective_until" not in source
    assert "INTERVAL '1 second'" in source
    assert "protected_runtime_readiness_authority_granted" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert source.count("BEFORE TRUNCATE") == 1
    assert "trg_wf_rtready_auth_lease_append_only" in source
    assert "trg_wf_rtready_auth_claim_append_only" in source
    assert "trg_wf_rtready_auth_lease_no_truncate" in source
    assert "trg_wf_rtready_auth_claim_no_truncate" in source
    assert (
        "refusing guarded downgrade: protected runtime-readiness authorization evidence exists"
        in source
    )
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_models_bind_complete_adr174_lineage_and_one_canonical_claim() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeReadinessAuthorizationClaimModel.__table__)
    result = cast(Table, WorkflowProtectedRuntimeStartConsumptionResultModel.__table__)
    coordination = cast(Table, WorkflowProtectedRuntimeStartCoordinationHeadModel.__table__)
    use_result = cast(Table, WorkflowProtectedRuntimeContextUseResultModel.__table__)
    start_lease = cast(Table, WorkflowProtectedRuntimeStartAuthorizationLeaseModel.__table__)
    start_auth_claim = cast(Table, WorkflowProtectedRuntimeStartAuthorizationClaimModel.__table__)
    start_claim = cast(Table, WorkflowProtectedRuntimeStartConsumptionClaimModel.__table__)
    start_attempt = cast(Table, WorkflowProtectedRuntimeStartConsumptionAttemptModel.__table__)

    assert lease.name == "workflow_event_runtime_readiness_auth_leases"
    assert claim.name == "workflow_event_runtime_readiness_auth_claims"
    required = {
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
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_generation",
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "starter_receipt_digest",
        "coordination_state",
    }
    assert required <= set(lease.c.keys())
    assert required <= set(claim.c.keys())
    expected_foreign_keys = {
        "fk_wf_rtready_claim_start_result",
        "fk_wf_rtready_claim_start_outcome",
        "fk_wf_rtready_claim_start_attempt",
        "fk_wf_rtready_claim_start_claim",
        "fk_wf_rtready_claim_start_lease",
        "fk_wf_rtready_claim_start_auth_claim",
        "fk_wf_rtready_claim_started_head",
        "fk_wf_rtready_auth_claim_lease",
    }
    assert expected_foreign_keys == {
        constraint.name for constraint in claim.foreign_key_constraints
    }
    assert {
        "uq_wf_rtready_auth_claim_result",
        "uq_wf_rtready_auth_claim_slot",
        "uq_wf_rtready_auth_scope_idem",
    } <= {constraint.name for constraint in claim.constraints}
    assert {
        "uq_wf_rtready_auth_lease_result",
        "uq_wf_rtready_auth_lease_slot",
        "uq_wf_rtready_auth_lease_claim",
    } <= {constraint.name for constraint in lease.constraints}
    assert "uq_wf_rtready_src_start_result_lineage" in {
        constraint.name for constraint in result.constraints
    }
    assert "uq_wf_rtready_src_start_result_outcome" in {
        constraint.name for constraint in result.constraints
    }
    assert "uq_wf_rtready_src_started_head" in {
        constraint.name for constraint in coordination.constraints
    }
    assert "fk_wf_rtstart_coord_ready_scope" in {
        constraint.name for constraint in coordination.foreign_key_constraints
    }
    assert set(SCOPE_COLUMNS) <= set(coordination.c.keys())
    scoped_target_constraints = {
        use_result: "uq_wf_rtready_src_use_result_scope",
        start_lease: "uq_wf_rtready_src_start_lease",
        start_auth_claim: "uq_wf_rtready_src_start_auth_claim",
        start_claim: "uq_wf_rtready_src_start_claim",
        start_attempt: "uq_wf_rtready_src_start_attempt",
        result: "uq_wf_rtready_src_start_result_lineage",
        coordination: "uq_wf_rtready_src_started_head",
    }
    for table, constraint_name in scoped_target_constraints.items():
        constraint = next(
            item
            for item in table.constraints
            if isinstance(item, UniqueConstraint) and item.name == constraint_name
        )
        assert _constraint_columns(constraint)[:3] == SCOPE_COLUMNS

    for table in (lease, claim):
        source_constraints = [
            constraint
            for constraint in table.foreign_key_constraints
            if constraint.name is not None
            and constraint.name.startswith(
                "fk_wf_rtready_lease_" if table is lease else "fk_wf_rtready_claim_"
            )
        ]
        assert len(source_constraints) == 7
        for constraint in source_constraints:
            assert isinstance(constraint, ForeignKeyConstraint)
            assert tuple(column.name for column in constraint.columns)[:3] == SCOPE_COLUMNS
            assert (
                tuple(element.column.name for element in constraint.elements)[:3] == SCOPE_COLUMNS
            )
    assert all(
        isinstance(constraint, UniqueConstraint)
        for constraint in claim.constraints
        if constraint.name
        in {
            "uq_wf_rtready_auth_claim_result",
            "uq_wf_rtready_auth_claim_slot",
        }
    )


def test_models_enforce_one_second_dedicated_readiness_authority_only() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeReadinessAuthorizationClaimModel.__table__)
    lease_checks = _checks(lease)
    claim_checks = _checks(claim)

    assert "INTERVAL '1 second'" in lease_checks
    assert (
        "readiness_attestation_valid_until <= readiness_attestation_observed_at "
        "+ INTERVAL '1 second'" in lease_checks
    )
    assert "valid_until = effective_until" in lease_checks
    assert "valid_until <= effective_until" not in lease_checks
    assert "single_use" in lease_checks
    assert "NOT renewable" in lease_checks
    assert "NOT transferable" in lease_checks
    assert "NOT lease_is_bearer_capability" in lease_checks
    assert "protected_runtime_readiness_authority_granted" in lease_checks
    assert "NOT protected_runtime_readiness_authority_granted" in claim_checks
    assert "runtime_started_in_protected_boundary" in lease_checks
    assert "start_attempt_terminal" in lease_checks
    for forbidden in (
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
        "protected_runtime_start_authority_granted",
    ):
        assert f"NOT {forbidden}" in lease_checks
        assert f"NOT {forbidden}" in claim_checks
