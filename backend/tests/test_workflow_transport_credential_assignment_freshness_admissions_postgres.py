from __future__ import annotations

import asyncio
import inspect
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from test_workflow_transport_credential_assignment_bindings_postgres import (
    _request as credential_binding_request,
)
from test_workflow_transport_credential_assignment_bindings_postgres import (
    _reset_live_rows as reset_binding_rows,
)
from test_workflow_transport_credential_assignment_bindings_postgres import (
    _seed_live_sources as seed_binding_sources,
)
from test_workflow_transport_credential_assignment_snapshots import assignment_fixture

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionError,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260815_0128_workflow_credential_assignment_freshness.py"
)


async def _audit() -> None:
    return None


def _head(
    route: Any,
    snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
    *,
    active: bool = True,
    revoked: bool = False,
    revision: str | None = None,
    generation: int | None = None,
    rotation_epoch: int | None = None,
) -> DeploymentPhysicalTransportCredentialAssignment:
    return assignment_fixture(
        assignment_id=snapshot.assignment_id,
        assignment_revision=revision or snapshot.assignment_revision,
        route=route,
        scope=snapshot.scope,
        active=active,
        revoked=revoked,
        credential_generation=generation or snapshot.credential_generation,
        rotation_epoch=rotation_epoch or snapshot.rotation_epoch,
        activated_at=snapshot.activated_at,
        expires_at=snapshot.expires_at,
    )


def _candidate(
    binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
    head: DeploymentPhysicalTransportCredentialAssignment,
    *,
    requested_at: datetime,
    idempotency_key: str,
) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission:
    policy = code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy()
    authority = WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority()
    admission_id = f"credential-assignment-freshness.pg-{canonical_digest(idempotency_key)[:24]}"
    values: dict[str, Any] = {
        "freshness_admission_id": admission_id,
        "physical_transport_credential_assignment_binding_id": binding.binding_id,
        "physical_transport_credential_assignment_binding_digest": binding.canonical_digest,
        "credential_assignment_snapshot_id": snapshot.snapshot_id,
        "credential_assignment_snapshot_digest": snapshot.canonical_digest,
        "assignment_id": head.assignment_id,
        "assignment_revision": head.assignment_revision,
        "source_assignment_digest": head.canonical_digest,
        "credential_generation": head.credential_generation,
        "rotation_epoch": head.rotation_epoch,
        "assignment_activated_at": head.activated_at,
        "assignment_expires_at": head.expires_at,
        "assignment_active": head.active,
        "assignment_non_revoked": not head.revoked,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "scope": binding.scope,
        "admitter_subject_id": (
            WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT
        ),
        "evaluated_at": requested_at,
        "valid_until": min(requested_at + timedelta(seconds=60), head.expires_at),
        "state": (
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState.ADMITTED_CURRENT
        ),
        "authority": authority,
    }
    payload = {
        "admitter_subject_id": values["admitter_subject_id"],
        "assignment_activated_at": head.activated_at.isoformat(),
        "assignment_active": head.active,
        "assignment_expires_at": head.expires_at.isoformat(),
        "assignment_id": head.assignment_id,
        "assignment_non_revoked": not head.revoked,
        "assignment_revision": head.assignment_revision,
        "authority": authority.canonical_value(),
        "credential_assignment_snapshot_digest": snapshot.canonical_digest,
        "credential_assignment_snapshot_id": snapshot.snapshot_id,
        "credential_generation": head.credential_generation,
        "evaluated_at": requested_at.isoformat(),
        "freshness_admission_id": admission_id,
        "physical_transport_credential_assignment_binding_digest": binding.canonical_digest,
        "physical_transport_credential_assignment_binding_id": binding.binding_id,
        "policy_digest": policy.canonical_digest,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "rotation_epoch": head.rotation_epoch,
        "scope": binding.scope.canonical_value(),
        "source_assignment_digest": head.canonical_digest,
        "state": "admitted_current",
        "valid_until": values["valid_until"].isoformat(),
    }
    return WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission(
        **values,
        canonical_digest=canonical_digest(payload),
    )


