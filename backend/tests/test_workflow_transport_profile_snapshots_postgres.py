from __future__ import annotations

from datetime import UTC, datetime
from inspect import getsource, signature
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Table
from test_workflow_transport_profile_snapshots import profile_fixture

from atlas.core.persistence.models import (
    EventPhysicalTransportProfileSnapshotClaimModel,
    EventPhysicalTransportProfileSnapshotModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application.transport_profile_snapshot_ports import (
    WorkflowTransportProfileSnapshotError,
    WorkflowTransportProfileSnapshotRepository,
    WorkflowTransportProfileSnapshotRequest,
)
from atlas.modules.workflows.application.transport_profile_snapshots import (
    WorkflowTransportProfileSnapshotService,
)

NOW = datetime(2026, 8, 14, 15, 0, tzinfo=UTC)
SNAPSHOTTER = "service.workflow-transport-profile-registry"


def _request() -> WorkflowTransportProfileSnapshotRequest:
    profile = profile_fixture()
    snapshot = WorkflowTransportProfileSnapshotService._build_snapshot(
        profile=profile,
        snapshotter_subject_id=SNAPSHOTTER,
        captured_at=NOW,
    )
    return WorkflowTransportProfileSnapshotRequest(
        expected_source_profile_id=profile.transport_profile_id,
        expected_source_profile_revision=profile.transport_profile_revision,
        expected_source_profile_digest=profile.canonical_digest,
        scope=profile.scope,
        snapshotter_subject_id=SNAPSHOTTER,
        requested_at=NOW,
        candidate=snapshot,
        idempotency_key="transport-profile-snapshot-postgres-0001",
        request_fingerprint="a" * 64,
    )


def test_models_enforce_immutable_revision_claim_and_zero_authority() -> None:
    snapshot_table = cast(Table, EventPhysicalTransportProfileSnapshotModel.__table__)
    claim_table = cast(Table, EventPhysicalTransportProfileSnapshotClaimModel.__table__)
    snapshot_constraints = {constraint.name for constraint in snapshot_table.constraints}
    claim_constraints = {constraint.name for constraint in claim_table.constraints}

    assert {
        "uq_event_transport_profile_snapshot_revision",
        "uq_event_transport_profile_snapshot_source_digest",
        "uq_event_transport_profile_snapshot_digest",
        "ck_event_transport_profile_snapshot_max_bytes",
        "ck_event_transport_profile_snapshot_state",
        "ck_event_transport_profile_snapshot_zero_auth",
    } <= snapshot_constraints
    assert {
        "uq_event_transport_profile_claim_scope_idem",
        "uq_event_transport_profile_claim_snapshot",
        "uq_event_transport_profile_claim_revision",
        "uq_event_transport_profile_claim_digest",
    } <= claim_constraints
    assert {
        "route_selection_authority_granted",
        "publication_authority_granted",
        "delivery_authority_granted",
        "dispatch_authority_granted",
        "execution_authority_granted",
    } <= set(snapshot_table.columns.keys())

    row = PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_model(_request().candidate)
    assert row.route_selection_authority_granted is False
    assert row.publication_authority_granted is False
    assert row.delivery_authority_granted is False
    assert row.dispatch_authority_granted is False
    assert row.execution_authority_granted is False


def test_snapshot_and_claim_round_trip_with_exact_payload_integrity() -> None:
    request = _request()
    snapshot_row = PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_claim_model(request)

    assert (
        PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_from_row(snapshot_row)
        == request.candidate
    )
    record = PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_record_from_claim(
        claim_row, snapshot_row
    )
    assert record.request_fingerprint == request.request_fingerprint
    assert record.snapshot == request.candidate
    assert claim_row.result_digest == request.candidate.canonical_digest
    assert claim_row.source_profile_digest == request.expected_source_profile_digest


def test_corrupted_snapshot_and_claim_fail_closed() -> None:
    request = _request()
    snapshot_row = PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_model(
        request.candidate
    )
    snapshot_row.maximum_message_byte_count += 1
    with pytest.raises(WorkflowTransportProfileSnapshotError) as snapshot_error:
        PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_from_row(snapshot_row)
    assert snapshot_error.value.code == (
        "workflow_transport_profile_snapshot_repository_contract_violation"
    )

    snapshot_row = PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_model(
        request.candidate
    )
    claim_row = PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_claim_model(request)
    claim_row.result_digest = "f" * 64
    with pytest.raises(WorkflowTransportProfileSnapshotError) as claim_error:
        PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_record_from_claim(
            claim_row, snapshot_row
        )
    assert claim_error.value.code == (
        "workflow_transport_profile_snapshot_repository_contract_violation"
    )


def test_repository_commits_snapshot_and_claim_atomically_and_replays_races() -> None:
    source = getsource(PostgreSQLWorkflowPlanRepository.snapshot_transport_profile)
    replay_source = getsource(PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_replay)

    assert source.count(".with_for_update()") == 1
    assert "_transport_profile_snapshot_evidence_matches" in source
    assert "session.add(self._transport_profile_snapshot_model(candidate))" in source
    assert "session.add(self._transport_profile_snapshot_claim_model(request))" in source
    assert "await session.commit()" in source
    assert "except IntegrityError:" in source
    assert source.count("await session.rollback()") >= 3
    assert "record.request_fingerprint == request.request_fingerprint" in replay_source
    assert "WorkflowTransportProfileSnapshotStatus.REPLAY" in replay_source
    assert "WorkflowTransportProfileSnapshotStatus.IDEMPOTENCY_CONFLICT" in replay_source
    assert "WorkflowTransportProfileSnapshotStatus.SOURCE_CONFLICT" in source
    assert "WorkflowTransportProfileSnapshotStatus.ALREADY_SNAPSHOTTED" in source


def test_adapters_match_transport_profile_snapshot_repository_protocol() -> None:
    for adapter in (
        InMemoryWorkflowPlanRepository,
        PostgreSQLWorkflowPlanRepository,
        UnavailableWorkflowPlanRepository,
    ):
        for method_name in (
            "get_transport_profile_snapshot",
            "get_transport_profile_snapshot_request",
            "snapshot_transport_profile",
        ):
            assert signature(getattr(adapter, method_name)) == signature(
                getattr(WorkflowTransportProfileSnapshotRepository, method_name)
            )


def test_migration_has_no_event_route_credential_or_network_fields() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260814_0119_event_transport_profile_snapshots.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0119"' in migration
    assert 'down_revision: str | None = "20260814_0118"' in migration
    assert 'snapshot_table = "event_transport_profile_snapshots"' in migration
    assert 'claim_table = "event_transport_profile_snapshot_claims"' in migration
    assert "uq_event_transport_profile_snapshot_revision" in migration
    assert "uq_event_transport_profile_claim_scope_idem" in migration
    assert "ck_event_transport_profile_snapshot_zero_auth" in migration

    forbidden_columns = {
        "event_id",
        "artifact_id",
        "logical_channel_binding_id",
        "outbox_entry_id",
        "run_id",
        "attempt_id",
        "lease_id",
        "endpoint",
        "hostname",
        "namespace",
        "topic",
        "stream",
        "queue",
        "partition",
        "routing_key",
        "credential",
        "secret_reference",
        "vault_path",
        "encryption_key",
        "provider_message_id",
        "publication_attempt",
        "receipt",
        "network_health",
    }
    snapshot_table = cast(Table, EventPhysicalTransportProfileSnapshotModel.__table__)
    claim_table = cast(Table, EventPhysicalTransportProfileSnapshotClaimModel.__table__)
    for table in (snapshot_table, claim_table):
        assert forbidden_columns.isdisjoint(table.columns.keys())
        assert not any("deployment" in key.target_fullname for key in table.foreign_keys)
    for field in forbidden_columns:
        assert f'sa.Column("{field}"' not in migration
