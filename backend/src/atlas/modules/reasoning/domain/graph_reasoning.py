"""ATLAS-041 SS12: graph and dependency reasoning.

Reuses `graph.domain.models.RelationshipType` and `AssertionMethod` directly -- ATLAS-026 already
supplies exactly the time-aware entities and relationships SS12 reasons over. This module adds
only what SS12 asks for beyond the graph module's own contract: a relationship-*nature*
classification axis (physical/logical/service/ownership/inferred) that `RelationshipType` doesn't
carry (`RelationshipType` names *which* edge kind it is -- `BACKED_BY`, `USES` -- not *what
nature* of connection it represents), traversal bounds, and impact/causality citation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.graph.domain.models import AssertionMethod, RelationshipType
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.claims import ConfidenceCategory


class RelationshipNature(StrEnum):
    """SS12: "distinguish physical, logical, service, ownership, and inferred relationships." An
    axis orthogonal to `graph.RelationshipType`."""

    PHYSICAL = "physical"
    LOGICAL = "logical"
    SERVICE = "service"
    OWNERSHIP = "ownership"
    INFERRED = "inferred"


class RelationshipDirection(StrEnum):
    FORWARD = "forward"
    REVERSE = "reverse"
    BIDIRECTIONAL = "bidirectional"


@dataclass(frozen=True, slots=True)
class GraphTraversalScope:
    """SS12: "traverse only authorized graph scope" and "bound depth and expansion to avoid
    irrelevant blast radius.\""""

    authorized_entity_ids: frozenset[str]
    maximum_depth: int
    maximum_expansion: int

    def __post_init__(self) -> None:
        if self.maximum_depth < 1:
            raise ValueError("maximum_depth must be positive")
        if self.maximum_expansion < 1:
            raise ValueError("maximum_expansion must be positive")


def is_within_traversal_scope(
    *, entity_id: str, depth: int, expansion_count: int, scope: GraphTraversalScope
) -> bool:
    return (
        entity_id in scope.authorized_entity_ids
        and depth <= scope.maximum_depth
        and expansion_count <= scope.maximum_expansion
    )


@dataclass(frozen=True, slots=True)
class DependencyClaim:
    """Covers SS12's remaining elements: relationship type/direction/source/observation time,
    nature classification, "avoid treating mere reachability as active dependency" (`
    is_active_dependency`, a separate field from mere graph connectivity), "preserve alternative
    paths, redundancy, and shared dependencies," and "cite graph evidence used for impact or
    causality claims.\""""

    claim_id: str
    from_entity_id: str
    to_entity_id: str
    relationship_type: RelationshipType
    relationship_nature: RelationshipNature
    direction: RelationshipDirection
    source: str
    observed_at: datetime
    assertion_method: AssertionMethod
    is_active_dependency: bool
    alternative_paths: tuple[str, ...]
    redundancy_present: bool
    shared_dependency_entity_ids: tuple[str, ...]
    confidence: ConfidenceCategory
    graph_evidence_citation: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.claim_id, "claim_id")
        validate_stable_identifier(self.from_entity_id, "from_entity_id")
        validate_stable_identifier(self.to_entity_id, "to_entity_id")
        if not self.source.strip():
            raise ValueError("a dependency claim requires a source")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.graph_evidence_citation.strip():
            raise ValueError(
                "SS12: cite graph evidence used for impact or causality claims --"
                " graph_evidence_citation is required"
            )

    @property
    def is_low_confidence(self) -> bool:
        """SS12: "expose missing or low-confidence relationships.\""""
        return self.confidence in (ConfidenceCategory.INSUFFICIENT, ConfidenceCategory.LOW)
