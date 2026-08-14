from __future__ import annotations

import asyncio
import inspect
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from test_workflow_event_logical_channel_bindings_postgres import (
    _binding as logical_binding_fixture,
)
from test_workflow_transport_profile_snapshots import profile_fixture
from test_workflow_transport_route_snapshots import route_fixture

from atlas.core.persistence.models import (
    EventPhysicalTransportProfileSnapshotModel,
    EventPhysicalTransportRouteSnapshotModel,
    WorkflowEventLogicalChannelBindingModel,
    WorkflowEventPhysicalTransportRouteBindingClaimModel,
    WorkflowEventPhysicalTransportRouteBindingModel,
    WorkflowEventTransportCompatibilityAdmissionModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application.physical_route_binding_ports import (
    WorkflowEventPhysicalTransportRouteBindingError,
    WorkflowEventPhysicalTransportRouteBindingRequest,
    WorkflowEventPhysicalTransportRouteBindingStatus,
)
from atlas.modules.workflows.application.physical_route_bindings import (
    WorkflowEventPhysicalTransportRouteBindingService,
)
from atlas.modules.workflows.application.transport_compatibility_admissions import (
    WorkflowEventTransportCompatibilityAdmissionService,
)
from atlas.modules.workflows.application.transport_profile_snapshots import (
    WorkflowTransportProfileSnapshotService,
)
from atlas.modules.workflows.application.transport_route_snapshots import (
    WorkflowTransportRouteSnapshotService,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportRouteSnapshot,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteBindingAuthority,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_route_binding_policy,
)


def _binding() -> WorkflowEventPhysicalTransportRouteBinding:
    policy = code_owned_workflow_event_physical_transport_route_binding_policy()
    values: dict[str, object] = {
        "binding_id": "physical-binding-1",
        "logical_channel_binding_id": "logical-binding-1",
        "logical_channel_binding_digest": "1" * 64,
        "transport_compatibility_admission_id": "compatibility-admission-1",
        "transport_compatibility_admission_digest": "2" * 64,
        "transport_profile_snapshot_id": "profile-snapshot-1",
        "transport_profile_snapshot_digest": "3" * 64,
        "transport_route_snapshot_id": "route-snapshot-1",
        "transport_route_snapshot_digest": "4" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "scope": WorkflowScope("org-1", "env-1", "site-1"),
        "binder_subject_id": "service-route-binder",
        "bound_at": datetime(2026, 8, 14, 8, 0, tzinfo=UTC),
        "state": WorkflowEventPhysicalTransportRouteBindingState.BOUND,
        "authority": WorkflowEventPhysicalTransportRouteBindingAuthority(),
    }
    digest_payload = {
        key: value.canonical_value()
        if isinstance(value, (WorkflowScope, WorkflowEventPhysicalTransportRouteBindingAuthority))
        else value.isoformat()
        if isinstance(value, datetime)
        else value.value
        if isinstance(value, WorkflowEventPhysicalTransportRouteBindingState)
        else value
        for key, value in values.items()
    }
    return WorkflowEventPhysicalTransportRouteBinding(
        **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
    )


def _request() -> WorkflowEventPhysicalTransportRouteBindingRequest:
    binding = _binding()
    return WorkflowEventPhysicalTransportRouteBindingRequest(
        expected_logical_channel_binding_id=binding.logical_channel_binding_id,
        expected_logical_channel_binding_digest=binding.logical_channel_binding_digest,
        expected_transport_compatibility_admission_id=(
            binding.transport_compatibility_admission_id
        ),
        expected_transport_compatibility_admission_digest=(
            binding.transport_compatibility_admission_digest
        ),
        expected_transport_profile_snapshot_id=binding.transport_profile_snapshot_id,
        expected_transport_profile_snapshot_digest=binding.transport_profile_snapshot_digest,
        expected_transport_route_snapshot_id=binding.transport_route_snapshot_id,
        expected_transport_route_snapshot_digest=binding.transport_route_snapshot_digest,
        expected_policy_digest=binding.policy_digest,
        scope=binding.scope,
        binder_subject_id=binding.binder_subject_id,
        requested_at=binding.bound_at,
        candidate=binding,
        idempotency_key="bind-route-1",
        request_fingerprint="5" * 64,
    )


def _integration_sources() -> tuple[
    WorkflowEventLogicalChannelBinding,
    WorkflowEventTransportCompatibilityAdmission,
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportRouteSnapshot,
]:
    logical = logical_binding_fixture()
    profile = WorkflowTransportProfileSnapshotService._build_snapshot(
        profile=profile_fixture(scope=logical.scope),
        snapshotter_subject_id="service.workflow-transport-profile-registry",
        captured_at=datetime(2026, 8, 14, 16, 0, tzinfo=UTC),
    )
    route = WorkflowTransportRouteSnapshotService._build_snapshot(
        route=route_fixture(scope=logical.scope),
        snapshotter_subject_id="service.workflow-transport-route-registry",
        captured_at=datetime(2026, 8, 14, 16, 0, tzinfo=UTC),
    )

    compatibility_service = WorkflowEventTransportCompatibilityAdmissionService(
        admission_repository=cast(Any, object()),
        audit_sink=cast(Any, object()),
    )
    admission = compatibility_service._build_admission(
        binding=logical,
        snapshot=profile,
        admitter_subject_id="service.workflow-transport-compatibility-admitter",
        admitted_at=datetime(2026, 8, 14, 16, 1, tzinfo=UTC),
    )
    return logical, admission, profile, route


def _integration_request() -> WorkflowEventPhysicalTransportRouteBindingRequest:
    logical, admission, profile, route = _integration_sources()
    binding_service = WorkflowEventPhysicalTransportRouteBindingService(
        binding_repository=cast(Any, object()),
        audit_sink=cast(Any, object()),
    )
    candidate = binding_service._build_binding(
        logical=logical,
        admission=admission,
        profile=profile,
        route=route,
        binder_subject_id="service.workflow-physical-transport-route-binder",
        bound_at=datetime(2026, 8, 14, 16, 2, tzinfo=UTC),
    )
    return WorkflowEventPhysicalTransportRouteBindingRequest(
        expected_logical_channel_binding_id=logical.binding_id,
        expected_logical_channel_binding_digest=logical.canonical_digest,
        expected_transport_compatibility_admission_id=admission.compatibility_admission_id,
        expected_transport_compatibility_admission_digest=admission.canonical_digest,
        expected_transport_profile_snapshot_id=profile.snapshot_id,
        expected_transport_profile_snapshot_digest=profile.canonical_digest,
        expected_transport_route_snapshot_id=route.snapshot_id,
        expected_transport_route_snapshot_digest=route.canonical_digest,
        expected_policy_digest=candidate.policy_digest,
        scope=candidate.scope,
        binder_subject_id=candidate.binder_subject_id,
        requested_at=candidate.bound_at,
        candidate=candidate,
        idempotency_key="physical-route-binding-postgres-integration-0001",
        request_fingerprint="9" * 64,
    )


async def _reset_integration_rows(
    engine: AsyncEngine,
    request: WorkflowEventPhysicalTransportRouteBindingRequest,
) -> None:
    identifiers = {
        "binding_id": request.candidate.binding_id,
        "logical_id": request.candidate.logical_channel_binding_id,
        "admission_id": request.candidate.transport_compatibility_admission_id,
        "profile_id": request.candidate.transport_profile_snapshot_id,
        "route_id": request.candidate.transport_route_snapshot_id,
    }
    statements = (
        "DELETE FROM workflow_event_physical_transport_route_binding_claims "
        "WHERE binding_id = :binding_id",
        "DELETE FROM workflow_event_physical_transport_route_bindings "
        "WHERE binding_id = :binding_id",
        "DELETE FROM workflow_event_transport_compatibility_admissions "
        "WHERE compatibility_admission_id = :admission_id",
        "DELETE FROM event_transport_route_snapshots WHERE snapshot_id = :route_id",
        "DELETE FROM event_transport_profile_snapshots WHERE snapshot_id = :profile_id",
        "DELETE FROM workflow_event_channel_bindings WHERE binding_id = :logical_id",
    )
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        for statement in statements:
            await connection.execute(text(statement), identifiers)


async def _seed_integration_sources(
    engine: AsyncEngine,
    request: WorkflowEventPhysicalTransportRouteBindingRequest,
) -> None:
    logical, admission, profile, route = _integration_sources()
    assert admission.compatibility_admission_id == (
        request.expected_transport_compatibility_admission_id
    )

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        await session.execute(text("SET LOCAL session_replication_role = replica"))
        session.add_all(
            (
                PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_model(logical),
                PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_model(profile),
                PostgreSQLWorkflowPlanRepository._transport_compatibility_admission_model(
                    admission
                ),
                PostgreSQLWorkflowPlanRepository._transport_route_snapshot_model(route),
            )
        )
        await session.commit()


async def _assert_durable_integration_sources(
    engine: AsyncEngine,
    request: WorkflowEventPhysicalTransportRouteBindingRequest,
) -> None:
    expected = _integration_sources()
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        logical_row = await session.get(
            WorkflowEventLogicalChannelBindingModel,
            request.expected_logical_channel_binding_id,
        )
        admission_row = await session.get(
            WorkflowEventTransportCompatibilityAdmissionModel,
            request.expected_transport_compatibility_admission_id,
        )
        profile_row = await session.get(
            EventPhysicalTransportProfileSnapshotModel,
            request.expected_transport_profile_snapshot_id,
        )
        route_row = await session.get(
            EventPhysicalTransportRouteSnapshotModel,
            request.expected_transport_route_snapshot_id,
        )

    assert logical_row is not None, "logical binding was not persisted"
    assert admission_row is not None, "compatibility admission was not persisted"
    assert profile_row is not None, "transport profile snapshot was not persisted"
    assert route_row is not None, "transport route snapshot was not persisted"
    durable = (
        PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_from_row(logical_row),
        PostgreSQLWorkflowPlanRepository._transport_compatibility_admission_from_row(admission_row),
        PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_from_row(profile_row),
        PostgreSQLWorkflowPlanRepository._transport_route_snapshot_from_row(route_row),
    )
    source_pairs: tuple[tuple[str, Any, Any], ...] = (
        ("logical", durable[0], expected[0]),
        ("admission", durable[1], expected[1]),
        ("profile", durable[2], expected[2]),
        ("route", durable[3], expected[3]),
    )
    for label, source, expected_source in source_pairs:
        assert source == expected_source, f"{label} source changed during PostgreSQL round-trip"
        assert canonical_digest(source.digest_payload()) == source.canonical_digest, (
            f"{label} source digest changed during PostgreSQL round-trip"
        )
    assert PostgreSQLWorkflowPlanRepository._physical_transport_route_binding_evidence_matches(
        logical_row=logical_row,
        admission_row=admission_row,
        profile_row=profile_row,
        route_row=route_row,
        request=request,
    ), "durable source chain does not satisfy the physical route binding contract"


def test_binding_and_claim_round_trip_verify_durable_payloads() -> None:
    request = _request()
    binding_row = PostgreSQLWorkflowPlanRepository._physical_transport_route_binding_model(
        request.candidate
    )
    assert (
        PostgreSQLWorkflowPlanRepository._physical_transport_route_binding_from_row(binding_row)
        == request.candidate
    )

    claim = PostgreSQLWorkflowPlanRepository._physical_transport_route_binding_claim_model(request)
    record = PostgreSQLWorkflowPlanRepository._physical_transport_route_binding_record_from_claim(
        claim, binding_row
    )
    assert record.request_fingerprint == request.request_fingerprint
    assert record.binding == request.candidate


def test_schema_is_unique_append_only_evidence_without_route_runtime_material() -> None:
    binding_table = cast(Table, WorkflowEventPhysicalTransportRouteBindingModel.__table__)
    claim_table = cast(Table, WorkflowEventPhysicalTransportRouteBindingClaimModel.__table__)
    names = set(binding_table.columns.keys()) | set(claim_table.columns.keys())
    assert {
        "binding_id",
        "logical_channel_binding_id",
        "transport_compatibility_admission_id",
        "transport_profile_snapshot_id",
        "transport_route_snapshot_id",
        "policy_digest",
    } <= names
    assert (
        not {
            "endpoint",
            "host",
            "url",
            "destination",
            "routing_contract",
            "private_route_descriptor_commitment",
            "credential_assignment",
            "secret_reference",
            "provider_message",
            "publication_attempt",
            "delivery_receipt",
        }
        & names
    )
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in binding_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("logical_channel_binding_id",) in unique_columns


def test_repository_uses_required_fixed_lock_order_and_atomic_commit() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.bind_physical_transport_route)
    positions = [
        source.index("logical_row ="),
        source.index("profile_row ="),
        source.index("admission_row ="),
        source.index("route_row ="),
    ]
    assert positions == sorted(positions)
    assert source.count(".with_for_update()") == 4
    binding_add = source.index("session.add(self._physical_transport_route_binding_model")
    binding_flush = source.index("await session.flush()", binding_add)
    claim_add = source.index("session.add(self._physical_transport_route_binding_claim_model")
    commit = source.index("await session.commit()", claim_add)
    assert binding_add < binding_flush < claim_add < commit


