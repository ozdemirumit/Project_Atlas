from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.decision_engine.domain.review_and_outcome import (
    DecisionOutcomeRecord,
    HumanReviewAction,
    OutcomeQualityLabel,
    ReviewActionKind,
    outcome_data_authorizes_automatic_model_training,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def review_action(**overrides: object) -> HumanReviewAction:
    defaults: dict[str, object] = {
        "action_id": "decision-review-action.example",
        "kind": ReviewActionKind.RERANK_HYPOTHESES,
        "target_reference": "decision-hypothesis.example",
        "reviewer_id": "subject.domain-expert",
        "reviewed_at": NOW,
        "reason": "New evidence more strongly supports the fabric-instability hypothesis.",
        "resulting_reviewed_version_id": "decision-record.example.v2",
    }
    defaults.update(overrides)
    return HumanReviewAction(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_review_action_constructs_cleanly() -> None:
    example = review_action()
    assert example.kind is ReviewActionKind.RERANK_HYPOTHESES


def test_review_action_requires_who_reviewed_it() -> None:
    with pytest.raises(ValueError, match="who reviewed it"):
        review_action(reviewer_id="   ")


def test_review_action_requires_a_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        review_action(reason="   ")


def test_review_action_rejects_naive_reviewed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        review_action(reviewed_at=NOW.replace(tzinfo=None))


def test_resulting_reviewed_version_id_may_be_none_for_an_annotation() -> None:
    example = review_action(resulting_reviewed_version_id=None)
    assert example.resulting_reviewed_version_id is None


def test_review_action_kind_has_seven_members() -> None:
    assert len(ReviewActionKind) == 7


def outcome(**overrides: object) -> DecisionOutcomeRecord:
    defaults: dict[str, object] = {
        "outcome_id": "decision-outcome.example",
        "decision_id": "decision-record.example",
        "confirmed_hypothesis_id": "decision-hypothesis.example",
        "selected_candidate_id": "decision-candidate.example",
        "actual_impact": "Momentary path redundancy loss.",
        "actual_duration_minutes": 4,
        "actual_service_interruption": "None observed.",
        "validation_outcome": "Controller B reported healthy after restart.",
        "recovery_outcome": None,
        "quality_labels": (),
        "recorded_at": NOW,
    }
    defaults.update(overrides)
    return DecisionOutcomeRecord(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_outcome_constructs_cleanly() -> None:
    example = outcome()
    assert example.confirmed_hypothesis_id == "decision-hypothesis.example"


def test_outcome_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        outcome(actual_duration_minutes=-1)


def test_outcome_rejects_naive_recorded_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        outcome(recorded_at=NOW.replace(tzinfo=None))


def test_outcome_may_carry_quality_labels() -> None:
    example = outcome(quality_labels=(OutcomeQualityLabel.MISSING_EVIDENCE,))
    assert example.quality_labels == (OutcomeQualityLabel.MISSING_EVIDENCE,)


def test_outcome_data_never_authorizes_automatic_model_training() -> None:
    assert outcome_data_authorizes_automatic_model_training() is False
