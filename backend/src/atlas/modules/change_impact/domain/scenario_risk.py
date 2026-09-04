"""ATLAS-044 SS17/SS18: scenario model and risk classification.

`RiskClassification` builds its own `RiskLevel` scale rather than reusing
`decision_engine.domain.hypotheses.DecisionConfidenceCategory` or
`reasoning.domain.claims.ConfidenceCategory` -- both rate confidence in a claim, while SS18 rates
the risk of the change itself, incorporating dimensions (capability class, blast radius,
reversibility) that have nothing to do with evidence confidence. `RiskClassification.evidence_
freshness_and_completeness_note` and `graph_completeness_note` exist because SS18 explicitly lists
"evidence freshness and graph completeness" as inputs to risk, not just to confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ScenarioKind(StrEnum):
    """SS17's six scenario kinds."""

    EXPECTED = "expected"
    DEGRADED_STARTING = "degraded_starting"
    IMPLEMENTATION_FAILURE = "implementation_failure"
    FAILOVER_OR_RECOVERY_FAILURE = "failover_or_recovery_failure"
    CONCURRENT_EVENT = "concurrent_event"
    NO_CHANGE = "no_change"


@dataclass(frozen=True, slots=True)
class Scenario:
    """SS17: "scenarios are bounded to plausible, decision-relevant conditions and carry
    separate assumptions and confidence.\""""

    scenario_id: str
    kind: ScenarioKind
    description: str
    assumptions: tuple[str, ...]
    confidence: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.scenario_id, "scenario_id")
        if not self.description.strip():
            raise ValueError("a scenario requires a description")
        if not self.assumptions:
            raise ValueError("a scenario requires at least one assumption")
        if not self.confidence.strip():
            raise ValueError("a scenario requires a confidence")


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


@dataclass(frozen=True, slots=True)
class RiskClassification:
    """SS18's eight risk inputs."""

    change_request_id: str
    capability_class: str
    service_criticality_and_blast_radius_note: str
    interruption_mode_and_duration_note: str
    data_and_security_consequence_note: str
    starting_health_and_redundancy_note: str
    reversibility_and_recovery_evidence_note: str
    plan_complexity_and_manual_dependency_note: str
    evidence_freshness_and_graph_completeness_note: str
    risk_level: RiskLevel

    def __post_init__(self) -> None:
        validate_stable_identifier(self.change_request_id, "change_request_id")
        if not self.capability_class.strip():
            raise ValueError("a risk classification requires an ATLAS-003 capability class")
        for field_name, value in (
            (
                "service_criticality_and_blast_radius_note",
                self.service_criticality_and_blast_radius_note,
            ),
            ("interruption_mode_and_duration_note", self.interruption_mode_and_duration_note),
            ("data_and_security_consequence_note", self.data_and_security_consequence_note),
            ("starting_health_and_redundancy_note", self.starting_health_and_redundancy_note),
            (
                "reversibility_and_recovery_evidence_note",
                self.reversibility_and_recovery_evidence_note,
            ),
            (
                "plan_complexity_and_manual_dependency_note",
                self.plan_complexity_and_manual_dependency_note,
            ),
            (
                "evidence_freshness_and_graph_completeness_note",
                self.evidence_freshness_and_graph_completeness_note,
            ),
        ):
            if not value.strip():
                raise ValueError(f"a risk classification requires {field_name}")
