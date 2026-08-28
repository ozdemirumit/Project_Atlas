from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.graph.adapters.composite import CompositeGraphSnapshotProvider
from atlas.modules.graph.domain.models import (
    EntityType,
    FreshnessState,
    GraphEntity,
    GraphEvidence,
    GraphSnapshot,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _entity(entity_id: str, entity_type: EntityType, evidence_ref: str) -> GraphEntity:
    return GraphEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        display_name=entity_id,
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        site_id="site.local",
        domain_id="domain.test",
        observed_at=NOW,
        valid_from=NOW,
        valid_to=None,
        freshness=FreshnessState.FRESH,
        confidence_basis="test fixture",
        evidence_references=(evidence_ref,),
        classification=DataClassification.INTERNAL,
        allowed_principals=frozenset({"role.development.operator"}),
    )


def _snapshot(*, entities: tuple[GraphEntity, ...], known_gaps: tuple[str, ...]) -> GraphSnapshot:
    evidence = tuple(
        GraphEvidence(
            reference=reference,
            source="test fixture",
            source_version="1.0.0",
            observed_at=NOW,
            freshness=FreshnessState.FRESH,
            trust_basis="test fixture",
            classification=DataClassification.INTERNAL,
        )
        for reference in dict.fromkeys(
            reference for entity in entities for reference in entity.evidence_references
        )
    )
    return GraphSnapshot(
        snapshot_id=f"snapshot.graph.test.{len(entities)}",
        schema_version="1.0",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        site_id="site.local",
        generated_at=NOW,
        freshness=FreshnessState.FRESH if entities else FreshnessState.UNKNOWN,
        completeness="partial" if entities else "unavailable",
        entities=entities,
        relationships=(),
        observations=(),
        evidence=evidence,
        known_gaps=known_gaps,
        data_profile="configured_test_read_only",
    )


class StubProvider:
    def __init__(self, snapshot: GraphSnapshot) -> None:
        self._snapshot = snapshot

    async def get_snapshot(self) -> GraphSnapshot:
        return self._snapshot


@pytest.mark.asyncio
async def test_composite_merges_entities_and_evidence_from_multiple_providers() -> None:
    storage_snapshot = _snapshot(
        entities=(_entity("asset.storage.a", EntityType.STORAGE_SYSTEM, "evidence.storage.a"),),
        known_gaps=("Storage-only gap.",),
    )
    fabric_snapshot = _snapshot(
        entities=(_entity("asset.san_switch.b", EntityType.SAN_SWITCH, "evidence.fabric.b"),),
        known_gaps=("Fabric-only gap.",),
    )
    provider = CompositeGraphSnapshotProvider(
        providers=(StubProvider(storage_snapshot), StubProvider(fabric_snapshot)),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
    )

    snapshot = await provider.get_snapshot()

    assert {entity.entity_id for entity in snapshot.entities} == {
        "asset.storage.a",
        "asset.san_switch.b",
    }
    assert {item.reference for item in snapshot.evidence} == {
        "evidence.storage.a",
        "evidence.fabric.b",
    }
    assert snapshot.completeness == "partial"
    assert snapshot.freshness is FreshnessState.FRESH
    assert set(snapshot.known_gaps) == {"Storage-only gap.", "Fabric-only gap."}
    assert snapshot.data_profile == "composite_configured_read_only"


@pytest.mark.asyncio
async def test_composite_deduplicates_identical_known_gaps() -> None:
    shared_gap = "No CMDB or hypervisor connector is configured in this environment."
    snapshot_a = _snapshot(entities=(), known_gaps=(shared_gap,))
    snapshot_b = _snapshot(entities=(), known_gaps=(shared_gap,))
    provider = CompositeGraphSnapshotProvider(
        providers=(StubProvider(snapshot_a), StubProvider(snapshot_b)),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
    )

    snapshot = await provider.get_snapshot()

    assert snapshot.entities == ()
    assert snapshot.completeness == "unavailable"
    assert snapshot.freshness is FreshnessState.UNKNOWN
    assert snapshot.known_gaps == (shared_gap,)


@pytest.mark.asyncio
async def test_composite_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="at least one provider"):
        CompositeGraphSnapshotProvider(
            providers=(),
            organization_id="organization.atlas.local",
            environment_id="environment.development",
        )
