"""ATLAS-024 SS14: impact assessment.

Reuses `graph.domain.models.StorageImpactResult` directly for SS14's core requirements -- current
inventory and graph relationships, relationship freshness, technical/business service mapping,
and affected/possibly-affected/unknown scope with explicit incomplete-graph-data -- rather than a
parallel impact shape. This module adds only what `StorageImpactResult` does not already carry:
the target capability being assessed, redundancy/path/cluster/protection state where modeled,
current health/maintenance context, and historical outcome evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.graph.domain.models import StorageImpactResult
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class ProtectionStateSummary:
    """SS14: "redundancy, path, cluster, and protection state where modeled." Every field is
    optional -- "where modeled" means this state may simply not exist for a given target."""

    redundancy_state: str | None
    path_state: str | None
    cluster_state: str | None
    protection_state: str | None


@dataclass(frozen=True, slots=True)
class DecisionImpactAssessment:
    assessment_id: str
    target_id: str
    target_capability_id: str | None
    graph_impact: StorageImpactResult
    protection_state: ProtectionStateSummary
    current_health_summary: str
    maintenance_context: str | None
    historical_outcome_evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.assessment_id, "assessment_id")
        validate_stable_identifier(self.target_id, "target_id")
        if not self.current_health_summary.strip():
            raise ValueError("a decision impact assessment requires a current health summary")


def has_incomplete_graph_data(assessment: DecisionImpactAssessment) -> bool:
    """SS14: "incomplete graph data is explicit." Reuses `StorageImpactResult.unknowns` rather
    than a second incompleteness signal."""
    return bool(assessment.graph_impact.unknowns)
