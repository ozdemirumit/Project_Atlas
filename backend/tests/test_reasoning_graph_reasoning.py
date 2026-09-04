from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.graph.domain.models import AssertionMethod, RelationshipType
from atlas.modules.reasoning.domain.claims import ConfidenceCategory
from atlas.modules.reasoning.domain.graph_reasoning import (
    DependencyClaim,
    GraphTraversalScope,
    RelationshipDirection,
    RelationshipNature,
    is_within_traversal_scope,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def scope(**overrides: object) -> GraphTraversalScope:
    defaults: dict[str, object] = {
        "authorized_entity_ids": frozenset({"target.a", "target.b"}),
        "maximum_depth": 3,
        "maximum_expansion": 50,
    }
    defaults.update(overrides)
    return GraphTraversalScope(**defaults)  # type: ignore[arg-type]


def test_graph_traversal_scope_requires_positive_depth() -> None:
    with pytest.raises(ValueError, match="maximum_depth"):
        scope(maximum_depth=0)


def test_graph_traversal_scope_requires_positive_expansion() -> None:
    with pytest.raises(ValueError, match="maximum_expansion"):
        scope(maximum_expansion=0)


def test_is_within_traversal_scope_true_for_authorized_entity_within_bounds() -> None:
    assert (
        is_within_traversal_scope(entity_id="target.a", depth=2, expansion_count=10, scope=scope())
        is True
    )


def test_is_within_traversal_scope_false_for_unauthorized_entity() -> None:
    assert (
        is_within_traversal_scope(
            entity_id="target.unauthorized", depth=1, expansion_count=1, scope=scope()
        )
        is False
    )


def test_is_within_traversal_scope_false_beyond_depth_bound() -> None:
    assert (
        is_within_traversal_scope(entity_id="target.a", depth=4, expansion_count=1, scope=scope())
        is False
    )


def test_is_within_traversal_scope_false_beyond_expansion_bound() -> None:
    assert (
        is_within_traversal_scope(entity_id="target.a", depth=1, expansion_count=51, scope=scope())
        is False
    )


def dependency_claim(**overrides: object) -> DependencyClaim:
    defaults: dict[str, object] = {
        "claim_id": "reasoning-dependency-claim.example",
        "from_entity_id": "target.a",
        "to_entity_id": "target.b",
        "relationship_type": RelationshipType.DEPENDS_ON,
        "relationship_nature": RelationshipNature.SERVICE,
        "direction": RelationshipDirection.FORWARD,
        "source": "graph.snapshot.example",
        "observed_at": NOW,
        "assertion_method": AssertionMethod.OBSERVED,
        "is_active_dependency": True,
        "alternative_paths": (),
        "redundancy_present": False,
        "shared_dependency_entity_ids": (),
        "confidence": ConfidenceCategory.HIGH,
        "graph_evidence_citation": "graph://snapshot.example/edge.a-b",
    }
    defaults.update(overrides)
    return DependencyClaim(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_dependency_claim_constructs_cleanly() -> None:
    example = dependency_claim()
    assert example.relationship_nature is RelationshipNature.SERVICE


def test_dependency_claim_requires_a_source() -> None:
    with pytest.raises(ValueError, match="source"):
        dependency_claim(source="   ")


def test_dependency_claim_rejects_naive_observed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        dependency_claim(observed_at=NOW.replace(tzinfo=None))


def test_dependency_claim_requires_graph_evidence_citation() -> None:
    with pytest.raises(ValueError, match="graph_evidence_citation is required"):
        dependency_claim(graph_evidence_citation="   ")


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (ConfidenceCategory.INSUFFICIENT, True),
        (ConfidenceCategory.LOW, True),
        (ConfidenceCategory.MODERATE, False),
        (ConfidenceCategory.HIGH, False),
        (ConfidenceCategory.CONFIRMED, False),
    ],
)
def test_is_low_confidence(confidence: ConfidenceCategory, expected: bool) -> None:
    assert dependency_claim(confidence=confidence).is_low_confidence is expected


def test_dependency_claim_can_represent_mere_reachability_distinct_from_active_dependency() -> None:
    example = dependency_claim(is_active_dependency=False)
    assert example.is_active_dependency is False
