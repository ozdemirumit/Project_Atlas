from __future__ import annotations

from atlas.modules.recommendations.domain.models import (
    RecommendationState,
    a_draft_recommendation_reaches_ready_for_review_without_completing_validation,
    an_approved_for_planning_recommendation_authorizes_infrastructure_execution,
    is_valid_recommendation_state_transition,
)


def test_absolute_rules_are_false() -> None:
    assert a_draft_recommendation_reaches_ready_for_review_without_completing_validation() is False
    assert an_approved_for_planning_recommendation_authorizes_infrastructure_execution() is False


def test_diagram_transitions_are_valid() -> None:
    valid_pairs = (
        (RecommendationState.DRAFT, RecommendationState.VALIDATING),
        (RecommendationState.VALIDATING, RecommendationState.DRAFT),
        (RecommendationState.VALIDATING, RecommendationState.READY_FOR_REVIEW),
        (RecommendationState.READY_FOR_REVIEW, RecommendationState.REVIEWED),
        (RecommendationState.READY_FOR_REVIEW, RecommendationState.REJECTED),
        (RecommendationState.REVIEWED, RecommendationState.APPROVED_FOR_PLANNING),
        (RecommendationState.REVIEWED, RecommendationState.SUPERSEDED),
        (RecommendationState.APPROVED_FOR_PLANNING, RecommendationState.EXPIRED),
        (RecommendationState.APPROVED_FOR_PLANNING, RecommendationState.SUPERSEDED),
        (RecommendationState.APPROVED_FOR_PLANNING, RecommendationState.IMPLEMENTED),
        (RecommendationState.IMPLEMENTED, RecommendationState.OUTCOME_REVIEWED),
        (RecommendationState.OUTCOME_REVIEWED, RecommendationState.RETIRED),
        (RecommendationState.REJECTED, RecommendationState.RETIRED),
        (RecommendationState.EXPIRED, RecommendationState.RETIRED),
    )
    for current, target in valid_pairs:
        assert is_valid_recommendation_state_transition(current, target) is True


def test_undiagrammed_transitions_are_rejected() -> None:
    invalid_pairs = (
        (RecommendationState.DRAFT, RecommendationState.READY_FOR_REVIEW),
        (RecommendationState.READY_FOR_REVIEW, RecommendationState.APPROVED_FOR_PLANNING),
        (RecommendationState.APPROVED_FOR_PLANNING, RecommendationState.DRAFT),
        (RecommendationState.SUPERSEDED, RecommendationState.RETIRED),
        (RecommendationState.RETIRED, RecommendationState.DRAFT),
    )
    for current, target in invalid_pairs:
        assert is_valid_recommendation_state_transition(current, target) is False


def test_terminal_states_have_no_outgoing_transitions() -> None:
    assert (
        is_valid_recommendation_state_transition(
            RecommendationState.RETIRED, RecommendationState.DRAFT
        )
        is False
    )
    for target in RecommendationState:
        assert is_valid_recommendation_state_transition(RecommendationState.SUPERSEDED, target) is (
            False
        )
