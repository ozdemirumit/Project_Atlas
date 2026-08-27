from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint
from test_workflow_protected_runtime_process_resume_authorizations import (
    _authorize,
    _Repository,
    _service,
    _source,
)

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeProcessResumeAuthorizationClaimModel,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "migrations"
    / "versions"
    / "20260821_0154_workflow_protected_runtime_process_resume_authorization.py"
)
POSTGRES_ADAPTER = ROOT / "src" / "atlas" / "modules" / "workflows" / "adapters" / "postgres.py"
MODELS = (
    WorkflowProtectedRuntimeProcessResumeAuthorizationClaimModel,
    WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseModel,
)


def _checks(table: Table) -> str:
    return " ".join(
        str(item.sqltext) for item in table.constraints if isinstance(item, CheckConstraint)
    )


def _constraint_names(table: Table) -> set[str]:
    return {item.name for item in table.constraints if isinstance(item.name, str)}


def test_migration_is_linear_bounded_append_only_and_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260821_0154"' in source
    assert 'down_revision: str | None = "20260821_0153"' in source
    assert source.count("op.create_table(") == 2
    assert "workflow_event_runtime_process_resume_auth_claims" in source
    assert "workflow_event_runtime_process_resume_auth_leases" in source
    assert "INTERVAL '1 second'" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "BEFORE TRUNCATE" in source
    assert "refusing guarded downgrade" in source
    assert "uq_wf_rtresume_src_sched_result" in source
    assert "uq_wf_rtresume_src_sched_attempt" in source
    assert "uq_wf_rtresume_src_sched_claim" in source
    assert 'nullable=name == "process_scheduling_failure_class"' in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_models_bind_exact_adr180_and_consumed_adr179_lineage() -> None:
    required = {
        "process_scheduling_result_id",
        "process_scheduling_result_digest",
        "process_scheduling_consumption_id",
        "process_scheduling_attempt_id",
        "process_scheduling_attempt_digest",
        "process_scheduling_claim_id",
        "process_scheduling_claim_digest",
        "process_scheduling_authorization_lease_id",
        "process_scheduling_authorization_lease_digest",
        "process_scheduling_authorization_claim_id",
        "process_scheduling_authorization_claim_digest",
        "process_scheduling_receipt_digest",
        "process_scheduling_result_state",
        "process_scheduling_outcome_known",
        "process_created",
        "process_sealed",
        "process_suspended",
        "process_scheduled",
        "process_runnable",
        "process_resumed",
        "process_dispatched",
        "process_executed",
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "destination_deployment_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "protected_slot_commitment",
        "protected_slot_generation",
        "process_scheduling_profile_digest",
        "primitive_digest",
        "source_protected_operation_reference",
        "source_scheduling_instruction_digest",
    }
    expected_fks = {
        "sched_result",
        "sched_attempt",
        "sched_claim",
        "sched_lease",
        "sched_auth_claim",
    }
    for model, prefix in (
        (WorkflowProtectedRuntimeProcessResumeAuthorizationClaimModel, "claim"),
        (WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseModel, "lease"),
    ):
        table = cast(Table, model.__table__)
        assert required <= set(table.c.keys())
        assert table.c.process_scheduling_failure_class.nullable is True
        assert table.c.process_scheduling_receipt_digest.nullable is False
        assert table.c.process_scheduling_result_digest.nullable is False
        foreign_keys = {
            item.name
            for item in table.foreign_key_constraints
            if isinstance(item, ForeignKeyConstraint)
        }
        assert {f"fk_wf_rtresume_{prefix}_{suffix}" for suffix in expected_fks} <= foreign_keys


def test_models_grant_only_non_operational_future_resume_submission() -> None:
    claim = cast(Table, WorkflowProtectedRuntimeProcessResumeAuthorizationClaimModel.__table__)
    lease = cast(Table, WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseModel.__table__)
    claim_checks = _checks(claim)
    lease_checks = _checks(lease)

    for checks in (claim_checks, lease_checks):
        assert "process_scheduled_suspended_in_protected_boundary" in checks
        assert "process_scheduling_outcome_known" in checks
        assert "process_scheduled" in checks
        assert "process_suspended" in checks
        assert "NOT process_runnable" in checks
        assert "NOT process_resumed" in checks
        assert "NOT process_dispatched" in checks
        assert "NOT process_executed" in checks
        assert "NOT runtime_resume_authorized" in checks
    assert "INTERVAL '1 second'" in lease_checks
    assert "single_use" in lease_checks
    assert "NOT renewable" in lease_checks
    assert "NOT transferable" in lease_checks
    assert "NOT replaceable" in lease_checks
    assert "NOT reissuable" in lease_checks
    assert "NOT lease_is_bearer_capability" in lease_checks
    assert "protected_runtime_process_resume_authority_granted" in lease_checks
    assert "NOT protected_runtime_process_resume_authority_granted" in claim_checks
    for forbidden in (
        "network_access_authorized",
        "publication_authorized",
        "delivery_authorized",
        "dispatch_authorized",
        "execution_authorized",
        "infrastructure_mutation_authorized",
        "connector_activity_authorized",
        "protected_runtime_process_scheduling_authority_granted",
    ):
        assert f"NOT {forbidden}" in claim_checks
        assert f"NOT {forbidden}" in lease_checks


