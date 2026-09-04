from __future__ import annotations

import pytest

from atlas.modules.ai_agents.domain.routing import (
    ParallelAgentGroup,
    RouterFallback,
    RoutingDecision,
    RoutingFactors,
    SpecialistArtifactReference,
    can_invoke_self_recursively,
    is_smallest_sufficient_role_set,
    synthesis_can_force_false_consensus,
)


def factors(**overrides: object) -> RoutingFactors:
    defaults: dict[str, object] = {
        "task_type": "health_deviation_analysis",
        "domain": "storage",
        "risk_level": "low",
        "evidence_need": "moderate",
        "available_validated_agent_ids": ("agent.health-analysis",),
    }
    defaults.update(overrides)
    return RoutingFactors(**defaults)  # type: ignore[arg-type]


def test_routing_factors_requires_available_agents() -> None:
    with pytest.raises(ValueError, match="at least one available validated agent"):
        factors(available_validated_agent_ids=())


def test_routing_decision_requires_agents_or_fallback() -> None:
    with pytest.raises(ValueError, match="either selected agents or a fallback"):
        RoutingDecision(
            task_id="task.example",
            selected_agent_ids=(),
            factors=factors(),
            fallback=None,
            rationale="No agents matched and no fallback chosen.",
        )


def test_routing_decision_rejects_both_agents_and_fallback() -> None:
    with pytest.raises(ValueError, match="cannot also select agents"):
        RoutingDecision(
            task_id="task.example",
            selected_agent_ids=("agent.health-analysis",),
            factors=factors(),
            fallback=RouterFallback.SAFE_REFUSAL,
            rationale="Ambiguous.",
        )


def test_routing_decision_accepts_selected_agents() -> None:
    decision = RoutingDecision(
        task_id="task.example",
        selected_agent_ids=("agent.health-analysis",),
        factors=factors(),
        fallback=None,
        rationale="Task type matches the Health Analysis Agent.",
    )
    assert decision.selected_agent_ids == ("agent.health-analysis",)


def test_routing_decision_accepts_fallback() -> None:
    decision = RoutingDecision(
        task_id="task.example",
        selected_agent_ids=(),
        factors=factors(),
        fallback=RouterFallback.HUMAN_CLARIFICATION,
        rationale="Target is ambiguous.",
    )
    assert decision.fallback is RouterFallback.HUMAN_CLARIFICATION


def test_is_smallest_sufficient_role_set_true_when_equal() -> None:
    assert is_smallest_sufficient_role_set(selected_count=2, minimum_sufficient_count=2) is True


def test_is_smallest_sufficient_role_set_false_when_larger() -> None:
    assert is_smallest_sufficient_role_set(selected_count=3, minimum_sufficient_count=2) is False


def test_parallel_agent_group_requires_independence() -> None:
    with pytest.raises(ValueError, match="independent bounded analyses"):
        ParallelAgentGroup(agent_ids=("agent.a", "agent.b"), is_independent=False, max_fan_out=3)


def test_parallel_agent_group_requires_at_least_two_agents() -> None:
    with pytest.raises(ValueError, match="at least two agents"):
        ParallelAgentGroup(agent_ids=("agent.a",), is_independent=True, max_fan_out=3)


def test_parallel_agent_group_rejects_exceeding_max_fan_out() -> None:
    with pytest.raises(ValueError, match="exceeds max_fan_out"):
        ParallelAgentGroup(
            agent_ids=("agent.a", "agent.b", "agent.c"), is_independent=True, max_fan_out=2
        )


def test_specialist_artifact_reference_requires_positive_version() -> None:
    with pytest.raises(ValueError, match="positive version"):
        SpecialistArtifactReference(
            agent_id="agent.health-analysis", artifact_id="artifact.example", artifact_version=0
        )


def test_synthesis_never_forces_false_consensus() -> None:
    assert synthesis_can_force_false_consensus() is False


def test_can_invoke_self_recursively_requires_approved_pattern() -> None:
    assert can_invoke_self_recursively(has_approved_bounded_pattern=False) is False
    assert can_invoke_self_recursively(has_approved_bounded_pattern=True) is True
