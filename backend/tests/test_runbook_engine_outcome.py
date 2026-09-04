from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.runbook_engine.domain.outcome import (
    FinalOutcome,
    RunbookOutcomeRecord,
    StepOutcome,
    StepOutcomeState,
    has_sufficient_outcome_history_for_broad_validation,
    outcome_as_revision_trigger,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def step_outcome(**overrides: object) -> StepOutcome:
    defaults: dict[str, object] = {
        "step_id": "runbook-step.example",
        "state": StepOutcomeState.COMPLETED,
        "note": None,
    }
    defaults.update(overrides)
    return StepOutcome(**defaults)  # type: ignore[arg-type]


def outcome(**overrides: object) -> RunbookOutcomeRecord:
    defaults: dict[str, object] = {
        "outcome_id": "runbook-outcome.example",
        "runbook_id": "runbook.example",
        "version_id": "runbook-version.example",
        "plan_id": "runbook-plan.example",
        "target_id": "target.example",
        "starting_context": "Controller B was reported degraded via a health-check alert.",
        "step_outcomes": (step_outcome(),),
        "actual_duration_minutes": 4,
        "actual_interruption": "None observed.",
        "actual_impact": "Momentary path redundancy loss.",
        "resource_use": "One storage operator for four minutes.",
        "validation_passed": True,
        "rollback_used": False,
        "recovery_used": False,
        "final_outcome": FinalOutcome.SUCCESS,
        "operator_feedback": None,
        "missing_or_ambiguous_instructions": (),
        "related_incident_reference": "incident.example",
        "related_problem_reference": None,
        "related_change_reference": None,
        "recorded_at": NOW,
    }
    defaults.update(overrides)
    return RunbookOutcomeRecord(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_outcome_constructs_cleanly() -> None:
    example = outcome()
    assert example.final_outcome is FinalOutcome.SUCCESS


def test_rejects_blank_starting_context() -> None:
    with pytest.raises(ValueError, match="starting context"):
        outcome(starting_context="   ")


def test_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        outcome(actual_duration_minutes=-1)


def test_rejects_naive_recorded_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        outcome(recorded_at=NOW.replace(tzinfo=None))


def test_successful_outcome_with_no_feedback_does_not_trigger_revision() -> None:
    assert outcome_as_revision_trigger(outcome()) is False


def test_failed_outcome_triggers_revision() -> None:
    assert outcome_as_revision_trigger(outcome(final_outcome=FinalOutcome.FAILURE)) is True


def test_partial_success_triggers_revision() -> None:
    assert outcome_as_revision_trigger(outcome(final_outcome=FinalOutcome.PARTIAL_SUCCESS)) is True


def test_missing_instructions_trigger_revision_even_on_success() -> None:
    example = outcome(
        final_outcome=FinalOutcome.SUCCESS,
        missing_or_ambiguous_instructions=("Step 3's expected duration was unclear.",),
    )
    assert outcome_as_revision_trigger(example) is True


def test_operator_feedback_triggers_revision_even_on_success() -> None:
    example = outcome(
        final_outcome=FinalOutcome.SUCCESS,
        operator_feedback="The precondition check took longer than expected.",
    )
    assert outcome_as_revision_trigger(example) is True


def test_broad_validation_rejects_a_minimum_below_two() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        has_sufficient_outcome_history_for_broad_validation((), minimum_successful_outcomes=1)


def test_broad_validation_false_with_a_single_success() -> None:
    outcomes = (outcome(),)
    assert (
        has_sufficient_outcome_history_for_broad_validation(outcomes, minimum_successful_outcomes=2)
        is False
    )


def test_broad_validation_true_with_enough_successes() -> None:
    outcomes = (
        outcome(outcome_id="runbook-outcome.a"),
        outcome(outcome_id="runbook-outcome.b"),
    )
    assert (
        has_sufficient_outcome_history_for_broad_validation(outcomes, minimum_successful_outcomes=2)
        is True
    )


def test_broad_validation_does_not_count_failures() -> None:
    outcomes = (
        outcome(outcome_id="runbook-outcome.a"),
        outcome(outcome_id="runbook-outcome.b", final_outcome=FinalOutcome.FAILURE),
    )
    assert (
        has_sufficient_outcome_history_for_broad_validation(outcomes, minimum_successful_outcomes=2)
        is False
    )
