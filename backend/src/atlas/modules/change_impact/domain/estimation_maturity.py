"""ATLAS-044 SS19/SS20: estimation methods and digital twin/simulation maturity.

`DigitalTwinMaturityLevel` is ATLAS-044's own authoritative D0-D3 scale, not a drop-in reuse of
`runbook_engine.domain.dry_run.SimulationMaturityLevel` -- that docstring explicitly deferred to
"ATLAS-044 maturity levels" for this document to eventually define, but on building it the two
scales turn out to answer different questions: SS20's four levels classify what *kind* of
analysis was run (static rules, time-aware snapshot, validated simulation, calibrated twin), while
`SimulationMaturityLevel` classifies how strongly one already-run dry-run's own claim can be
trusted (unvalidated through production-observed). They are not interchangeable, so
`runbook_engine`'s already-shipped, tested scale is left as its own local stand-in rather than
retrofitted. `permitted_claim_for` gives SS20's "Atlas must not call graph traversal or LLM
prediction a validated digital twin" a structural home: the permitted claim text is derived from
the level, never independently assertable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EstimationMethod(StrEnum):
    """SS19's eight estimation methods."""

    DETERMINISTIC_GRAPH_TRAVERSAL_AND_RULE_EVALUATION = (
        "deterministic_graph_traversal_and_rule_evaluation"
    )
    DOMAIN_FORMULAS_AND_CAPACITY_MODELS = "domain_formulas_and_capacity_models"
    VENDOR_DOCUMENTED_BEHAVIOR_AND_TIMING = "vendor_documented_behavior_and_timing"
    APPROVED_RUNBOOK_STEP_TIMING = "approved_runbook_step_timing"
    COMPARABLE_REVIEWED_HISTORICAL_OUTCOMES = "comparable_reviewed_historical_outcomes"
    VALIDATED_LAB_MEASUREMENTS = "validated_lab_measurements"
    HUMAN_EXPERT_ESTIMATES_WITH_PROVENANCE = "human_expert_estimates_with_provenance"
    BOUNDED_AI_SYNTHESIS = "bounded_ai_synthesis"


@dataclass(frozen=True, slots=True)
class EstimateProvenance:
    """SS19: "every estimate declares method and evidence." `is_insufficient_for_consequential_
    approval` is derived, not a separately-settable flag, so it cannot drift from the facts it
    is computed from."""

    method: EstimationMethod
    evidence_references: tuple[str, ...]
    has_applicable_support: bool

    def __post_init__(self) -> None:
        if not self.evidence_references:
            raise ValueError("an estimate provenance requires at least one evidence reference")

    @property
    def is_insufficient_for_consequential_approval(self) -> bool:
        """SS19: "model-only estimates without applicable support are labeled insufficient for
        consequential approval.\""""
        return (
            self.method is EstimationMethod.BOUNDED_AI_SYNTHESIS and not self.has_applicable_support
        )


class DigitalTwinMaturityLevel(StrEnum):
    """SS20's four maturity levels."""

    D0 = "d0"
    D1 = "d1"
    D2 = "d2"
    D3 = "d3"


_PERMITTED_CLAIMS: dict[DigitalTwinMaturityLevel, str] = {
    DigitalTwinMaturityLevel.D0: "Potentially affected graph and rule-based risk",
    DigitalTwinMaturityLevel.D1: "Estimated impact under declared assumptions",
    DigitalTwinMaturityLevel.D2: "Simulated result within tested domain and model limits",
    DigitalTwinMaturityLevel.D3: "Comparative simulation with measured error and coverage",
}


def permitted_claim_for(level: DigitalTwinMaturityLevel) -> str:
    """SS20's table: each maturity level has exactly one permitted claim."""
    return _PERMITTED_CLAIMS[level]


@dataclass(frozen=True, slots=True)
class SimulationOutputRecord:
    """SS20: "simulation output records model version, parameters, validation coverage, and
    known error.\""""

    maturity_level: DigitalTwinMaturityLevel
    model_version: str
    parameters: tuple[tuple[str, str], ...]
    validation_coverage: str
    known_error: str

    def __post_init__(self) -> None:
        if not self.model_version.strip():
            raise ValueError("a simulation output record requires a model version")
        if not self.validation_coverage.strip():
            raise ValueError("a simulation output record requires validation coverage")
        if not self.known_error.strip():
            raise ValueError("a simulation output record requires known error")

    @property
    def permitted_claim(self) -> str:
        return permitted_claim_for(self.maturity_level)
