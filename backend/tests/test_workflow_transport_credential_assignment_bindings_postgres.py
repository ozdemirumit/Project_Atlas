from __future__ import annotations

import asyncio
import inspect
import os
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from test_workflow_physical_transport_route_bindings_postgres import (
    _integration_request as physical_route_binding_request,
)
from test_workflow_physical_transport_route_bindings_postgres import (
    _integration_sources as physical_route_sources,
)
from test_workflow_transport_credential_assignment_snapshots import assignment_fixture

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application.credential_assignment_binding_ports import (
    WorkflowTransportCredentialAssignmentBindingError,
    WorkflowTransportCredentialAssignmentBindingRepository,
    WorkflowTransportCredentialAssignmentBindingRequest,
    WorkflowTransportCredentialAssignmentBindingStatus,
)
from atlas.modules.workflows.application.credential_assignment_bindings import (
    WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
)
from atlas.modules.workflows.application.credential_assignment_snapshots import (
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
    WorkflowTransportCredentialAssignmentSnapshotService,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportRouteSnapshot,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260815_0127_workflow_transport_credential_assignment_bindings.py"
)
BOUND_AT = datetime(2026, 8, 15, 12, 5, tzinfo=UTC)


async def _audit() -> None:
    return None


async def _failed_audit() -> None:
    raise RuntimeError("required precommit audit is unavailable")


def _assignment_snapshot(
    route: EventPhysicalTransportRouteSnapshot,
    *,
    revision: str,
    generation: int,
    rotation_epoch: int,
    captured_at: datetime,
) -> EventPhysicalTransportCredentialAssignmentSnapshot:
    assignment = assignment_fixture(
        assignment_revision=revision,
        route=route,
        scope=route.scope,
        credential_generation=generation,
        rotation_epoch=rotation_epoch,
        activated_at=captured_at - timedelta(days=10),
        expires_at=captured_at + timedelta(days=20),
    )
    return WorkflowTransportCredentialAssignmentSnapshotService._build_snapshot(
        assignment=assignment,
        route=route,
        snapshotter_subject_id=WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
        captured_at=captured_at,
    )