def test_uniqueness_enforces_replay_one_winner_and_no_reissue() -> None:
    claim = cast(Table, WorkflowProtectedRuntimeProcessResumeAuthorizationClaimModel.__table__)
    lease = cast(Table, WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseModel.__table__)
    assert {
        "uq_wf_rtresume_scope_idem",
        "uq_wf_rtresume_claim_result",
        "uq_wf_rtresume_claim_lease",
        "uq_wf_rtresume_claim_lineage",
    } <= _constraint_names(claim)
    assert {
        "uq_wf_rtresume_lease_result",
        "uq_wf_rtresume_lease_claim",
        "uq_wf_rtresume_lease_lineage",
    } <= _constraint_names(lease)
    assert all(
        isinstance(item, UniqueConstraint)
        for table in (claim, lease)
        for item in table.constraints
        if isinstance(item.name, str) and item.name.startswith("uq_wf_rtresume")
    )
    for table, name in (
        (claim, "fk_wf_rtresume_claim_auth_lease"),
        (lease, "fk_wf_rtresume_lease_auth_claim"),
    ):
        foreign_key = next(item for item in table.foreign_key_constraints if item.name == name)
        assert foreign_key.deferrable is True
        assert foreign_key.initially == "DEFERRED"


def test_repository_is_replay_first_atomic_and_revalidates_full_source() -> None:
    source = POSTGRES_ADAPTER.read_text(encoding="utf-8")
    start = source.index("async def authorize_protected_runtime_process_resume")
    end = source.index(
        "async def list_protected_runtime_process_resume_authorization_presentations", start
    )
    body = source[start:end]

    assert body.index("_protected_runtime_process_resume_replay") < body.index(
        "validate_workflow_protected_runtime_process_resume_authorization_request"
    )
    assert "_protected_runtime_process_resume_source_from_locked" in body
    assert "scheduling_source_current" in body
    assert body.count("await session.commit()") == 1
    assert "await session.flush()" in body
    assert "func.clock_timestamp()" in source
    assert "_lock_protected_runtime_process_scheduling_authorization_rows" in source
    assert "_protected_runtime_process_scheduling_source_is_current" in source


@pytest.mark.asyncio
async def test_postgres_models_accept_real_resume_claim_and_lease() -> None:
    source = await _source()
    repository = _Repository(source)
    service = _service(repository)
    lease = await _authorize(service, source)
    request = repository.requests[-1]
    result_row = SimpleNamespace()
    attempt_row = SimpleNamespace(
        protected_operation_reference=source.attempt.protected_operation_reference,
        instruction_digest="a" * 64,
    )
    claim_row = PostgreSQLWorkflowPlanRepository._protected_runtime_process_resume_claim_model(
        request.candidate_claim,
        authorization_lease_id=lease.authorization_lease_id,
        idempotency_key=request.idempotency_key,
        audit_payload={
            "policy_digest": lease.policy_digest,
            "request_fingerprint": request.request_fingerprint,
            "scope": lease.scope.canonical_value(),
            "process_scheduling_result_id": source.result.result_id,
        },
        result_row=cast(Any, result_row),
        attempt_row=cast(Any, attempt_row),
        source_observed_at=request.requested_at,
    )
    lease_row = PostgreSQLWorkflowPlanRepository._protected_runtime_process_resume_lease_model(
        lease,
        request.process_state_attestation,
        result_row=cast(Any, result_row),
        attempt_row=cast(Any, attempt_row),
        source_observed_at=request.requested_at,
    )

    assert claim_row.process_scheduling_result_digest == source.result.canonical_digest
    assert claim_row.runtime_resume_authorized is False
    assert claim_row.protected_runtime_process_resume_authority_granted is False
    assert lease_row.runtime_resume_authorized is False
    assert lease_row.protected_runtime_process_resume_authority_granted is True
    assert lease_row.effective_until <= lease_row.issued_at + timedelta(seconds=1)
    assert (
        PostgreSQLWorkflowPlanRepository._protected_runtime_process_resume_claim_from_row(claim_row)
        == request.candidate_claim
    )
    assert (
        PostgreSQLWorkflowPlanRepository._protected_runtime_process_resume_lease_from_row(lease_row)
        == lease
    )


def test_alembic_graph_has_single_0154_head_and_identifiers_fit_postgresql() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260827_0168"]
    revision = script.get_revision("20260821_0154")
    assert revision is not None
    assert revision.down_revision == "20260821_0153"
    names = {
        item.name
        for model in MODELS
        for item in cast(Table, model.__table__).constraints
        if isinstance(item.name, str)
    }
    assert names
    assert max(map(len, names)) <= 63
