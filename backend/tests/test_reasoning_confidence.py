from __future__ import annotations

import pytest

from atlas.modules.reasoning.domain.claims import ConfidenceCategory
from atlas.modules.reasoning.domain.confidence import (
    ConfidenceAssessment,
    ContradictionRecord,
    absence_of_alert_is_evidence,
    approval_can_increase_confidence,
    is_independent_support,
    support_weight_for,
)


def assessment(**overrides: object) -> ConfidenceAssessment:
    defaults: dict[str, object] = {
        "category": ConfidenceCategory.MODERATE,
        "supporting_factors": ("Two independent evidence units support the claim.",),
        "reducing_factors": ("One evidence unit is slightly stale.",),
        "important_unknowns": ("Host queue depth is unknown.",),
        "what_would_change_it": "A confirmed path-failure event would raise confidence.",
        "numeric_score": None,
        "numeric_score_calibration_reference": None,
    }
    defaults.update(overrides)
    return ConfidenceAssessment(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_assessment_constructs_cleanly() -> None:
    example = assessment()
    assert example.category is ConfidenceCategory.MODERATE


def test_requires_at_least_one_supporting_factor() -> None:
    with pytest.raises(ValueError, match="supporting factor"):
        assessment(supporting_factors=())


def test_requires_what_would_change_it() -> None:
    with pytest.raises(ValueError, match="what would change it"):
        assessment(what_would_change_it="   ")


def test_numeric_score_requires_calibration_reference() -> None:
    with pytest.raises(ValueError, match="numeric_score_calibration_reference"):
        assessment(numeric_score=0.8, numeric_score_calibration_reference=None)


def test_numeric_score_constructs_with_calibration_reference() -> None:
    example = assessment(
        numeric_score=0.8, numeric_score_calibration_reference="calibration.dataset.v1"
    )
    assert example.numeric_score == 0.8


def test_calibration_reference_without_numeric_score_rejected() -> None:
    with pytest.raises(ValueError, match="only meaningful alongside"):
        assessment(numeric_score=None, numeric_score_calibration_reference="calibration.v1")


def test_numeric_score_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="must be within"):
        assessment(numeric_score=1.5, numeric_score_calibration_reference="calibration.v1")


def test_is_independent_support_true_for_new_direct_evidence() -> None:
    assert (
        is_independent_support(
            evidence_id="evidence.b",
            already_counted_evidence_ids=frozenset({"evidence.a"}),
            derivative_of=None,
        )
        is True
    )


def test_is_independent_support_false_for_derivative_evidence() -> None:
    assert (
        is_independent_support(
            evidence_id="evidence.b",
            already_counted_evidence_ids=frozenset(),
            derivative_of="evidence.a",
        )
        is False
    )


def test_is_independent_support_false_for_already_counted_evidence() -> None:
    assert (
        is_independent_support(
            evidence_id="evidence.a",
            already_counted_evidence_ids=frozenset({"evidence.a"}),
            derivative_of=None,
        )
        is False
    )


def test_support_weight_full_when_fresh_and_applicable() -> None:
    assert support_weight_for(is_fresh=True, is_applicable=True) == 1.0


def test_support_weight_halved_when_stale() -> None:
    assert support_weight_for(is_fresh=False, is_applicable=True) == 0.5


def test_support_weight_quartered_when_stale_and_inapplicable() -> None:
    assert support_weight_for(is_fresh=False, is_applicable=False) == 0.25


def test_contradiction_record_requires_distinct_evidence() -> None:
    with pytest.raises(ValueError, match="two distinct evidence units"):
        ContradictionRecord(
            evidence_id_a="evidence.a", evidence_id_b="evidence.a", description="Conflict."
        )


def test_contradiction_record_requires_a_description() -> None:
    with pytest.raises(ValueError, match="description"):
        ContradictionRecord(
            evidence_id_a="evidence.a", evidence_id_b="evidence.b", description="   "
        )


def test_contradiction_record_constructs_cleanly() -> None:
    example = ContradictionRecord(
        evidence_id_a="evidence.a",
        evidence_id_b="evidence.b",
        description="Vendor guide and internal runbook disagree on the threshold.",
    )
    assert example.evidence_id_a == "evidence.a"


def test_approval_never_increases_confidence() -> None:
    assert approval_can_increase_confidence() is False


def test_absence_of_alert_is_evidence_when_coverage_and_health_known() -> None:
    assert (
        absence_of_alert_is_evidence(alert_coverage_known=True, alert_system_health_known=True)
        is True
    )


def test_absence_of_alert_is_not_evidence_when_coverage_unknown() -> None:
    assert (
        absence_of_alert_is_evidence(alert_coverage_known=False, alert_system_health_known=True)
        is False
    )