def _request(
    *,
    revision: str = "13",
    generation: int = 23,
    rotation_epoch: int = 8,
    bound_at: datetime = BOUND_AT,
    idempotency_key: str = "credential-assignment-binding-postgres-0001",
    fingerprint: str = "a" * 64,
) -> tuple[
    WorkflowTransportCredentialAssignmentBindingRequest,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportCredentialAssignmentSnapshot,
]:
    route_request = physical_route_binding_request()
    route = physical_route_sources()[3]
    route_binding = route_request.candidate
    assignment = _assignment_snapshot(
        route,
        revision=revision,
        generation=generation,
        rotation_epoch=rotation_epoch,
        captured_at=bound_at - timedelta(minutes=1),
    )
    service = WorkflowEventPhysicalTransportCredentialAssignmentBindingService(
        binding_repository=cast(Any, object()),
        audit_sink=cast(Any, object()),
    )
    binding = service._build_binding(
        route_binding=route_binding,
        route=route,
        assignment=assignment,
        binder_subject_id="service.workflow-physical-transport-credential-binder",
        bound_at=bound_at,
    )
    request = WorkflowTransportCredentialAssignmentBindingRequest(
        expected_physical_transport_route_binding_id=route_binding.binding_id,
        expected_physical_transport_route_binding_digest=route_binding.canonical_digest,
        expected_transport_route_snapshot_id=route.snapshot_id,
        expected_transport_route_snapshot_digest=route.canonical_digest,
        expected_credential_assignment_snapshot_id=assignment.snapshot_id,
        expected_credential_assignment_snapshot_digest=assignment.canonical_digest,
        expected_policy_digest=binding.policy_digest,
        scope=binding.scope,
        binder_subject_id=binding.binder_subject_id,
        requested_at=binding.bound_at,
        candidate=binding,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        required_precommit_audit=_audit,
    )
    return request, route, assignment


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_models_match_migration_identity_and_zero_authority_contract() -> None:
    binding = cast(Table, WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.__table__)
    claim = cast(
        Table, WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel.__table__
    )
    assert binding.name == "workflow_event_physical_transport_credential_bindings"
    assert claim.name == "workflow_event_physical_transport_credential_binding_claims"
    assert {
        (
            "physical_transport_route_binding_id",
            "credential_assignment_snapshot_id",
        ),
        ("canonical_digest",),
    } <= _unique_columns(binding)
    assert {
        ("idempotency_scope_id", "idempotency_key"),
        ("binding_id",),
        ("canonical_digest",),
    } <= _unique_columns(claim)
    checks = "\n".join(
        str(constraint.sqltext)
        for constraint in binding.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "state = 'bound'" in checks
    for column in (
        "route_selection_authority_granted",
        "route_binding_authority_granted",
        "endpoint_resolution_authority_granted",
        "protected_artifact_access_authority_granted",
        "credential_selection_authority_granted",
        "credential_assignment_binding_authority_granted",
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


def test_binding_and_claim_round_trip_recompute_exact_payloads() -> None:
    request, _, _ = _request()
    binding_row = PostgreSQLWorkflowPlanRepository._credential_assignment_binding_model(
        request.candidate
    )
    assert (
        PostgreSQLWorkflowPlanRepository._credential_assignment_binding_from_row(binding_row)
        == request.candidate
    )
    claim = PostgreSQLWorkflowPlanRepository._credential_assignment_binding_claim_model(request)
    record = PostgreSQLWorkflowPlanRepository._credential_assignment_binding_record_from_claim(
        claim, binding_row
    )
    assert record.request_fingerprint == request.request_fingerprint
    assert record.binding == request.candidate


def test_repository_has_fixed_lock_order_flush_and_post_lock_replay() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.bind_credential_assignment)
    route_binding_lock = source.index("route_binding_row =")
    route_snapshot_lock = source.index("route_snapshot_row =", route_binding_lock)
    assignment_snapshot_lock = source.index("assignment_snapshot_row =", route_snapshot_lock)
    evidence = source.index("_credential_assignment_binding_evidence_matches")
    replay = source.index("_credential_assignment_binding_replay", assignment_snapshot_lock)
    binding_add = source.index("session.add(self._credential_assignment_binding_model")
    flush = source.index("await session.flush()", binding_add)
    claim_add = source.index("session.add(self._credential_assignment_binding_claim_model")
    commit = source.index("await session.commit()", claim_add)
    assert route_binding_lock < route_snapshot_lock < assignment_snapshot_lock
    assert assignment_snapshot_lock < evidence < replay < binding_add < flush < claim_add < commit
    assert source.count(".with_for_update()") == 3


def test_migration_is_linear_two_table_append_only_evidence() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260815_0127"' in migration
    assert 'down_revision: str | None = "20260815_0126"' in migration
    assert migration.count("op.create_table(") == 2
    assert "uq_wf_transport_credential_binding_pair" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "reject_wf_transport_credential_binding_mutation" in migration

    downgrade = migration.split("def downgrade()", maxsplit=1)[1].split(
        "def _zero_authority_columns", maxsplit=1
    )[0]
    suffix_blocks = re.findall(
        r"for suffix in reversed\(\s*\(\s*(.*?)\s*\)\s*\):\s*op\.drop_index",
        downgrade,
        flags=re.DOTALL,
    )
    assert len(suffix_blocks) == 2
    claim_suffixes, binding_suffixes = (
        set(re.findall(r'"([a-z_]+)"', block)) for block in suffix_blocks
    )
    binding_only_suffixes = {
        "route_binding_digest",
        "route_snapshot_digest",
        "assignment_snapshot_digest",
        "policy_id",
    }
    assert claim_suffixes.isdisjoint(binding_only_suffixes)
    assert binding_only_suffixes <= binding_suffixes


def test_adapters_match_repository_protocol() -> None:
    for adapter in (
        InMemoryWorkflowPlanRepository,
        PostgreSQLWorkflowPlanRepository,
        UnavailableWorkflowPlanRepository,
    ):
        for method_name in (
            "get_physical_transport_route_binding_by_id",
            "get_transport_route_snapshot_by_id",
            "get_credential_assignment_snapshot_by_id",
            "get_credential_assignment_binding",
            "list_credential_assignment_bindings",
            "get_credential_assignment_binding_request",
            "bind_credential_assignment",
        ):
            assert inspect.signature(getattr(adapter, method_name)) == inspect.signature(
                getattr(WorkflowTransportCredentialAssignmentBindingRepository, method_name)
            )


@pytest.mark.asyncio
async def test_unavailable_production_adapter_fails_closed() -> None:
    request, _, _ = _request()
    repository = UnavailableWorkflowPlanRepository()
    assert repository.durable is False
    with pytest.raises(WorkflowTransportCredentialAssignmentBindingError) as error:
        await repository.bind_credential_assignment(request)
    assert (
        error.value.code
        == "workflow_transport_credential_assignment_binding_repository_unavailable"
    )


async def _reset_live_rows(
    engine: AsyncEngine,
    requests: tuple[WorkflowTransportCredentialAssignmentBindingRequest, ...],
) -> None:
    route_binding_id = requests[0].candidate.physical_transport_route_binding_id
    route_snapshot_id = requests[0].candidate.transport_route_snapshot_id
    assignment_snapshot_ids = tuple(
        request.candidate.credential_assignment_snapshot_id for request in requests
    )
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        await connection.execute(
            text(
                "DELETE FROM workflow_event_physical_transport_credential_binding_claims "
                "WHERE physical_transport_route_binding_id = :route_binding_id"
            ),
            {"route_binding_id": route_binding_id},
        )
        await connection.execute(
            text(
                "DELETE FROM workflow_event_physical_transport_credential_bindings "
                "WHERE physical_transport_route_binding_id = :route_binding_id"
            ),
            {"route_binding_id": route_binding_id},
        )
        await connection.execute(
            text(
                "DELETE FROM event_transport_credential_assignment_snapshots "
                "WHERE snapshot_id = ANY(:snapshot_ids)"
            ),
            {"snapshot_ids": list(assignment_snapshot_ids)},
        )
        await connection.execute(
            text(
                "DELETE FROM workflow_event_physical_transport_route_binding_claims "
                "WHERE binding_id = :route_binding_id"
            ),
            {"route_binding_id": route_binding_id},
        )
        await connection.execute(
            text(
                "DELETE FROM workflow_event_physical_transport_route_bindings "
                "WHERE binding_id = :route_binding_id"
            ),
            {"route_binding_id": route_binding_id},
        )
        await connection.execute(
            text("DELETE FROM event_transport_route_snapshots WHERE snapshot_id = :snapshot_id"),
            {"snapshot_id": route_snapshot_id},
        )


async def _seed_live_sources(
    engine: AsyncEngine,
    *,
    route: EventPhysicalTransportRouteSnapshot,
    assignments: tuple[EventPhysicalTransportCredentialAssignmentSnapshot, ...],
) -> None:
    route_binding = physical_route_binding_request().candidate
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        await session.execute(text("SET LOCAL session_replication_role = replica"))
        session.add_all(
            (
                PostgreSQLWorkflowPlanRepository._transport_route_snapshot_model(route),
                PostgreSQLWorkflowPlanRepository._physical_transport_route_binding_model(
                    route_binding
                ),
                *(
                    PostgreSQLWorkflowPlanRepository._credential_assignment_snapshot_model(
                        assignment
                    )
                    for assignment in assignments
                ),
            )
        )
        await session.commit()


async def _live_result_counts(
    engine: AsyncEngine,
    request: WorkflowTransportCredentialAssignmentBindingRequest,
) -> tuple[int, int]:
    async with engine.connect() as connection:
        binding_count = await connection.scalar(
            text(
                "SELECT count(*) "
                "FROM workflow_event_physical_transport_credential_bindings "
                "WHERE binding_id = :binding_id"
            ),
            {"binding_id": request.candidate.binding_id},
        )
        claim_count = await connection.scalar(
            text(
                "SELECT count(*) "
                "FROM workflow_event_physical_transport_credential_binding_claims "
                "WHERE idempotency_key = :idempotency_key "
                "AND binder_subject_id = :binder_subject_id"
            ),
            {
                "idempotency_key": request.idempotency_key,
                "binder_subject_id": request.binder_subject_id,
            },
        )
    return int(binding_count or 0), int(claim_count or 0)


@pytest.mark.asyncio
async def test_live_postgres_precommit_audit_failure_persists_no_result() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    request, route, assignment = _request(
        idempotency_key="credential-assignment-binding-postgres-audit-failure",
        fingerprint="c" * 64,
    )
    failed_request = replace(request, required_precommit_audit=_failed_audit)
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        await _reset_live_rows(engine, (request,))
        await _seed_live_sources(engine, route=route, assignments=(assignment,))

        result = await PostgreSQLWorkflowPlanRepository(engine=engine).bind_credential_assignment(
            failed_request
        )

        assert (
            result.status
            is WorkflowTransportCredentialAssignmentBindingStatus.PRECOMMIT_AUDIT_FAILED
        )
        assert result.binding is None
        assert await _live_result_counts(engine, request) == (0, 0)
    finally:
        await _reset_live_rows(engine, (request,))
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_tampered_source_payload_persists_no_result() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    request, route, assignment = _request(
        idempotency_key="credential-assignment-binding-postgres-source-tamper",
        fingerprint="d" * 64,
    )
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        await _reset_live_rows(engine, (request,))
        await _seed_live_sources(engine, route=route, assignments=(assignment,))
        tampered_digest = "f" * 64
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(
                text(
                    "UPDATE event_transport_credential_assignment_snapshots "
                    "SET canonical_digest = :tampered_digest, "
                    "payload = jsonb_set(payload, '{canonical_digest}', "
                    "CAST(:tampered_json AS JSONB), false) "
                    "WHERE snapshot_id = :snapshot_id"
                ),
                {
                    "snapshot_id": assignment.snapshot_id,
                    "tampered_digest": tampered_digest,
                    "tampered_json": f'"{tampered_digest}"',
                },
            )

        result = await PostgreSQLWorkflowPlanRepository(engine=engine).bind_credential_assignment(
            request
        )

        assert result.status is WorkflowTransportCredentialAssignmentBindingStatus.EVIDENCE_CONFLICT
        assert result.binding is None
        assert await _live_result_counts(engine, request) == (0, 0)
    finally:
        await _reset_live_rows(engine, (request,))
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_claim_unique_conflict_rolls_back_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    first_request, route, first_assignment = _request(
        idempotency_key="credential-assignment-binding-postgres-claim-owner",
        fingerprint="e" * 64,
    )
    conflicting_request, _, conflicting_assignment = _request(
        revision="15",
        generation=25,
        rotation_epoch=10,
        bound_at=BOUND_AT + timedelta(minutes=4),
        idempotency_key="credential-assignment-binding-postgres-claim-conflict",
        fingerprint="6" * 64,
    )
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        await _reset_live_rows(engine, (first_request, conflicting_request))
        await _seed_live_sources(
            engine,
            route=route,
            assignments=(first_assignment, conflicting_assignment),
        )
        repository = PostgreSQLWorkflowPlanRepository(engine=engine)
        first = await repository.bind_credential_assignment(first_request)
        assert first.status is WorkflowTransportCredentialAssignmentBindingStatus.BOUND

        original_claim_model = (
            PostgreSQLWorkflowPlanRepository._credential_assignment_binding_claim_model
        )

        def _conflicting_claim_model(
            cls: type[PostgreSQLWorkflowPlanRepository],
            request: WorkflowTransportCredentialAssignmentBindingRequest,
        ) -> WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel:
            del cls
            claim = original_claim_model(request)
            claim.idempotency_key = first_request.idempotency_key
            return claim

        monkeypatch.setattr(
            PostgreSQLWorkflowPlanRepository,
            "_credential_assignment_binding_claim_model",
            classmethod(_conflicting_claim_model),
        )

        conflict = await repository.bind_credential_assignment(conflicting_request)

        assert (
            conflict.status is WorkflowTransportCredentialAssignmentBindingStatus.EVIDENCE_CONFLICT
        )
        assert conflict.binding is None
        assert await _live_result_counts(engine, first_request) == (1, 1)
        assert await _live_result_counts(engine, conflicting_request) == (0, 0)
    finally:
        await _reset_live_rows(engine, (first_request, conflicting_request))
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_concurrency_append_only_and_multiple_generations() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    first_request, route, first_assignment = _request()
    second_request, _, second_assignment = _request(
        revision="14",
        generation=24,
        rotation_epoch=9,
        bound_at=BOUND_AT + timedelta(minutes=2),
        idempotency_key="credential-assignment-binding-postgres-0002",
        fingerprint="b" * 64,
    )
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        await _reset_live_rows(engine, (first_request, second_request))
        await _seed_live_sources(
            engine,
            route=route,
            assignments=(first_assignment, second_assignment),
        )
        repository = PostgreSQLWorkflowPlanRepository(engine=engine)

        first, replay = await asyncio.gather(
            repository.bind_credential_assignment(first_request),
            repository.bind_credential_assignment(first_request),
        )
        assert {first.status, replay.status} == {
            WorkflowTransportCredentialAssignmentBindingStatus.BOUND,
            WorkflowTransportCredentialAssignmentBindingStatus.REPLAY,
        }
        assert first.binding == replay.binding == first_request.candidate

        second = await repository.bind_credential_assignment(second_request)
        assert second.status is WorkflowTransportCredentialAssignmentBindingStatus.BOUND
        assert second.binding == second_request.candidate
        listed = await repository.list_credential_assignment_bindings(scope=first_request.scope)
        selected = {
            binding.credential_assignment_snapshot_id
            for binding in listed
            if binding.physical_transport_route_binding_id
            == first_request.candidate.physical_transport_route_binding_id
        }
        assert selected == {
            first_request.candidate.credential_assignment_snapshot_id,
            second_request.candidate.credential_assignment_snapshot_id,
        }

        table_names = (
            "workflow_event_physical_transport_credential_bindings",
            "workflow_event_physical_transport_credential_binding_claims",
        )
        trigger_names = (
            "trg_wf_transport_credential_bindings_append_only",
            "trg_wf_transport_credential_binding_claims_append_only",
        )
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
                    "AND tgname IN (" + ",".join(f"'{name}'" for name in trigger_names) + ")"
                )
            )
            binding_count = await connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM workflow_event_physical_transport_credential_bindings "
                    "WHERE physical_transport_route_binding_id = :route_binding_id"
                ),
                {"route_binding_id": (first_request.candidate.physical_transport_route_binding_id)},
            )
            claim_count = await connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM workflow_event_physical_transport_credential_binding_claims "
                    "WHERE physical_transport_route_binding_id = :route_binding_id"
                ),
                {"route_binding_id": (first_request.candidate.physical_transport_route_binding_id)},
            )
        assert all(value is not None for value in tables.scalars())
        assert triggers == 2
        assert binding_count == claim_count == 2

        for statement in (
            "UPDATE workflow_event_physical_transport_credential_bindings "
            "SET state = state WHERE binding_id = :binding_id",
            "DELETE FROM workflow_event_physical_transport_credential_binding_claims "
            "WHERE binding_id = :binding_id",
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(statement),
                        {"binding_id": first_request.candidate.binding_id},
                    )
    finally:
        await _reset_live_rows(engine, (first_request, second_request))
        await engine.dispose()
