"""ATLAS-024 SS10/SS11: hypothesis model and evidence strength.

Reuses Reasoning's `QualityRating` (ATLAS-041 SS10, STRONG/ADEQUATE/WEAK/UNKNOWN) for evidence
strength ratings, since it is a generic rating scale rather than one tied to Reasoning's own
dimension names.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.quality import QualityRating


class DecisionConfidenceCategory(StrEnum):
    """SS12's four confidence categories -- distinct from Reasoning's five-category
    `ConfidenceCategory` (ATLAS-041 SS18: Insufficient/Low/Moderate/High/Confirmed). Decision
    Engine's own scale has no `CONFIRMED` category and uses `MEDIUM` rather than `MODERATE`;
    defined as its own enum rather than reusing Reasoning's, since the two scales genuinely
    differ -- matching this session's established practice for `EpistemicType` vs `ClaimType`."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class DecisionHypothesis:
    """SS10's nine declared elements."""

    hypothesis_id: str
    description: str
    causal_or_dependency_path: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    alternative_explanations: tuple[str, ...]
    validation_steps: tuple[str, ...]
    confidence_category: DecisionConfidenceCategory
    confidence_basis: str
    potential_impact_if_true: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.hypothesis_id, "hypothesis_id")
        if not self.description.strip():
            raise ValueError("a decision hypothesis requires a description")
        if not self.confidence_basis.strip():
            raise ValueError("a decision hypothesis requires a confidence basis")
        if not self.potential_impact_if_true.strip():
            raise ValueError("a decision hypothesis requires the potential impact if true")


def rank_hypotheses_without_hiding(
    hypotheses: tuple[DecisionHypothesis, ...],
    *,
    confidence_rank: dict[DecisionConfidenceCategory, int],
) -> tuple[DecisionHypothesis, ...]:
    """SS10: "hypotheses are ranked but never hidden solely because they have lower confidence.
    Material alternatives remain visible." Returns every input hypothesis, only reordered --
    `sorted` cannot drop elements, so nothing here can silently hide one."""
    return tuple(
        sorted(
            hypotheses,
            key=lambda hypothesis: confidence_rank[hypothesis.confidence_category],
            reverse=True,
        )
    )


class EvidenceStrengthDimension(StrEnum):
    """SS11's nine considered dimensions."""

    OBSERVATION_DIRECTNESS = "observation_directness"
    SOURCE_AUTHORITY_AND_INTEGRITY = "source_authority_and_integrity"
    PRODUCT_AND_VERSION_MATCH = "product_and_version_match"
    TARGET_AND_ENVIRONMENT_MATCH = "target_and_environment_match"
    FRESHNESS = "freshness"
    INDEPENDENT_CORROBORATION = "independent_corroboration"
    GRAPH_COMPLETENESS = "graph_completeness"
    DATA_QUALITY_WARNINGS = "data_quality_warnings"
    CONFLICT_AND_SUPERSESSION = "conflict_and_supersession"


@dataclass(frozen=True, slots=True)
class EvidenceStrengthAssessment:
    evidence_id: str
    dimension: EvidenceStrengthDimension
    rating: QualityRating
    note: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "evidence_id")
        if not self.note.strip():
            raise ValueError("an evidence strength assessment requires a note")


def model_rhetorical_certainty_affects_evidence_strength() -> bool:
    """SS11: "the model's rhetorical certainty does not affect evidence strength." Always
    `False`."""
    return False
