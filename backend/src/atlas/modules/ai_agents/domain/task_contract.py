"""ATLAS-040 SS8: the task contract.

Reuses `guardrails.domain.agent_guardrails.AgentBudget` again for "time, tool-call, context, and
resource budgets" and `atlas.core.capabilities.CapabilityClass` for the capability-class ceiling,
matching `definition.AgentDefinition`'s own reuse -- a task contract's budget/ceiling are scoped
per-task, distinct instances of the same shapes, not the agent definition's own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.guardrails.domain.agent_guardrails import AgentBudget
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class TaskContract:
    """SS8's ten declared elements."""

    task_id: str
    user_request: str
    normalized_intent: str
    authenticated_subject_id: str
    permitted_organizational_scope: frozenset[str]
    target_ids: tuple[str, ...]
    environment_id: str | None
    time_range_start: datetime | None
    time_range_end: datetime | None
    requested_outcome: str
    acceptable_artifact_types: tuple[str, ...]
    allowed_data_classes: tuple[DataClassification, ...]
    allowed_tool_capabilities: tuple[str, ...]
    capability_class_ceiling: CapabilityClass
    required_freshness_seconds: int
    required_evidence_quality: str
    budget: AgentBudget
    requires_human_review: bool
    requires_approval: bool
    cancellation_token: str
    expires_at: datetime
    correlation_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.task_id, "task_id")
        if not self.user_request.strip():
            raise ValueError("a task contract requires a user request")
        if not self.normalized_intent.strip():
            raise ValueError("a task contract requires a normalized intent")
        validate_stable_identifier(self.authenticated_subject_id, "authenticated_subject_id")
        if not self.permitted_organizational_scope:
            raise ValueError("a task contract requires a permitted organizational scope")
        if not self.requested_outcome.strip():
            raise ValueError("a task contract requires a requested outcome")
        if not self.acceptable_artifact_types:
            raise ValueError("a task contract requires at least one acceptable artifact type")
        if not self.allowed_data_classes:
            raise ValueError("a task contract requires at least one allowed data class")
        if not self.allowed_tool_capabilities:
            raise ValueError("a task contract requires at least one allowed tool capability")
        if self.required_freshness_seconds < 1:
            raise ValueError("required_freshness_seconds must be positive")
        if not self.required_evidence_quality.strip():
            raise ValueError("a task contract requires a required evidence quality")
        for field_name, value in (
            ("time_range_start", self.time_range_start),
            ("time_range_end", self.time_range_end),
            ("expires_at", self.expires_at),
            ("created_at", self.created_at),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if (
            self.time_range_start is not None
            and self.time_range_end is not None
            and self.time_range_end < self.time_range_start
        ):
            raise ValueError("time_range_end must not precede time_range_start")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if not self.cancellation_token.strip():
            raise ValueError("a task contract requires a cancellation token")
        if not self.correlation_id.strip():
            raise ValueError("a task contract requires a correlation id")


def is_ambiguous_target_scope_or_purpose(contract: TaskContract) -> bool:
    """SS8: "ambiguous target, scope, or purpose is resolved before a potentially consequential
    tool request." Concrete proxy: no target named, no environment named, or the normalized
    intent is identical to the raw request -- i.e., no actual normalization occurred."""
    return (
        not contract.target_ids
        or contract.environment_id is None
        or contract.normalized_intent.strip() == contract.user_request.strip()
    )