def test_repository_rechecks_exact_replay_after_waiting_on_source_locks() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.bind_physical_transport_route)
    logical_lock = source.index("logical_row =")
    post_lock_replay = source.index("_physical_transport_route_binding_replay", logical_lock)
    existing_binding = source.index("existing = cast", post_lock_replay)
    assert logical_lock < post_lock_replay < existing_binding
    assert source.count("_physical_transport_route_binding_replay") >= 3


def test_repository_rehydrates_and_recomputes_all_four_source_digests() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._physical_transport_route_binding_evidence_matches
    )
    assert "_event_logical_channel_binding_from_row" in source
    assert "_transport_profile_snapshot_from_row" in source
    assert "_transport_compatibility_admission_from_row" in source
    assert "_transport_route_snapshot_from_row" in source
    assert "canonical_digest(source.digest_payload()) == source.canonical_digest" in source
    assert (
        "logical.scope == admission.scope == profile.scope == route.scope == candidate.scope"
        in source
    )


def test_migration_has_single_linear_head_constraints_and_append_only_triggers() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0122_workflow_physical_transport_route_bindings.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260814_0122"' in migration
    assert 'down_revision: str | None = "20260814_0121"' in migration
    assert "uq_wf_physical_route_binding_logical_binding" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "trg_wf_physical_route_bindings_append_only" in migration
    assert "trg_wf_physical_route_binding_claims_append_only" in migration
    assert "ck_wf_physical_route_binding_zero_auth" in migration


