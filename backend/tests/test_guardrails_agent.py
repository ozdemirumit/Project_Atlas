from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.guardrails.domain.agent_guardrails import (
    AgentBudget,
    AgentBudgetUsage,
    AgentHandoff,
    BackgroundTaskRegistration,
    budget_exceeded_dimensions,
    is_valid_independent_human_approval,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def budget(**overrides: object) -> AgentBudget:
    defaults: dict[str, object] = {
        "max_delegation_depth": 3,
        "max_fan_out": 5,
        "max_iterations": 10,
        "max_tool_calls": 20,
        "max_retries": 3,
        "max_context_tokens": 8000,
        "max_runtime_seconds": 300,
    }
    defaults.update(overrides)
    return AgentBudget(**defaults)  # type: ignore[arg-type]


def usage(**overrides: object) -> AgentBudgetUsage:
    defaults: dict[str, object] = {
        "delegation_depth": 1,
        "fan_out": 1,
        "iterations": 1,
        "tool_calls": 1,
        "retries": 0,
        "context_tokens": 100,
        "runtime_seconds": 10,
    }
    defaults.update(overrides)
    return AgentBudgetUsage(**defaults)  # type: ignore[arg-type]


def test_usage_within_budget_exceeds_nothing() -> None:
    assert budget_exceeded_dimensions(usage(), budget=budget()) == ()


def test_each_dimension_is_independently_detected() -> None:
    assert budget_exceeded_dimensions(usage(delegation_depth=10), budget=budget()) == (
        "delegation_depth",
    )
    assert budget_exceeded_dimensions(usage(fan_out=10), budget=budget()) == ("fan_out",)
    assert budget_exceeded_dimensions(usage(iterations=99), budget=budget()) == ("iterations",)
    assert budget_exceeded_dimensions(usage(tool_calls=99), budget=budget()) == ("tool_calls",)
    assert budget_exceeded_dimensions(usage(retries=99), budget=budget()) == ("retries",)
    assert budget_exceeded_dimensions(usage(context_tokens=999999), budget=budget()) == (
        "context_tokens",
    )
    assert budget_exceeded_dimensions(usage(runtime_seconds=99999), budget=budget()) == (
        "runtime_seconds",
    )


def test_multiple_exceeded_dimensions_are_all_reported() -> None:
    exceeded = budget_exceeded_dimensions(usage(delegation_depth=10, fan_out=10), budget=budget())
    assert set(exceeded) == {"delegation_depth", "fan_out"}


def test_budget_rejects_non_positive_values() -> None:
    with pytest.raises(ValueError, match="max_delegation_depth"):
        budget(max_delegation_depth=0)
    with pytest.raises(ValueError, match="max_fan_out"):
        budget(max_fan_out=0)


def test_budget_rejects_a_negative_retry_count() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        budget(max_retries=-1)


def test_a_handoff_within_original_scope_does_not_expand() -> None:
    handoff = AgentHandoff(
        from_agent_id="agent.a",
        to_agent_id="agent.b",
        original_identity_id="subject.example",
        original_scope=frozenset({"read", "diagnose"}),
        handoff_scope=frozenset({"read"}),
    )
    assert handoff.expands_scope is False


def test_a_handoff_adding_a_new_scope_expands() -> None:
    handoff = AgentHandoff(
        from_agent_id="agent.a",
        to_agent_id="agent.b",
        original_identity_id="subject.example",
        original_scope=frozenset({"read"}),
        handoff_scope=frozenset({"read", "write"}),
    )
    assert handoff.expands_scope is True


def test_a_human_approver_is_valid() -> None:
    assert is_valid_independent_human_approval(approver_is_human=True) is True


def test_an_agent_approver_is_never_valid() -> None:
    assert is_valid_independent_human_approval(approver_is_human=False) is False


def test_background_task_registration_requires_a_positive_expiry() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        BackgroundTaskRegistration(
            task_id="task.example",
            owner_identity_id="subject.example",
            service_identity_id="service.example",
            expires_at=datetime(2026, 9, 4, 12, 0),
        )


def test_background_task_registration_constructs_cleanly() -> None:
    registration = BackgroundTaskRegistration(
        task_id="task.example",
        owner_identity_id="subject.example",
        service_identity_id="service.example",
        expires_at=NOW,
    )
    assert registration.task_id == "task.example"
