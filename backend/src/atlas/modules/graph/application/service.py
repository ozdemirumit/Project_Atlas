from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.graph.application.engine import (
    GraphAccessContext,
    GraphImpactError,
    InMemoryGraphImpactAnalyzer,
)
from atlas.modules.graph.application.ports import GraphSnapshotProvider
from atlas.modules.graph.domain.models import StorageImpactResult


@dataclass(frozen=True, slots=True)
class GraphReadContext:
    subject_id: str
    actor_type: str
    authentication_method: str
    assurance_level: str
    organization_id: str
    environment_id: str
    site_id: str
    resource_id: str
    role_ids: tuple[str, ...]
    group_ids: tuple[str, ...]
    correlation_id: str
    decision_id: str
    requested_at: datetime
    classification_ceiling: DataClassification = DataClassification.INTERNAL


class GraphImpactService:
    def __init__(
        self,
        *,
        provider: GraphSnapshotProvider,
        audit_sink: AuditSink,
        max_nodes: int = 100,
    ) -> None:
        self._provider = provider
        self._audit_sink = audit_sink
        self._max_nodes = max_nodes

    async def analyze_storage_impact(
        self, *, entity_id: str, max_depth: int, context: GraphReadContext
    ) -> StorageImpactResult:
        if context.resource_id != "resource.graph.storage-impact.synthetic":
            raise GraphImpactError(
                "graph_scope_mismatch", "The graph target is outside the authorized scope."
            )
        snapshot = await self._provider.get_snapshot()
        analyzer = InMemoryGraphImpactAnalyzer(snapshot=snapshot, max_nodes=self._max_nodes)
        result = analyzer.analyze(
            start_entity_id=entity_id,
            max_depth=max_depth,
            access=GraphAccessContext(
                organization_id=context.organization_id,
                environment_id=context.environment_id,
                site_id=context.site_id,
                principals=frozenset((context.subject_id, *context.role_ids, *context.group_ids)),
                classification_ceiling=context.classification_ceiling,
            ),
        )
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.graph.storage_impact.read",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id="graph.storage-impact.read",
                resource_type="resource.graph.storage-impact",
                scope_reference="/".join(
                    (
                        context.organization_id,
                        context.environment_id,
                        context.site_id,
                        context.resource_id,
                    )
                ),
                decision_id=context.decision_id,
                outcome="succeeded",
                result_code="graph_storage_impact_returned",
            )
        )
        return result
