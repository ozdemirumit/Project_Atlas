from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.decision_engine.domain.impact import (
    DecisionImpactAssessment,
    ProtectionStateSummary,
    has_incomplete_graph_data,
)
from atlas.modules.graph.domain.models import FreshnessState, StorageImpactResult

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def graph_impact(**overrides: object) -> StorageImpactResult:
    defaults: dict[str, object] = {
        "snapshot_id": "graph-snapshot.example",
        "snapshot_generated_at": NOW,
        "start_entity_id": "target.example",
        "max_depth": 3,
        "freshness": FreshnessState.FRESH,
        "completeness": "complete",
        "entities": (),
        "relationships": (),
        "paths": (),
        "evidence": (),
        "direct_entity_ids": ("target.example",),
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


def protection_state(**overrides: object) -> ProtectionStateSummary:
    defaults: dict[str, object] = {
        "redundancy_state": "redundant",
        "path_state": "healthy",
        "cluster_state": None,
        "protection_state": None,
    }
    defaults.update(overrides)
    return ProtectionStateSummary(**defaults)  # type: ignore[arg-type]


def assessment(**overrides: object) -> DecisionImpactAssessment:
    defaults: dict[str, object] = {
        "assessment_id": "decision-impact-assessment.example",
        "target_id": "target.example",
        "target_capability_id": "capability.storage.controller.restart",
        "graph_impact": graph_impact(),
        "protection_state": protection_state(),
        "current_health_summary": "Controller B reports degraded, controller A healthy.",
        "maintenance_context": None,
        "historical_outcome_evidence_ids": (),
    }
    defaults.update(overrides)
    return DecisionImpactAssessment(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_assessment_constructs_cleanly() -> None:
    example = assessment()
    assert example.target_id == "target.example"


def test_rejects_blank_current_health_summary() -> None:
    with pytest.raises(ValueError, match="current health summary"):
        assessment(current_health_summary="   ")


def test_target_capability_id_may_be_none() -> None:
    example = assessment(target_capability_id=None)
    assert example.target_capability_id is None


def test_protection_state_fields_are_all_optional() -> None:
    example = ProtectionStateSummary(
        redundancy_state=None, path_state=None, cluster_state=None, protection_state=None
    )
    assert example.redundancy_state is None


def test_has_incomplete_graph_data_false_when_no_unknowns() -> None:
    example = assessment(graph_impact=graph_impact(unknowns=()))
    assert has_incomplete_graph_data(example) is False


def test_has_incomplete_graph_data_true_when_unknowns_present() -> None:
    example = assessment(
        graph_impact=graph_impact(unknowns=("Redundant path state is not modeled.",))
    )
    assert has_incomplete_graph_data(example) is True


def test_assessment_carries_the_full_graph_impact_scope() -> None:
    example = assessment()
    assert example.graph_impact.direct_entity_ids == ("target.example",)
    assert example.graph_impact.technical_service_ids == ("service.file-shares",)
