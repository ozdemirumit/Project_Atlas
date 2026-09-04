from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.reasoning.domain.claims import (
    ClaimLifecycleState,
    ClaimValidationState,
    ConfidenceCategory,
    ReasoningClaim,
    ReasoningRelationship,
    ReasoningRelationshipKind,
    requires_supporting_evidence,
)
from atlas.modules.reasoning.domain.models import EpistemicType

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def claim(**overrides: object) -> ReasoningClaim:
    defaults: dict[str, object] = {
        "claim_id": "reasoning-claim.example",
        "epistemic_type": EpistemicType.OBSERVATION,
        "text": "Controller B reported a degraded status at 10:04 UTC.",
        "scope_target_id": "target.example",
        "time_window_start": NOW,
        "time_window_end": None,
        "supporting_evidence_ids": ("evidence.example",),
        "contradicting_evidence_ids": (),
        "assumptions": (),
        "dependencies": (),
        "confidence": ConfidenceCategory.HIGH,
        "confidence_rationale": "Direct connector observation, independently corroborated.",
        "agent_version": "reasoning-agent.v1",
        "deterministic_method_version": None,
        "validation_state": ClaimValidationState.UNVALIDATED,
        "reviewer_feedback": None,
        "relationships": (),
        "lifecycle_state": ClaimLifecycleState.ACTIVE,
        "superseded_by_claim_id": None,
    }
    defaults.update(overrides)
    return ReasoningClaim(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("epistemic_type", "expected"),
    [
        (EpistemicType.OBSERVATION, True),
        (EpistemicType.RETRIEVED_FACT, True),
        (EpistemicType.CALCULATED_FINDING, True),
        (EpistemicType.CORRELATION, True),
        (EpistemicType.INFERENCE, False),
        (EpistemicType.HYPOTHESIS, False),
        (EpistemicType.ASSUMPTION, False),
        (EpistemicType.UNKNOWN, False),
        (EpistemicType.RECOMMENDATION, False),
    ],
)
def test_requires_supporting_evidence(epistemic_type: EpistemicType, expected: bool) -> None:
    assert requires_supporting_evidence(epistemic_type) is expected


def test_a_well_formed_claim_constructs_cleanly() -> None:
    example = claim()
    assert example.confidence is ConfidenceCategory.HIGH


def test_rejects_blank_text() -> None:
    with pytest.raises(ValueError, match="claim text"):
        claim(text="   ")


def test_rejects_naive_time_window_start() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        claim(time_window_start=NOW.replace(tzinfo=None))


def test_rejects_time_window_end_before_start() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        claim(time_window_start=NOW, time_window_end=NOW - timedelta(hours=1))


def test_rejects_blank_confidence_rationale() -> None:
    with pytest.raises(ValueError, match="confidence rationale"):
        claim(confidence_rationale="   ")


def test_disputed_claim_requires_reviewer_feedback() -> None:
    with pytest.raises(ValueError, match="requires reviewer feedback"):
        claim(validation_state=ClaimValidationState.DISPUTED, reviewer_feedback=None)


def test_disputed_claim_constructs_with_reviewer_feedback() -> None:
    example = claim(
        validation_state=ClaimValidationState.DISPUTED,
        reviewer_feedback="The vendor advisory predates this firmware version.",
    )
    assert example.reviewer_feedback is not None


def test_superseded_claim_requires_the_superseding_claim() -> None:
    with pytest.raises(ValueError, match="requires the claim that superseded it"):
        claim(lifecycle_state=ClaimLifecycleState.SUPERSEDED, superseded_by_claim_id=None)


def test_active_claim_cannot_carry_a_superseded_by_reference() -> None:
    with pytest.raises(ValueError, match="only meaningful for a SUPERSEDED"):
        claim(
            lifecycle_state=ClaimLifecycleState.ACTIVE,
            superseded_by_claim_id="reasoning-claim.next",
        )


def test_evidence_gap_for_evidence_required_type_with_no_evidence() -> None:
    example = claim(epistemic_type=EpistemicType.OBSERVATION, supporting_evidence_ids=())
    assert example.is_evidence_gap is True


def test_no_evidence_gap_for_evidence_required_type_with_evidence() -> None:
    example = claim(
        epistemic_type=EpistemicType.OBSERVATION, supporting_evidence_ids=("evidence.example",)
    )
    assert example.is_evidence_gap is False


def test_no_evidence_gap_for_a_type_that_does_not_require_evidence() -> None:
    example = claim(epistemic_type=EpistemicType.HYPOTHESIS, supporting_evidence_ids=())
    assert example.is_evidence_gap is False


def test_has_contradicting_evidence() -> None:
    example = claim(contradicting_evidence_ids=("evidence.contradicting-example",))
    assert example.has_contradicting_evidence is True


def test_reasoning_relationship_constructs_cleanly() -> None:
    relationship = ReasoningRelationship(
        kind=ReasoningRelationshipKind.HYPOTHESIS, reference_id="reasoning-hypothesis.example"
    )
    assert relationship.kind is ReasoningRelationshipKind.HYPOTHESIS
