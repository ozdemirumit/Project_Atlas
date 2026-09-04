from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.change_impact.domain.traversal import (
    AffectedItemClassification,
    DependencyTraversalResult,
    EdgeKind,
    ImpactCategory,
    TraversalDirection,
    is_unbounded_reachability,
)
from atlas.modules.graph.domain.models import (
    EntityType,
    FreshnessState,
    GraphEntity,
    ImpactPath,
    ImpactScope,
    StorageImpactResult,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def entity(entity_id: str) -> GraphEntity:
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


def graph_impact(**overrides: object) -> StorageImpactResult:
    defaults: dict[str, object] = {
        "snapshot_id": "graph-snapshot.example",
        "snapshot_generated_at": NOW,
        "start_entity_id": "target.controller-b",
        "max_depth": 3,
        "freshness": FreshnessState.FRESH,
        "completeness": "complete",
        "entities": (entity("target.controller-b"), entity("target.host-01")),
        "relationships": (),
        "paths": (
            ImpactPath(
                scope=ImpactScope.DIRECT,
                entity_ids=("target.controller-b", "target.host-01"),
                relationship_ids=("relationship.controller-host",),
                evidence_references=("evidence.example",),
            ),
        ),
        "evidence": (),
        "direct_entity_ids": ("target.controller-b", "target.host-01"),
        "possible_entity_ids": (),
        "technical_service_ids": ("service.file-shares",),
        "business_service_ids": (),
        "unknowns": (),
        "known_gaps": (),
        "outage_confirmed": False,
        "digital_twin_maturity": "structural_only",
        "data_profile": "synthetic_lab",
        "safety_notice": "Decision support only.",
    }
    defaults.update(overrides)
    return StorageImpactResult(**defaults)  # type: ignore[arg-type]


def classification(**overrides: object) -> AffectedItemClassification:
    defaults: dict[str, object] = {
        "entity_id": "target.host-01",
        "impact_category": ImpactCategory.FIRST_ORDER,
        "edge_kinds": (EdgeKind.OBSERVED,),
    }
    defaults.update(overrides)
    return AffectedItemClassification(**defaults)  # type: ignore[arg-type]


def traversal(**overrides: object) -> DependencyTraversalResult:
    defaults: dict[str, object] = {
        "traversal_id": "traversal.example",
        "change_request_id": "change-request.example",
        "graph_impact": graph_impact(),
        "direction": TraversalDirection.DOWNSTREAM,
        "classifications": (classification(),),
        "inaccessible_or_missing_subgraph_notes": (),
    }
    defaults.update(overrides)
    return DependencyTraversalResult(**defaults)  # type: ignore[arg-type]


def test_traversal_accepts_valid_classification() -> None:
    result = traversal()
    assert result.classifications[0].entity_id == "target.host-01"


def test_classification_requires_at_least_one_edge_kind() -> None:
    with pytest.raises(ValueError, match="at least one edge kind"):
        classification(edge_kinds=())


def test_is_unbounded_reachability_true_for_entity_outside_known_sets() -> None:
    assert is_unbounded_reachability("target.unrelated", graph_impact()) is True


def test_is_unbounded_reachability_false_for_entity_with_evidenced_path() -> None:
    assert is_unbounded_reachability("target.host-01", graph_impact()) is False


def test_is_unbounded_reachability_true_when_classified_but_no_path_evidence() -> None:
    impact = graph_impact(paths=(), direct_entity_ids=("target.host-01",))
    assert is_unbounded_reachability("target.host-01", impact) is True


def test_traversal_rejects_classification_for_unknown_entity() -> None:
    with pytest.raises(ValueError, match="unknown entity"):
        traversal(classifications=(classification(entity_id="target.not-in-graph"),))


def test_traversal_rejects_unbounded_reachability_classification() -> None:
    impact = graph_impact(entities=(entity("target.controller-b"), entity("target.unreached")))
    with pytest.raises(ValueError, match="unbounded reachability"):
        traversal(
            graph_impact=impact,
            classifications=(classification(entity_id="target.unreached"),),
        )


def test_traversal_rejects_duplicate_classification() -> None:
    with pytest.raises(ValueError, match="duplicate classification"):
        traversal(classifications=(classification(), classification()))
