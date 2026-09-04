from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.guardrails.domain.models import (
    GUARDRAIL_INVARIANT_SUMMARIES,
    GuardrailClass,
    GuardrailDecision,
    GuardrailInvariant,
    GuardrailOutcome,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def decision(**overrides: object) -> GuardrailDecision:
    defaults: dict[str, object] = {
        "decision_id": "guardrail-decision.example",
        "decided_at": NOW,
        "rule_id": "guardrail-rule.example",
        "rule_version": 1,
        "guardrail_class": GuardrailClass.ADVISORY,
        "input_reference": "input.example",
        "outcome": GuardrailOutcome.PASS,
        "reason_code": "example_reason",
        "detail": "Example authorized detail.",
        "evidence_references": (),
        "detector_version": "detector.v1",
        "required_next_action": "None.",
        "correlation_id": "correlation.example",
    }
    defaults.update(overrides)
    return GuardrailDecision(**defaults)  # type: ignore[arg-type]


def test_every_invariant_has_exactly_sixteen_members() -> None:
    assert len(list(GuardrailInvariant)) == 16


def test_every_invariant_has_a_summary() -> None:
    for invariant in GuardrailInvariant:
        assert invariant in GUARDRAIL_INVARIANT_SUMMARIES
        assert GUARDRAIL_INVARIANT_SUMMARIES[invariant].strip()


def test_invariant_values_are_the_documents_own_grd_identifiers() -> None:
    values = {invariant.value for invariant in GuardrailInvariant}
    assert values == {f"GRD-{n:03d}" for n in range(1, 17)}


def test_a_pass_outcome_constructs_cleanly() -> None:
    example = decision()
    assert example.outcome is GuardrailOutcome.PASS
    assert example.blocking is False


@pytest.mark.parametrize("outcome", [GuardrailOutcome.BLOCK, GuardrailOutcome.QUARANTINE])
def test_block_and_quarantine_outcomes_are_blocking(outcome: GuardrailOutcome) -> None:
    example = decision(outcome=outcome)
    assert example.blocking is True


@pytest.mark.parametrize(
    "outcome", [GuardrailOutcome.WARN, GuardrailOutcome.REDACT, GuardrailOutcome.REVIEW]
)
def test_non_block_non_quarantine_outcomes_are_not_blocking(outcome: GuardrailOutcome) -> None:
    example = decision(outcome=outcome)
    assert example.blocking is False


def test_an_invariant_class_decision_may_pass() -> None:
    decision(guardrail_class=GuardrailClass.INVARIANT, outcome=GuardrailOutcome.PASS)


def test_an_invariant_class_decision_may_block() -> None:
    decision(guardrail_class=GuardrailClass.INVARIANT, outcome=GuardrailOutcome.BLOCK)


@pytest.mark.parametrize(
    "outcome",
    [
        GuardrailOutcome.WARN,
        GuardrailOutcome.QUARANTINE,
        GuardrailOutcome.REDACT,
        GuardrailOutcome.REVIEW,
    ],
)
def test_an_invariant_class_decision_rejects_every_other_outcome(
    outcome: GuardrailOutcome,
) -> None:
    with pytest.raises(ValueError, match="can only pass or block"):
        decision(guardrail_class=GuardrailClass.INVARIANT, outcome=outcome)


def test_non_invariant_classes_allow_every_outcome() -> None:
    for guardrail_class in (
        GuardrailClass.PLATFORM_MINIMUM,
        GuardrailClass.POLICY_CONFIGURABLE,
        GuardrailClass.ADVISORY,
    ):
        for outcome in GuardrailOutcome:
            decision(guardrail_class=guardrail_class, outcome=outcome)


def test_rejects_a_non_positive_rule_version() -> None:
    with pytest.raises(ValueError, match="rule_version must be positive"):
        decision(rule_version=0)


def test_rejects_a_naive_decided_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        decision(decided_at=datetime(2026, 9, 4, 12, 0))


def test_rejects_a_naive_expires_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        decision(expires_at=datetime(2026, 9, 4, 12, 0))


def test_rejects_a_blank_input_reference() -> None:
    with pytest.raises(ValueError, match="input reference"):
        decision(input_reference="   ")


def test_rejects_a_blank_reason_code() -> None:
    with pytest.raises(ValueError, match="reason code"):
        decision(reason_code="   ")


def test_rejects_blank_detail() -> None:
    with pytest.raises(ValueError, match="authorized detail"):
        decision(detail="   ")


def test_rejects_a_blank_detector_version() -> None:
    with pytest.raises(ValueError, match="detector version"):
        decision(detector_version="   ")


def test_rejects_a_blank_required_next_action() -> None:
    with pytest.raises(ValueError, match="required next action"):
        decision(required_next_action="   ")
