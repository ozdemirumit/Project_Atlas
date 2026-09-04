from __future__ import annotations

import pytest

from atlas.modules.change_impact.domain.dimensions import (
    ImpactDimension,
    ImpactDimensionAssessment,
    ImpactSeverity,
    highest_material_dimensions,
)


def assessment(**overrides: object) -> ImpactDimensionAssessment:
    defaults: dict[str, object] = {
        "dimension": ImpactDimension.AVAILABILITY,
        "severity": ImpactSeverity.MODERATE,
        "rationale": "Controller B failover causes a brief path interruption.",
        "affected_entity_ids": ("entity.controller-b",),
    }
    defaults.update(overrides)
    return ImpactDimensionAssessment(**defaults)  # type: ignore[arg-type]


def test_impact_dimension_has_ten_members() -> None:
    assert len(ImpactDimension) == 10


def test_assessment_requires_rationale() -> None:
    with pytest.raises(ValueError, match="rationale"):
        assessment(rationale="")


def test_highest_material_dimensions_excludes_none_severity() -> None:
    assessments = (assessment(severity=ImpactSeverity.NONE),)
    assert highest_material_dimensions(assessments) == ()


def test_highest_material_dimensions_keeps_only_the_highest() -> None:
    low = assessment(dimension=ImpactDimension.PERFORMANCE, severity=ImpactSeverity.LOW)
    high = assessment(dimension=ImpactDimension.REDUNDANCY, severity=ImpactSeverity.HIGH)
    result = highest_material_dimensions((low, high))
    assert result == (high,)


def test_highest_material_dimensions_keeps_ties() -> None:
    first = assessment(dimension=ImpactDimension.REDUNDANCY, severity=ImpactSeverity.HIGH)
    second = assessment(dimension=ImpactDimension.DATA, severity=ImpactSeverity.HIGH)
    result = highest_material_dimensions((first, second))
    assert set(result) == {first, second}


def test_highest_material_dimensions_empty_for_no_assessments() -> None:
    assert highest_material_dimensions(()) == ()
