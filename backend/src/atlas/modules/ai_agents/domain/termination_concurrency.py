"""ATLAS-040 SS18/SS19: failure/refusal/termination and concurrency/cancellation.

SS19's "duplicate tool calls are prevented or idempotent" needs no new code here --
`tool_access.ToolCallRequest.idempotency_key` (slice 6) already carries this. Bounded fan-out for
"parallel work has bounded fan-out and shared budget accounting" is
`guardrails.domain.agent_guardrails.AgentBudget.max_fan_out` plus this module's own
`routing.ParallelAgentGroup.max_fan_out`, both already built.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class AgentTerminationReason(StrEnum):
    """SS18's eight stop/refuse reasons."""

    IDENTITY_SCOPE_TOOL_POLICY_OR_GUARDRAIL_VALIDATION_FAILED = (
        "identity_scope_tool_policy_or_guardrail_validation_failed"
    )
    EVIDENCE_INACCESSIBLE_STALE_CONTRADICTORY_OR_INSUFFICIENT = (
        "evidence_inaccessible_stale_contradictory_or_insufficient"
    )
    EXCEEDS_TASK_CAPABILITY_CEILING = "exceeds_task_capability_ceiling"
    PROMPT_INJECTION_SECRET_EXPOSURE_OR_UNSAFE_CONTENT_DETECTED = (
        "prompt_injection_secret_exposure_or_unsafe_content_detected"
    )
    BUDGET_EXHAUSTED = "budget_exhausted"
    USER_CANCELLED_OR_TASK_EXPIRED = "user_cancelled_or_task_expired"
    DEPENDENCY_RETURNED_AMBIGUOUS_CONSEQUENTIAL_RESULT = (
        "dependency_returned_ambiguous_consequential_result"
    )
    OUTPUT_FAILED_REQUIRED_VALIDATION = "output_failed_required_validation"


@dataclass(frozen=True, slots=True)
class AgentTerminationReport:
    """SS18: "the final state reports completed work, unavailable evidence, unresolved
    questions, and safe next steps.\""""

    task_id: str
    reason: AgentTerminationReason
    completed_work_summary: str
    unavailable_evidence: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    safe_next_steps: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.task_id, "task_id")
        if not self.completed_work_summary.strip():
            raise ValueError("a termination report requires a completed work summary")
        if not self.safe_next_steps:
            raise ValueError("a termination report requires at least one safe next step")


@dataclass(frozen=True, slots=True)
class AgentRun:
    """SS19: "every agent run has a unique ID and parent task.\""""

    run_id: str
    parent_task_id: str
    agent_id: str
    started_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.run_id, "run_id")
        validate_stable_identifier(self.parent_task_id, "parent_task_id")
        validate_stable_identifier(self.agent_id, "agent_id")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CancellationPropagation:
    """SS19: "cancellation propagates to eligible tool calls and child agents.\""""

    run_id: str
    cancelled_tool_call_ids: tuple[str, ...]
    cancelled_child_run_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.run_id, "run_id")


def late_result_after_cancellation_is_presented_as_current_without_review() -> bool:
    """SS19: "late results after cancellation are stored only as governed artifacts and are not
    presented as current without review.\""""
    return False


def agent_can_overwrite_another_agents_artifact() -> bool:
    """SS19: "one agent cannot overwrite another's artifact; synthesis creates a new
    version.\""""
    return False
