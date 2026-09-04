from __future__ import annotations

import pytest

from atlas.modules.explainability.domain.confidence import (
    ConfidenceExplanation,
    detect_forbidden_confidence_language,
)
from atlas.modules.guardrails.domain.reasoning_guardrails import ConfidenceLevel


def confidence(**overrides: object) -> ConfidenceExplanation:
    defaults: dict[str, object] = {
        "category": ConfidenceLevel.HIGH,
        "category_definition": "High confidence: multiple independent, current signals agree.",
        "supporting_factors": ("Matches a known, resolved fault pattern.",),
        "limiting_factors": ("The vendor advisory was published before this firmware version.",),
        "remaining_alternatives": ("A transient network blip could also explain this.",),
        "missing_or_conflicting_evidence": (),
        "what_would_change_the_category": "A repeat occurrence after the fix would lower it.",
        "is_confirmed": False,
        "domain_criteria_met": False,
    }
    defaults.update(overrides)
    return ConfidenceExplanation(**defaults)  # type: ignore[arg-type]


def test_ordinary_text_has_no_forbidden_language() -> None:
    assert detect_forbidden_confidence_language("This is likely the cause.") == ()


@pytest.mark.parametrize(
    "text",
    [
        "This is certain to be the cause.",
        "This fix is guaranteed to resolve it.",
        "This change is safe.",
        "There will be no impact.",
    ],
)
def test_each_forbidden_word_is_detected(text: str) -> None:
    assert detect_forbidden_confidence_language(text) != ()


def test_a_percentage_is_flagged_even_when_plausible() -> None:
    detected = detect_forbidden_confidence_language("This is 87% likely to be the cause.")
    assert detected != ()


def test_a_well_formed_confidence_explanation_constructs_cleanly() -> None:
    example = confidence()
    assert example.category is ConfidenceLevel.HIGH


def test_confirmed_requires_domain_criteria_met() -> None:
    with pytest.raises(ValueError, match="domain criteria"):
        confidence(is_confirmed=True, domain_criteria_met=False)


def test_confirmed_is_allowed_when_domain_criteria_are_met() -> None:
    example = confidence(is_confirmed=True, domain_criteria_met=True)
    assert example.is_confirmed is True


def test_not_confirmed_does_not_require_domain_criteria() -> None:
    example = confidence(is_confirmed=False, domain_criteria_met=False)
    assert example.is_confirmed is False


def test_requires_at_least_one_supporting_factor() -> None:
    with pytest.raises(ValueError, match="supporting factor"):
        confidence(supporting_factors=())


def test_limiting_factors_may_be_empty() -> None:
    example = confidence(limiting_factors=())
    assert example.limiting_factors == ()


def test_rejects_blank_category_definition() -> None:
    with pytest.raises(ValueError, match="category definition"):
        confidence(category_definition="   ")


def test_rejects_blank_what_would_change_the_category() -> None:
    with pytest.raises(ValueError, match="what would change the category"):
        confidence(what_would_change_the_category="   ")
