"""ATLAS-024 SS13: conflict handling.

Reuses Reasoning's `EvidenceConflictRecord`/`ConflictingEvidenceSide` (ATLAS-041 SS20) directly --
both preserve each side without ever naming a winner, exactly SS13's "prefer no silent winner
when applicability cannot be resolved" and "preserve conflicting evidence references." This
module adds only what SS13 asks for beyond that: a conflict-kind classification and the resulting
confidence/validation consequences of an unresolved conflict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.decision_engine.domain.hypotheses import DecisionConfidenceCategory
from atlas.modules.reasoning.domain.evidence_gaps import EvidenceConflictRecord

_REDUCED_CONFIDENCE_CATEGORIES = frozenset(
    {DecisionConfidenceCategory.LOW, DecisionConfidenceCategory.INSUFFICIENT}
)


class ConflictKind(StrEnum):
    """SS13: "identify whether conflict concerns time, product version, target, source
    authority, or interpretation.\""""

    TIME = "time"
    PRODUCT_VERSION = "product_version"
    TARGET = "target"
    SOURCE_AUTHORITY = "source_authority"
    INTERPRETATION = "interpretation"


@dataclass(frozen=True, slots=True)
class DecisionConflict:
    conflict: EvidenceConflictRecord
    kind: ConflictKind
    resulting_confidence_category: DecisionConfidenceCategory
    recommended_discriminating_validation_step: str

    def __post_init__(self) -> None:
        if not self.recommended_discriminating_validation_step.strip():
            raise ValueError(
                "SS13: a decision conflict requires a recommended discriminating validation step"
            )
        if self.resulting_confidence_category not in _REDUCED_CONFIDENCE_CATEGORIES:
            raise ValueError(
                "SS13: an unresolved conflict reduces confidence or returns insufficient"
                " evidence -- resulting_confidence_category must be LOW or INSUFFICIENT"
            )


def can_summarize_conflict_as_consensus() -> bool:
    """SS13: "prevent conflicting evidence from being summarized into false consensus." Always
    `False`."""
    return False
