"""ATLAS-025 SS20: availability and failure.

Every row of SS20's failure table resolves to the same shape: deny, with a stable, auditable
reason code -- never a raised exception past the caller, and never, under any failure, an Allow.
`evaluate_policy_safely` is the last line of defense wrapping the "fetch policy sets, evaluate"
pipeline; `deny_for_failure` is the single well-formed DENY every failure path produces, so there
is exactly one place that constructs a failure decision, not one per call site.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import StrEnum

from atlas.modules.policy_engine.domain.evaluation import evaluate_policy
from atlas.modules.policy_engine.domain.models import (
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyDecisionRequest,
    PolicyReason,
)
from atlas.modules.policy_engine.domain.policy_set import PolicySet


class PolicyFailureReason(StrEnum):
    """SS20's seven named failure rows, as a stable reason code -- never a raw exception message,
    which could leak internals into a decision record."""

    POLICY_STORE_UNAVAILABLE = "policy_store_unavailable"
    EVALUATION_ERROR = "evaluation_error"
    UNKNOWN_POLICY_VERSION = "unknown_policy_version"
    CONTEXT_SERVICE_UNAVAILABLE = "context_service_unavailable"
    APPROVAL_SERVICE_UNAVAILABLE = "approval_service_unavailable"
    AUDIT_UNAVAILABLE = "audit_unavailable"
    CLOCK_UNCERTAINTY = "clock_uncertainty"


_FAILURE_SUMMARY: dict[PolicyFailureReason, str] = {
    PolicyFailureReason.POLICY_STORE_UNAVAILABLE: (
        "The policy store is unavailable and no verified active snapshot within the allowed age"
        " exists."
    ),
    PolicyFailureReason.EVALUATION_ERROR: "Policy evaluation failed unexpectedly.",
    PolicyFailureReason.UNKNOWN_POLICY_VERSION: "A referenced policy version is unknown.",
    PolicyFailureReason.CONTEXT_SERVICE_UNAVAILABLE: "Required decision context is unavailable.",
    PolicyFailureReason.APPROVAL_SERVICE_UNAVAILABLE: (
        "The approval service is unavailable for this approval-required action."
    ),
    PolicyFailureReason.AUDIT_UNAVAILABLE: (
        "Required audit persistence is unavailable for this sensitive action."
    ),
    PolicyFailureReason.CLOCK_UNCERTAINTY: (
        "The current time cannot be established with sufficient certainty for this time-bound"
        " decision."
    ),
}


def deny_for_failure(
    reason: PolicyFailureReason,
    *,
    decision_id: str,
    decided_at: datetime,
    decision_request_id: str,
    correlation_id: str,
    actor_id: str,
    operation_id: str,
) -> PolicyDecision:
    """The one well-formed DENY decision every SS20 failure row resolves to. Never raises --
    this itself is the last line of defense against an upstream failure ever becoming an Allow."""
    return PolicyDecision(
        decision_id=decision_id,
        decided_at=decided_at,
        outcome=PolicyDecisionOutcome.DENY,
        reasons=(PolicyReason(summary=_FAILURE_SUMMARY[reason]),),
        decision_request_id=decision_request_id,
        correlation_id=correlation_id,
        actor_id=actor_id,
        operation_id=operation_id,
        non_overridable_rule_references=(),
    )


async def evaluate_policy_safely(
    *,
    resolve_policy_sets: Callable[[], Awaitable[tuple[PolicySet, ...]]],
    request: PolicyDecisionRequest,
    decision_id: str,
    decided_at: datetime,
) -> PolicyDecision:
    """Fetches policy sets through `resolve_policy_sets` and evaluates. Any exception while
    fetching is SS20's "policy store unavailable" row; any exception while evaluating is its
    "evaluation error" row -- alerting on the latter is an observability concern for the caller,
    not something a pure decision function can do itself."""
    try:
        resolved = await resolve_policy_sets()
    except Exception:
        return deny_for_failure(
            PolicyFailureReason.POLICY_STORE_UNAVAILABLE,
            decision_id=decision_id,
            decided_at=decided_at,
            decision_request_id=request.decision_request_id,
            correlation_id=request.correlation_id,
            actor_id=request.actor_id,
            operation_id=request.operation_id,
        )
    try:
        return evaluate_policy(request, resolved, decision_id=decision_id, decided_at=decided_at)
    except Exception:
        return deny_for_failure(
            PolicyFailureReason.EVALUATION_ERROR,
            decision_id=decision_id,
            decided_at=decided_at,
            decision_request_id=request.decision_request_id,
            correlation_id=request.correlation_id,
            actor_id=request.actor_id,
            operation_id=request.operation_id,
        )
