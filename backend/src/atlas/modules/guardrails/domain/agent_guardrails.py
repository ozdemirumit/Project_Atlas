"""ATLAS-047 SS21: agent and loop guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class AgentBudget:
    """SS21: "delegation depth, fan-out, iterations, tool calls, retries, context, and runtime
    are bounded.\""""

    max_delegation_depth: int
    max_fan_out: int
    max_iterations: int
    max_tool_calls: int
    max_retries: int
    max_context_tokens: int
    max_runtime_seconds: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("max_delegation_depth", self.max_delegation_depth),
            ("max_fan_out", self.max_fan_out),
            ("max_iterations", self.max_iterations),
            ("max_tool_calls", self.max_tool_calls),
            ("max_context_tokens", self.max_context_tokens),
            ("max_runtime_seconds", self.max_runtime_seconds),
        ):
            if value < 1:
                raise ValueError(f"{field_name} must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")


@dataclass(frozen=True, slots=True)
class AgentBudgetUsage:
    delegation_depth: int
    fan_out: int
    iterations: int
    tool_calls: int
    retries: int
    context_tokens: int
    runtime_seconds: int


def budget_exceeded_dimensions(usage: AgentBudgetUsage, *, budget: AgentBudget) -> tuple[str, ...]:
    """SS21: "budget exhaustion returns partial state and safe next step." Identifies exactly
    which dimension(s) triggered exhaustion so a caller can report why, not just that it
    happened."""
    exceeded: list[str] = []
    if usage.delegation_depth > budget.max_delegation_depth:
        exceeded.append("delegation_depth")
    if usage.fan_out > budget.max_fan_out:
        exceeded.append("fan_out")
    if usage.iterations > budget.max_iterations:
        exceeded.append("iterations")
    if usage.tool_calls > budget.max_tool_calls:
        exceeded.append("tool_calls")
    if usage.retries > budget.max_retries:
        exceeded.append("retries")
    if usage.context_tokens > budget.max_context_tokens:
        exceeded.append("context_tokens")
    if usage.runtime_seconds > budget.max_runtime_seconds:
        exceeded.append("runtime_seconds")
    return tuple(exceeded)


@dataclass(frozen=True, slots=True)
class AgentHandoff:
    """SS21: "agent handoff preserves original identity and cannot expand scope.\""""

    from_agent_id: str
    to_agent_id: str
    original_identity_id: str
    original_scope: frozenset[str]
    handoff_scope: frozenset[str]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.from_agent_id, "from_agent_id")
        validate_stable_identifier(self.to_agent_id, "to_agent_id")
        validate_stable_identifier(self.original_identity_id, "original_identity_id")

    @property
    def expands_scope(self) -> bool:
        return not self.handoff_scope.issubset(self.original_scope)


def is_valid_independent_human_approval(*, approver_is_human: bool) -> bool:
    """SS21: "parallel agents cannot approve or validate each other as independent humans." No
    agent, regardless of its relationship to the requesting task tree, can ever satisfy this --
    the check is a single, unconditional gate on whether the approver is a real human at all."""
    return approver_is_human


@dataclass(frozen=True, slots=True)
class BackgroundTaskRegistration:
    """SS21: "background tasks require named owner, expiry, and service identity.\""""

    task_id: str
    owner_identity_id: str
    service_identity_id: str
    expires_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.task_id, "task_id")
        validate_stable_identifier(self.owner_identity_id, "owner_identity_id")
        validate_stable_identifier(self.service_identity_id, "service_identity_id")
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
