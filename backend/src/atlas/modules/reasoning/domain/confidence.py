"""ATLAS-041 SS18/SS19: confidence representation and updating.

Reuses this module's own `ConfidenceCategory` (slice 2, SS18's five categories) rather than a
second scale. "Human correction creates a new reasoning version" is deferred to the reasoning
artifact slice (SS22) -- that is where versioning is a real, modeled concept; nothing here would
have anything to version yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.claims import ConfidenceCategory


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    """SS18: "every category includes supporting factors, reducing factors, important unknowns,
    and what evidence could change it." "Numeric scores are used only after calibration against
    domain datasets and are displayed with their interpretation" -- `numeric_score` can be
    present if and only if `numeric_score_calibration_reference` is too."""

    category: ConfidenceCategory
    supporting_factors: tuple[str, ...]
    reducing_factors: tuple[str, ...]
    important_unknowns: tuple[str, ...]
    what_would_change_it: str
    numeric_score: float | None
    numeric_score_calibration_reference: str | None

    def __post_init__(self) -> None:
        if not self.supporting_factors:
            raise ValueError("a confidence assessment requires at least one supporting factor")
        if not self.what_would_change_it.strip():
            raise ValueError("a confidence assessment requires a statement of what would change it")
        if self.numeric_score is not None:
            if not 0.0 <= self.numeric_score <= 1.0:
                raise ValueError("numeric_score must be within [0.0, 1.0]")
            if self.numeric_score_calibration_reference is None:
                raise ValueError(
                    "SS18: numeric scores are used only after calibration against domain"
                    " datasets -- a numeric_score requires numeric_score_calibration_reference"
                )
        if self.numeric_score is None and self.numeric_score_calibration_reference is not None:
            raise ValueError(
                "numeric_score_calibration_reference is only meaningful alongside a numeric_score"
            )


def is_independent_support(
    *, evidence_id: str, already_counted_evidence_ids: frozenset[str], derivative_of: str | None
) -> bool:
    """SS19: "duplicate or derivative evidence is not counted as independent support.\""""
    if derivative_of is not None:
        return False
    return evidence_id not in already_counted_evidence_ids


def support_weight_for(*, is_fresh: bool, is_applicable: bool) -> float:
    """SS19: "stale or inapplicable evidence reduces support." Full weight only when both fresh
    and applicable; halved for each condition that fails."""
    weight = 1.0
    if not is_fresh:
        weight *= 0.5
    if not is_applicable:
        weight *= 0.5
    return weight


@dataclass(frozen=True, slots=True)
class ContradictionRecord:
    """SS19: "contradictory authoritative evidence is surfaced and cannot be averaged away."
    Deliberately has no averaged/reconciled-confidence field -- only the two contradicting sides
    preserved separately -- so nothing in this type can represent the forbidden average."""

    evidence_id_a: str
    evidence_id_b: str
    description: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id_a, "evidence_id_a")
        validate_stable_identifier(self.evidence_id_b, "evidence_id_b")
        if self.evidence_id_a == self.evidence_id_b:
            raise ValueError("a contradiction requires two distinct evidence units")
        if not self.description.strip():
            raise ValueError("a contradiction record requires a description")


def approval_can_increase_confidence() -> bool:
    """SS19: "confidence never increases because an action was approved." Always `False`."""
    return False


def absence_of_alert_is_evidence(
    *, alert_coverage_known: bool, alert_system_health_known: bool
) -> bool:
    """SS19: "lack of an alert is evidence only when alert coverage and health are known.\""""
    return alert_coverage_known and alert_system_health_known
