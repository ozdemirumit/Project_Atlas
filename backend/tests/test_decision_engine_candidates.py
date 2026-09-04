from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.decision_engine.domain.candidates import (
    DecisionRecommendationCandidate,
    RecommendationCandidateKind,
)


def candidate(**overrides: object) -> DecisionRecommendationCandidate:
    defaults: dict[str, object] = {
        "candidate_id": "decision-candidate.example",
        "kind": RecommendationCandidateKind.PLAN_CONFIGURATION_OR_OPERATIONAL_CHANGE,
        "evidence_ids": ("evidence.example",),
        "rationale": "Restarting controller B should clear the degraded state.",
        "capability_class": CapabilityClass.C3_CONTROLLED_CHANGE,
        "risk_summary": "Momentary path redundancy loss during restart.",
        "impact_assessment_id": "decision-impact-assessment.example",
        "duration_minimum_minutes": 1,
        "duration_maximum_minutes": 5,
        "service_interruption": "None expected.",
        "prerequisites": ("Redundant path confirmed healthy.",),
        "required_approvals": ("role.storage-operator-approval",),
        "validation_criteria": ("Controller B reports healthy status.",),
        "recovery_reference": "runbook-recovery.partial-example",
        "alternatives": ("Escalate to vendor support.",),
        "unknowns": (),
    }
    defaults.update(overrides)
    return DecisionRecommendationCandidate(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_candidate_constructs_cleanly() -> None:
    example = candidate()
    assert example.kind is RecommendationCandidateKind.PLAN_CONFIGURATION_OR_OPERATIONAL_CHANGE


def test_rejects_blank_rationale() -> None:
    with pytest.raises(ValueError, match="rationale"):
        candidate(rationale="   ")


def test_rejects_negative_duration_minimum() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        candidate(duration_minimum_minutes=-1)


def test_rejects_negative_duration_maximum() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        candidate(duration_maximum_minutes=-1)


def test_rejects_duration_minimum_exceeding_maximum() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        candidate(duration_minimum_minutes=10, duration_maximum_minutes=5)


def test_duration_may_be_entirely_unset() -> None:
    example = candidate(duration_minimum_minutes=None, duration_maximum_minutes=None)
    assert example.duration_minimum_minutes is None


def test_no_action_candidate_cannot_carry_service_interruption() -> None:
    with pytest.raises(ValueError, match="there is no action to interrupt or approve"):
        candidate(
            kind=RecommendationCandidateKind.NO_ACTION,
            service_interruption="None.",
            required_approvals=(),
        )


def test_no_action_candidate_cannot_carry_required_approvals() -> None:
    with pytest.raises(ValueError, match="there is no action to interrupt or approve"):
        candidate(
            kind=RecommendationCandidateKind.NO_ACTION,
            service_interruption=None,
            required_approvals=("role.example",),
        )


def test_no_action_candidate_constructs_cleanly_without_either() -> None:
    example = candidate(
        kind=RecommendationCandidateKind.NO_ACTION,
        service_interruption=None,
        required_approvals=(),
        rationale="Current evidence does not justify any action.",
    )
    assert example.kind is RecommendationCandidateKind.NO_ACTION


def test_recommendation_candidate_kind_has_seven_members() -> None:
    assert len(RecommendationCandidateKind) == 7
