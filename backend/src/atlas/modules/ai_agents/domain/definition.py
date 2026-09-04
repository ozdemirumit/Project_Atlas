"""ATLAS-040 SS7: the agent definition contract.

Reuses `guardrails.domain.agent_guardrails.AgentBudget` (ATLAS-047 SS21) directly for SS7's
"context, token, time, tool-call, retry" budgets -- that type already models exactly this shape.
`model_endpoint_reference` names an `ai.domain.models.ModelEndpointProfile.endpoint_id` (ATLAS-014)
by reference rather than embedding the whole profile, since an agent definition does not own model
endpoints. `capability_class_ceiling` reuses `atlas.core.capabilities.CapabilityClass` directly.
`AgentLifecycleState` is defined here, ahead of its own SS25 slice, the same way Reasoning's
`StopReason` and Decision Engine's `DecisionSupersessionState` were defined in an aggregator slice
before their dedicated lifecycle/stopping-rules slices built the fuller transition logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.ai_agents.domain.catalog import AgentRole
from atlas.modules.guardrails.domain.agent_guardrails import AgentBudget
from atlas.modules.identity.domain.models import validate_stable_identifier


class AgentLifecycleState(StrEnum):
    """SS25's seven lifecycle states."""

    DRAFT = "draft"
    EVALUATING = "evaluating"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """SS7's fourteen declared elements."""

    agent_id: str
    version: int
    role: AgentRole
    name: str
    purpose: str
    owner: str
    lifecycle_state: AgentLifecycleState
    model_endpoint_reference: str
    supported_model_capabilities: tuple[str, ...]
    prompt_template_version: str
    instruction_hierarchy_profile: str
    accepted_task_types: tuple[str, ...]
    input_schema_version: str
    output_schema_version: str
    required_evidence_fields: tuple[str, ...]
    allowed_tool_categories: tuple[str, ...]
    allowed_data_classes: tuple[DataClassification, ...]
    capability_class_ceiling: CapabilityClass
    required_permission_id: str
    required_scope: frozenset[str]
    budget: AgentBudget
    cost_budget_units: float | None
    memory_policy: str
    memory_retention_class: str
    guardrail_profile_id: str
    policy_profile_id: str
    validation_profile_id: str
    handoff_conditions: tuple[str, ...]
    termination_conditions: tuple[str, ...]
    evaluation_suite_ids: tuple[str, ...]
    supported_domains: tuple[str, ...]
    known_limitations: tuple[str, ...]
    compatible_model_ids: tuple[str, ...]
    release_reference: str
    rollback_reference: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.agent_id, "agent_id")
        if self.version < 1:
            raise ValueError("an agent definition requires a positive version")
        if not self.name.strip():
            raise ValueError("an agent definition requires a name")
        if not self.purpose.strip():
            raise ValueError("an agent definition requires a purpose")
        if not self.owner.strip():
            raise ValueError("an agent definition requires an owner")
        if not self.model_endpoint_reference.strip():
            raise ValueError("an agent definition requires a model endpoint reference")
        if not self.accepted_task_types:
            raise ValueError("an agent definition requires at least one accepted task type")
        if not self.input_schema_version.strip():
            raise ValueError("an agent definition requires an input schema version")
        if not self.output_schema_version.strip():
            raise ValueError("an agent definition requires an output schema version")
        if not self.allowed_tool_categories:
            raise ValueError("an agent definition requires at least one allowed tool category")
        if not self.allowed_data_classes:
            raise ValueError("an agent definition requires at least one allowed data class")
        if not self.required_permission_id.strip():
            raise ValueError("an agent definition requires a required permission id")
        if not self.memory_policy.strip():
            raise ValueError("an agent definition requires a memory policy")
        if not self.memory_retention_class.strip():
            raise ValueError("an agent definition requires a memory retention class")
        if not self.guardrail_profile_id.strip():
            raise ValueError("an agent definition requires a guardrail profile id")
        if not self.policy_profile_id.strip():
            raise ValueError("an agent definition requires a policy profile id")
        if not self.validation_profile_id.strip():
            raise ValueError("an agent definition requires a validation profile id")
        if not self.termination_conditions:
            raise ValueError("an agent definition requires at least one termination condition")
        if not self.evaluation_suite_ids:
            raise ValueError("an agent definition requires at least one evaluation suite")
        if not self.release_reference.strip():
            raise ValueError("an agent definition requires a release reference")
        if self.cost_budget_units is not None and self.cost_budget_units < 0:
            raise ValueError("cost_budget_units must not be negative")


def definition_change_requires_new_version(
    *,
    behavior_changed: bool,
    tool_access_changed: bool,
    evidence_use_changed: bool,
    risk_changed: bool,
) -> bool:
    """SS7: "a definition change that can alter behavior, tool access, evidence use, or risk
    produces a new version.\""""
    return behavior_changed or tool_access_changed or evidence_use_changed or risk_changed
