from __future__ import annotations

from datetime import UTC, datetime
from inspect import getsource, signature
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table, UniqueConstraint
from test_workflow_transport_route_snapshots import route_fixture

from atlas.core.persistence.models import (
    EventPhysicalTransportRouteSnapshotClaimModel,
    EventPhysicalTransportRouteSnapshotModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application.transport_route_snapshot_ports import (
    WorkflowTransportRouteSnapshotError,
    WorkflowTransportRouteSnapshotRepository,
    WorkflowTransportRouteSnapshotRequest,
)
from atlas.modules.workflows.application.transport_route_snapshots import (
    WorkflowTransportRouteSnapshotService,
)

NOW = datetime(2026, 8, 14, 16, 0, tzinfo=UTC)
SNAPSHOTTER = "service.workflow-transport-route-registry"
MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260814_0121_event_transport_route_snapshots.py"
)


def _request() -> WorkflowTransportRouteSnapshotRequest:
    route = route_fixture()
    snapshot = WorkflowTransportRouteSnapshotService._build_snapshot(
        route=route,
        snapshotter_subject_id=SNAPSHOTTER,
        captured_at=NOW,
    )
    return WorkflowTransportRouteSnapshotRequest(
        expected_source_route_id=route.route_id,
        expected_source_route_revision=route.route_revision,
        expected_source_route_digest=route.canonical_digest,
        scope=route.scope,
        snapshotter_subject_id=SNAPSHOTTER,
        requested_at=NOW,
        candidate=snapshot,
        idempotency_key="transport-route-snapshot-postgres-0001",
        request_fingerprint="a" * 64,
    )


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_models_enforce_immutable_revision_claim_and_zero_authority() -> None:
    snapshot_table = cast(Table, EventPhysicalTransportRouteSnapshotModel.__table__)
    claim_table = cast(Table, EventPhysicalTransportRouteSnapshotClaimModel.__table__)

    assert {("route_id", "route_revision"), ("source_route_digest",), ("canonical_digest",)} <= (
        _unique_columns(snapshot_table)
    )
    assert {
        ("idempotency_scope_id", "idempotency_key"),
        ("snapshot_id",),
        ("route_id", "route_revision"),
        ("canonical_digest",),
    } <= _unique_columns(claim_table)

    checks = "\n".join(
        str(constraint.sqltext)
        for constraint in snapshot_table.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "state = 'snapshotted'" in checks
    for column in (
        "endpoint_resolution_authority_granted",
        "credential_access_authority_granted",
        "network_access_authority_granted",
        "readiness_probe_authority_granted",
        "publication_authority_granted",
        "delivery_authority_granted",
        "dispatch_authority_granted",
        "execution_authority_granted",
    ):
        assert f"NOT {column}" in checks


def test_snapshot_and_claim_round_trip_with_exact_payload_integrity() -> None:
    request = _request()
    snapshot_row = PostgreSQLWorkflowPlanRepository._transport_route_snapshot_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._transport_route_snapshot_claim_model(request)

    assert (
        PostgreSQLWorkflowPlanRepository._transport_route_snapshot_from_row(snapshot_row)
        == request.candidate
    )
    record = PostgreSQLWorkflowPlanRepository._transport_route_snapshot_record_from_claim(
        claim_row, snapshot_row
    )
    assert record.request_fingerprint == request.request_fingerprint
    assert record.snapshot == request.candidate
    assert claim_row.result_digest == request.candidate.canonical_digest
    assert claim_row.source_route_digest == request.expected_source_route_digest


def test_corrupted_snapshot_and_claim_fail_closed() -> None:
    request = _request()
    snapshot_row = PostgreSQLWorkflowPlanRepository._transport_route_snapshot_model(
        request.candidate
    )
    snapshot_row.network_policy_digest = "f" * 64
    with pytest.raises(WorkflowTransportRouteSnapshotError) as snapshot_error:
        PostgreSQLWorkflowPlanRepository._transport_route_snapshot_from_row(snapshot_row)
    assert snapshot_error.value.code == (
        "workflow_transport_route_snapshot_repository_contract_violation"
    )

    snapshot_row = PostgreSQLWorkflowPlanRepository._transport_route_snapshot_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._transport_route_snapshot_claim_model(request)
    claim_row.result_digest = "f" * 64
    with pytest.raises(WorkflowTransportRouteSnapshotError) as claim_error:
        PostgreSQLWorkflowPlanRepository._transport_route_snapshot_record_from_claim(
            claim_row, snapshot_row
        )
    assert claim_error.value.code == (
        "workflow_transport_route_snapshot_repository_contract_violation"
    )


def test_repository_commits_snapshot_and_claim_atomically_and_replays_races() -> None:
    source = getsource(PostgreSQLWorkflowPlanRepository.snapshot_transport_route)
    replay_source = getsource(PostgreSQLWorkflowPlanRepository._transport_route_snapshot_replay)

    assert source.count(".with_for_update()") == 1
    assert "_transport_route_snapshot_evidence_matches" in source
    assert "session.add(self._transport_route_snapshot_model(candidate))" in source
    assert "session.add(self._transport_route_snapshot_claim_model(request))" in source
    assert "await session.commit()" in source
    assert "except IntegrityError:" in source
    assert source.count("await session.rollback()") >= 3
    assert "record.request_fingerprint == request.request_fingerprint" in replay_source
    assert "WorkflowTransportRouteSnapshotStatus.REPLAY" in replay_source
    assert "WorkflowTransportRouteSnapshotStatus.IDEMPOTENCY_CONFLICT" in replay_source
    assert "WorkflowTransportRouteSnapshotStatus.SOURCE_CONFLICT" in source
    assert "WorkflowTransportRouteSnapshotStatus.ALREADY_SNAPSHOTTED" in source


def test_adapters_match_route_snapshot_repository_protocol() -> None:
    for adapter in (
        InMemoryWorkflowPlanRepository,
        PostgreSQLWorkflowPlanRepository,
        UnavailableWorkflowPlanRepository,
    ):
        for method_name in (
            "get_transport_route_snapshot",
            "get_transport_route_snapshot_request",
            "snapshot_transport_route",
        ):
            assert signature(getattr(adapter, method_name)) == signature(
                getattr(WorkflowTransportRouteSnapshotRepository, method_name)
            )


def test_schema_excludes_raw_locator_secret_runtime_and_binding_fields() -> None:
    snapshot_table = cast(Table, EventPhysicalTransportRouteSnapshotModel.__table__)
    claim_table = cast(Table, EventPhysicalTransportRouteSnapshotClaimModel.__table__)
    columns = set(snapshot_table.columns.keys()) | set(claim_table.columns.keys())
    forbidden = {
        "hostname",
        "url",
        "ip_address",
        "broker_endpoint",
        "namespace",
        "topic",
        "stream",
        "queue",
        "partition",
        "routing_key",
        "endpoint_set_digest",
        "destination_digest",
        "routing_contract_digest",
        "credential_id",
        "credential_reference",
        "secret_reference",
        "vault_path",
        "certificate_reference",
        "encryption_key_reference",
        "network_health",
        "readiness",
        "provider_message_id",
        "publication_attempt_id",
        "route_binding_id",
        "logical_channel_binding_id",
        "compatibility_admission_id",
    }
    assert columns.isdisjoint(forbidden)
    assert not snapshot_table.foreign_keys
    assert {key.target_fullname for key in claim_table.foreign_keys} == {
        "event_transport_route_snapshots.snapshot_id"
    }


def test_migration_is_linear_and_adds_append_only_database_triggers() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260814_0121"' in migration
    assert 'down_revision: str | None = "20260814_0120"' in migration
    assert 'snapshot_table = "event_transport_route_snapshots"' in migration
    assert 'claim_table = "event_transport_route_snapshot_claims"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "reject_event_transport_route_snapshot_mutation" in migration
    assert "trg_event_transport_route_snapshots_append_only" not in migration
    assert "CREATE TRIGGER trg_{table_name}_append_only" in migration
    assert "DROP TRIGGER IF EXISTS trg_{table_name}_append_only" in migration
    assert "DROP FUNCTION IF EXISTS reject_event_transport_route_snapshot_mutation()" in migration
    assert "workflow_event_physical_transport_route_bindings" not in migration
    assert "workflow_transport_route_binding_claims" not in migration


def test_memory_is_nondurable_and_unavailable_fails_closed() -> None:
    memory_source = getsource(InMemoryWorkflowPlanRepository.snapshot_transport_route)
    unavailable_source = getsource(UnavailableWorkflowPlanRepository.snapshot_transport_route)
    assert "async with self._lock:" in memory_source
    assert InMemoryWorkflowPlanRepository().durable is False
    assert "_raise_transport_route_snapshot()" in unavailable_source
