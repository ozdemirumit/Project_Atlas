from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.explainability.domain.policy_denial import (
    ControlFamily,
    PolicyDenialExplanation,
    detect_optional_advice_framing,
    explain_policy_denial,
)
from atlas.modules.policy_engine.domain.models import (
    NonOverridableRule,
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyReason,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def decision(**overrides: object) -> PolicyDecision:
    defaults: dict[str, object] = {
        "decision_id": "decision.example",
        "decided_at": NOW,
        "outcome": PolicyDecisionOutcome.ALLOW,
        "reasons": (),
        "decision_request_id": "decision-request.example",
        "correlation_id": "correlation.example",
        "actor_id": "actor.example",
        "operation_id": "operation.restart-controller",
        "non_overridable_rule_references": (),
        "evaluated_policy_set_versions": (),
        "additional_conditions": (),
    }
    defaults.update(overrides)
    return PolicyDecision(**defaults)  # type: ignore[arg-type]


def test_ordinary_text_has_no_optional_advice_framing() -> None:
    assert detect_optional_advice_framing("This operation requires approval.") == ()


@pytest.mark.parametrize(
    "text",
    [
        "You could optionally request approval.",
        "If you want, you may retry later.",
        "You may want to consider requesting approval.",
        "Consider opening a change record.",
    ],
)
def test_optional_advice_framing_is_detected(text: str) -> None:
    assert detect_optional_advice_framing(text) != ()


def test_allow_decision_explains_with_no_control_family() -> None:
    explanation = explain_policy_denial(
        decision(),
        requested_operation="restart controller B",
        is_eligible_for_detailed_view=False,
    )
    assert explanation.outcome is PolicyDecisionOutcome.ALLOW
    assert explanation.control_family is None
    assert explanation.reason_summary == "This operation is permitted."


def test_deny_from_non_overridable_rule_maps_to_the_rules_control_family() -> None:
    explanation = explain_policy_denial(
        decision(
            outcome=PolicyDecisionOutcome.DENY,
            reasons=(
                PolicyReason(
                    summary="The request was not authenticated.",
                    non_overridable_rule=NonOverridableRule.UNAUTHENTICATED_ACCESS,
                ),
            ),
            non_overridable_rule_references=(NonOverridableRule.UNAUTHENTICATED_ACCESS,),
        ),
        requested_operation="restart controller B",
        is_eligible_for_detailed_view=False,
    )
    assert explanation.control_family is ControlFamily.AUTHENTICATION
    assert explanation.reason_code == "non-overridable.unauthenticated_access"
    assert explanation.reason_summary == "The request was not authenticated."


def test_deny_from_a_policy_rule_maps_to_the_policy_control_family() -> None:
    explanation = explain_policy_denial(
        decision(
            outcome=PolicyDecisionOutcome.DENY,
            reasons=(
                PolicyReason(
                    summary="No policy rule permits this operation.",
                    policy_rule_reference="policy-set.example/rule.7",
                ),
            ),
        ),
        requested_operation="restart controller B",
        is_eligible_for_detailed_view=False,
    )
    assert explanation.control_family is ControlFamily.POLICY
    assert explanation.reason_code == "policy-set.example/rule.7"


def test_require_approval_maps_to_the_approval_control_family() -> None:
    explanation = explain_policy_denial(
        decision(outcome=PolicyDecisionOutcome.REQUIRE_APPROVAL),
        requested_operation="restart controller B",
        is_eligible_for_detailed_view=False,
    )
    assert explanation.control_family is ControlFamily.APPROVAL
    assert explanation.reason_summary == "This operation requires approval."
    assert explanation.reason_code == "policy.require_approval"


def test_detailed_reasons_are_empty_when_not_eligible() -> None:
    explanation = explain_policy_denial(
        decision(
            outcome=PolicyDecisionOutcome.DENY,
            reasons=(PolicyReason(summary="No policy rule permits this operation."),),
        ),
        requested_operation="restart controller B",
        is_eligible_for_detailed_view=False,
    )
    assert explanation.detailed_reasons == ()


def test_detailed_reasons_are_populated_when_eligible() -> None:
    explanation = explain_policy_denial(
        decision(
            outcome=PolicyDecisionOutcome.DENY,
            reasons=(PolicyReason(summary="No policy rule permits this operation."),),
        ),
        requested_operation="restart controller B",
        is_eligible_for_detailed_view=True,
    )
    assert len(explanation.detailed_reasons) == 1
    assert explanation.detailed_reasons[0].summary == "No policy rule permits this operation."


def _explanation(**overrides: object) -> PolicyDenialExplanation:
    defaults: dict[str, object] = {
        "requested_operation": "restart controller B",
        "outcome": PolicyDecisionOutcome.DENY,
        "control_family": ControlFamily.POLICY,
        "reason_code": "policy.deny",
        "reason_summary": "No policy rule permits this operation.",
        "required_next_step": "This operation is not permitted.",
        "additional_required_next_steps": (),
        "detailed_reasons": (),
    }
    defaults.update(overrides)
    return PolicyDenialExplanation(**defaults)  # type: ignore[arg-type]


def test_rejects_blank_requested_operation() -> None:
    with pytest.raises(ValueError, match="requested operation"):
        _explanation(requested_operation="   ")


def test_rejects_blank_reason_summary() -> None:
    with pytest.raises(ValueError, match="reason summary"):
        _explanation(reason_summary="   ")


def test_rejects_blank_required_next_step() -> None:
    with pytest.raises(ValueError, match="required next step"):
        _explanation(required_next_step="   ")


def test_a_denial_cannot_construct_with_optional_advice_framing_in_the_summary() -> None:
    with pytest.raises(ValueError, match="optional advice"):
        _explanation(reason_summary="You may want to consider retrying.")


def test_a_denial_cannot_construct_with_optional_advice_framing_in_the_next_step() -> None:
    with pytest.raises(ValueError, match="optional advice"):
        _explanation(required_next_step="If you want, you could optionally retry.")


def test_allow_outcome_is_exempt_from_the_optional_advice_check() -> None:
    example = _explanation(
        outcome=PolicyDecisionOutcome.ALLOW,
        control_family=None,
        reason_code="policy.allow",
        reason_summary="This operation is permitted.",
        required_next_step="No further action is required; the operation may proceed.",
    )
    assert example.outcome is PolicyDecisionOutcome.ALLOW
