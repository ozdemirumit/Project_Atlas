from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.reasoning.domain.causal_reasoning import (
    CausalAssertion,
    CounterfactualBasis,
    CounterfactualQuestionKind,
    CounterfactualStatement,
    HumanConfirmation,
    recent_change_alone_proves_causation,
    recovery_strengthens_hypothesis,
    shared_upstream_dependency_explains_correlation,
    temporal_precedence_alone_proves_causation,
)
from atlas.modules.reasoning.domain.models import EpistemicType

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def assertion(**overrides: object) -> CausalAssertion:
    defaults: dict[str, object] = {
        "claim_id": "reasoning-causal-assertion.example",
        "epistemic_type": EpistemicType.INFERENCE,
        "asserts_root_cause": False,
        "contributing_causes": (),
        "latent_conditions": (),
        "is_confirmed_cause": False,
        "confirmation_criteria": None,
    }
    defaults.update(overrides)
    return CausalAssertion(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_assertion_constructs_cleanly() -> None:
    example = assertion()
    assert example.epistemic_type is EpistemicType.INFERENCE


def test_correlation_cannot_assert_root_cause() -> None:
    with pytest.raises(ValueError, match="correlation is not labeled root cause"):
        assertion(epistemic_type=EpistemicType.CORRELATION, asserts_root_cause=True)


def test_correlation_without_root_cause_assertion_constructs_cleanly() -> None:
    example = assertion(epistemic_type=EpistemicType.CORRELATION, asserts_root_cause=False)
    assert example.asserts_root_cause is False


def test_non_correlation_can_assert_root_cause() -> None:
    example = assertion(epistemic_type=EpistemicType.INFERENCE, asserts_root_cause=True)
    assert example.asserts_root_cause is True


def test_confirmed_cause_requires_confirmation_criteria() -> None:
    with pytest.raises(ValueError, match="confirmation_criteria is required"):
        assertion(is_confirmed_cause=True, confirmation_criteria=None)


def test_confirmed_cause_constructs_with_confirmation_criteria() -> None:
    example = assertion(
        is_confirmed_cause=True,
        confirmation_criteria="Domain-defined validation checklist completed.",
    )
    assert example.is_confirmed_cause is True


def test_unconfirmed_cause_cannot_carry_confirmation_criteria() -> None:
    with pytest.raises(ValueError, match="only meaningful when is_confirmed_cause"):
        assertion(is_confirmed_cause=False, confirmation_criteria="Not applicable.")


def test_temporal_precedence_alone_never_proves_causation() -> None:
    assert temporal_precedence_alone_proves_causation() is False


def test_recent_change_alone_never_proves_causation() -> None:
    assert recent_change_alone_proves_causation() is False


def test_recovery_strengthens_hypothesis_when_both_considered() -> None:
    assert (
        recovery_strengthens_hypothesis(
            alternative_causes_considered=True, coincident_recovery_considered=True
        )
        is True
    )


def test_recovery_does_not_strengthen_hypothesis_when_only_one_considered() -> None:
    assert (
        recovery_strengthens_hypothesis(
            alternative_causes_considered=True, coincident_recovery_considered=False
        )
        is False
    )


def test_shared_upstream_dependency_explains_correlation_with_two_symptoms() -> None:
    assert (
        shared_upstream_dependency_explains_correlation(
            correlated_symptom_count=2, shared_dependency_id="target.upstream"
        )
        is True
    )


def test_shared_upstream_dependency_does_not_explain_a_single_symptom() -> None:
    assert (
        shared_upstream_dependency_explains_correlation(
            correlated_symptom_count=1, shared_dependency_id="target.upstream"
        )
        is False
    )


def test_shared_upstream_dependency_requires_a_dependency_id() -> None:
    assert (
        shared_upstream_dependency_explains_correlation(
            correlated_symptom_count=3, shared_dependency_id=None
        )
        is False
    )


def test_human_confirmation_constructs_cleanly() -> None:
    example = HumanConfirmation(
        confirmed_by="subject.domain-expert",
        confirmed_at=NOW,
        statement="Confirmed the fabric instability caused the outage.",
    )
    assert example.confirmed_by == "subject.domain-expert"


def test_human_confirmation_requires_who_confirmed_it() -> None:
    with pytest.raises(ValueError, match="who confirmed it"):
        HumanConfirmation(confirmed_by="   ", confirmed_at=NOW, statement="Confirmed.")


def test_human_confirmation_rejects_naive_confirmed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        HumanConfirmation(
            confirmed_by="subject.domain-expert",
            confirmed_at=NOW.replace(tzinfo=None),
            statement="Confirmed.",
        )


def counterfactual(**overrides: object) -> CounterfactualStatement:
    defaults: dict[str, object] = {
        "statement_id": "reasoning-counterfactual.example",
        "question_kind": CounterfactualQuestionKind.EXPECTED_IF_LEADING_HYPOTHESIS_FALSE,
        "answer": "Path errors would be absent on both fabrics.",
        "basis": CounterfactualBasis.ESTIMATE,
        "supporting_reference": None,
    }
    defaults.update(overrides)
    return CounterfactualStatement(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_counterfactual_constructs_cleanly() -> None:
    example = counterfactual()
    assert example.basis is CounterfactualBasis.ESTIMATE


def test_counterfactual_requires_an_answer() -> None:
    with pytest.raises(ValueError, match="requires an answer"):
        counterfactual(answer="   ")


def test_validated_simulator_basis_requires_a_supporting_reference() -> None:
    with pytest.raises(ValueError, match="requires a supporting_reference"):
        counterfactual(basis=CounterfactualBasis.VALIDATED_SIMULATOR, supporting_reference=None)


def test_validated_simulator_basis_constructs_with_a_supporting_reference() -> None:
    example = counterfactual(
        basis=CounterfactualBasis.VALIDATED_SIMULATOR,
        supporting_reference="simulator.fabric-model.v2",
    )
    assert example.supporting_reference is not None


def test_estimate_basis_cannot_carry_a_supporting_reference() -> None:
    with pytest.raises(ValueError, match="only meaningful when basis is not ESTIMATE"):
        counterfactual(basis=CounterfactualBasis.ESTIMATE, supporting_reference="simulator.example")
