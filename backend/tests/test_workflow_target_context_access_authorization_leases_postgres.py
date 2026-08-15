from __future__ import annotations

import inspect
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationClaimModel,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.postgres import (
    PostgreSQLWorkflowPlanRepository,
    _TargetContextAccessLockedSources,
)
from atlas.modules.workflows.application.target_context_access_authorization_lease_ports import (
    WorkflowTargetContextAccessAuthorizationLeaseIdempotencyRecord,
    WorkflowTargetContextAccessAuthorizationLeaseRequest,
    WorkflowTargetContextAccessAuthorizationLeaseStatus,
)
from atlas.modules.workflows.domain import WorkflowScope, canonical_digest

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260815_0132_workflow_target_context_access_authorization_lease.py"
)
NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_schema_preserves_internal_currentness_evidence_and_single_authority() -> None:
    lease = cast(
        Table,
        WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseModel.__table__,
    )
    claim = cast(
        Table,
        WorkflowEventPhysicalTransportTargetContextAccessAuthorizationClaimModel.__table__,
    )
    assert lease.name == "workflow_event_tctx_access_authorization_leases"
    assert claim.name == "workflow_event_tctx_access_authorization_claims"
    assert {("target_context_binding_id",), ("canonical_digest",)} <= _unique_columns(lease)
    assert {
        ("idempotency_scope_id", "idempotency_key"),
        ("authorization_lease_id",),
        ("canonical_digest",),
    } <= _unique_columns(claim)
    assert {
        "outbox_entry_id",
        "outbox_entry_digest",
        "route_head_id",
        "route_head_digest",
        "route_head_generation",
        "route_head_fencing_token_digest",
        "assignment_id",
        "assignment_revision",
        "assignment_digest",
        "credential_generation",
        "rotation_epoch",
        "assignment_expires_at",
        "authorization_evidence_digest",
        "authorization_evidence_payload",
    } <= set(lease.columns.keys())
    checks = "\n".join(
        str(constraint.sqltext)
        for constraint in lease.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "valid_until = issued_at + INTERVAL '5 seconds'" in checks
    assert "valid_until <= assignment_expires_at" in checks
    authority_columns = {
        column.name for column in lease.columns if column.name.endswith("_authority_granted")
    }
    assert len(authority_columns) == 17
    assert all(
        name == "protected_artifact_access_authority_granted" or f"NOT {name}" in checks
        for name in authority_columns
    )
    for item in (*lease.constraints, *lease.indexes, *claim.constraints, *claim.indexes):
        if item.name is not None:
            assert len(item.name) <= 63


def test_migration_is_linear_append_only_and_registers_canonical_evidence() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260815_0132"' in migration
    assert 'down_revision: str | None = "20260815_0131"' in migration
    assert "authorization_evidence_digest" in migration
    assert "authorization_evidence_payload" in migration
    assert "route_head_fencing_token_digest" in migration
    assert "trg_wf_tctx_access_leases_append_only" in migration
    assert "trg_wf_tctx_access_claims_append_only" in migration
    assert "BEFORE UPDATE OR DELETE" in migration


def test_repository_locks_lineage_reverifies_signature_and_inserts_atomic_pair() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.authorize_target_context_access)
    lock = source.index("_lock_target_context_access_sources")
    first_signature = source.index("_target_context_access_request_is_valid", lock)
    replay = source.index("_target_context_access_replay", first_signature)
    evidence = source.index("_target_context_access_evidence_matches", replay)
    audit = source.index("required_precommit_audit", evidence)
    second_clock = source.index("clock_timestamp", audit)
    second_signature = source.index("_target_context_access_request_is_valid", second_clock)
    second_evidence = source.index("_target_context_access_evidence_matches", second_signature)
    lease_add = source.index("_target_context_access_lease_model", second_evidence)
    flush = source.index("await session.flush()", lease_add)
    claim_add = source.index("_target_context_access_claim_model", flush)
    commit = source.index("await session.commit()", claim_add)
    assert (
        lock
        < first_signature
        < replay
        < evidence
        < audit
        < second_clock
        < second_signature
        < second_evidence
        < lease_add
        < flush
        < claim_add
        < commit
    )
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_target_context_access_sources
    )
    positions = [
        lock_source.index("binding ="),
        lock_source.index("endpoint_result = cast"),
        lock_source.index("credential_result = cast"),
        lock_source.index("route_binding = cast"),
        lock_source.index("logical_binding = cast"),
        lock_source.index("outbox = cast"),
        lock_source.index("route_snapshot = cast"),
        lock_source.index("route_head = cast"),
        lock_source.index("credential_binding = cast"),
        lock_source.index("credential_snapshot = cast"),
        lock_source.index("pg_advisory_xact_lock"),
        lock_source.index("assignment_rows ="),
        lock_source.index("clock_timestamp"),
    ]
    assert positions == sorted(positions)
    assert "WorkflowOutboxPublicationLeaseModel" not in lock_source
    assert "WorkflowOrchestrationLeaseModel" not in lock_source


