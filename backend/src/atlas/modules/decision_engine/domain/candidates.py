"""ATLAS-024 SS15: recommendation candidates.

This module's `RecommendationCandidateKind`/`DecisionRecommendationCandidate` are deliberately
not built on top of `recommendations.domain.models.RecommendationOption`: that module is a
specialized, richer downstream consumer of decision-support output (ATLAS-024's own dependency
note: "ATLAS-042 through ATLAS-044 refine RCA, recommendation, and change impact"), so the
dependency runs from `recommendations` toward `decision_engine`, not the reverse -- importing it
here would invert that direction. Reuses `atlas.core.capabilities.CapabilityClass` rather than a
new capability enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier


class RecommendationCandidateKind(StrEnum):
    """SS15's seven candidate kinds."""

    GATHER_ADDITIONAL_EVIDENCE = "gather_additional_evidence"
    VALIDATE_A_HYPOTHESIS = "validate_a_hypothesis"
    APPLY_NON_INVASIVE_WORKAROUND = "apply_non_invasive_workaround"
    PLAN_CONFIGURATION_OR_OPERATIONAL_CHANGE = "plan_configuration_or_operational_change"
    ESCALATE_TO_VENDOR_OR_ANOTHER_DOMAIN = "escalate_to_vendor_or_another_domain"
    MONITOR_AND_REEVALUATE = "monitor_and_reevaluate"
    NO_ACTION = "no_action"


@dataclass(frozen=True, slots=True)
class DecisionRecommendationCandidate:
    """SS15's "as applicable" elements. A `NO_ACTION` candidate cannot carry
    `service_interruption` or `required_approvals` -- there is no action to interrupt or
    approve, so SS15's "take no action when evidence does not justify one" is a real,
    structurally distinct shape rather than a candidate that merely says "no action" in prose
    while still carrying an approval requirement."""

    candidate_id: str
    kind: RecommendationCandidateKind
    evidence_ids: tuple[str, ...]
    rationale: str
    capability_class: CapabilityClass
    risk_summary: str | None
    impact_assessment_id: str | None
    duration_minimum_minutes: int | None
    duration_maximum_minutes: int | None
    service_interruption: str | None
    prerequisites: tuple[str, ...]
    required_approvals: tuple[str, ...]
    validation_criteria: tuple[str, ...]
    recovery_reference: str | None
    alternatives: tuple[str, ...]
    unknowns: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.candidate_id, "candidate_id")
        if not self.rationale.strip():
            raise ValueError("a recommendation candidate requires a rationale")
        if self.duration_minimum_minutes is not None and self.duration_minimum_minutes < 0:
            raise ValueError("duration_minimum_minutes must not be negative")
        if self.duration_maximum_minutes is not None and self.duration_maximum_minutes < 0:
            raise ValueError("duration_maximum_minutes must not be negative")
        if (
            self.duration_minimum_minutes is not None
            and self.duration_maximum_minutes is not None
            and self.duration_minimum_minutes > self.duration_maximum_minutes
        ):
            raise ValueError("duration_minimum_minutes must not exceed duration_maximum_minutes")
        if self.kind is RecommendationCandidateKind.NO_ACTION and (
            self.service_interruption is not None or self.required_approvals
        ):
            raise ValueError(
                "a NO_ACTION candidate cannot carry service_interruption or required_approvals"
                " -- there is no action to interrupt or approve"
            )