def _admission_request(
    binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
    head: DeploymentPhysicalTransportCredentialAssignment,
    *,
    requested_at: datetime,
    idempotency_key: str,
) -> WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest:
    candidate = _candidate(
        binding,
        snapshot,
        head,
        requested_at=requested_at,
        idempotency_key=idempotency_key,
    )
    fingerprint = canonical_digest(
        {
            "admitter_subject_id": candidate.admitter_subject_id,
            "assignment_head_digest": head.canonical_digest,
            "assignment_revision": head.assignment_revision,
            "credential_assignment_binding_digest": binding.canonical_digest,
            "credential_assignment_binding_id": binding.binding_id,
            "credential_assignment_snapshot_digest": snapshot.canonical_digest,
            "credential_assignment_snapshot_id": snapshot.snapshot_id,
            "credential_generation": head.credential_generation,
            "rotation_epoch": head.rotation_epoch,
            "scope": binding.scope.canonical_value(),
        }
    )
    return WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest(
        expected_credential_assignment_binding_id=binding.binding_id,
        expected_credential_assignment_binding_digest=binding.canonical_digest,
        expected_credential_assignment_snapshot_id=snapshot.snapshot_id,
        expected_credential_assignment_snapshot_digest=snapshot.canonical_digest,
        expected_assignment_id=head.assignment_id,
        expected_assignment_revision=head.assignment_revision,
        expected_source_assignment_digest=head.canonical_digest,
        expected_credential_generation=head.credential_generation,
        expected_rotation_epoch=head.rotation_epoch,
        expected_assignment_activated_at=head.activated_at,
        expected_assignment_expires_at=head.expires_at,
        expected_assignment_active=head.active,
        expected_assignment_revoked=head.revoked,
        expected_policy_digest=candidate.policy_digest,
        scope=binding.scope,
        admitter_subject_id=candidate.admitter_subject_id,
        requested_at=requested_at,
        candidate=candidate,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        required_precommit_audit=_audit,
    )


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_models_enforce_append_only_identity_window_and_17_zero_authority_flags() -> None:
    admission = cast(
        Table,
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.__table__,
    )
    claim = cast(
        Table,
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel.__table__,
    )
    assert admission.name == "workflow_event_transport_credential_freshness_admissions"
    assert claim.name == "workflow_event_transport_credential_freshness_claims"
    assert ("canonical_digest",) in _unique_columns(admission)
    assert {
        ("idempotency_scope_id", "idempotency_key"),
        ("freshness_admission_id",),
        ("canonical_digest",),
    } <= _unique_columns(claim)
    assert ("credential_assignment_binding_id",) not in _unique_columns(admission), (
        "one binding must allow multiple admissions"
    )
    checks = "\n".join(
        str(constraint.sqltext)
        for constraint in admission.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "state = 'admitted_current'" in checks
    assert "valid_until <= assignment_expires_at" in checks
    assert "60" in checks
    authority_columns = {
        column.name for column in admission.columns if column.name.endswith("_authority_granted")
    }
    assert len(authority_columns) == 17
    assert all(f"NOT {name}" in checks for name in authority_columns)


def test_repository_uses_fixed_lock_order_shared_advisory_lock_and_database_time() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.admit_credential_assignment_freshness
    )
    lock = source.index("_lock_credential_assignment_freshness_sources")
    evidence = source.index("_credential_assignment_freshness_evidence_matches", lock)
    replay = source.index("_credential_assignment_freshness_replay", evidence)
    audit = source.index("required_precommit_audit", replay)
    commit_time = source.index("clock_timestamp", audit)
    admission_add = source.index("_credential_assignment_freshness_admission_model", audit)
    flush = source.index("await session.flush()", admission_add)
    claim_add = source.index("_credential_assignment_freshness_claim_model", flush)
    commit = source.index("await session.commit()", claim_add)
    assert (
        lock < evidence < replay < audit < commit_time < admission_add < flush < claim_add < commit
    )

    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_credential_assignment_freshness_sources
    )
    positions = [
        lock_source.index("binding_row ="),
        lock_source.index("snapshot_row ="),
        lock_source.index("pg_advisory_xact_lock"),
        lock_source.index("assignment_rows ="),
        lock_source.index("clock_timestamp"),
    ]
    assert positions == sorted(positions)
    assert lock_source.count(".with_for_update()") == 3
    assert "_credential_assignment_registry_lock_id" in lock_source
    assert "rotation_epoch" in lock_source and "credential_generation" in lock_source


