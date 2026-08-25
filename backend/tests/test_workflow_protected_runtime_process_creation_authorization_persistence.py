from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel,
    WorkflowProtectedRuntimeReadinessConsumptionResultModel,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "20260818_0150_workflow_protected_runtime_process_creation_authorization.py"
)


def _checks(table: Table) -> str:
    return " ".join(
        str(item.sqltext) for item in table.constraints if isinstance(item, CheckConstraint)
    )


def _constraint_names(table: Table) -> set[str]:
    return {item.name for item in table.constraints if isinstance(item.name, str)}


def test_migration_is_linear_append_only_and_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260818_0150"' in source
    assert 'down_revision: str | None = "20260817_0149"' in source
    assert source.count("op.create_table(") == 2
    assert "workflow_event_runtime_process_creation_auth_claims" in source
    assert "workflow_event_runtime_process_creation_auth_leases" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "BEFORE TRUNCATE" in source
    assert "trg_wf_rtproc_auth_claim_append_only" in source
    assert "trg_wf_rtproc_auth_lease_append_only" in source
    assert "INTERVAL '1 second'" in source
    assert "runtime_ready_in_protected_boundary" in source
    assert "refusing guarded downgrade" in source
    assert source.index("op.drop_table(CLAIM_TABLE)") < source.index("op.drop_table(LEASE_TABLE)")
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_models_bind_exact_ready_result_and_canonical_adr160_176_lineage() -> None:
    claim = cast(
        Table,
        WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel.__table__,
    )
    lease = cast(
        Table,
        WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel.__table__,
    )
    result = cast(Table, WorkflowProtectedRuntimeReadinessConsumptionResultModel.__table__)

    assert claim.name == "workflow_event_runtime_process_creation_auth_claims"
    assert lease.name == "workflow_event_runtime_process_creation_auth_leases"
    required = {
        "readiness_result_id",
        "readiness_result_digest",
        "readiness_consumption_id",
        "readiness_attempt_id",
        "readiness_attempt_digest",
        "readiness_claim_id",
        "readiness_claim_digest",
        "readiness_authorization_lease_id",
        "readiness_authorization_lease_digest",
        "readiness_authorization_claim_id",
        "readiness_authorization_claim_digest",
        "start_result_id",
        "start_result_digest",
        "start_attempt_id",
        "start_attempt_digest",
        "runtime_start_authorization_lease_id",
        "runtime_start_authorization_claim_id",
        "destination_deployment_id",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_generation",
        "runtime_envelope_id",
        "runtime_envelope_generation",
        "readiness_profile_digest",
        "process_created",
        "process_scheduled",
        "readiness_failure_class",
        "assessor_receipt_digest",
    }
    for table in (claim, lease):
        assert required <= set(table.c.keys())
        foreign_keys = {
            item.name
            for item in table.foreign_key_constraints
            if isinstance(item, ForeignKeyConstraint)
        }
        prefix = "claim" if table is claim else "lease"
        assert {
            f"fk_wf_rtproc_{prefix}_ready_result",
            f"fk_wf_rtproc_{prefix}_ready_outcome",
            f"fk_wf_rtproc_{prefix}_ready_attempt",
            f"fk_wf_rtproc_{prefix}_ready_claim",
            f"fk_wf_rtproc_{prefix}_ready_lease",
            f"fk_wf_rtproc_{prefix}_ready_auth_claim",
            f"fk_wf_rtproc_{prefix}_started_head",
        } <= foreign_keys
    assert "process_creation_profile_digest" in lease.c
    assert {
        "uq_wf_rtproc_src_ready_result_lineage",
        "uq_wf_rtproc_src_ready_result_outcome",
    } <= _constraint_names(result)


def test_models_enforce_single_use_process_creation_authority_only() -> None:
    claim = cast(
        Table,
        WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel.__table__,
    )
    lease = cast(
        Table,
        WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel.__table__,
    )
    claim_checks = _checks(claim)
    lease_checks = _checks(lease)

    assert "runtime_ready_in_protected_boundary" in claim_checks
    assert "runtime_ready_in_protected_boundary" in lease_checks
    assert "INTERVAL '1 second'" in lease_checks
    assert "valid_until = effective_until" in lease_checks
    assert "single_use" in lease_checks
    assert "NOT renewable" in lease_checks
    assert "NOT transferable" in lease_checks
    assert "NOT lease_is_bearer_capability" in lease_checks
    assert "protected_runtime_process_creation_authority_granted" in lease_checks
    assert "NOT protected_runtime_process_creation_authority_granted" in claim_checks
    for forbidden in (
        "network_access_authorized",
        "readiness_probe_authorized",
        "publication_authorized",
        "delivery_authorized",
        "dispatch_authorized",
        "execution_authorized",
        "infrastructure_mutation_authorized",
        "protected_runtime_readiness_authority_granted",
    ):
        assert f"NOT {forbidden}" in claim_checks
        assert f"NOT {forbidden}" in lease_checks


def test_uniqueness_is_tenant_idempotent_and_one_per_source_result() -> None:
    claim = cast(
        Table,
        WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel.__table__,
    )
    lease = cast(
        Table,
        WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel.__table__,
    )
    assert {
        "uq_wf_rtproc_auth_scope_idem",
        "uq_wf_rtproc_auth_claim_ready_result",
        "uq_wf_rtproc_auth_claim_lease",
        "uq_wf_rtproc_auth_claim_lineage",
    } <= _constraint_names(claim)
    assert {
        "uq_wf_rtproc_auth_lease_ready_result",
        "uq_wf_rtproc_auth_lease_claim",
        "uq_wf_rtproc_auth_lease_claim_digest",
    } <= _constraint_names(lease)
    assert all(
        isinstance(item, UniqueConstraint)
        for table in (claim, lease)
        for item in table.constraints
        if isinstance(item.name, str) and item.name.startswith("uq_wf_rtproc")
    )

    lease_claim_fk = next(
        item
        for item in lease.foreign_key_constraints
        if item.name == "fk_wf_rtproc_auth_lease_claim"
    )
    claim_lease_fk = next(
        item
        for item in claim.foreign_key_constraints
        if item.name == "fk_wf_rtproc_auth_claim_lease"
    )
    assert lease_claim_fk.deferrable is True
    assert lease_claim_fk.initially == "DEFERRED"
    assert claim_lease_fk.deferrable is True
    assert claim_lease_fk.initially == "DEFERRED"


def test_alembic_graph_has_single_0150_head() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260825_0165"]
    revision = script.get_revision("20260818_0150")
    assert revision is not None
    assert revision.down_revision == "20260817_0149"


def test_new_postgresql_identifiers_fit_limit() -> None:
    names = {
        item.name
        for model in (
            WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel,
            WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel,
        )
        for item in cast(Table, model.__table__).constraints
        if isinstance(item.name, str)
    }
    assert names
    assert max(map(len, names)) <= 63
