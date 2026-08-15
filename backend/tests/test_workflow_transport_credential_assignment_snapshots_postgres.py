from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from test_workflow_transport_credential_assignment_snapshots import (
    NOW,
    assignment_fixture,
    route_fixture,
)

from atlas.core.persistence.models import (
    DeploymentEventTransportCredentialAssignmentModel,
    EventPhysicalTransportCredentialAssignmentSnapshotClaimModel,
    EventPhysicalTransportCredentialAssignmentSnapshotModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application.credential_assignment_snapshot_ports import (
    DeploymentPhysicalTransportCredentialAssignmentRegistry,
    WorkflowTransportCredentialAssignmentSnapshotError,
    WorkflowTransportCredentialAssignmentSnapshotRepository,
    WorkflowTransportCredentialAssignmentSnapshotRequest,
    WorkflowTransportCredentialAssignmentSnapshotStatus,
)
from atlas.modules.workflows.application.credential_assignment_snapshots import (
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
    WorkflowTransportCredentialAssignmentSnapshotService,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260815_0126_workflow_transport_credential_assignment_snapshots.py"
)


async def _audit() -> None:
    return None


def _request() -> WorkflowTransportCredentialAssignmentSnapshotRequest:
    route = route_fixture()
    assignment = assignment_fixture(route=route)
    snapshot = WorkflowTransportCredentialAssignmentSnapshotService._build_snapshot(
        assignment=assignment,
        route=route,
        snapshotter_subject_id=WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
        captured_at=NOW,
    )
    return WorkflowTransportCredentialAssignmentSnapshotRequest(
        expected_source_assignment_id=assignment.assignment_id,
        expected_source_assignment_revision=assignment.assignment_revision,
        expected_source_assignment_digest=assignment.canonical_digest,
        scope=assignment.scope,
        snapshotter_subject_id=WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
        requested_at=NOW,
        candidate=snapshot,
        idempotency_key="credential-assignment-postgres-0001",
        request_fingerprint="a" * 64,
        required_precommit_audit=_audit,
    )


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_models_enforce_registry_snapshot_claim_identity_and_zero_authority() -> None:
    source = cast(Table, DeploymentEventTransportCredentialAssignmentModel.__table__)
    snapshot = cast(Table, EventPhysicalTransportCredentialAssignmentSnapshotModel.__table__)
    claim = cast(Table, EventPhysicalTransportCredentialAssignmentSnapshotClaimModel.__table__)

    assert {("source_assignment_digest",), ("canonical_digest",)} <= _unique_columns(source)
    assert (
        "assignment_id",
        "rotation_epoch",
        "credential_generation",
    ) in _unique_columns(source)
    assert {
        ("assignment_id", "assignment_revision"),
        ("source_assignment_digest",),
        ("canonical_digest",),
    } <= _unique_columns(snapshot)
    assert {
        ("idempotency_scope_id", "idempotency_key"),
        ("snapshot_id",),
        ("assignment_id", "assignment_revision"),
        ("canonical_digest",),
    } <= _unique_columns(claim)

    checks = "\n".join(
        str(constraint.sqltext)
        for constraint in snapshot.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "state = 'snapshotted' AND source_non_revoked" in checks
    assert "activated_at <= captured_at AND captured_at < expires_at" in checks
    source_checks = "\n".join(
        str(constraint.sqltext)
        for constraint in source.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "NOT (active AND revoked)" in source_checks
    for column in (
        "endpoint_resolution_authority_granted",
        "protected_artifact_access_authority_granted",
        "credential_selection_authority_granted",
        "credential_access_authority_granted",
        "credential_brokerage_authority_granted",
        "credential_resolution_authority_granted",
        "credential_delivery_authority_granted",
        "network_access_authority_granted",
        "readiness_probe_authority_granted",
        "publication_authority_granted",
        "delivery_authority_granted",
        "dispatch_authority_granted",
        "execution_authority_granted",
        "infrastructure_mutation_authority_granted",
    ):
        assert f"NOT {column}" in checks


def test_registry_snapshot_and_claim_round_trip_with_exact_payload_integrity() -> None:
    request = _request()
    assignment = assignment_fixture(route=route_fixture())
    source_row = PostgreSQLWorkflowPlanRepository._credential_assignment_model(assignment)
    snapshot_row = PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_claim_model(
        request
    )

    assert (
        PostgreSQLWorkflowPlanRepository._credential_assignment_from_row(source_row) == assignment
    )
    assert (
        PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_from_row(snapshot_row)
        == request.candidate
    )
    record = PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_record_from_claim(
        claim_row, snapshot_row
    )
    assert record.request_fingerprint == request.request_fingerprint
    assert record.snapshot == request.candidate
    assert claim_row.result_digest == request.candidate.canonical_digest


def test_corrupted_registry_snapshot_and_claim_fail_closed() -> None:
    request = _request()
    assignment = assignment_fixture(route=route_fixture())
    source_row = PostgreSQLWorkflowPlanRepository._credential_assignment_model(assignment)
    source_row.credential_profile_digest = "f" * 64
    with pytest.raises(WorkflowTransportCredentialAssignmentSnapshotError):
        PostgreSQLWorkflowPlanRepository._credential_assignment_from_row(source_row)

    snapshot_row = PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_model(
        request.candidate
    )
    snapshot_row.broker_policy_digest = "f" * 64
    with pytest.raises(WorkflowTransportCredentialAssignmentSnapshotError):
        PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_from_row(snapshot_row)

    snapshot_row = PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_claim_model(
        request
    )
    claim_row.result_digest = "f" * 64
    with pytest.raises(WorkflowTransportCredentialAssignmentSnapshotError):
        PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_record_from_claim(
            claim_row, snapshot_row
        )


def test_repository_locks_sources_audits_then_commits_snapshot_and_claim_atomically() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.snapshot_credential_assignment)
    assignment_lock = source.index("source_row =")
    route_lock = source.index("route_row =", assignment_lock)
    database_time = source.index("clock_timestamp", route_lock)
    evidence = source.index("_credential_assignment_snapshot_evidence_matches", database_time)
    post_lock_replay = source.index(
        "_credential_assignment_snapshot_replay(session, request=request)", route_lock
    )
    precommit_audit = source.index("await request.required_precommit_audit()", evidence)
    snapshot_add = source.index("session.add(self._credential_assignment_snapshot_model")
    claim_add = source.index("session.add(self._credential_assignment_snapshot_claim_model")
    commit = source.index("await session.commit()", claim_add)
    assert assignment_lock < route_lock < post_lock_replay < database_time < evidence
    assert evidence < precommit_audit < snapshot_add < claim_add < commit
    assert source.count(".with_for_update()") == 2
    assert "pg_advisory_xact_lock" in source
    synchronization = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.synchronize_credential_assignments
    )
    assert "pg_advisory_xact_lock" in synchronization
    assert "except IntegrityError:" in source

    replay = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_replay
    )
    assert "record.request_fingerprint == request.request_fingerprint" in replay
    assert "REPLAY" in replay
    assert "IDEMPOTENCY_CONFLICT" in replay