@pytest.mark.asyncio
async def test_unavailable_production_adapter_fails_closed_without_memory_fallback() -> None:
    repository = UnavailableWorkflowPlanRepository()
    assert repository.durable is False
    with pytest.raises(WorkflowEventPhysicalTransportRouteBindingError) as error:
        await repository.bind_physical_transport_route(_request())
    assert error.value.code == "workflow_physical_transport_route_binding_repository_unavailable"


def test_live_postgres_fixture_is_one_exact_valid_scope_chain() -> None:
    request = _integration_request()
    logical, admission, profile, route = _integration_sources()

    assert logical.scope == admission.scope == profile.scope == route.scope == request.scope
    assert PostgreSQLWorkflowPlanRepository._physical_transport_route_binding_evidence_matches(
        logical_row=PostgreSQLWorkflowPlanRepository._event_logical_channel_binding_model(logical),
        admission_row=(
            PostgreSQLWorkflowPlanRepository._transport_compatibility_admission_model(admission)
        ),
        profile_row=PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_model(profile),
        route_row=PostgreSQLWorkflowPlanRepository._transport_route_snapshot_model(route),
        request=request,
    )


@pytest.mark.asyncio
async def test_live_postgres_serializes_exact_replay_and_enforces_append_only_storage() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    request = _integration_request()
    try:
        await _reset_integration_rows(engine, request)
        await _seed_integration_sources(engine, request)
        await _assert_durable_integration_sources(engine, request)
        repository = PostgreSQLWorkflowPlanRepository(engine=engine)

        first, second = await asyncio.gather(
            repository.bind_physical_transport_route(request),
            repository.bind_physical_transport_route(request),
        )

        assert {first.status, second.status} == {
            WorkflowEventPhysicalTransportRouteBindingStatus.BOUND,
            WorkflowEventPhysicalTransportRouteBindingStatus.REPLAY,
        }
        assert first.binding == second.binding == request.candidate

        async with engine.connect() as connection:
            binding_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_physical_transport_route_bindings "
                    "WHERE binding_id = :binding_id"
                ),
                {"binding_id": request.candidate.binding_id},
            )
            claim_count = await connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM workflow_event_physical_transport_route_binding_claims "
                    "WHERE binding_id = :binding_id"
                ),
                {"binding_id": request.candidate.binding_id},
            )
        assert binding_count == claim_count == 1

        mutations = (
            (
                "UPDATE workflow_event_physical_transport_route_bindings "
                "SET state = state WHERE binding_id = :binding_id"
            ),
            (
                "DELETE FROM workflow_event_physical_transport_route_bindings "
                "WHERE binding_id = :binding_id"
            ),
            (
                "UPDATE workflow_event_physical_transport_route_binding_claims "
                "SET result_digest = result_digest WHERE binding_id = :binding_id"
            ),
            (
                "DELETE FROM workflow_event_physical_transport_route_binding_claims "
                "WHERE binding_id = :binding_id"
            ),
        )
        for mutation in mutations:
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(mutation), {"binding_id": request.candidate.binding_id}
                    )
    finally:
        await _reset_integration_rows(engine, request)
        await engine.dispose()
