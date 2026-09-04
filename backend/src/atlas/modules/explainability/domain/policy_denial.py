"""ATLAS-046 SS17: policy and denial explanation.

Reuses `policy_engine.domain.explanation.explain_decision` (ATLAS-025 SS26) as its source of
truth rather than re-deriving a second safe projection of `PolicyDecision` -- that function's own
docstring already establishes it exposes nothing unsafe (no untriggered rule internals, no other
identity's data, no secrets), so this module adds only what SS17 asks for beyond it: a control
family classification, and a detail-eligibility gate over the ordered reason list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.policy_engine.domain.explanation import (
    PolicyExplanationReason,
    explain_decision,
)
from atlas.modules.policy_engine.domain.models import (
    NonOverridableRule,
    PolicyDecision,
    PolicyDecisionOutcome,
)

_OPTIONAL_ADVICE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bif you (?:want|wish|would like)\b"),
    re.compile(r"(?i)\byou (?:may|might) (?:want|wish) to\b"),
    re.compile(r"(?i)\boptional(?:ly)?\b"),
    re.compile(r"(?i)\bconsider\b"),
)


def detect_optional_advice_framing(text: str) -> tuple[str, ...]:
    """SS17: "denial is never rephrased by the AI as optional advice.\""""
    return tuple(pattern.pattern for pattern in _OPTIONAL_ADVICE_PATTERNS if pattern.search(text))


class ControlFamily(StrEnum):
    """SS17's fixed set of control families a denial or requirement may belong to."""

    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    SCOPE = "scope"
    CAPABILITY = "capability"
    POLICY = "policy"
    APPROVAL = "approval"
    PRECONDITION = "precondition"
    TRUST = "trust"
    GUARDRAIL = "guardrail"


_NON_OVERRIDABLE_CONTROL_FAMILY: dict[NonOverridableRule, ControlFamily] = {
    NonOverridableRule.UNAUTHENTICATED_ACCESS: ControlFamily.AUTHENTICATION,
    NonOverridableRule.UNAUTHORIZED_SCOPE: ControlFamily.SCOPE,
    NonOverridableRule.UNKNOWN_CAPABILITY_CLASS: ControlFamily.CAPABILITY,
    NonOverridableRule.UNTRUSTED_CONNECTOR: ControlFamily.TRUST,
    NonOverridableRule.INVALID_APPROVAL: ControlFamily.APPROVAL,
    NonOverridableRule.SECRET_IN_CONTEXT: ControlFamily.GUARDRAIL,
    NonOverridableRule.C5_AUTONOMOUS_EXECUTION: ControlFamily.POLICY,
    NonOverridableRule.AI_APPROVAL_OR_EXECUTION: ControlFamily.POLICY,
    NonOverridableRule.AUDIT_UNAVAILABLE: ControlFamily.PRECONDITION,
    NonOverridableRule.CROSS_BOUNDARY_ACCESS: ControlFamily.SCOPE,
}

_OUTCOME_CONTROL_FAMILY: dict[PolicyDecisionOutcome, ControlFamily] = {
    PolicyDecisionOutcome.DENY: ControlFamily.POLICY,
    PolicyDecisionOutcome.REQUIRE_APPROVAL: ControlFamily.APPROVAL,
    PolicyDecisionOutcome.REQUIRE_ADDITIONAL_EVIDENCE: ControlFamily.PRECONDITION,
    PolicyDecisionOutcome.REQUIRE_ELEVATED_ROLE: ControlFamily.PERMISSION,
    PolicyDecisionOutcome.REQUIRE_CHANGE_RECORD: ControlFamily.PRECONDITION,
    PolicyDecisionOutcome.REQUIRE_CHANGE_WINDOW: ControlFamily.PRECONDITION,
    PolicyDecisionOutcome.REQUIRE_STEP_UP_AUTHENTICATION: ControlFamily.AUTHENTICATION,
    PolicyDecisionOutcome.REQUIRE_MANUAL_EXECUTION: ControlFamily.POLICY,
}

