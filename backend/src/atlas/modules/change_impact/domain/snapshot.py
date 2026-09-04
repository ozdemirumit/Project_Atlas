"""ATLAS-044 SS7: the analysis snapshot.

Reuses `graph.domain.models.GraphSnapshot` directly for target inventory/configuration,
relationships, and "graph source, confidence, observation time, and known gaps" -- SS7's own list
of required elements is, for those items, exactly what `GraphSnapshot` already carries (ATLAS-026
is named as the source in SS5's analysis architecture diagram). The remaining SS7 elements --
current health/alerts/capacity/load/latency/maintenance state, business service criticality and
owner, data-protection state, recent/concurrent changes, and product/firmware/compatibility/
support state -- have no home in `GraphSnapshot`, so this module adds them as raw, per-entity
observed state. This snapshot captures *inputs as observed*, not yet analyzed; SS11-SS14 build
the actual redundancy/capacity/data-protection/service analyses on top of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.graph.domain.models import GraphSnapshot
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class EntityCurrentState:
    entity_id: str
    health_status: str
    active_alert_count: int
    capacity_used_percent: float | None
    load_percent: float | None
    latency_ms: float | None
    in_maintenance: bool
    firmware_version: str | None
    compatibility_status: str | None
    support_status: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.entity_id, "entity_id")
        if not self.health_status.strip():
            raise ValueError("an entity current state requires a health status")
        if self.active_alert_count < 0:
            raise ValueError("active_alert_count must not be negative")
        for field_name, percent in (
            ("capacity_used_percent", self.capacity_used_percent),
            ("load_percent", self.load_percent),
        ):
            if percent is not None and not (0.0 <= percent <= 100.0):
                raise ValueError(f"{field_name} must be within 0 and 100")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms must not be negative")


@dataclass(frozen=True, slots=True)
class ServiceCriticalityRecord:
    service_id: str
    criticality: str
    owner: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.service_id, "service_id")
        if not self.criticality.strip():
            raise ValueError("a service criticality record requires a criticality")
        if not self.owner.strip():
            raise ValueError("a service criticality record requires an owner")


@dataclass(frozen=True, slots=True)
class DataProtectionState:
    """SS7's "backup, replication, snapshot, recovery, and data-protection state" -- raw observed
    state per entity, ahead of SS13's fuller data-protection and recoverability analysis."""

    entity_id: str
    backup_status: str
    replication_status: str | None
    snapshot_status: str | None
    recovery_state: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.entity_id, "entity_id")
        if not self.backup_status.strip():
            raise ValueError("a data protection state requires a backup status")


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    """SS7: "impact is calculated against an immutable, time-stamped snapshot." Immutability comes
    from the frozen dataclass; every entity referenced by the supplementary records must be a real
    entity in `graph_snapshot` -- this snapshot never asserts state about an entity the graph
    itself does not know about."""

    snapshot_id: str
    change_request_id: str
    generated_at: datetime
    graph_snapshot: GraphSnapshot
    entity_current_states: tuple[EntityCurrentState, ...]
    service_criticality: tuple[ServiceCriticalityRecord, ...]
    data_protection_states: tuple[DataProtectionState, ...]
    recent_and_concurrent_change_references: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.snapshot_id, "snapshot_id")
        validate_stable_identifier(self.change_request_id, "change_request_id")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        known_entity_ids = {entity.entity_id for entity in self.graph_snapshot.entities}
        for state in self.entity_current_states:
            if state.entity_id not in known_entity_ids:
                raise ValueError(
                    f"entity current state references unknown entity {state.entity_id!r}"
                )
        for protection in self.data_protection_states:
            if protection.entity_id not in known_entity_ids:
                raise ValueError(
                    f"data protection state references unknown entity {protection.entity_id!r}"
                )
        state_entity_ids = [state.entity_id for state in self.entity_current_states]
        if len(state_entity_ids) != len(set(state_entity_ids)):
            raise ValueError("entity_current_states must not repeat an entity")
        protection_entity_ids = [state.entity_id for state in self.data_protection_states]
        if len(protection_entity_ids) != len(set(protection_entity_ids)):
            raise ValueError("data_protection_states must not repeat an entity")
