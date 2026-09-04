from __future__ import annotations

import pytest

from atlas.modules.reasoning.domain.artifact import StopReason
from atlas.modules.reasoning.domain.summary import (
    ReasoningSummary,
    StoppingConditions,
    StoppingReport,
    determine_stop_reason,
    scan_summary_for_prohibited_content,
)


def summary(**overrides: object) -> ReasoningSummary:
    defaults: dict[str, object] = {
        "what_is_known": "Controller B reported a degraded status at 10:04 UTC.",
        "what_atlas_infers_and_why": (
            "Fabric instability is likely, given the observed path errors."
        ),
        "remaining_alternatives": ("Resource saturation on controller B.",),
        "unknown_or_stale": ("Host queue depth is unknown.",),
        "confidence_and_why": (
            "Moderate: two independent evidence units support this, but alternatives remain."
        ),
        "safest_check_to_improve_conclusion": "Query path error counters on both fabrics.",
        "decision_support_statement": (
            "Evidence supports further diagnostics, not yet a restart recommendation."
        ),
    }
    defaults.update(overrides)
    return ReasoningSummary(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_summary_constructs_cleanly() -> None:
    example = summary()
    assert example.safest_check_to_improve_conclusion is not None


def test_rejects_blank_what_is_known() -> None:
    with pytest.raises(ValueError, match="what is known"):
        summary(what_is_known="   ")


def test_rejects_blank_inference() -> None:
    with pytest.raises(ValueError, match="what Atlas infers"):
        summary(what_atlas_infers_and_why="   ")


def test_rejects_blank_confidence_and_why() -> None:
    with pytest.raises(ValueError, match="confidence and why"):
        summary(confidence_and_why="   ")


def test_rejects_blank_decision_support_statement() -> None:
    with pytest.raises(ValueError, match="decision the evidence"):
        summary(decision_support_statement="   ")


def test_safest_check_may_be_none_when_none_remains() -> None:
    example = summary(safest_check_to_improve_conclusion=None)
    assert example.safest_check_to_improve_conclusion is None


def test_scan_summary_for_prohibited_content_with_clean_text() -> None:
    assert scan_summary_for_prohibited_content(summary()) == ()


def test_scan_summary_for_prohibited_content_detects_a_secret_pattern() -> None:
    example = summary(
        what_is_known="Authenticate first: api_key=NOTAREALSECRETPLACEHOLDERVALUE0000"
    )
    assert scan_summary_for_prohibited_content(example) != ()


def stopping_conditions(**overrides: object) -> StoppingConditions:
    defaults: dict[str, object] = {
        "question_answered_at_required_level": False,
        "domain_confirmation_criterion_met": False,
        "next_check_requires_unavailable_permission_or_approval": False,
        "evidence_insufficient_and_no_safe_check_remains": False,
        "budget_exhausted": False,
        "new_checks_would_repeat_existing_evidence": False,
        "guardrail_or_policy_blocks_further_work": False,
        "user_cancelled_or_task_expired": False,
    }
    defaults.update(overrides)
    return StoppingConditions(**defaults)  # type: ignore[arg-type]


def test_determine_stop_reason_none_when_nothing_holds() -> None:
    assert determine_stop_reason(stopping_conditions()) is None


def test_determine_stop_reason_question_answered() -> None:
    conditions = stopping_conditions(question_answered_at_required_level=True)
    assert determine_stop_reason(conditions) is StopReason.QUESTION_ANSWERED


def test_determine_stop_reason_prioritizes_cancellation_over_budget() -> None:
    conditions = stopping_conditions(user_cancelled_or_task_expired=True, budget_exhausted=True)
    assert determine_stop_reason(conditions) is StopReason.USER_CANCELLED_OR_TASK_EXPIRED


def test_determine_stop_reason_prioritizes_guardrail_over_question_answered() -> None:
    conditions = stopping_conditions(
        guardrail_or_policy_blocks_further_work=True,
        question_answered_at_required_level=True,
    )
    assert determine_stop_reason(conditions) is StopReason.GUARDRAIL_OR_POLICY_BLOCK


def test_stopping_report_requires_a_current_state_summary() -> None:
    with pytest.raises(ValueError, match="current state summary"):
        StoppingReport(stop_reason=StopReason.BUDGET_EXHAUSTED, current_state_summary="   ")


def test_stopping_report_constructs_cleanly() -> None:
    example = StoppingReport(
        stop_reason=StopReason.BUDGET_EXHAUSTED,
        current_state_summary="Time budget exhausted with two hypotheses still active.",
    )
    assert example.stop_reason is StopReason.BUDGET_EXHAUSTED
