from __future__ import annotations

import pytest

from atlas.modules.reasoning.domain.claims import ConfidenceCategory
from atlas.modules.reasoning.domain.hypotheses import (
    DiscriminatingCheckReference,
    HypothesisGenerationBudget,
    HypothesisSourceKind,
    HypothesisState,
    ReasoningHypothesis,
    active_hypotheses,
    satisfies_diversity_requirement,
)


def hypothesis(**overrides: object) -> ReasoningHypothesis:
    defaults: dict[str, object] = {
        "hypothesis_id": "reasoning-hypothesis.example",
        "causal_statement": "Fabric instability may be the initiating cause.",
        "source_kind": HypothesisSourceKind.CURRENT_SYMPTOMS_AND_TOPOLOGY,
        "initiating_factors": ("A fabric link flap preceded the symptom.",),
        "contributing_factors": (),
        "amplifying_factors": (),
        "scope_target_ids": ("target.example",),
        "onset": "Approximately 10:00 UTC.",
        "expected_observable_consequences": ("Path errors on both fabrics.",),
        "supporting_evidence_ids": ("evidence.example",),
        "contradicting_or_absent_evidence_ids": (),
        "assumptions": (),
        "known_confounders": (),
        "discriminating_checks": (),
        "state": HypothesisState.PROPOSED,
        "confidence": ConfidenceCategory.LOW,
        "reason_for_state_change": None,
    }
    defaults.update(overrides)
    return ReasoningHypothesis(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_hypothesis_constructs_cleanly() -> None:
    example = hypothesis()
    assert example.state is HypothesisState.PROPOSED


def test_rejects_blank_causal_statement() -> None:
    with pytest.raises(ValueError, match="causal statement"):
        hypothesis(causal_statement="   ")


def test_rejects_no_scope_targets() -> None:
    with pytest.raises(ValueError, match="at least one scope target"):
        hypothesis(scope_target_ids=())


def test_rejects_blank_onset() -> None:
    with pytest.raises(ValueError, match="onset"):
        hypothesis(onset="   ")


def test_non_proposed_state_requires_a_reason_for_change() -> None:
    with pytest.raises(ValueError, match="requires a reason for the state"):
        hypothesis(
            state=HypothesisState.SUPPORTED,
            reason_for_state_change=None,
            supporting_evidence_ids=("evidence.example",),
        )


def test_proposed_state_cannot_carry_a_reason_for_change() -> None:
    with pytest.raises(ValueError, match="only meaningful once"):
        hypothesis(state=HypothesisState.PROPOSED, reason_for_state_change="Not applicable yet.")


def test_non_proposed_state_constructs_with_a_reason() -> None:
    example = hypothesis(
        state=HypothesisState.WEAKENED,
        reason_for_state_change="Expected consequence was not observed.",
    )
    assert example.reason_for_state_change is not None


def test_confirmed_hypothesis_requires_supporting_evidence() -> None:
    with pytest.raises(ValueError, match="requires supporting evidence"):
        hypothesis(
            state=HypothesisState.CONFIRMED,
            reason_for_state_change="Domain confirmation criteria met.",
            supporting_evidence_ids=(),
        )


def test_confirmed_hypothesis_constructs_with_supporting_evidence() -> None:
    example = hypothesis(
        state=HypothesisState.CONFIRMED,
        reason_for_state_change="Domain confirmation criteria met.",
        supporting_evidence_ids=("evidence.example",),
    )
    assert example.state is HypothesisState.CONFIRMED


def test_discriminating_check_reference_requires_both_fields() -> None:
    with pytest.raises(ValueError, match="expected_result_if_true"):
        DiscriminatingCheckReference(
            check_reference="check.path-status", expected_result_if_true="   "
        )


def test_active_hypotheses_excludes_rejected() -> None:
    proposed = hypothesis(hypothesis_id="reasoning-hypothesis.a")
    rejected = hypothesis(
        hypothesis_id="reasoning-hypothesis.b",
        state=HypothesisState.REJECTED,
        reason_for_state_change="Expected consequence never materialized.",
    )
    result = active_hypotheses((proposed, rejected))
    assert result == (proposed,)


def test_active_hypotheses_includes_confirmed() -> None:
    confirmed = hypothesis(
        state=HypothesisState.CONFIRMED,
        reason_for_state_change="Domain confirmation criteria met.",
        supporting_evidence_ids=("evidence.example",),
    )
    assert active_hypotheses((confirmed,)) == (confirmed,)


def test_satisfies_diversity_requirement_within_bounds_and_diverse() -> None:
    budget = HypothesisGenerationBudget(maximum_hypotheses=5, minimum_distinct_source_kinds=2)
    hypotheses = (
        hypothesis(
            hypothesis_id="reasoning-hypothesis.a",
            source_kind=HypothesisSourceKind.CURRENT_SYMPTOMS_AND_TOPOLOGY,
        ),
        hypothesis(
            hypothesis_id="reasoning-hypothesis.b",
            source_kind=HypothesisSourceKind.RECENT_CHANGE_OR_CONFIGURATION_DRIFT,
        ),
    )
    assert satisfies_diversity_requirement(hypotheses, budget=budget) is True


def test_satisfies_diversity_requirement_false_when_exceeding_maximum() -> None:
    budget = HypothesisGenerationBudget(maximum_hypotheses=1, minimum_distinct_source_kinds=1)
    hypotheses = (
        hypothesis(hypothesis_id="reasoning-hypothesis.a"),
        hypothesis(hypothesis_id="reasoning-hypothesis.b"),
    )
    assert satisfies_diversity_requirement(hypotheses, budget=budget) is False


def test_satisfies_diversity_requirement_false_when_not_diverse_enough() -> None:
    budget = HypothesisGenerationBudget(maximum_hypotheses=5, minimum_distinct_source_kinds=2)
    hypotheses = (
        hypothesis(
            hypothesis_id="reasoning-hypothesis.a",
            source_kind=HypothesisSourceKind.USER_SUPPLIED,
        ),
        hypothesis(
            hypothesis_id="reasoning-hypothesis.b",
            source_kind=HypothesisSourceKind.USER_SUPPLIED,
        ),
    )
    assert satisfies_diversity_requirement(hypotheses, budget=budget) is False


def test_satisfies_diversity_requirement_scales_down_for_a_single_hypothesis() -> None:
    budget = HypothesisGenerationBudget(maximum_hypotheses=5, minimum_distinct_source_kinds=3)
    hypotheses = (hypothesis(hypothesis_id="reasoning-hypothesis.a"),)
    assert satisfies_diversity_requirement(hypotheses, budget=budget) is True