_DEFAULT_REASON_SUMMARY: dict[PolicyDecisionOutcome, str] = {
    PolicyDecisionOutcome.ALLOW: "This operation is permitted.",
    PolicyDecisionOutcome.REQUIRE_APPROVAL: "This operation requires approval.",
    PolicyDecisionOutcome.REQUIRE_ADDITIONAL_EVIDENCE: (
        "This operation requires additional evidence."
    ),
    PolicyDecisionOutcome.REQUIRE_ELEVATED_ROLE: "This operation requires an elevated role.",
    PolicyDecisionOutcome.REQUIRE_CHANGE_RECORD: "This operation requires a change record.",
    PolicyDecisionOutcome.REQUIRE_CHANGE_WINDOW: "This operation requires an approved change"
    " window.",
    PolicyDecisionOutcome.REQUIRE_STEP_UP_AUTHENTICATION: (
        "This operation requires step-up authentication."
    ),
    PolicyDecisionOutcome.REQUIRE_MANUAL_EXECUTION: (
        "This operation requires manual execution under human governance."
    ),
}


def _control_family_for(decision: PolicyDecision) -> ControlFamily | None:
    if decision.outcome is PolicyDecisionOutcome.ALLOW:
        return None
    if decision.non_overridable_rule_references:
        return _NON_OVERRIDABLE_CONTROL_FAMILY[decision.non_overridable_rule_references[0]]
    return _OUTCOME_CONTROL_FAMILY[decision.outcome]


@dataclass(frozen=True, slots=True)
class PolicyDenialExplanation:
    """SS17's user-safe policy/denial explanation: requested operation and outcome, a stable
    reason code and safe summary, the control family, and the next authorized action when one
    exists. `detailed_reasons` carries the full ordered reason list -- with references -- only
    when the caller has already determined the viewer is an eligible security or audit role;
    everyone else sees only the single primary reason summary."""

    requested_operation: str
    outcome: PolicyDecisionOutcome
    control_family: ControlFamily | None
    reason_code: str
    reason_summary: str
    required_next_step: str
    additional_required_next_steps: tuple[str, ...]
    detailed_reasons: tuple[PolicyExplanationReason, ...]

    def __post_init__(self) -> None:
        if not self.requested_operation.strip():
            raise ValueError("a policy explanation requires the requested operation")
        if not self.reason_summary.strip():
            raise ValueError("a policy explanation requires a reason summary")
        if not self.required_next_step.strip():
            raise ValueError("a policy explanation requires a required next step")
        if self.outcome is not PolicyDecisionOutcome.ALLOW and (
            detect_optional_advice_framing(self.reason_summary)
            or detect_optional_advice_framing(self.required_next_step)
        ):
            raise ValueError(
                "a denial or requirement must never be rephrased as optional advice (SS17)"
            )


def explain_policy_denial(
    decision: PolicyDecision,
    *,
    requested_operation: str,
    is_eligible_for_detailed_view: bool,
) -> PolicyDenialExplanation:
    explanation = explain_decision(decision)
    primary = explanation.reasons[0] if explanation.reasons else None
    reason_code = (
        primary.reference
        if primary is not None and primary.reference is not None
        else f"policy.{decision.outcome.value}"
    )
    reason_summary = (
        primary.summary if primary is not None else _DEFAULT_REASON_SUMMARY[decision.outcome]
    )
    return PolicyDenialExplanation(
        requested_operation=requested_operation,
        outcome=decision.outcome,
        control_family=_control_family_for(decision),
        reason_code=reason_code,
        reason_summary=reason_summary,
        required_next_step=explanation.required_next_step,
        additional_required_next_steps=explanation.additional_required_next_steps,
        detailed_reasons=explanation.reasons if is_eligible_for_detailed_view else (),
    )
