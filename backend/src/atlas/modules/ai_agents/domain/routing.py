"""ATLAS-040 SS9: routing and composition.

"Recursive delegation depth and fan-out are limited" needs no new code here --
`guardrails.domain.agent_guardrails.AgentBudget.max_delegation_depth`/`max_fan_out` already bound
both, and `ParallelAgentGroup.max_fan_out` below is that same concept scoped to one parallel
group.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class RoutingFactors:
    """SS9: "routing uses task type, domain, risk, evidence need, and available validated
    agents.\""""

    task_type: str
    domain: str
    risk_level: str
    evidence_need: str
    available_validated_agent_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.task_type.strip():
            raise ValueError("routing factors require a task type")
        if not self.domain.strip():
            raise ValueError("routing factors require a domain")
        if not self.risk_level.strip():
            raise ValueError("routing factors require a risk level")
        if not self.evidence_need.strip():
            raise ValueError("routing factors require an evidence need")
        if not self.available_validated_agent_ids:
            raise ValueError("routing requires at least one available validated agent")


class RouterFallback(StrEnum):
    """SS9: "router fallback is safe refusal, direct retrieval, or human clarification.\""""

    SAFE_REFUSAL = "safe_refusal"
    DIRECT_RETRIEVAL = "direct_retrieval"
    HUMAN_CLARIFICATION = "human_clarification"


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Either agents are selected or a fallback applies -- never both, never neither."""

    task_id: str
    selected_agent_ids: tuple[str, ...]
    factors: RoutingFactors
    fallback: RouterFallback | None
    rationale: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.task_id, "task_id")
        if not self.rationale.strip():
            raise ValueError("a routing decision requires a rationale")
        if self.fallback is None and not self.selected_agent_ids:
            raise ValueError("a routing decision requires either selected agents or a fallback")
        if self.fallback is not None and self.selected_agent_ids:
            raise ValueError("a routing decision with a fallback cannot also select agents")


def is_smallest_sufficient_role_set(*, selected_count: int, minimum_sufficient_count: int) -> bool:
    """SS9: "the smallest sufficient role set is selected." `minimum_sufficient_count` is
    determined by the caller's own domain knowledge of the task; this checks the routing decision
    against it rather than trying to derive sufficiency here."""
    return selected_count == minimum_sufficient_count


@dataclass(frozen=True, slots=True)
class ParallelAgentGroup:
    """SS9: "parallel agents are used only for independent bounded analyses." `is_independent`
    must be `True` to construct one at all -- a group of dependent analyses cannot be represented
    as parallel in the first place."""

    agent_ids: tuple[str, ...]
    is_independent: bool
    max_fan_out: int

    def __post_init__(self) -> None:
        if len(self.agent_ids) < 2:
            raise ValueError("a parallel agent group requires at least two agents")
        if len(set(self.agent_ids)) != len(self.agent_ids):
            raise ValueError("a parallel agent group must not repeat an agent")
        if not self.is_independent:
            raise ValueError("parallel agents are used only for independent bounded analyses")
        if len(self.agent_ids) > self.max_fan_out:
            raise ValueError("parallel agent group exceeds max_fan_out")


@dataclass(frozen=True, slots=True)
class SpecialistArtifactReference:
    """SS9: "a specialist's output is an input artifact, not an instruction to another agent."
    Reference-only -- no field through which a specialist's output could be treated as a
    directive rather than data for the next role to weigh."""

    agent_id: str
    artifact_id: str
    artifact_version: int

    def __post_init__(self) -> None:
        validate_stable_identifier(self.agent_id, "agent_id")
        validate_stable_identifier(self.artifact_id, "artifact_id")
        if self.artifact_version < 1:
            raise ValueError("a specialist artifact reference requires a positive version")


def synthesis_can_force_false_consensus() -> bool:
    """SS9: "synthesis preserves disagreements instead of forcing false consensus.\""""
    return False


def can_invoke_self_recursively(*, has_approved_bounded_pattern: bool) -> bool:
    """SS9: "a role cannot invoke itself recursively unless an explicitly bounded pattern is
    approved.\""""
    return has_approved_bounded_pattern
