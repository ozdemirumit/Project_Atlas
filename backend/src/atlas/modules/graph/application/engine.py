from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from atlas.core.classification import DataClassification
from atlas.modules.graph.domain.models import (
    EntityType,
    GraphEntity,
    GraphRelationship,
    GraphSnapshot,
    ImpactPath,
    ImpactScope,
    StorageImpactResult,
)


@dataclass(frozen=True, slots=True)
class GraphAccessContext:
    organization_id: str
    environment_id: str
    site_id: str
    principals: frozenset[str]
    classification_ceiling: DataClassification


class GraphImpactError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class InMemoryGraphImpactAnalyzer:
    def __init__(self, *, snapshot: GraphSnapshot, max_nodes: int = 100) -> None:
        self._snapshot = snapshot
        self._max_nodes = max_nodes

    def analyze(
        self,
        *,
        start_entity_id: str,
        access: GraphAccessContext,
        max_depth: int,
    ) -> StorageImpactResult:
        if max_depth < 1 or max_depth > 5:
            raise GraphImpactError(
                "graph_depth_out_of_range", "Graph depth must be between 1 and 5."
            )

        entities = {
            item.entity_id: item
            for item in self._snapshot.entities
            if self._entity_visible(item, access)
        }
        relationships = {
            item.relationship_id: item
            for item in self._snapshot.relationships
            if self._relationship_visible(item, entities, access)
        }
        start = entities.get(start_entity_id)
        if start is None or start.entity_type is not EntityType.STORAGE_SYSTEM:
            raise GraphImpactError(
                "graph_target_unavailable",
                "The requested graph target is unavailable in the authorized scope.",
            )

        incoming: dict[str, list[GraphRelationship]] = {}
        for relationship in relationships.values():
            incoming.setdefault(relationship.target_entity_id, []).append(relationship)
        for values in incoming.values():
            values.sort(key=lambda item: item.relationship_id)

        queue: deque[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], int]] = deque(
            [(start_entity_id, (start_entity_id,), (), (), 0)]
        )
        visited = {start_entity_id}
        paths: list[ImpactPath] = []
        used_relationship_ids: set[str] = set()
        direct_ids: list[str] = []
        possible_ids: list[str] = []

        while queue:
            current_id, entity_path, relationship_path, evidence_path, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for relationship in incoming.get(current_id, []):
                dependent_id = relationship.source_entity_id
                if dependent_id in visited:
                    continue
                if len(visited) >= self._max_nodes:
                    raise GraphImpactError(
                        "graph_query_limit_reached",
                        "The bounded graph query reached its authorized node limit.",
                    )
                visited.add(dependent_id)
                next_depth = depth + 1
                next_entity_path = (*entity_path, dependent_id)
                next_relationship_path = (*relationship_path, relationship.relationship_id)
                next_evidence_path = tuple(
                    dict.fromkeys((*evidence_path, *relationship.evidence_references))
                )
                scope = ImpactScope.DIRECT if next_depth == 1 else ImpactScope.POSSIBLE
                paths.append(
                    ImpactPath(
                        scope=scope,
                        entity_ids=next_entity_path,
                        relationship_ids=next_relationship_path,
                        evidence_references=next_evidence_path,
                    )
                )
                used_relationship_ids.update(next_relationship_path)
                if scope is ImpactScope.DIRECT:
                    direct_ids.append(dependent_id)
                else:
                    possible_ids.append(dependent_id)
                queue.append(
                    (
                        dependent_id,
                        next_entity_path,
                        next_relationship_path,
                        next_evidence_path,
                        next_depth,
                    )
                )

        returned_entity_ids = {entity_id for path in paths for entity_id in path.entity_ids}
        returned_entity_ids.add(start_entity_id)
        returned_entities = tuple(
            entity for entity_id, entity in entities.items() if entity_id in returned_entity_ids
        )
        returned_relationships = tuple(
            relationship
            for relationship_id, relationship in relationships.items()
            if relationship_id in used_relationship_ids
        )
        evidence_refs = {
            reference for entity in returned_entities for reference in entity.evidence_references
        } | {reference for path in paths for reference in path.evidence_references}
        returned_evidence = tuple(
            record
            for record in self._snapshot.evidence
            if record.reference in evidence_refs
            and access.classification_ceiling.permits(record.classification)
        )

        self._validate_output(
            access=access,
            entities=returned_entities,
            relationships=returned_relationships,
        )
        return StorageImpactResult(
            snapshot_id=self._snapshot.snapshot_id,
            snapshot_generated_at=self._snapshot.generated_at,
            start_entity_id=start_entity_id,
            max_depth=max_depth,
            freshness=self._snapshot.freshness,
            completeness=self._snapshot.completeness,
            entities=returned_entities,
            relationships=returned_relationships,
            paths=tuple(paths),
            evidence=returned_evidence,
            direct_entity_ids=tuple(direct_ids),
            possible_entity_ids=tuple(possible_ids),
            technical_service_ids=tuple(
                item.entity_id
                for item in returned_entities
                if item.entity_type is EntityType.TECHNICAL_SERVICE
            ),
            business_service_ids=tuple(
                item.entity_id
                for item in returned_entities
                if item.entity_type is EntityType.BUSINESS_SERVICE
            ),
            unknowns=(
                "Redundancy and failover state are not observed in this graph snapshot.",
                "Reachability does not establish that any downstream service is unavailable.",
            ),
            known_gaps=self._snapshot.known_gaps,
            outage_confirmed=False,
            digital_twin_maturity="D0-D1 dependency analysis",
            data_profile=self._snapshot.data_profile,
            safety_notice=(
                "Decision support only. Dependencies indicate possible impact, not an outage "
                "or authorization to change infrastructure."
            ),
        )

    @staticmethod
    def _entity_visible(item: GraphEntity, access: GraphAccessContext) -> bool:
        return (
            item.organization_id == access.organization_id
            and item.environment_id == access.environment_id
            and item.site_id == access.site_id
            and access.classification_ceiling.permits(item.classification)
            and bool(item.allowed_principals & access.principals)
        )

    @staticmethod
    def _relationship_visible(
        item: GraphRelationship,
        entities: dict[str, GraphEntity],
        access: GraphAccessContext,
    ) -> bool:
        return (
            item.source_entity_id in entities
            and item.target_entity_id in entities
            and access.classification_ceiling.permits(item.classification)
            and bool(item.allowed_principals & access.principals)
        )

    def _validate_output(
        self,
        *,
        access: GraphAccessContext,
        entities: tuple[GraphEntity, ...],
        relationships: tuple[GraphRelationship, ...],
    ) -> None:
        visible_ids = {item.entity_id for item in entities}
        if any(not self._entity_visible(item, access) for item in entities):
            raise GraphImpactError("graph_output_denied", "Graph output policy validation failed.")
        if any(
            not self._relationship_visible(item, {e.entity_id: e for e in entities}, access)
            or item.source_entity_id not in visible_ids
            or item.target_entity_id not in visible_ids
            for item in relationships
        ):
            raise GraphImpactError("graph_output_denied", "Graph output policy validation failed.")