@pytest.mark.asyncio
async def test_memory_and_postgres_share_request_validation() -> None:
    invalid = replace(_request(), idempotency_key="short")
    with pytest.raises(ValueError, match="idempotency key"):
        await InMemoryWorkflowPlanRepository().snapshot_credential_assignment(invalid)
    for adapter in (InMemoryWorkflowPlanRepository, PostgreSQLWorkflowPlanRepository):
        source = inspect.getsource(adapter.snapshot_credential_assignment)
        assert "validate_workflow_transport_credential_assignment_snapshot_request" in source


@pytest.mark.asyncio
async def test_memory_registry_uses_latest_generation_and_revocation_head() -> None:
    route = route_fixture()
    old = assignment_fixture(route=route, assignment_revision="13")
    current = assignment_fixture(
        route=route,
        assignment_revision="14",
        credential_generation=24,
        rotation_epoch=9,
    )
    revoked = assignment_fixture(
        route=route,
        assignment_revision="15",
        credential_generation=25,
        rotation_epoch=10,
        active=False,
        revoked=True,
    )
    repository = InMemoryWorkflowPlanRepository()
    await repository.synchronize_credential_assignments((old, current))
    assert (
        await repository.get_active_credential_assignment(
            assignment_id=old.assignment_id,
            assignment_revision=old.assignment_revision,
        )
        is None
    )
    assert (
        await repository.get_active_credential_assignment(
            assignment_id=current.assignment_id,
            assignment_revision=current.assignment_revision,
        )
        == current
    )
    await repository.synchronize_credential_assignments((revoked,))
    for revision in (
        old.assignment_revision,
        current.assignment_revision,
        revoked.assignment_revision,
    ):
        assert (
            await repository.get_active_credential_assignment(
                assignment_id=old.assignment_id,
                assignment_revision=revision,
            )
            is None
        )