def _locked_sources(*, route_head: object, assignment: object) -> _TargetContextAccessLockedSources:
    return _TargetContextAccessLockedSources(
        binding=None,
        endpoint_result=None,
        credential_result=None,
        route_binding=None,
        logical_binding=None,
        outbox=cast(Any, object()),
        route_snapshot=None,
        route_head=cast(Any, route_head),
        credential_binding=None,
        credential_snapshot=None,
        credential_head=cast(Any, assignment),
        observed_at=NOW,
    )


def test_same_route_new_head_generation_or_fence_changes_authorization_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        PostgreSQLWorkflowPlanRepository,
        "_dispatch_outbox_from_row",
        staticmethod(
            lambda _: SimpleNamespace(
                outbox_entry_id="outbox.imp-209",
                canonical_digest="1" * 64,
            )
        ),
    )
    monkeypatch.setattr(
        PostgreSQLWorkflowPlanRepository,
        "_route_selection_head_from_row",
        staticmethod(lambda row: row),
    )
    assignment = SimpleNamespace(
        assignment_id="assignment.imp-209",
        assignment_revision="1",
        canonical_digest="2" * 64,
        credential_generation=7,
        rotation_epoch=9,
        expires_at=NOW + timedelta(minutes=5),
    )
    original_head = SimpleNamespace(
        head_id="route-head.imp-209",
        canonical_digest="3" * 64,
        generation=11,
        fencing_token_digest="4" * 64,
        selected_route_id="route.same",
    )
    replacement_head = SimpleNamespace(
        head_id="route-head.imp-209",
        canonical_digest="5" * 64,
        generation=12,
        fencing_token_digest="6" * 64,
        selected_route_id="route.same",
    )
    original = (
        PostgreSQLWorkflowPlanRepository._target_context_access_authorization_evidence_payload(
            _locked_sources(route_head=original_head, assignment=assignment)
        )
    )
    replacement = (
        PostgreSQLWorkflowPlanRepository._target_context_access_authorization_evidence_payload(
            _locked_sources(route_head=replacement_head, assignment=assignment)
        )
    )
    assert original_head.selected_route_id == replacement_head.selected_route_id
    assert canonical_digest(original) != canonical_digest(replacement)


@pytest.mark.asyncio
async def test_exact_replay_rejects_changed_transaction_time_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored_payload = {
        "route_selection_head": {
            "head_id": "head.imp-209",
            "canonical_digest": "1" * 64,
            "generation": 1,
            "fencing_token_digest": "2" * 64,
        }
    }
    fresh_payload = {
        "route_selection_head": {
            "head_id": "head.imp-209",
            "canonical_digest": "3" * 64,
            "generation": 2,
            "fencing_token_digest": "4" * 64,
        }
    }
    lease = SimpleNamespace(
        valid_until=NOW + timedelta(seconds=4),
        target_context_binding_id="binding.imp-209",
        policy_digest="5" * 64,
    )
    lease_row = SimpleNamespace(authorization_evidence_digest=canonical_digest(stored_payload))
    claim = SimpleNamespace(
        authorization_lease_id="lease.imp-209",
        request_fingerprint="6" * 64,
    )

    class Session:
        async def get(self, model: object, key: str) -> object:
            return lease_row

    repository = cast(
        PostgreSQLWorkflowPlanRepository, object.__new__(PostgreSQLWorkflowPlanRepository)
    )

    async def load_claim(*args: object, **kwargs: object) -> object:
        return claim

    monkeypatch.setattr(repository, "_load_target_context_access_claim", load_claim)
    monkeypatch.setattr(
        repository,
        "_target_context_access_record_from_claim",
        lambda loaded_claim, loaded_row: (
            WorkflowTargetContextAccessAuthorizationLeaseIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                lease=cast(Any, lease),
            )
        ),
    )
    monkeypatch.setattr(
        repository,
        "_target_context_access_authorization_evidence_payload",
        lambda locked: fresh_payload,
    )
    monkeypatch.setattr(
        repository,
        "_target_context_access_evidence_matches",
        lambda **kwargs: True,
    )
    request = cast(
        WorkflowTargetContextAccessAuthorizationLeaseRequest,
        SimpleNamespace(
            scope=SCOPE,
            accessor_subject_id="service.workflow-protected-transport-context-accessor",
            idempotency_key="target-context-access-0001",
            request_fingerprint="6" * 64,
            expected_target_context_binding_id="binding.imp-209",
            expected_policy_digest="5" * 64,
        ),
    )
    locked = _locked_sources(route_head=object(), assignment=object())
    result = await repository._target_context_access_replay(
        cast(Any, Session()), request=request, locked=locked
    )
    assert result is not None
    assert result.status is WorkflowTargetContextAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository._target_context_access_replay)
    assert "authorization_evidence_digest" in source


@pytest.mark.asyncio
async def test_live_postgres_target_context_access_schema_is_installed() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            columns = set(
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'workflow_event_tctx_access_authorization_leases'"
                        )
                    )
                ).scalars()
            )
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger "
                            "WHERE tgname IN ('trg_wf_tctx_access_leases_append_only', "
                            "'trg_wf_tctx_access_claims_append_only')"
                        )
                    )
                ).scalars()
            )
        assert {"authorization_evidence_digest", "authorization_evidence_payload"} <= columns
        assert triggers == {
            "trg_wf_tctx_access_leases_append_only",
            "trg_wf_tctx_access_claims_append_only",
        }
    finally:
        await engine.dispose()
