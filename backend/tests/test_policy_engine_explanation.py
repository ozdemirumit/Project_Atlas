from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.policy_engine.domain.explanation import explain_decision
from atlas.modules.policy_engine.domain.models import (
    NonOverridableRule,
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyReason,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def decision(
    *,
    outcome: PolicyDecisionOutcome,
    reasons: tuple[PolicyReason, ...] = (),
    non_overridable_rule_references: tuple[NonOverridableRule, ...] = (),
    additional_conditions: tuple[PolicyDecisionOutcome, ...] = (),
) -> PolicyDecision:
    return PolicyDecision(
        decision_id="policy-decision.example",
        decided_at=NOW,
        outcome=outcome,
        reasons=reasons,
        decision_request_id="policy-decision-request.example",
        correlation_id="correlation.example",
        actor_id="subject.example",
        operation_id="operation.example",
        non_overridable_rule_references=non_overridable_rule_references,
        additional_conditions=additional_conditions,
    )


def test_an_allow_decision_explains_with_no_reasons_and_a_proceed_step() -> None:
    explanation = explain_decision(decision(outcome=PolicyDecisionOutcome.ALLOW))
    assert explanation.reasons == ()
    assert "may proceed" in explanation.required_next_step


def test_a_non_overridable_denial_reference_is_prefixed_and_traceable() -> None:
    reason = PolicyReason(
        non_overridable_rule=NonOverridableRule.SECRET_IN_CONTEXT,
        summary="The request context contains a secret value.",
    )
    explanation = explain_decision(
        decision(
            outcome=PolicyDecisionOutcome.DENY,
            reasons=(reason,),
            non_overridable_rule_references=(NonOverridableRule.SECRET_IN_CONTEXT,),
        )
    )
    assert explanation.reasons[0].reference == "non-overridable.secret_in_context"
    assert explanation.reasons[0].summary == "The request context contains a secret value."


def test_a_policy_rule_denial_reference_passes_through_unchanged() -> None:
    reason = PolicyReason(
        policy_rule_reference="policy-set.example:v1#policy-rule.example",
        summary="Denied by an explicit rule.",
    )
    explanation = explain_decision(decision(outcome=PolicyDecisionOutcome.DENY, reasons=(reason,)))
    assert explanation.reasons[0].reference == "policy-set.example:v1#policy-rule.example"


def test_a_deny_by_default_reason_has_no_reference() -> None:
    reason = PolicyReason(summary="No policy rule grants this operation; policy denies by default.")
    explanation = explain_decision(decision(outcome=PolicyDecisionOutcome.DENY, reasons=(reason,)))
    assert explanation.reasons[0].reference is None


def test_additional_conditions_each_produce_their_own_next_step() -> None:
    explanation = explain_decision(
        decision(
            outcome=PolicyDecisionOutcome.REQUIRE_CHANGE_WINDOW,
            additional_conditions=(PolicyDecisionOutcome.REQUIRE_APPROVAL,),
        )
    )
    assert "change window" in explanation.required_next_step
    assert len(explanation.additional_required_next_steps) == 1
    assert "approver" in explanation.additional_required_next_steps[0]


@pytest.mark.parametrize("outcome", list(PolicyDecisionOutcome))
def test_every_outcome_has_a_non_empty_required_next_step(
    outcome: PolicyDecisionOutcome,
) -> None:
    reasons = (PolicyReason(summary="Example."),) if outcome is PolicyDecisionOutcome.DENY else ()
    explanation = explain_decision(decision(outcome=outcome, reasons=reasons))
    assert explanation.required_next_step.strip()


def test_the_decision_identifier_is_preserved() -> None:
    explanation = explain_decision(decision(outcome=PolicyDecisionOutcome.ALLOW))
    assert explanation.decision_id == "policy-decision.example"
