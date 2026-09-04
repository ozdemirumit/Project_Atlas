"""ATLAS-025 SS26: policy explanation.

"It does not expose sensitive rule internals that enable bypass, other users' permissions, or
secret context" -- `PolicyDecision` never carries any of those to begin with (no other evaluated-
but-untriggered rule content, no other identity's data, no secrets), so this module is a safe
projection of an already-safe record, not a filter standing between untrusted internals and a
user. What it adds: a fixed, non-configurable "required next step" sentence per outcome, since
`PolicyDecision` itself only carries structured outcomes and reasons, not prose telling the
requester what to do about it.

SS8 also lists "validity interval and expiry" as part of a decision's own contract; `PolicyDecision`
does not model that yet (no slice has added it), so this explanation's "expiry where relevant"
requirement is not yet fulfilled -- stated plainly rather than fabricated from nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.policy_engine.domain.models import PolicyDecision, PolicyDecisionOutcome

_REQUIRED_NEXT_STEP: dict[PolicyDecisionOutcome, str] = {
    PolicyDecisionOutcome.ALLOW: "No further action is required; the operation may proceed.",
    PolicyDecisionOutcome.DENY: (
        "This operation is not permitted. Contact a policy administrator if you believe this is"
        " incorrect."
    ),
    PolicyDecisionOutcome.REQUIRE_APPROVAL: (
        "Obtain approval from an authorized approver for this exact operation."
    ),
    PolicyDecisionOutcome.REQUIRE_ADDITIONAL_EVIDENCE: (
        "Supply the additional evidence this operation requires, then retry."
    ),
    PolicyDecisionOutcome.REQUIRE_ELEVATED_ROLE: (
        "Request a role authorized for this operation, then retry."
    ),
    PolicyDecisionOutcome.REQUIRE_CHANGE_RECORD: (
        "Open a change record for this operation, then retry."
    ),
    PolicyDecisionOutcome.REQUIRE_CHANGE_WINDOW: (
        "Retry this operation within an approved change window."
    ),
    PolicyDecisionOutcome.REQUIRE_STEP_UP_AUTHENTICATION: (
        "Complete step-up authentication, then retry."
    ),
    PolicyDecisionOutcome.REQUIRE_MANUAL_EXECUTION: (
        "This operation requires an exceptional, human-governed manual execution procedure."
    ),
}


@dataclass(frozen=True, slots=True)
class PolicyExplanationReason:
    summary: str
    reference: str | None


@dataclass(frozen=True, slots=True)
class PolicyExplanation:
    """SS26's user-safe explanation: outcome, applicable reasons, required next step(s), and the
    decision identifier -- exactly SS26's list, minus expiry (see module docstring)."""

    decision_id: str
    outcome: PolicyDecisionOutcome
    reasons: tuple[PolicyExplanationReason, ...]
    required_next_step: str
    additional_required_next_steps: tuple[str, ...]


def _reference_for(
    reason_non_overridable_rule: str | None, policy_rule_reference: str | None
) -> str | None:
    if policy_rule_reference is not None:
        return policy_rule_reference
    if reason_non_overridable_rule is not None:
        return f"non-overridable.{reason_non_overridable_rule}"
    return None


def explain_decision(decision: PolicyDecision) -> PolicyExplanation:
    reasons = tuple(
        PolicyExplanationReason(
            summary=reason.summary,
            reference=_reference_for(
                None if reason.non_overridable_rule is None else reason.non_overridable_rule.value,
                reason.policy_rule_reference,
            ),
        )
        for reason in decision.reasons
    )
    return PolicyExplanation(
        decision_id=decision.decision_id,
        outcome=decision.outcome,
        reasons=reasons,
        required_next_step=_REQUIRED_NEXT_STEP[decision.outcome],
        additional_required_next_steps=tuple(
            _REQUIRED_NEXT_STEP[outcome] for outcome in decision.additional_conditions
        ),
    )
