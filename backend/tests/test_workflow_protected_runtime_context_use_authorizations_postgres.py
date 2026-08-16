from __future__ import annotations

import inspect
import os
import re
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Table, UniqueConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeContextInjectionAttemptModel,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseModel,
    WorkflowProtectedRuntimeContextInjectionConsumptionClaimModel,
    WorkflowProtectedRuntimeContextInjectionResultModel,
    WorkflowProtectedRuntimeContextUseAuthorizationClaimModel,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260816_0143_workflow_protected_runtime_context_use_authorization.py"
)


def _checks(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if hasattr(constraint, "sqltext")
    )


def test_migration_is_linear_append_only_guarded_and_non_colliding() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()

    assert 'revision: str = "20260816_0143"' in source
    assert 'down_revision: str | None = "20260816_0142"' in source
    assert source.count("op.create_table(") == 2
    assert "workflow_event_runtime_context_use_auth_leases" in source
    assert "workflow_event_runtime_context_use_auth_claims" in source
    assert 'SOURCE_TABLE = "workflow_event_runtime_context_injection_results"' in source
    assert 'ATTEMPT_TABLE = "workflow_event_runtime_context_injection_attempts"' in source
    assert "_upstream_foreign_keys" in source
    assert "uq_wf_rtctx_inj_result_id_digest" in source
    assert "uq_wf_rtctx_inj_attempt_id_digest" in source
    assert "uq_wf_rtctx_inj_consume_claim_id_digest" in source
    assert "uq_wf_rtctx_inj_auth_lease_id_digest" in source
    assert "fk_wf_rtctx_use_{prefix}_result" in source
    assert "fk_wf_rtctx_use_{prefix}_attempt" in source
    assert "fk_wf_rtctx_use_{prefix}_consume_claim" in source
    assert "fk_wf_rtctx_use_{prefix}_inj_auth_lease" in source
    assert "fk_wf_rtctx_use_auth_claim_lease" in source
    assert "fk_wf_rtctx_use_auth_lease_claim" in source
    assert source.count("deferrable=True") == 2
    assert source.count('initially="DEFERRED"') == 2
    assert "uq_wf_rtctx_use_auth_lease_result" in source
    assert "uq_wf_rtctx_use_auth_lease_slot_generation" in source
    assert "uq_wf_rtctx_use_auth_scope_idem" in source
    assert "INTERVAL '1 second'" in source
    assert "effective_until <= injected_context_usable_until" in source
    assert "claimed_at < injected_context_usable_until" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "trg_wf_rtctx_use_auth_lease_append_only" in source
    assert "trg_wf_rtctx_use_auth_claim_append_only" in source
    assert "refusing guarded downgrade: runtime-context use authorization evidence exists" in source
    guard_index = source.index("refusing guarded downgrade")
    assert guard_index < source.index('"uq_wf_rtctx_inj_auth_lease_id_digest"', guard_index)
    assert policy.canonical_digest in source
    assert policy.runtime_slot_profile_digest in source
    assert policy.use_profile_digest in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_orm_binds_exact_result_slot_fence_and_one_winner_constraints() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeContextUseAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeContextUseAuthorizationClaimModel.__table__)

    assert lease.name == "workflow_event_runtime_context_use_auth_leases"
    assert claim.name == "workflow_event_runtime_context_use_auth_claims"
    assert {
        "injection_result_id",
        "injection_result_digest",
        "injection_id",
        "injection_attempt_id",
        "injection_attempt_digest",
        "injection_consumption_claim_id",
        "injection_consumption_claim_digest",
        "injection_authorization_lease_id",
        "injection_authorization_lease_digest",
        "injector_receipt_digest",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_post_generation",
        "injected_context_usable_until",
    } <= set(lease.c.keys())
    assert "runtime_slot_pre_generation" not in lease.c
    assert "fk_wf_rtctx_use_auth_claim_lease" in {
        constraint.name for constraint in claim.foreign_key_constraints
    }
    lease_claim_fk = next(
        constraint
        for constraint in lease.foreign_key_constraints
        if constraint.name == "fk_wf_rtctx_use_auth_lease_claim"
    )
    assert lease_claim_fk.deferrable is True
    assert lease_claim_fk.initially == "DEFERRED"
    assert {
        "uq_wf_rtctx_use_auth_lease_result",
        "uq_wf_rtctx_use_auth_lease_slot_generation",
        "uq_wf_rtctx_use_auth_lease_claim",
    } <= {constraint.name for constraint in lease.constraints}
    assert {
        "uq_wf_rtctx_use_auth_claim_result",
        "uq_wf_rtctx_use_auth_claim_slot_generation",
        "uq_wf_rtctx_use_auth_scope_idem",
    } <= {constraint.name for constraint in claim.constraints}