def test_migration_is_linear_append_only_and_matches_60_second_expiry_contract() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260815_0128"' in migration
    assert 'down_revision: str | None = "20260815_0127"' in migration
    assert "valid_until <= assignment_expires_at" in migration
    assert "INTERVAL '60 seconds'" in migration
    assert "trg_wf_cred_fresh_admissions_append_only" in migration
    assert "trg_wf_cred_fresh_claims_append_only" in migration
    assert migration.count("_authority_granted") >= 17
    assert "UNIQUE (credential_assignment_binding_id)" not in migration


@pytest.mark.asyncio
async def test_unavailable_production_adapter_fails_closed() -> None:
    repository = UnavailableWorkflowPlanRepository()
    with pytest.raises(WorkflowTransportCredentialAssignmentFreshnessAdmissionError):
        await repository.list_credential_assignment_freshness_admissions(
            scope=WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
        )


async def _reset_live(
    engine: AsyncEngine,
    binding_request: Any,
    *,
    assignment_id: str,
) -> None:
    binding_id = binding_request.candidate.binding_id
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        await connection.execute(
            text(
                "DELETE FROM workflow_event_transport_credential_freshness_claims "
                "WHERE credential_assignment_binding_id = :binding_id"
            ),
            {"binding_id": binding_id},
        )
        await connection.execute(
            text(
                "DELETE FROM workflow_event_transport_credential_freshness_admissions "
                "WHERE credential_assignment_binding_id = :binding_id"
            ),
            {"binding_id": binding_id},
        )
        await connection.execute(
            text(
                "DELETE FROM deployment_event_transport_credential_assignments "
                "WHERE assignment_id = :assignment_id"
            ),
            {"assignment_id": assignment_id},
        )
    await reset_binding_rows(engine, (binding_request,))


@pytest.mark.asyncio
async def test_live_postgres_atomic_replay_multiple_admissions_and_append_only_guards() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    binding_request, route, snapshot = credential_binding_request(
        idempotency_key="credential-binding-for-freshness-pg-0001",
        fingerprint="d" * 64,
        bound_at=datetime.now(UTC) - timedelta(seconds=2),
    )
    binding = binding_request.candidate
    head = _head(route, snapshot)
    engine = create_async_engine(database_url, pool_pre_ping=True)
    first = _admission_request(
        binding,
        snapshot,
        head,
        requested_at=datetime.now(UTC),
        idempotency_key="credential-freshness-pg-0001",
    )
    second = _admission_request(
        binding,
        snapshot,
        head,
        requested_at=first.requested_at + timedelta(seconds=1),
        idempotency_key="credential-freshness-pg-0002",
    )
    try:
        await _reset_live(engine, binding_request, assignment_id=head.assignment_id)
        await seed_binding_sources(engine, route=route, assignments=(snapshot,))
        repository = PostgreSQLWorkflowPlanRepository(engine=engine)
        await repository.synchronize_credential_assignments((head,))
        bound = await repository.bind_credential_assignment(binding_request)
        assert bound.binding == binding

        admitted, replay = await asyncio.gather(
            repository.admit_credential_assignment_freshness(first),
            repository.admit_credential_assignment_freshness(first),
        )
        assert {admitted.status, replay.status} == {
            WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.ADMITTED_CURRENT,
            WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.REPLAY,
        }
        another = await repository.admit_credential_assignment_freshness(second)
        assert (
            another.status
            is WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.ADMITTED_CURRENT
        )

        async with engine.connect() as connection:
            observed_window = await connection.scalar(
                text(
                    "SELECT max(valid_until - evaluated_at) "
                    "FROM workflow_event_transport_credential_freshness_admissions "
                    "WHERE credential_assignment_binding_id = :binding_id"
                ),
                {"binding_id": binding.binding_id},
            )
            admission_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_transport_credential_freshness_admissions "
                    "WHERE credential_assignment_binding_id = :binding_id"
                ),
                {"binding_id": binding.binding_id},
            )
        assert observed_window <= timedelta(seconds=60)
        assert admission_count == 2

        for statement in (
            "UPDATE workflow_event_transport_credential_freshness_admissions "
            "SET state = state WHERE credential_assignment_binding_id = :binding_id",
            "DELETE FROM workflow_event_transport_credential_freshness_claims "
            "WHERE credential_assignment_binding_id = :binding_id",
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(text(statement), {"binding_id": binding.binding_id})
    finally:
        await _reset_live(engine, binding_request, assignment_id=head.assignment_id)
        await engine.dispose()
