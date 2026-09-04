from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.ai_agents.domain.termination_concurrency import (
    AgentRun,
    AgentTerminationReason,
    AgentTerminationReport,
    CancellationPropagation,
    agent_can_overwrite_another_agents_artifact,
    late_result_after_cancellation_is_presented_as_current_without_review,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def report(**overrides: object) -> AgentTerminationReport:
    defaults: dict[str, object] = {
        "task_id": "task.example",
        "reason": AgentTerminationReason.BUDGET_EXHAUSTED,
        "completed_work_summary": "Retrieved health observations for controller B.",
        "unavailable_evidence": ("Path error counters unavailable.",),
        "unresolved_questions": ("Whether the fabric contributed to the deviation.",),
        "safe_next_steps": ("Retry with an extended time budget.",),
    }
    defaults.update(overrides)
    return AgentTerminationReport(**defaults)  # type: ignore[arg-type]


def test_termination_report_accepts_valid_state() -> None:
    assert report().reason is AgentTerminationReason.BUDGET_EXHAUSTED


def test_termination_report_requires_completed_work_summary() -> None:
    with pytest.raises(ValueError, match="completed work summary"):
        report(completed_work_summary="")


def test_termination_report_requires_at_least_one_safe_next_step() -> None:
    with pytest.raises(ValueError, match="at least one safe next step"):
        report(safe_next_steps=())


def test_agent_run_requires_timezone_aware_started_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AgentRun(
            run_id="agent-run.example",
            parent_task_id="task.example",
            agent_id="agent.health-analysis",
            started_at=datetime(2026, 9, 4, 12, 0),
        )


def test_cancellation_propagation_accepts_empty_cancelled_sets() -> None:
    propagation = CancellationPropagation(
        run_id="agent-run.example", cancelled_tool_call_ids=(), cancelled_child_run_ids=()
    )
    assert propagation.run_id == "agent-run.example"


def test_late_results_never_presented_as_current_without_review() -> None:
    assert late_result_after_cancellation_is_presented_as_current_without_review() is False


def test_agent_can_never_overwrite_another_agents_artifact() -> None:
    assert agent_can_overwrite_another_agents_artifact() is False
