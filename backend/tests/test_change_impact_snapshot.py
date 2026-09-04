from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.change_impact.domain.snapshot import (
    AnalysisSnapshot,
    DataProtectionState,
    EntityCurrentState,
    ServiceCriticalityRecord,
)
from atlas.modules.graph.domain.models import (
    EntityType,
    FreshnessState,
    GraphEntity,
    GraphEvidence,
    GraphSnapshot,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def entity(entity_id: str = "entity.controller-b") -> GraphEntity:
    return GraphEntity(
        entity_id=entity_id,
        entity_type=EntityType.STORAGE_SYSTEM,
        display_name=entity_id,
        organization_id="organization.example",
        environment_id="environment.production",
        site_id="site.primary",
        domain_id="domain.storage",
        observed_at=NOW,
        valid_from=NOW,
        valid_to=None,
        freshness=FreshnessState.FRESH,
        confidence_basis="test fixture",
        evidence_references=("evidence.example",),
        classification=DataClassification.INTERNAL,
        allowed_principals=frozenset({"role.storage.operator"}),
    )


def graph_snapshot(entities: tuple[GraphEntity, ...] = (entity(),)) -> GraphSnapshot:
    return GraphSnapshot(
        snapshot_id="snapshot.graph.example",
        schema_version="1.0",
        organization_id="organization.example",
        environment_id="environment.production",
        site_id="site.primary",
        generated_at=NOW,
        freshness=FreshnessState.FRESH,
        completeness="partial",
        entities=entities,
        relationships=(),
        observations=(),
        evidence=(
            GraphEvidence(
                reference="evidence.example",
                source="hitachi_ops_center",
                source_version="1.0",
                observed_at=NOW,
                freshness=FreshnessState.FRESH,
                trust_basis="vendor API",
                classification=DataClassification.INTERNAL,
            ),
        ),
        known_gaps=(),
        data_profile="configured_test_read_only",
    )


def entity_state(**overrides: object) -> EntityCurrentState:
    defaults: dict[str, object] = {
        "entity_id": "entity.controller-b",
        "health_status": "healthy",
        "active_alert_count": 0,
        "capacity_used_percent": 62.5,
        "load_percent": 40.0,
        "latency_ms": 3.2,
        "in_maintenance": False,
        "firmware_version": "6.1.0",
        "compatibility_status": "supported",
        "support_status": "in_support",
    }
    defaults.update(overrides)
    return EntityCurrentState(**defaults)  # type: ignore[arg-type]


def snapshot(**overrides: object) -> AnalysisSnapshot:
    defaults: dict[str, object] = {
        "snapshot_id": "snapshot.change-impact.example",
        "change_request_id": "change-request.example",
        "generated_at": NOW,
        "graph_snapshot": graph_snapshot(),
        "entity_current_states": (entity_state(),),
        "service_criticality": (
            ServiceCriticalityRecord(
                service_id="service.file-shares", criticality="high", owner="storage-team"
            ),
        ),
        "data_protection_states": (
            DataProtectionState(
                entity_id="entity.controller-b",
                backup_status="current",
                replication_status="synchronized",
                snapshot_status="current",
                recovery_state="ready",
            ),
        ),
        "recent_and_concurrent_change_references": (),
    }
    defaults.update(overrides)
    return AnalysisSnapshot(**defaults)  # type: ignore[arg-type]


def test_snapshot_accepts_valid_state() -> None:
    result = snapshot()
    assert result.entity_current_states[0].entity_id == "entity.controller-b"


def test_entity_current_state_rejects_out_of_range_percent() -> None:
    with pytest.raises(ValueError, match="within 0 and 100"):
        entity_state(capacity_used_percent=150.0)


def test_entity_current_state_rejects_negative_latency() -> None:
    with pytest.raises(ValueError, match="latency_ms must not be negative"):
        entity_state(latency_ms=-1.0)


def test_snapshot_rejects_entity_current_state_for_unknown_entity() -> None:
    with pytest.raises(ValueError, match="unknown entity"):
        snapshot(entity_current_states=(entity_state(entity_id="entity.unknown"),))


def test_snapshot_rejects_data_protection_state_for_unknown_entity() -> None:
    with pytest.raises(ValueError, match="unknown entity"):
        snapshot(
            data_protection_states=(
                DataProtectionState(
                    entity_id="entity.unknown",
                    backup_status="current",
                    replication_status=None,
                    snapshot_status=None,
                    recovery_state=None,
                ),
            )
        )


def test_snapshot_rejects_duplicate_entity_current_state() -> None:
    with pytest.raises(ValueError, match="must not repeat"):
        snapshot(entity_current_states=(entity_state(), entity_state()))


def test_snapshot_requires_timezone_aware_generated_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        snapshot(generated_at=datetime(2026, 9, 4, 12, 0))
