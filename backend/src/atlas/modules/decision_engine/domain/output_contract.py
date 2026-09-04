"""ATLAS-024 SS18: output contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DecisionOutputContract:
    """SS18's fixed eleven-part structure, in order. `rollback_or_recovery` may be `None` --
    SS18 itself says "where relevant.\""""

    problem_or_request_summary: str
    current_assessment: str
    evidence_and_citations: tuple[str, ...]
    affected_components_and_services: tuple[str, ...]
    probable_causes_and_alternatives: tuple[str, ...]
    confidence_unknowns_assumptions_freshness: str
    recommended_steps: tuple[str, ...]
    risk_impact_duration_interruption: str
    preconditions_policy_and_approvals: tuple[str, ...]
    rollback_or_recovery: str | None
    verification_criteria: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.problem_or_request_summary.strip():
            raise ValueError("a decision output contract requires a problem or request summary")
        if not self.current_assessment.strip():
            raise ValueError("a decision output contract requires a current assessment")
        if not self.confidence_unknowns_assumptions_freshness.strip():
            raise ValueError(
                "a decision output contract requires confidence, unknowns, assumptions, and"
                " freshness"
            )
        if not self.risk_impact_duration_interruption.strip():
            raise ValueError(
                "a decision output contract requires risk, impact, duration, and interruption"
            )
        if not self.verification_criteria:
            raise ValueError(
                "a decision output contract requires at least one verification criterion"
            )
