"""ATLAS-041 SS10: evidence quality.

SS10: "a single aggregate quality score must not hide one critical weakness. For example,
authoritative vendor guidance can still be inapplicable to the installed version."
`EvidenceQualityAssessment` deliberately has no aggregate/overall score field -- only the
per-dimension breakdown -- so nothing in this type can even represent the thing SS10 forbids.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class QualityDimension(StrEnum):
    """SS10's nine separate quality dimensions."""

    AUTHORITY_AND_PROVENANCE = "authority_and_provenance"
    INTEGRITY_AND_COLLECTION_METHOD = "integrity_and_collection_method"
    TARGET_AND_VERSION_APPLICABILITY = "target_and_version_applicability"
    TEMPORAL_FRESHNESS_AND_COVERAGE = "temporal_freshness_and_coverage"
    COMPLETENESS_AND_RESOLUTION = "completeness_and_resolution"
    INDEPENDENCE = "independence"
    CONSISTENCY = "consistency"
    SOURCE_BIAS_OR_LIMITATIONS = "source_bias_or_limitations"
    ACCESS_AND_CLASSIFICATION_CONFIDENCE = "access_and_classification_confidence"


class QualityRating(StrEnum):
    STRONG = "strong"
    ADEQUATE = "adequate"
    WEAK = "weak"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class QualityDimensionAssessment:
    dimension: QualityDimension
    rating: QualityRating
    note: str

    def __post_init__(self) -> None:
        if not self.note.strip():
            raise ValueError("a quality dimension assessment requires a note")


@dataclass(frozen=True, slots=True)
class EvidenceQualityAssessment:
    evidence_id: str
    dimension_assessments: tuple[QualityDimensionAssessment, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "evidence_id")
        dimensions = tuple(assessment.dimension for assessment in self.dimension_assessments)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("an evidence quality assessment cannot rate the same dimension twice")

    @property
    def weakest_dimensions(self) -> tuple[QualityDimensionAssessment, ...]:
        """Surfaces every `WEAK`-rated dimension explicitly -- SS10's own worked example
        (authoritative vendor guidance that's still inapplicable to the installed version) is
        exactly one weak dimension among otherwise-strong ones, which this property is built to
        surface rather than average away."""
        return tuple(
            assessment
            for assessment in self.dimension_assessments
            if assessment.rating is QualityRating.WEAK
        )