def test_adapters_match_registry_and_snapshot_repository_protocols() -> None:
    for adapter in (
        InMemoryWorkflowPlanRepository,
        PostgreSQLWorkflowPlanRepository,
        UnavailableWorkflowPlanRepository,
    ):
        assert inspect.signature(adapter.get_active_credential_assignment) == inspect.signature(
            DeploymentPhysicalTransportCredentialAssignmentRegistry.get_active_credential_assignment
        )
        for method_name in (
            "get_credential_assignment_snapshot",
            "list_credential_assignment_snapshots",
            "get_credential_assignment_snapshot_request",
            "snapshot_credential_assignment",
        ):
            assert inspect.signature(getattr(adapter, method_name)) == inspect.signature(
                getattr(WorkflowTransportCredentialAssignmentSnapshotRepository, method_name)
            )


def test_schema_excludes_secret_locator_workflow_and_network_authority() -> None:
    source = cast(Table, DeploymentEventTransportCredentialAssignmentModel.__table__)
    snapshot = cast(Table, EventPhysicalTransportCredentialAssignmentSnapshotModel.__table__)
    claim = cast(Table, EventPhysicalTransportCredentialAssignmentSnapshotClaimModel.__table__)
    columns = set(source.columns) | set(snapshot.columns) | set(claim.columns)
    forbidden = {
        "password",
        "token",
        "secret",
        "secret_reference",
        "vault_path",
        "secret_store",
        "username",
        "private_key",
        "certificate",
        "endpoint",
        "hostname",
        "url",
        "ip_address",
        "workflow_id",
        "materialization_id",
        "protected_artifact_id",
    }
    assert columns.isdisjoint(forbidden)
    assert {key.target_fullname for key in snapshot.foreign_keys} == {
        "event_transport_route_snapshots.snapshot_id"
    }
    assert {key.target_fullname for key in claim.foreign_keys} == {
        "event_transport_credential_assignment_snapshots.snapshot_id"
    }


def test_migration_is_linear_three_table_append_only_evidence() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260815_0126"' in migration
    assert 'down_revision: str | None = "20260814_0125"' in migration
    assert migration.count("op.create_table(") == 3
    assert 'source_table = "deployment_event_transport_credential_assignments"' in migration
    assert 'snapshot_table = "event_transport_credential_assignment_snapshots"' in migration
    assert 'claim_table = "event_transport_credential_assignment_snapshot_claims"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "reject_event_transport_credential_assignment_mutation" in migration
    assert "CREATE TRIGGER trg_{table_name}_append_only" in migration
    assert "DROP TRIGGER IF EXISTS trg_{table_name}_append_only" in migration
    assert '"route_snapshot"' in migration
    assert '"snapshotter",\n            "state"' in migration
    assert '"expires",\n            "active"' in migration


async def _reset_live_credential_snapshot_rows(
    engine: AsyncEngine,
    request: WorkflowTransportCredentialAssignmentSnapshotRequest,
) -> None:
    values = {
        "snapshot_id": request.candidate.snapshot_id,
        "assignment_id": request.candidate.assignment_id,
        "route_snapshot_id": request.candidate.route_snapshot_id,
    }
    statements = (
        "DELETE FROM event_transport_credential_assignment_snapshot_claims "
        "WHERE snapshot_id = :snapshot_id",
        "DELETE FROM event_transport_credential_assignment_snapshots "
        "WHERE snapshot_id = :snapshot_id",
        "DELETE FROM deployment_event_transport_credential_assignments "
        "WHERE assignment_id = :assignment_id",
        "DELETE FROM event_transport_route_snapshots WHERE snapshot_id = :route_snapshot_id",
    )
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for statement in statements:
            await connection.execute(text(statement), values)


