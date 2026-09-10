"""Pass 28 of this session's standing audit loop found `GraphEntity`, `GraphRelationship`, and
`GraphSnapshot` had zero identifier-format validation -- unlike every sibling domain module in
this codebase (`inventory/devices.py`, `connectors/domain/models.py`, `itsm/*.py`,
`storage/domain/models.py`, etc.), which all validate their identifier fields via
`validate_stable_identifier` or an equivalent local regex. This matters because
`graph/application/engine.py`'s per-entity authorization filter
(`InMemoryGraphImpactAnalyzer._entity_visible`/`_relationship_visible`) compares these fields
directly against the request's access scope, per item, in a loop over a snapshot -- an
authorization-relevant filter implicitly relying on well-formed domain data with no domain-level
guarantee that it is. These tests prove `entity_id`/`organization_id`/`environment_id`/
`site_id`/`domain_id` (`GraphEntity`), `relationship_id`/`source_entity_id`/`target_entity_id`
(`GraphRelationship`), and `snapshot_id`/`organization_id`/`environment_id`/`site_id`
(`GraphSnapshot`) now reject a malformed value, matching every sibling module's practice. Real
construction across this codebase's own adapters (e.g. `graph/adapters/configured_hitachi.py`'s
`entity_id=f"asset.storage.{_identity(...)}"`, `_identity()` being a lowercase-hex digest) was
confirmed to already produce values that satisfy this grammar -- this is additive, not a
behavior change for any real caller.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.graph.domain.models import (
    AssertionMethod,
    EntityType,
    FreshnessState,
    GraphEntity,
    GraphRelationship,
    GraphSnapshot,
    RelationshipType,
)

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def _entity(**overrides: object) -> GraphEntity:
    values: dict[str, object] = {
        "entity_id": "asset.storage.deadbeef00",
        "entity_type": EntityType.STORAGE_SYSTEM,
        "display_name": "Test Array",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "domain_id": "domain.storage",
        "observed_at": NOW,
        "valid_from": NOW,
        "valid_to": None,
        "freshness": FreshnessState.FRESH,
        "confidence_basis": "test fixture",
        "evidence_references": ("evidence.test.0001",),
        "classification": DataClassification.INTERNAL,
        "allowed_principals": frozenset({"role.development.operator"}),
    }
    values.update(overrides)
    return GraphEntity(**values)  # type: ignore[arg-type]


def _relationship(**overrides: object) -> GraphRelationship:
    values: dict[str, object] = {
        "relationship_id": "relationship.storage.deadbeef00.deadbeef01",
        "relationship_type": RelationshipType.DEPENDS_ON,
        "source_entity_id": "asset.storage.deadbeef00",
        "target_entity_id": "asset.storage.deadbeef01",
        "assertion_method": AssertionMethod.OBSERVED,
        "observed_at": NOW,
        "valid_from": NOW,
        "valid_to": None,
        "freshness": FreshnessState.FRESH,
        "confidence_basis": "test fixture",
        "evidence_references": ("evidence.test.0001",),
        "classification": DataClassification.INTERNAL,
        "allowed_principals": frozenset({"role.development.operator"}),
    }
    values.update(overrides)
    return GraphRelationship(**values)  # type: ignore[arg-type]


def _snapshot(**overrides: object) -> GraphSnapshot:
    values: dict[str, object] = {
        "snapshot_id": "snapshot.graph.test.0001",
        "schema_version": "1.0",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "generated_at": NOW,
        "freshness": FreshnessState.FRESH,
        "completeness": "bounded",
        "entities": (),
        "relationships": (),
        "observations": (),
        "evidence": (),
        "known_gaps": (),
        "data_profile": "test",
    }
    values.update(overrides)
    return GraphSnapshot(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    ["entity_id", "organization_id", "environment_id", "site_id", "domain_id"],
)
@pytest.mark.parametrize("malformed", ["", "Uppercase.Not.Allowed", "0starts-with-digit"])
def test_graph_entity_rejects_malformed_identifiers(field: str, malformed: str) -> None:
    with pytest.raises(ValueError, match="not a valid stable identifier"):
        _entity(**{field: malformed})


def test_graph_entity_accepts_a_real_adapter_shaped_identifier() -> None:
    entity = _entity(entity_id="asset.storage.deadbeef00")
    assert entity.entity_id == "asset.storage.deadbeef00"


@pytest.mark.parametrize(
    "field",
    ["relationship_id", "source_entity_id", "target_entity_id"],
)
def test_graph_relationship_rejects_malformed_identifiers(field: str) -> None:
    with pytest.raises(ValueError, match="not a valid stable identifier"):
        _relationship(**{field: ""})


@pytest.mark.parametrize(
    "field",
    ["snapshot_id", "organization_id", "environment_id", "site_id"],
)
def test_graph_snapshot_rejects_malformed_identifiers(field: str) -> None:
    with pytest.raises(ValueError, match="not a valid stable identifier"):
        _snapshot(**{field: ""})
