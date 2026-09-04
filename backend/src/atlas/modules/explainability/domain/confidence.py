"""ATLAS-046 SS12: confidence and uncertainty language.

Reuses `guardrails.reasoning_guardrails.ConfidenceLevel` rather than a second confidence scale.
`ConfidenceExplanation.__post_init__` gives SS12's ""confirmed" is used only when domain criteria
are met" real teeth: `is_confirmed` cannot be True unless `domain_criteria_met` is also True.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from atlas.modules.guardrails.domain.reasoning_guardrails import ConfidenceLevel

_FORBIDDEN_WORDS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bcertain\b"),
    re.compile(r"(?i)\bguaranteed\b"),
    re.compile(r"(?i)\bsafe\b"),
    re.compile(r"(?i)\bno impact\b"),
)

_PERCENTAGE_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d+)?\s*%")


def detect_forbidden_confidence_language(text: str) -> tuple[str, ...]:
    """SS12: "Atlas avoids unsupported percentages and words such as certain, guaranteed, safe,
    or no impact." Every percentage is flagged unconditionally -- this function has no way to
    tell a genuinely supported percentage (a real `ClaimType.CALCULATION`) from a fabricated one,
    so it surfaces all of them and leaves that distinction to the caller."""
    found = [pattern.pattern for pattern in _FORBIDDEN_WORDS if pattern.search(text)]
    if _PERCENTAGE_PATTERN.search(text):
        found.append(_PERCENTAGE_PATTERN.pattern)
    return tuple(found)


@dataclass(frozen=True, slots=True)
class ConfidenceExplanation:
    """SS12's six required elements."""

    category: ConfidenceLevel
    category_definition: str
    supporting_factors: tuple[str, ...]
    limiting_factors: tuple[str, ...]
    remaining_alternatives: tuple[str, ...]
    missing_or_conflicting_evidence: tuple[str, ...]
    what_would_change_the_category: str
    is_confirmed: bool
    domain_criteria_met: bool

    def __post_init__(self) -> None:
        if not self.category_definition.strip():
            raise ValueError("a confidence explanation requires a category definition")
        if not self.supporting_factors:
            raise ValueError("a confidence explanation requires at least one supporting factor")
        if not self.what_would_change_the_category.strip():
            raise ValueError(
                "a confidence explanation requires a statement of what would change the category"
            )
        if self.is_confirmed and not self.domain_criteria_met:
            raise ValueError(
                '"confirmed" can only be used when domain criteria are explicitly met (SS12)'
            )
