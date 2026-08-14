from __future__ import annotations

from pathlib import Path
from typing import cast

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from atlas.core.persistence.models import (
    WorkflowEventTransportCompatibilityAdmissionClaimModel,
    WorkflowEventTransportCompatibilityAdmissionModel,
)

ROOT = Path(__file__).resolve().parents[1]
POSTGRES_SOURCE = (ROOT / "src/atlas/modules/workflows/adapters/postgres.py").read_text(
    encoding="utf-8"
)
MEMORY_SOURCE = (ROOT / "src/atlas/modules/workflows/adapters/memory.py").read_text(
    encoding="utf-8"
)
UNAVAILABLE_SOURCE = (ROOT / "src/atlas/modules/workflows/adapters/unavailable.py").read_text(
    encoding="utf-8"
)
MIGRATION_SOURCE = (
    ROOT / "migrations/versions/20260814_0120_workflow_transport_compatibility_admissions.py"
).read_text(encoding="utf-8")


def _column_names(constraint: UniqueConstraint) -> tuple[str, ...]:
    return tuple(column.name for column in constraint.columns)


def test_admission_table_enforces_immutable_pair_and_zero_authority() -> None:
    table = cast(Table, WorkflowEventTransportCompatibilityAdmissionModel.__table__)
    unique_sets = {
        _column_names(constraint)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert (
        "logical_channel_binding_id",
        "transport_profile_snapshot_id",
        "policy_digest",
    ) in unique_sets
    assert ("canonical_digest",) in unique_sets

    checks = "\n".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "state = 'admitted'" in checks
    for column in (
        "route_selection_authority_granted",
        "route_binding_authority_granted",
        "credential_access_authority_granted",
        "publication_authority_granted",
        "delivery_authority_granted",
        "dispatch_authority_granted",
        "execution_authority_granted",
    ):
        assert f"NOT {column}" in checks


def test_admission_and_claim_reference_only_immutable_sources() -> None:
    admission_table = cast(Table, WorkflowEventTransportCompatibilityAdmissionModel.__table__)
    claim_table = cast(Table, WorkflowEventTransportCompatibilityAdmissionClaimModel.__table__)
    admission_targets = {
        element.target_fullname
        for constraint in admission_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        for element in constraint.elements
    }
    assert admission_targets == {
        "event_transport_profile_snapshots.snapshot_id",
        "workflow_event_channel_bindings.binding_id",
    }

    claim_targets = {
        element.target_fullname
        for constraint in claim_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        for element in constraint.elements
    }
    assert claim_targets == {
        "event_transport_profile_snapshots.snapshot_id",
        "workflow_event_channel_bindings.binding_id",
        "workflow_event_transport_compatibility_admissions.compatibility_admission_id",
    }


def test_claim_has_scoped_idempotency_and_one_result_identity() -> None:
    table = cast(Table, WorkflowEventTransportCompatibilityAdmissionClaimModel.__table__)
    unique_sets = {
        _column_names(constraint)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("idempotency_scope_id", "idempotency_key") in unique_sets
    assert ("compatibility_admission_id",) in unique_sets
    assert ("canonical_digest",) in unique_sets


def test_persistence_schema_excludes_route_runtime_and_secret_fields() -> None:
    columns = {
        column.name
        for model in (
            WorkflowEventTransportCompatibilityAdmissionModel,
            WorkflowEventTransportCompatibilityAdmissionClaimModel,
        )
        for column in cast(Table, model.__table__).columns
    }
    forbidden = {
        "route_id",
        "route_binding_id",
        "selected_route",
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
        "credential_id",
        "secret_reference",
        "vault_path",
        "certificate_reference",
        "encryption_key_reference",
        "provider_message_id",
        "publication_attempt_id",
        "retry_count",
        "receipt_id",
        "acknowledgement_id",
        "offset",
        "network_health",
        "readiness",
    }
    assert columns.isdisjoint(forbidden)


def test_postgres_locks_sources_in_fixed_order_and_writes_atomically() -> None:
    start = POSTGRES_SOURCE.index("    async def admit_transport_compatibility(")
    end = POSTGRES_SOURCE.index("    async def get_dispatch_intent_staging_request(", start)
    method = POSTGRES_SOURCE[start:end]
    binding_lock = method.index("WorkflowEventLogicalChannelBindingModel")
    profile_lock = method.index("EventPhysicalTransportProfileSnapshotModel")
    assert binding_lock < profile_lock
    assert method.count(".with_for_update()") == 2
    assert "_transport_compatibility_admission_evidence_matches" in method
    assert "session.add(self._transport_compatibility_admission_model(candidate))" in method
    assert "session.add(self._transport_compatibility_admission_claim_model(request))" in method
    assert "await session.commit()" in method


def test_postgres_race_distinguishes_exact_replay_from_conflict() -> None:
    start = POSTGRES_SOURCE.index("    async def admit_transport_compatibility(")
    end = POSTGRES_SOURCE.index("    async def get_dispatch_intent_staging_request(", start)
    method = POSTGRES_SOURCE[start:end]
    integrity = method.index("except IntegrityError:")
    assert "await session.rollback()" in method[integrity:]
    assert method.count("_transport_compatibility_admission_replay") >= 2

    replay_start = POSTGRES_SOURCE.index("    async def _transport_compatibility_admission_replay(")
    replay_end = POSTGRES_SOURCE.index(
        "    @classmethod\n    async def _load_transport_compatibility_admission_claim(",
        replay_start,
    )
    replay = POSTGRES_SOURCE[replay_start:replay_end]
    assert "REPLAY" in replay
    assert "IDEMPOTENCY_CONFLICT" in replay


def test_memory_is_explicitly_nondurable_and_unavailable_fails_closed() -> None:
    assert "class InMemoryWorkflowPlanRepository" in MEMORY_SOURCE
    assert "def durable(self) -> bool:\n        return False" in MEMORY_SOURCE
    assert "async def admit_transport_compatibility(" in MEMORY_SOURCE
    assert "async with self._lock:" in MEMORY_SOURCE

    assert "class UnavailableWorkflowPlanRepository" in UNAVAILABLE_SOURCE
    assert "async def admit_transport_compatibility(" in UNAVAILABLE_SOURCE
    assert "_raise_transport_compatibility_admission()" in UNAVAILABLE_SOURCE
    assert "workflow_transport_compatibility_admission_repository_unavailable" in (
        UNAVAILABLE_SOURCE
    )


def test_migration_is_linear_and_contains_no_mutable_source_fk() -> None:
    assert 'revision: str = "20260814_0120"' in MIGRATION_SOURCE
    assert 'down_revision: str | None = "20260814_0119"' in MIGRATION_SOURCE
    assert "workflow_event_channel_bindings.binding_id" in MIGRATION_SOURCE
    assert "event_transport_profile_snapshots.snapshot_id" in MIGRATION_SOURCE
    for forbidden_target in (
        "deployment_event_transport_profiles",
        "workflow_dispatch_event_envelopes",
        "workflow_dispatch_outbox_entries",
        "workflow_execution_attempts",
        "workflow_outbox_publication_leases",
    ):
        assert forbidden_target not in MIGRATION_SOURCE
