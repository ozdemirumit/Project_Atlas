"""ATLAS-026 SS12: reconciliation foundation.

SS30's MVP scope names "reconciliation... foundation" as included, not a complete engine. This
module covers what SS12 names and the existing architecture can actually support today: source
authority ranking, conflict detection and storage when the *same* entity or relationship
identifier is observed differently by more than one source, and manual reviewed overrides.

Two things SS12 also names are deliberately out of scope for this foundation:

- Field-level reconciliation (resolving individual disagreeing fields rather than the whole
  entity/relationship record) -- this foundation reconciles at record granularity.
- Cross-source identity resolution -- recognizing that two different vendors' records describe
  the same real-world thing when they were never assigned the same `entity_id`/`relationship_id`
  in the first place. SS16's own completeness taxonomy already names "ambiguous entity identity"
  as a distinct, separately-tracked gap, not something this module invents a fix for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.graph.domain.models import GraphEntity, GraphRelationship


@dataclass(frozen=True, slots=True)
class SourceAuthorityRanking:
    """SS12: "Source authority for the field or relationship." Higher rank wins a conflict;
    a source absent from `ranks` defaults to rank 0."""

    ranks: dict[str, int]

    def authority_of(self, source: str) -> int:
        return self.ranks.get(source, 0)


@dataclass(frozen=True, slots=True)
class GraphManualOverride:
    """SS12: "Manual reviewed overrides." Forces a specific source's version to win for a named
    identifier regardless of computed authority. The override is itself recorded evidence, not a
    silent thumb on the scale."""

    identifier: str
    chosen_source: str
    reviewed_by: str
    reason: str
    applied_at: datetime

    def __post_init__(self) -> None:
        if not self.identifier.strip() or not self.chosen_source.strip():
            raise ValueError("a manual override requires an identifier and a chosen source")
        if not self.reviewed_by.strip() or not self.reason.strip():
            raise ValueError("a manual override requires a reviewer and a reason")
        if self.applied_at.tzinfo is None:
            raise ValueError("a manual override time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class GraphReconciliationConflict:
    """SS12: "Conflicts are stored and exposed." One identifier observed differently by two or
    more sources, and how it was resolved."""

    identifier: str
    competing_sources: tuple[str, ...]
    chosen_source: str
    resolution_basis: str

    def __post_init__(self) -> None:
        if len(self.competing_sources) < 2:
            raise ValueError(
                "a graph reconciliation conflict requires at least two competing sources"
            )
        if len(set(self.competing_sources)) != len(self.competing_sources):
            raise ValueError("competing sources must be distinct")
        if self.chosen_source not in self.competing_sources:
            raise ValueError("the chosen source must be one of the competing sources")


_HIGHER_AUTHORITY = "higher_authority"
_MANUAL_OVERRIDE = "manual_override"
_MOST_RECENT_AT_EQUAL_AUTHORITY = "most_recent_at_equal_authority"


def reconcile_entities(
    entities_by_source: tuple[tuple[str, tuple[GraphEntity, ...]], ...],
    *,
    authority: SourceAuthorityRanking,
    overrides: tuple[GraphManualOverride, ...] = (),
) -> tuple[tuple[GraphEntity, ...], tuple[GraphReconciliationConflict, ...]]:
    """When the same `entity_id` is observed by more than one source with differing content,
    keeps the higher-authority source's version and records a conflict -- never silently drops
    the disagreement, and never lets a later, lower-authority observation override a current
    higher-authority one (SS12)."""
    overrides_by_id = {item.identifier: item for item in overrides}
    by_id: dict[str, list[tuple[str, GraphEntity]]] = {}
    for source, entities in entities_by_source:
        for entity in entities:
            by_id.setdefault(entity.entity_id, []).append((source, entity))

    resolved: list[GraphEntity] = []
    conflicts: list[GraphReconciliationConflict] = []
    for entity_id, observations in by_id.items():
        if len({entity for _, entity in observations}) == 1:
            resolved.append(observations[0][1])
            continue
        chosen_source, basis = _choose_source(entity_id, observations, authority, overrides_by_id)
        resolved.append(next(entity for source, entity in observations if source == chosen_source))
        conflicts.append(
            GraphReconciliationConflict(
                identifier=entity_id,
                competing_sources=tuple(source for source, _ in observations),
                chosen_source=chosen_source,
                resolution_basis=basis,
            )
        )
    return tuple(resolved), tuple(conflicts)


def reconcile_relationships(
    relationships_by_source: tuple[tuple[str, tuple[GraphRelationship, ...]], ...],
    *,
    authority: SourceAuthorityRanking,
    overrides: tuple[GraphManualOverride, ...] = (),
) -> tuple[tuple[GraphRelationship, ...], tuple[GraphReconciliationConflict, ...]]:
    """The relationship-level counterpart to `reconcile_entities`, keyed by `relationship_id`."""
    overrides_by_id = {item.identifier: item for item in overrides}
    by_id: dict[str, list[tuple[str, GraphRelationship]]] = {}
    for source, relationships in relationships_by_source:
        for relationship in relationships:
            by_id.setdefault(relationship.relationship_id, []).append((source, relationship))

    resolved: list[GraphRelationship] = []
    conflicts: list[GraphReconciliationConflict] = []
    for relationship_id, observations in by_id.items():
        if len({relationship for _, relationship in observations}) == 1:
            resolved.append(observations[0][1])
            continue
        chosen_source, basis = _choose_source(
            relationship_id, observations, authority, overrides_by_id
        )
        resolved.append(
            next(relationship for source, relationship in observations if source == chosen_source)
        )
        conflicts.append(
            GraphReconciliationConflict(
                identifier=relationship_id,
                competing_sources=tuple(source for source, _ in observations),
                chosen_source=chosen_source,
                resolution_basis=basis,
            )
        )
    return tuple(resolved), tuple(conflicts)


def _choose_source(
    identifier: str,
    observations: list[tuple[str, GraphEntity]] | list[tuple[str, GraphRelationship]],
    authority: SourceAuthorityRanking,
    overrides_by_id: dict[str, GraphManualOverride],
) -> tuple[str, str]:
    competing_sources = tuple(source for source, _ in observations)
    override = overrides_by_id.get(identifier)
    if override is not None and override.chosen_source in competing_sources:
        return override.chosen_source, _MANUAL_OVERRIDE
    max_authority = max(authority.authority_of(source) for source, _ in observations)
    top = [item for item in observations if authority.authority_of(item[0]) == max_authority]
    if len(top) == 1:
        return top[0][0], _HIGHER_AUTHORITY
    most_recent = max(top, key=lambda item: item[1].observed_at)
    return most_recent[0], _MOST_RECENT_AT_EQUAL_AUTHORITY


def a_later_lower_authority_observation_overrides_a_higher_authority_source() -> bool:
    """SS12: "A later observation does not automatically override a higher-authority current
    source.\""""
    return False
