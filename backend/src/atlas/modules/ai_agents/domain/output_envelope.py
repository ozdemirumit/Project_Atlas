"""ATLAS-040 SS15: the agent output envelope.

Wraps `reasoning.domain.artifact.ReasoningArtifact` (ATLAS-041 SS22) directly rather than
re-capturing any of its fields: SS15's "facts and observations," "evidence and citations,"
"inferences and hypotheses," "assumptions, unknowns, conflicts, and freshness," and "confidence
representation and rationale" are exactly the eleven elements that artifact already aggregates.
This module adds only what a reasoning artifact does not carry -- the agent/task/correlation
envelope around it, and optional references out to Change Impact's `ImpactResult` and a
recommendation, for the roles whose output actually touches those domains.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.artifact import ReasoningArtifact


@dataclass(frozen=True, slots=True)
class AgentOutputEnvelope:
    """SS15's declared elements."""

    envelope_id: str
    agent_id: str
    agent_definition_version: int
    task_id: str
    correlation_id: str
    request_summary: str
    reasoning_artifact: ReasoningArtifact
    affected_component_ids: tuple[str, ...]
    affected_service_ids: tuple[str, ...]
    recommendation_reference: str | None
    impact_result_reference: str | None
    required_permission_ids: tuple[str, ...]
    required_policy_references: tuple[str, ...]
    requires_human_review: bool
    created_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.envelope_id, "envelope_id")
        validate_stable_identifier(self.agent_id, "agent_id")
        if self.agent_definition_version < 1:
            raise ValueError("an output envelope requires a positive agent definition version")
        validate_stable_identifier(self.task_id, "task_id")
        if not self.correlation_id.strip():
            raise ValueError("an output envelope requires a correlation id")
        if not self.request_summary.strip():
            raise ValueError("an output envelope requires a request summary")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
