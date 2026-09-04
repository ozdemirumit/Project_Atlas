"""ATLAS-040 SS10: the handoff contract.

Reuses `guardrails.domain.agent_guardrails.AgentHandoff` (ATLAS-047 SS21) directly for identity
and scope -- SS10's own "original task contract and unchanged authorization context" is exactly
what that type's `expands_scope` property exists to guard, so `AgentHandoffContract` refuses to
construct at all when the wrapped handoff would expand scope. "Handoffs ... do not grant
additional data or tools" holds by absence: this type has no field through which a handoff could
grant a tool or data class the destination agent's own definition does not already allow. "Contain
no credentials" reuses Guardrails' `detect_secret_patterns` across every free-text field.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.guardrails.domain.agent_guardrails import AgentBudget, AgentHandoff
from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class ToolCallOutcome:
    tool_id: str
    succeeded: bool
    detail: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.tool_id, "tool_id")
        if not self.detail.strip():
            raise ValueError("a tool call outcome requires a detail")


@dataclass(frozen=True, slots=True)
class AgentHandoffContract:
    """SS10's declared elements."""

    handoff_id: str
    source_agent_version: int
    destination_agent_version: int
    identity_and_scope: AgentHandoff
    task_contract_id: str
    purpose: str
    requested_output_schema: str
    facts: tuple[str, ...]
    evidence_references: tuple[str, ...]
    assumptions: tuple[str, ...]
    hypotheses: tuple[str, ...]
    unknowns: tuple[str, ...]
    data_freshness_note: str
    completed_tool_calls: tuple[ToolCallOutcome, ...]
    failed_tool_calls: tuple[ToolCallOutcome, ...]
    remaining_budget: AgentBudget
    deadline: datetime
    safety_constraints: tuple[str, ...]
    policy_constraints: tuple[str, ...]
    user_constraints: tuple[str, ...]
    correlation_id: str
    parent_artifact_reference: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.handoff_id, "handoff_id")
        if self.source_agent_version < 1 or self.destination_agent_version < 1:
            raise ValueError("a handoff requires positive source and destination versions")
        validate_stable_identifier(self.task_contract_id, "task_contract_id")
        if not self.purpose.strip():
            raise ValueError("a handoff requires a purpose")
        if not self.requested_output_schema.strip():
            raise ValueError("a handoff requires a requested output schema")
        if not self.data_freshness_note.strip():
            raise ValueError("a handoff requires a data freshness note")
        if self.deadline.tzinfo is None:
            raise ValueError("deadline must be timezone-aware")
        if not self.correlation_id.strip():
            raise ValueError("a handoff requires a correlation id")
        if self.identity_and_scope.expands_scope:
            raise ValueError(
                "a handoff cannot expand the original scope -- authorization context is unchanged"
            )
        for text in (
            self.purpose,
            *self.facts,
            *self.assumptions,
            *self.hypotheses,
            *self.unknowns,
        ):
            if detect_secret_patterns(text):
                raise ValueError("a handoff must not contain credentials or secret values")
