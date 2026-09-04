"""ATLAS-044 SS9/SS10: dependency traversal and direct/transitive impact.

Reuses `graph.domain.models.StorageImpactResult` directly for the traversed graph and its
evidenced `ImpactPath`s -- SS10's own requirement, "each affected item includes the path and
relationship evidence that connects it to the change," is exactly what `ImpactPath` already
enforces structurally (it cannot be constructed without both). This module adds only what
`StorageImpactResult` does not carry: SS9's edge-kind and traversal-direction awareness, and
SS10's finer six-way impact categorization (`StorageImpactResult`'s own `direct_entity_ids`/
`possible_entity_ids` split is coarser -- a confidence classification, not a relationship-kind
one).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.graph.domain.models import StorageImpactResult
from atlas.modules.identity.domain.models import validate_stable_identifier


class EdgeKind(StrEnum):
    """SS9: "distinguishes configured, observed, inferred, and historical edges." Not a reuse of
    `graph.domain.models.AssertionMethod` (OBSERVED/CALCULATED/INFERRED/MANUAL) -- the two sets
    do not align: `CALCULATED` has no analog here, `HISTORICAL` (an edge no longer active) has no
    analog there, and `MANUAL` is a human declaration at read time rather than SS9's "configured"
    (a persisted vendor/system configuration state)."""

    CONFIGURED = "configured"
    OBSERVED = "observed"
    INFERRED = "inferred"
    HISTORICAL = "historical"


class TraversalDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BIDIRECTIONAL = "bidirectional"


class ImpactCategory(StrEnum):
    """SS10's six categories."""

    DIRECT = "direct"
    FIRST_ORDER = "first_order"
    TRANSITIVE = "transitive"
    SHARED_DEPENDENCY = "shared_dependency"
    OPERATIONAL = "operational"
    BUSINESS = "business"


@dataclass(frozen=True, slots=True)
class AffectedItemClassification:
    """Binds one entity from a `StorageImpactResult`'s already-evidenced impact paths to SS10's
    impact category and SS9's edge-kind metadata. Path and relationship evidence themselves stay
    on `StorageImpactResult.paths` -- never duplicated here."""

    entity_id: str
    impact_category: ImpactCategory
    edge_kinds: tuple[EdgeKind, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.entity_id, "entity_id")
        if not self.edge_kinds:
            raise ValueError("an affected item classification requires at least one edge kind")


def is_unbounded_reachability(entity_id: str, graph_impact: StorageImpactResult) -> bool:
    """SS10: "unbounded reachability is not labeled impact." An entity that the traversal reached
    but that carries neither a direct/possible classification nor evidenced path is unbounded
    reachability, not impact."""
    known = set(graph_impact.direct_entity_ids) | set(graph_impact.possible_entity_ids)
    if entity_id not in known:
        return True
    return not any(entity_id in path.entity_ids for path in graph_impact.paths)


@dataclass(frozen=True, slots=True)
class DependencyTraversalResult:
    traversal_id: str
    change_request_id: str
    graph_impact: StorageImpactResult
    direction: TraversalDirection
    classifications: tuple[AffectedItemClassification, ...]
    inaccessible_or_missing_subgraph_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.traversal_id, "traversal_id")
        validate_stable_identifier(self.change_request_id, "change_request_id")
        known_entity_ids = {entity.entity_id for entity in self.graph_impact.entities}
        seen: set[tuple[str, ImpactCategory]] = set()
        for classification in self.classifications:
            if classification.entity_id not in known_entity_ids:
                raise ValueError(
                    f"classification references unknown entity {classification.entity_id!r}"
                )
            if is_unbounded_reachability(classification.entity_id, self.graph_impact):
                raise ValueError(
                    f"{classification.entity_id!r} is unbounded reachability, not labeled "
                    "impact per SS10"
                )
            key = (classification.entity_id, classification.impact_category)
            if key in seen:
                raise ValueError(
                    f"duplicate classification for entity {classification.entity_id!r} in "
                    f"category {classification.impact_category.value!r}"
                )
            seen.add(key)
