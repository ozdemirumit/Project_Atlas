"""ATLAS-046 SS24: consistency and validation.

Covers what is checkable from the `Explanation` object itself: source-artifact version binding,
evidence-required claims left as gaps, and unsupported certainty language in the summary (reusing
`guardrails.output_guardrails.detect_unsupported_certainty_language`). Numeric/unit/target
consistency and policy/approval-state softening require the actual rendered text and the source
artifacts themselves -- a rendering-pipeline concern, a later slice's job, not this one's.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.explainability.domain.models import Explanation
from atlas.modules.guardrails.domain.output_guardrails import (
    detect_unsupported_certainty_language,
)
from atlas.modules.guardrails.domain.reasoning_guardrails import ClaimType

_EVIDENCE_REQUIRED_CLAIM_TYPES = frozenset(
    {ClaimType.FACT, ClaimType.CALCULATION, ClaimType.CORRELATION}
)


class ValidationOutcome(StrEnum):
    """SS24: "failed validation returns a safe incomplete state or routes to review.\""""

    VALID = "valid"
    SAFE_INCOMPLETE = "safe_incomplete"
    ROUTE_TO_REVIEW = "route_to_review"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    outcome: ValidationOutcome
    violations: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.outcome is ValidationOutcome.VALID


def validate_explanation(
    explanation: Explanation, *, current_source_artifact_versions: dict[str, str]
) -> ValidationResult:
    stale_or_missing_source: list[str] = []
    other_violations: list[str] = []

    for artifact_id, recorded_version in zip(
        explanation.source_artifact_ids, explanation.source_artifact_versions, strict=True
    ):
        current_version = current_source_artifact_versions.get(artifact_id)
        if current_version is None:
            stale_or_missing_source.append(f"source artifact {artifact_id} is no longer available")
        elif current_version != recorded_version:
            stale_or_missing_source.append(
                f"source artifact {artifact_id} has moved from version {recorded_version} to"
                f" {current_version}"
            )

    for claim in explanation.claims:
        if claim.is_evidence_gap and claim.claim_type in _EVIDENCE_REQUIRED_CLAIM_TYPES:
            other_violations.append(f"claim {claim.claim_id} has no supporting evidence")

    if detect_unsupported_certainty_language(explanation.summary):
        other_violations.append("summary contains unsupported certainty language")

    all_violations = tuple(stale_or_missing_source + other_violations)
    if not all_violations:
        return ValidationResult(outcome=ValidationOutcome.VALID, violations=())
    if stale_or_missing_source:
        # A source artifact moving or disappearing is unrecoverable without regenerating the
        # explanation entirely -- the safest available state is "incomplete," not a review queue
        # that implies a human could resolve it by looking harder at unchanged content.
        return ValidationResult(
            outcome=ValidationOutcome.SAFE_INCOMPLETE, violations=all_violations
        )
    return ValidationResult(outcome=ValidationOutcome.ROUTE_TO_REVIEW, violations=all_violations)
