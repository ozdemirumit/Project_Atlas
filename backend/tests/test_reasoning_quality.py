from __future__ import annotations

import pytest

from atlas.modules.reasoning.domain.quality import (
    EvidenceQualityAssessment,
    QualityDimension,
    QualityDimensionAssessment,
    QualityRating,
)


def dimension_assessment(**overrides: object) -> QualityDimensionAssessment:
    defaults: dict[str, object] = {
        "dimension": QualityDimension.AUTHORITY_AND_PROVENANCE,
        "rating": QualityRating.STRONG,
        "note": "Directly observed via a governed connector.",
    }
    defaults.update(overrides)
    return QualityDimensionAssessment(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_dimension_assessment_constructs_cleanly() -> None:
    example = dimension_assessment()
    assert example.rating is QualityRating.STRONG


def test_dimension_assessment_requires_a_note() -> None:
    with pytest.raises(ValueError, match="requires a note"):
        dimension_assessment(note="   ")


def assessment(**overrides: object) -> EvidenceQualityAssessment:
    defaults: dict[str, object] = {
        "evidence_id": "evidence.example",
        "dimension_assessments": (dimension_assessment(),),
    }
    defaults.update(overrides)
    return EvidenceQualityAssessment(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_assessment_constructs_cleanly() -> None:
    example = assessment()
    assert len(example.dimension_assessments) == 1


def test_assessment_rejects_duplicate_dimensions() -> None:
    duplicated = (
        dimension_assessment(),
        dimension_assessment(rating=QualityRating.WEAK, note="Second, conflicting rating."),
    )
    with pytest.raises(ValueError, match="cannot rate the same dimension twice"):
        assessment(dimension_assessments=duplicated)


def test_assessment_may_be_partial() -> None:
    example = assessment(dimension_assessments=())
    assert example.dimension_assessments == ()


def test_weakest_dimensions_surfaces_only_weak_ratings() -> None:
    assessments = (
        dimension_assessment(
            dimension=QualityDimension.AUTHORITY_AND_PROVENANCE,
            rating=QualityRating.STRONG,
            note="Directly observed via a governed connector.",
        ),
        dimension_assessment(
            dimension=QualityDimension.TARGET_AND_VERSION_APPLICABILITY,
            rating=QualityRating.WEAK,
            note="Vendor guidance predates the installed firmware version.",
        ),
    )
    example = assessment(dimension_assessments=assessments)
    assert len(example.weakest_dimensions) == 1
    assert (
        example.weakest_dimensions[0].dimension is QualityDimension.TARGET_AND_VERSION_APPLICABILITY
    )


def test_weakest_dimensions_empty_when_nothing_is_weak() -> None:
    example = assessment()
    assert example.weakest_dimensions == ()


def test_a_single_strong_dimension_does_not_hide_a_weak_one() -> None:
    """SS10's own worked example: authoritative vendor guidance can still be inapplicable to the
    installed version -- one weak dimension must surface even alongside a strong one."""
    assessments = (
        dimension_assessment(
            dimension=QualityDimension.AUTHORITY_AND_PROVENANCE,
            rating=QualityRating.STRONG,
            note="Authoritative vendor documentation.",
        ),
        dimension_assessment(
            dimension=QualityDimension.TARGET_AND_VERSION_APPLICABILITY,
            rating=QualityRating.WEAK,
            note="Documentation targets a different firmware version than what is installed.",
        ),
    )
    example = assessment(dimension_assessments=assessments)
    assert len(example.weakest_dimensions) == 1
