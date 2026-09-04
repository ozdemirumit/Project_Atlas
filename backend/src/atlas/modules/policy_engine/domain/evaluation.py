"""ATLAS-025 SS9: the full decision -- the non-overridable minimum first, then precedence
combination over every rule that matched across a set of already-resolved policy sets.

This is deliberately downstream of `resolve_policy_sets` (which policy sets apply) rather than
re-doing that work: callers resolve first, then pass the result here to decide what those sets'
rules actually say about one request.
"""

from __future__ import annotations

from datetime import datetime

from atlas.modules.policy_engine.domain.models import (
    NON_OVERRIDABLE_RULE_SUMMARIES,
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyDecisionRequest,
    PolicyReason,
    evaluate_non_overridable_minimum,
)
from atlas.modules.policy_engine.domain.policy_set import PolicySet
from atlas.modules.policy_engine.domain.rule import PolicyRule

# SS8 lists nine outcomes but does not rank the seven REQUIRE_* variants against one another --
# see PolicyDecision's own docstring for why this module picks one fixed ranking rather than
# leaving simultaneous REQUIRE_* matches ambiguous.
_REQUIRE_OUTCOME_RESTRICTIVENESS: tuple[PolicyDecisionOutcome, ...] = (
    PolicyDecisionOutcome.REQUIRE_MANUAL_EXECUTION,
    PolicyDecisionOutcome.REQUIRE_STEP_UP_AUTHENTICATION,
    PolicyDecisionOutcome.REQUIRE_CHANGE_WINDOW,
    PolicyDecisionOutcome.REQUIRE_CHANGE_RECORD,
    PolicyDecisionOutcome.REQUIRE_ELEVATED_ROLE,
    PolicyDecisionOutcome.REQUIRE_ADDITIONAL_EVIDENCE,
    PolicyDecisionOutcome.REQUIRE_APPROVAL,
)


def _rule_reference(policy_set: PolicySet, rule: PolicyRule) -> str:
    return f"{policy_set.version_reference}#{rule.rule_id}"


def evaluate_policy(
    request: PolicyDecisionRequest,
    resolved_policy_sets: tuple[PolicySet, ...],
    *,
    decision_id: str,
    decided_at: datetime,
) -> PolicyDecision:
    """The full ATLAS-025 decision: SS10's non-overridable minimum first (any violation denies
    outright, before any policy set is even read), then SS9's precedence combination --

    1. Any matched DENY rule, from any resolved set, wins outright (SS9: "any applicable deny
       wins"). All matching deny reasons are recorded, not just the first.
    2. Otherwise, every matched REQUIRE_* rule is combined (SS9: "one satisfied condition does
       not remove another") into a single primary `outcome` (the most restrictive, by this
       module's documented ranking) plus `additional_conditions` for the rest.
    3. Otherwise, an explicit matched ALLOW rule (SS9 point 8) permits the operation.
    4. Otherwise -- nothing matched at all -- the request is denied by default (SS3), not
       allowed: an operation is only ever permitted by an explicit rule, never by the mere
       absence of a denial.
    """
    evaluated_versions = tuple(policy_set.version_reference for policy_set in resolved_policy_sets)

    non_overridable_violations = evaluate_non_overridable_minimum(request)
    if non_overridable_violations:
        return PolicyDecision(
            decision_id=decision_id,
            decided_at=decided_at,
            outcome=PolicyDecisionOutcome.DENY,
            reasons=tuple(
                PolicyReason(
                    non_overridable_rule=rule, summary=NON_OVERRIDABLE_RULE_SUMMARIES[rule]
                )
                for rule in non_overridable_violations
            ),
            decision_request_id=request.decision_request_id,
            correlation_id=request.correlation_id,
            actor_id=request.actor_id,
            operation_id=request.operation_id,
            non_overridable_rule_references=non_overridable_violations,
            evaluated_policy_set_versions=evaluated_versions,
        )

    matched = [
        (policy_set, rule)
        for policy_set in resolved_policy_sets
        for rule in policy_set.rules
        if rule.matches(request)
    ]

    deny_matches = [pair for pair in matched if pair[1].effect is PolicyDecisionOutcome.DENY]
    if deny_matches:
        return PolicyDecision(
            decision_id=decision_id,
            decided_at=decided_at,
            outcome=PolicyDecisionOutcome.DENY,
            reasons=tuple(
                PolicyReason(
                    policy_rule_reference=_rule_reference(policy_set, rule),
                    summary=rule.summary,
                )
                for policy_set, rule in deny_matches
            ),
            decision_request_id=request.decision_request_id,
            correlation_id=request.correlation_id,
            actor_id=request.actor_id,
            operation_id=request.operation_id,
            non_overridable_rule_references=(),
            evaluated_policy_set_versions=evaluated_versions,
        )

    require_matches = [
        pair
        for pair in matched
        if pair[1].effect not in (PolicyDecisionOutcome.DENY, PolicyDecisionOutcome.ALLOW)
    ]
    if require_matches:
        distinct_outcomes = sorted(
            {rule.effect for _, rule in require_matches},
            key=_REQUIRE_OUTCOME_RESTRICTIVENESS.index,
        )
        return PolicyDecision(
            decision_id=decision_id,
            decided_at=decided_at,
            outcome=distinct_outcomes[0],
            reasons=tuple(
                PolicyReason(
                    policy_rule_reference=_rule_reference(policy_set, rule),
                    summary=rule.summary,
                )
                for policy_set, rule in require_matches
            ),
            decision_request_id=request.decision_request_id,
            correlation_id=request.correlation_id,
            actor_id=request.actor_id,
            operation_id=request.operation_id,
            non_overridable_rule_references=(),
            evaluated_policy_set_versions=evaluated_versions,
            additional_conditions=tuple(distinct_outcomes[1:]),
        )

    allow_matches = [pair for pair in matched if pair[1].effect is PolicyDecisionOutcome.ALLOW]
    if allow_matches:
        return PolicyDecision(
            decision_id=decision_id,
            decided_at=decided_at,
            outcome=PolicyDecisionOutcome.ALLOW,
            reasons=tuple(
                PolicyReason(
                    policy_rule_reference=_rule_reference(policy_set, rule),
                    summary=rule.summary,
                )
                for policy_set, rule in allow_matches
            ),
            decision_request_id=request.decision_request_id,
            correlation_id=request.correlation_id,
            actor_id=request.actor_id,
            operation_id=request.operation_id,
            non_overridable_rule_references=(),
            evaluated_policy_set_versions=evaluated_versions,
        )

    return PolicyDecision(
        decision_id=decision_id,
        decided_at=decided_at,
        outcome=PolicyDecisionOutcome.DENY,
        reasons=(
            PolicyReason(summary="No policy rule grants this operation; policy denies by default."),
        ),
        decision_request_id=request.decision_request_id,
        correlation_id=request.correlation_id,
        actor_id=request.actor_id,
        operation_id=request.operation_id,
        non_overridable_rule_references=(),
        evaluated_policy_set_versions=evaluated_versions,
    )
