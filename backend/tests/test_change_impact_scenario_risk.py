from __future__ import annotations

import pytest

from atlas.modules.change_impact.domain.scenario_risk import (
    RiskClassification,
    RiskLevel,
    Scenario,
    ScenarioKind,
)


def scenario(**overrides: object) -> Scenario:
    defaults: dict[str, object] = {
        "scenario_id": "scenario.expected",
        "kind": ScenarioKind.EXPECTED,
        "description": "Controller B fails over cleanly to controller A within 5 minutes.",
        "assumptions": ("Controller A is healthy at start.",),
        "confidence": "high",
    }
    defaults.update(overrides)
    return Scenario(**defaults)  # type: ignore[arg-type]


def risk(**overrides: object) -> RiskClassification:
    defaults: dict[str, object] = {
        "change_request_id": "change-request.example",
        "capability_class": "C2",
        "service_criticality_and_blast_radius_note": "One high-criticality service affected.",
        "interruption_mode_and_duration_note": "Performance degradation, 2-10 minutes.",
        "data_and_security_consequence_note": "No data or security consequence expected.",
        "starting_health_and_redundancy_note": "Both controllers healthy at start.",
        "reversibility_and_recovery_evidence_note": "Rollback available, tested 2026-08.",
        "plan_complexity_and_manual_dependency_note": "Single automated step, no manual work.",
        "evidence_freshness_and_graph_completeness_note": "Graph snapshot is 3 minutes old.",
        "risk_level": RiskLevel.MODERATE,
    }
    defaults.update(overrides)
    return RiskClassification(**defaults)  # type: ignore[arg-type]


def test_scenario_kind_has_six_members() -> None:
    assert len(ScenarioKind) == 6


def test_scenario_requires_at_least_one_assumption() -> None:
    with pytest.raises(ValueError, match="at least one assumption"):
        scenario(assumptions=())


def test_scenario_requires_confidence() -> None:
    with pytest.raises(ValueError, match="requires a confidence"):
        scenario(confidence="")


def test_risk_classification_accepts_valid_state() -> None:
    assert risk().risk_level is RiskLevel.MODERATE


def test_risk_classification_requires_capability_class() -> None:
    with pytest.raises(ValueError, match="ATLAS-003 capability class"):
        risk(capability_class="")


def test_risk_classification_requires_every_input_note() -> None:
    with pytest.raises(ValueError, match="evidence_freshness_and_graph_completeness_note"):
        risk(evidence_freshness_and_graph_completeness_note="")