async def _seed_live_credential_snapshot_sources(
    engine: AsyncEngine,
    request: WorkflowTransportCredentialAssignmentSnapshotRequest,
) -> None:
    route = route_fixture()
    assignment = assignment_fixture(route=route)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        await session.execute(text("SET LOCAL session_replication_role = replica"))
        session.add_all(
            (
                PostgreSQLWorkflowPlanRepository._transport_route_snapshot_model(route),
                PostgreSQLWorkflowPlanRepository._credential_assignment_model(assignment),
            )
        )
        await session.commit()
    assert request.candidate.route_snapshot_id == route.snapshot_id
    assert request.expected_source_assignment_digest == assignment.canonical_digest


@pytest.mark.asyncio
async def test_memory_is_nondurable_and_unavailable_fails_closed() -> None:
    memory = InMemoryWorkflowPlanRepository()
    assert memory.durable is False
    unavailable = UnavailableWorkflowPlanRepository()
    with pytest.raises(WorkflowTransportCredentialAssignmentSnapshotError):
        await unavailable.get_active_credential_assignment(
            assignment_id="credential-assignment.test",
            assignment_revision="1",
        )


@pytest.mark.asyncio
async def test_live_postgres_has_append_only_tables_when_dsn_is_configured() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    table_names = (
        "deployment_event_transport_credential_assignments",
        "event_transport_credential_assignment_snapshots",
        "event_transport_credential_assignment_snapshot_claims",
    )
    try:
        async with engine.connect() as connection:
            tables = await connection.execute(
                text(
                    "SELECT to_regclass(name) FROM unnest(ARRAY["
                    + ",".join(f"'{name}'" for name in table_names)
                    + "]) AS name"
                )
            )
            triggers = await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal "
                    "AND tgname IN ("
                    + ",".join(f"'trg_{name}_append_only'" for name in table_names)
                    + ")"
                )
            )
        assert all(value is not None for value in tables.scalars())
        assert triggers == 3
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_serializes_exact_credential_snapshot_replay() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    request = _request()
    try:
        await _reset_live_credential_snapshot_rows(engine, request)
        await _seed_live_credential_snapshot_sources(engine, request)
        repository = PostgreSQLWorkflowPlanRepository(engine=engine)
        first, second = await asyncio.gather(
            repository.snapshot_credential_assignment(request),
            repository.snapshot_credential_assignment(request),
        )
        assert {first.status, second.status} == {
            WorkflowTransportCredentialAssignmentSnapshotStatus.SNAPSHOTTED,
            WorkflowTransportCredentialAssignmentSnapshotStatus.REPLAY,
        }
        assert first.snapshot == second.snapshot == request.candidate
        async with engine.connect() as connection:
            snapshot_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM event_transport_credential_assignment_snapshots "
                    "WHERE snapshot_id = :snapshot_id"
                ),
                {"snapshot_id": request.candidate.snapshot_id},
            )
            claim_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM event_transport_credential_assignment_snapshot_claims "
                    "WHERE snapshot_id = :snapshot_id"
                ),
                {"snapshot_id": request.candidate.snapshot_id},
            )
        assert snapshot_count == claim_count == 1
        route = route_fixture()
        current = assignment_fixture(
            route=route,
            assignment_revision="14",
            credential_generation=24,
            rotation_epoch=9,
        )
        revoked = assignment_fixture(
            route=route,
            assignment_revision="15",
            credential_generation=25,
            rotation_epoch=10,
            active=False,
            revoked=True,
        )
        await repository.synchronize_credential_assignments((current,))
        assert (
            await repository.get_active_credential_assignment(
                assignment_id=current.assignment_id,
                assignment_revision=request.candidate.assignment_revision,
            )
            is None
        )
        assert (
            await repository.get_active_credential_assignment(
                assignment_id=current.assignment_id,
                assignment_revision=current.assignment_revision,
            )
            == current
        )
        await repository.synchronize_credential_assignments((revoked,))
        assert (
            await repository.get_active_credential_assignment(
                assignment_id=revoked.assignment_id,
                assignment_revision=current.assignment_revision,
            )
            is None
        )
        with pytest.raises(DBAPIError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE event_transport_credential_assignment_snapshots "
                        "SET state = state WHERE snapshot_id = :snapshot_id"
                    ),
                    {"snapshot_id": request.candidate.snapshot_id},
                )
    finally:
        await _reset_live_credential_snapshot_rows(engine, request)
        await engine.dispose()
