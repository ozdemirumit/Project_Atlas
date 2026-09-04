"""ATLAS-041 SS23/SS24: user-facing reasoning summary and stopping rules.

Reuses Guardrails' `detect_secret_patterns` (a seventh reuse this session) for the secret portion
of SS23's "does not expose private chain-of-thought, hidden prompts, secrets, or unauthorized
evidence," and slice 12's `StopReason` for SS24's eight stopping-rule reasons rather than a
second enum.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.reasoning.domain.artifact import StopReason


@dataclass(frozen=True, slots=True)
class ReasoningSummary:
    """SS23's fixed seven-part structure, in order."""

    what_is_known: str
    what_atlas_infers_and_why: str
    remaining_alternatives: tuple[str, ...]
    unknown_or_stale: tuple[str, ...]
    confidence_and_why: str
    safest_check_to_improve_conclusion: str | None
    decision_support_statement: str

    def __post_init__(self) -> None:
        if not self.what_is_known.strip():
            raise ValueError("a reasoning summary requires what is known")
        if not self.what_atlas_infers_and_why.strip():
            raise ValueError("a reasoning summary requires what Atlas infers and why")
        if not self.confidence_and_why.strip():
            raise ValueError("a reasoning summary requires confidence and why")
        if not self.decision_support_statement.strip():
            raise ValueError(
                "a reasoning summary requires what decision the evidence can and cannot support"
            )


def scan_summary_for_prohibited_content(summary: ReasoningSummary) -> tuple[str, ...]:
    """SS23: the secret portion of "does not expose private chain-of-thought, hidden prompts,
    secrets, or unauthorized evidence.\""""
    combined_text = " ".join(
        (
            summary.what_is_known,
            summary.what_atlas_infers_and_why,
            summary.confidence_and_why,
            summary.decision_support_statement,
        )
    )
    return detect_secret_patterns(combined_text)


@dataclass(frozen=True, slots=True)
class StoppingConditions:
    """Inputs to SS24's stopping-rule evaluation, one boolean per named condition."""

    question_answered_at_required_level: bool
    domain_confirmation_criterion_met: bool
    next_check_requires_unavailable_permission_or_approval: bool
    evidence_insufficient_and_no_safe_check_remains: bool
    budget_exhausted: bool
    new_checks_would_repeat_existing_evidence: bool
    guardrail_or_policy_blocks_further_work: bool
    user_cancelled_or_task_expired: bool


_STOP_REASON_PRECEDENCE: tuple[tuple[str, StopReason], ...] = (
    ("user_cancelled_or_task_expired", StopReason.USER_CANCELLED_OR_TASK_EXPIRED),
    ("guardrail_or_policy_blocks_further_work", StopReason.GUARDRAIL_OR_POLICY_BLOCK),
    (
        "next_check_requires_unavailable_permission_or_approval",
        StopReason.REQUIRES_UNAVAILABLE_PERMISSION_OR_APPROVAL,
    ),
    ("domain_confirmation_criterion_met", StopReason.DOMAIN_CONFIRMATION_MET),
    ("question_answered_at_required_level", StopReason.QUESTION_ANSWERED),
    ("budget_exhausted", StopReason.BUDGET_EXHAUSTED),
    (
        "new_checks_would_repeat_existing_evidence",
        StopReason.NEW_CHECKS_WOULD_REPEAT_EXISTING_EVIDENCE,
    ),
    (
        "evidence_insufficient_and_no_safe_check_remains",
        StopReason.EVIDENCE_INSUFFICIENT_NO_SAFE_CHECK_REMAINS,
    ),
)


def determine_stop_reason(conditions: StoppingConditions) -> StopReason | None:
    """SS24: "reasoning stops when" any of eight conditions holds. Returns the first true
    condition in a fixed precedence order -- hard external stops (cancellation, guardrail/policy
    block, unavailable permission) take precedence over softer internal reasons (budget
    exhaustion, evidence insufficiency) so a hard stop is never masked -- or `None` if reasoning
    should continue."""
    for field_name, reason in _STOP_REASON_PRECEDENCE:
        if getattr(conditions, field_name):
            return reason
    return None


@dataclass(frozen=True, slots=True)
class StoppingReport:
    """SS24: "stopping reports the current state; it does not fabricate closure." No field on
    this type can claim resolution beyond what `stop_reason` and `current_state_summary`
    actually establish -- there is no separate "resolved"/"closed" flag to fabricate."""

    stop_reason: StopReason
    current_state_summary: str

    def __post_init__(self) -> None:
        if not self.current_state_summary.strip():
            raise ValueError("a stopping report requires a current state summary")
