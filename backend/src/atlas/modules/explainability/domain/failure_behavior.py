"""ATLAS-046 SS27: failure behavior.

Composes what earlier slices already built -- `validate_explanation` (SS24, slice 4) for missing
citations and source-version conflicts, `Explanation.is_stale` (SS14, slice 1) for staleness --
into SS27's failure rules, rather than re-deriving detection logic a second time.

Slice 4's `ValidationOutcome.SAFE_INCOMPLETE` is triggered by a stale-or-missing source-artifact
*version* binding, which folds SS27's "conflicting source versions produce a conflict
explanation" together with an unavailable source into one outcome; this module maps both to
`CONFLICT_EXPLANATION` since neither can be silently smoothed over into current language, and
states that imprecision here rather than inventing a third outcome slice 4 does not actually
distinguish. `ROUTE_TO_REVIEW` (evidence-gap claims or unsupported-certainty language) maps to
`BLOCKED`, matching "missing citations ... block material unsupported claims."

SS27's "explanation failure never changes a deny to allow" is enforced by the absence of a code
path everywhere else in this module (nothing here accepts or derives a `PolicyDecisionOutcome`),
and `apply_explanation_failure_to_policy_outcome` gives that absence a concrete, testable call
site: it always returns its input outcome unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.explainability.domain.models import Explanation
from atlas.modules.explainability.domain.validation import ValidationOutcome, ValidationResult
from atlas.modules.policy_engine.domain.models import PolicyDecisionOutcome


class ExplanationReadiness(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    CONFLICT_EXPLANATION = "conflict_explanation"


_READINESS_FOR_VALIDATION_OUTCOME: dict[ValidationOutcome, ExplanationReadiness] = {
    ValidationOutcome.VALID: ExplanationReadiness.READY,
    ValidationOutcome.SAFE_INCOMPLETE: ExplanationReadiness.CONFLICT_EXPLANATION,
    ValidationOutcome.ROUTE_TO_REVIEW: ExplanationReadiness.BLOCKED,
}


@dataclass(frozen=True, slots=True)
class RestrictedEvidenceDisclosure:
    """SS27: "unauthorized evidence is omitted with a safe disclosure that relevant restricted
    context may exist when policy permits.\""""

    omitted_count: int
    disclosure: str

    def __post_init__(self) -> None:
        if self.omitted_count < 0:
            raise ValueError("omitted_count must not be negative")
        if self.omitted_count > 0 and not self.disclosure.strip():
            raise ValueError("omitted restricted evidence requires a safe disclosure statement")
        if self.omitted_count == 0 and self.disclosure.strip():
            raise ValueError(
                "a disclosure statement is only meaningful when evidence was actually omitted"
            )


@dataclass(frozen=True, slots=True)
class ExplanationReadinessAssessment:
    readiness: ExplanationReadiness
    is_stale: bool
    renderer_fallback_required: bool
    restricted_evidence_disclosure: RestrictedEvidenceDisclosure
    blocks_consequential_approval_readiness: bool


def assess_explanation_readiness(
    explanation: Explanation,
    *,
    validation: ValidationResult,
    restricted_evidence_disclosure: RestrictedEvidenceDisclosure,
    renderer_failed: bool,
    at: datetime,
    is_consequential: bool,
) -> ExplanationReadinessAssessment:
    """SS27: "inability to produce a complete explanation blocks consequential approval readiness
    where required" -- `blocks_consequential_approval_readiness` is only ever True when the
    caller has already determined the underlying recommendation is consequential."""
    readiness = _READINESS_FOR_VALIDATION_OUTCOME[validation.outcome]
    return ExplanationReadinessAssessment(
        readiness=readiness,
        is_stale=explanation.is_stale(at=at),
        renderer_fallback_required=renderer_failed,
        restricted_evidence_disclosure=restricted_evidence_disclosure,
        blocks_consequential_approval_readiness=(
            is_consequential and readiness is not ExplanationReadiness.READY
        ),
    )


def apply_explanation_failure_to_policy_outcome(
    outcome: PolicyDecisionOutcome, *, assessment: ExplanationReadinessAssessment
) -> PolicyDecisionOutcome:
    """SS27: "explanation failure never changes a deny to allow." Always returns `outcome`
    unchanged -- an explanation failure can affect whether an explanation is ready to present,
    never the policy decision it explains."""
    return outcome
