from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaimModel,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseModel,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "20260820_0152_workflow_protected_runtime_process_scheduling_authorization.py"
)


def _checks(table: Table) -> str:
    return " ".join(
        str(item.sqltext) for item in table.constraints if isinstance(item, CheckConstraint)
    )


def _constraint_names(table: Table) -> set[str]:
    return {item.name for item in table.constraints if isinstance(item.name, str)}


def test_migration_is_linear_bounded_append_only_and_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260820_0152"' in source
    assert 'down_revision: str | None = "20260820_0151"' in source
    assert source.count("op.create_table(") == 2
    assert "workflow_event_runtime_process_scheduling_auth_claims" in source
    assert "workflow_event_runtime_process_scheduling_auth_leases" in source
    assert "func.clock_timestamp" not in source
    assert "INTERVAL '1 second'" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "BEFORE TRUNCATE" in source
    assert "refusing guarded downgrade" in source
    assert "uq_wf_rtpsched_src_result_lineage" in source
    assert "uq_wf_rtpsched_src_attempt_lineage" in source
    assert "uq_wf_rtpsched_src_claim_lineage" in source
    assert "uq_wf_rtpsched_src_auth_lease" in source
    assert 'nullable=name == "process_creation_failure_class"' in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_models_bind_exact_successful_adr178_lineage() -> None:
    claim = cast(Table, WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaimModel.__table__)
    lease = cast(Table, WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseModel.__table__)
    required = {
        "process_creation_result_id",
        "process_creation_result_digest",
        "process_creation_consumption_id",
        "process_creation_attempt_id",
        "process_creation_attempt_digest",
        "process_creation_claim_id",
        "process_creation_claim_digest",
        "process_creation_authorization_lease_id",
        "process_creation_authorization_lease_digest",
        "process_creation_authorization_claim_id",
        "process_creation_authorization_claim_digest",
        "process_creation_receipt_digest",
        "process_creation_result_state",
        "process_creation_outcome_known",
        "process_created",
        "process_sealed",
        "process_suspended",
        "process_scheduled",
        "process_resumed",
        "process_dispatched",
        "process_executed",
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "destination_deployment_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_generation",
        "process_creation_profile_digest",
        "primitive_digest",
    }
    expected_fks = {
        "result",
        "attempt",
        "claim",
        "src_lease",
        "src_auth_claim",
    }
    for table, prefix in ((claim, "claim"), (lease, "lease")):
        assert required <= set(table.c.keys())
        assert table.c.process_creation_failure_class.nullable is True
        assert table.c.process_creation_receipt_digest.nullable is False
        assert table.c.process_creation_result_digest.nullable is False
        names = {
            item.name
            for item in table.foreign_key_constraints
            if isinstance(item, ForeignKeyConstraint)
        }
        assert {f"fk_wf_rtpsched_{prefix}_{suffix}" for suffix in expected_fks} <= names
        for foreign_key in table.foreign_key_constraints:
            constraint_name = foreign_key.name
            if isinstance(constraint_name, str) and constraint_name.startswith(
                f"fk_wf_rtpsched_{prefix}_"
            ):
                local = {column.name for column in foreign_key.columns}
                if constraint_name.endswith(("result", "attempt", "claim", "src_lease")):
                    assert {"organization_id", "environment_id", "site_id"} <= local
                assert len(local) <= 32


def test_models_grant_only_one_future_scheduling_request_authority() -> None:
    claim = cast(Table, WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaimModel.__table__)
    lease = cast(Table, WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseModel.__table__)
    claim_checks = _checks(claim)
    lease_checks = _checks(lease)

    for checks in (claim_checks, lease_checks):
        assert "process_created_suspended_in_protected_boundary" in checks
        assert "process_creation_outcome_known" in checks
        assert "process_created" in checks
        assert "process_sealed" in checks
        assert "process_suspended" in checks
        assert "NOT process_scheduled" in checks
        assert "NOT process_resumed" in checks
        assert "NOT process_dispatched" in checks
        assert "NOT process_executed" in checks
    assert "INTERVAL '1 second'" in lease_checks
    assert "issued_at = effective_from" in lease_checks
    assert "valid_until = effective_until" in lease_checks
    assert "single_use" in lease_checks
    assert "NOT renewable" in lease_checks
    assert "NOT transferable" in lease_checks
    assert "NOT replaceable" in lease_checks
    assert "NOT reissuable" in lease_checks
    assert "NOT lease_is_bearer_capability" in lease_checks
    assert "protected_runtime_process_scheduling_authority_granted" in lease_checks
    assert "NOT protected_runtime_process_scheduling_authority_granted" in claim_checks
    for forbidden in (
        "network_access_authorized",
        "publication_authorized",
        "delivery_authorized",
        "dispatch_authorized",
        "execution_authorized",
        "infrastructure_mutation_authorized",
        "connector_activity_authorized",
        "protected_runtime_process_creation_authority_granted",
    ):
        assert f"NOT {forbidden}" in claim_checks
        assert f"NOT {forbidden}" in lease_checks


def test_uniqueness_enforces_replay_one_winner_and_no_reissue() -> None:
    claim = cast(Table, WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaimModel.__table__)
    lease = cast(Table, WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseModel.__table__)
    assert {
        "uq_wf_rtpsched_scope_idem",
        "uq_wf_rtpsched_claim_result",
        "uq_wf_rtpsched_claim_lease",
        "uq_wf_rtpsched_claim_lineage",
    } <= _constraint_names(claim)
    assert {
        "uq_wf_rtpsched_lease_result",
        "uq_wf_rtpsched_lease_claim",
        "uq_wf_rtpsched_lease_lineage",
    } <= _constraint_names(lease)
    assert all(
        isinstance(item, UniqueConstraint)
        for table in (claim, lease)
        for item in table.constraints
        if isinstance(item.name, str) and item.name.startswith("uq_wf_rtpsched")
    )
    claim_lease = next(
        item
        for item in claim.foreign_key_constraints
        if item.name == "fk_wf_rtpsched_claim_auth_lease"
    )
    lease_claim = next(
        item
        for item in lease.foreign_key_constraints
        if item.name == "fk_wf_rtpsched_lease_auth_claim"
    )
    for foreign_key in (claim_lease, lease_claim):
        assert foreign_key.deferrable is True
        assert foreign_key.initially == "DEFERRED"


def test_alembic_graph_keeps_0152_as_parent_and_identifiers_fit_postgresql() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260825_0165"]
    revision = script.get_revision("20260820_0152")
    assert revision is not None
    assert revision.down_revision == "20260820_0151"
    child = script.get_revision("20260821_0153")
    assert child is not None
    assert child.down_revision == "20260820_0152"
    names = {
        item.name
        for model in (
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationClaimModel,
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseModel,
        )
        for item in cast(Table, model.__table__).constraints
        if isinstance(item.name, str)
    }
    assert names
    assert max(map(len, names)) <= 63