def test_orm_composite_upstream_lineage_rejects_id_digest_mismatch() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeContextUseAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeContextUseAuthorizationClaimModel.__table__)
    parents = (
        (
            cast(Table, WorkflowProtectedRuntimeContextInjectionResultModel.__table__),
            ("result_id", "canonical_digest"),
            ("injection_result_id", "injection_result_digest"),
        ),
        (
            cast(Table, WorkflowProtectedRuntimeContextInjectionAttemptModel.__table__),
            ("attempt_id", "canonical_digest"),
            ("injection_attempt_id", "injection_attempt_digest"),
        ),
        (
            cast(
                Table,
                WorkflowProtectedRuntimeContextInjectionConsumptionClaimModel.__table__,
            ),
            ("claim_id", "canonical_digest"),
            ("injection_consumption_claim_id", "injection_consumption_claim_digest"),
        ),
        (
            cast(
                Table,
                WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseModel.__table__,
            ),
            ("authorization_lease_id", "canonical_digest"),
            ("injection_authorization_lease_id", "injection_authorization_lease_digest"),
        ),
    )

    for parent, remote_columns, local_columns in parents:
        assert any(
            tuple(column.name for column in constraint.columns) == remote_columns
            for constraint in parent.constraints
            if isinstance(constraint, UniqueConstraint)
        )
        for child in (lease, claim):
            assert any(
                tuple(element.parent.name for element in constraint.elements) == local_columns
                and tuple(element.column.name for element in constraint.elements) == remote_columns
                and all(element.column.table is parent for element in constraint.elements)
                for constraint in child.foreign_key_constraints
            )


def test_orm_enforces_one_second_single_use_zero_operational_authority() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeContextUseAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeContextUseAuthorizationClaimModel.__table__)
    lease_checks = _checks(lease)
    claim_checks = _checks(claim)

    assert "INTERVAL '1 second'" in lease_checks
    assert "effective_until <= injected_context_usable_until" in lease_checks
    assert "claimed_at < injected_context_usable_until" in claim_checks
    assert "single_use" in lease_checks
    assert "NOT renewable" in lease_checks
    assert "NOT transferable" in lease_checks
    assert "NOT lease_is_bearer_capability" in lease_checks
    assert "protected_runtime_context_use_authority_granted" in lease_checks
    assert "NOT protected_runtime_context_use_authority_granted" in claim_checks
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
        "protected_runtime_context_injection_authority_granted",
    ):
        assert f"NOT {forbidden}" in lease_checks
        assert f"NOT {forbidden}" in claim_checks


def test_schema_discloses_no_context_payload_locator_endpoint_credential_or_secret() -> None:
    tables = (
        cast(Table, WorkflowProtectedRuntimeContextUseAuthorizationLeaseModel.__table__),
        cast(Table, WorkflowProtectedRuntimeContextUseAuthorizationClaimModel.__table__),
    )
    forbidden = {
        "raw_context",
        "runtime_payload",
        "runtime_slot_locator",
        "protected_operation_reference",
        "endpoint",
        "credential",
        "secret",
        "bearer_token",
    }
    for table in tables:
        assert forbidden.isdisjoint(table.c.keys())
        assert table.c.payload.nullable is False
        assert table.c.injector_receipt_digest.nullable is False


def test_repository_uses_two_database_times_canonical_locks_and_consumption_hook() -> None:
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_runtime_context_use_authorization_rows
    )
    authorize_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.authorize_protected_runtime_context_use
    )
    presentation_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.list_protected_runtime_context_use_authorization_presentations
    )
    evidence_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_context_use_evidence_matches
    )
    retime_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_context_use_retimed_request
    )

    assert lock_source.count("clock_timestamp") == 2
    assert "with_for_update" in lock_source
    assert lock_source.index("injection_authorization_lease =") < lock_source.index("claim = cast(")
    assert lock_source.index("claim = cast(") < lock_source.index("attempt = cast(")
    assert lock_source.index("attempt = cast(") < lock_source.index("result = cast(")
    assert lock_source.index("result = cast(") < lock_source.index("destination_head = cast(")
    assert lock_source.index("destination_head = cast(") < lock_source.index("slot_statement =")
    assert "WorkflowProtectedRuntimeContextInjectionDestinationHeadModel" in lock_source
    assert "runtime_slot_post_generation" in lock_source
    assert "request.pre_attestation_observed_at" in evidence_source
    assert "locked.first_observed_at" in evidence_source
    assert "locked.observed_at < attestation.valid_until" in evidence_source
    assert "locked.observed_at < attestation.injected_context_usable_until" in evidence_source
    assert "destination.destination_generation" in evidence_source
    assert "destination.destination_fencing_token_digest" in evidence_source
    assert "request.lifecycle_attestation.injected_context_usable_until" in retime_source
    assert "except IntegrityError" in authorize_source
    assert "_protected_runtime_context_use_replay" in authorize_source
    assert "_protected_runtime_context_use_consumed_expression" in presentation_source


@pytest.mark.asyncio
async def test_live_postgres_tables_and_append_only_triggers_when_configured() -> None:
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
                            "AND tablename IN (:lease, :claim)"
                        ),
                        {
                            "lease": "workflow_event_runtime_context_use_auth_leases",
                            "claim": "workflow_event_runtime_context_use_auth_claims",
                        },
                    )
                ).scalars()
            )
            assert tables == {
                "workflow_event_runtime_context_use_auth_leases",
                "workflow_event_runtime_context_use_auth_claims",
            }
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_rtctx_use_auth_lease_append_only', "
                            "'trg_wf_rtctx_use_auth_claim_append_only')"
                        )
                    )
                ).scalars()
            )
            assert triggers == {
                "trg_wf_rtctx_use_auth_lease_append_only",
                "trg_wf_rtctx_use_auth_claim_append_only",
            }
    finally:
        await engine.dispose()
