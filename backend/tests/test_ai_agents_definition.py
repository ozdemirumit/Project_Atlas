from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.ai_agents.domain.catalog import AgentRole
from atlas.modules.ai_agents.domain.definition import (
    AgentDefinition,
    AgentLifecycleState,
    definition_change_requires_new_version,
)
from atlas.modules.guardrails.domain.agent_guardrails import AgentBudget


def budget() -> AgentBudget:
    return AgentBudget(
        max_delegation_depth=2,
        max_fan_out=3,
        max_iterations=10,
        max_tool_calls=20,
        max_retries=3,
        max_context_tokens=32000,
        max_runtime_seconds=120,
    )


def definition(**overrides: object) -> AgentDefinition:
    defaults: dict[str, object] = {
        "agent_id": "agent.health-analysis",
        "version": 1,
        "role": AgentRole.HEALTH_ANALYSIS_AGENT,
        "name": "Health Analysis Agent",
        "purpose": "Interpret health observations and deviations.",
        "owner": "ai-architecture-team",
        "lifecycle_state": AgentLifecycleState.ACTIVE,
        "model_endpoint_reference": "model-endpoint.primary",
        "supported_model_capabilities": ("structured_output", "tool_calling"),
        "prompt_template_version": "health-analysis.v3",
        "instruction_hierarchy_profile": "standard-agent-hierarchy.v1",
        "accepted_task_types": ("health_deviation_analysis",),
        "input_schema_version": "health-analysis-request.v1",
        "output_schema_version": "health-analysis-output.v1",
        "required_evidence_fields": ("observation_references",),
        "allowed_tool_categories": ("c0_c1_observations", "graph", "knowledge"),
        "allowed_data_classes": (DataClassification.INTERNAL,),
        "capability_class_ceiling": CapabilityClass.C1_READ_ONLY,
        "required_permission_id": "permission.health.read",
        "required_scope": frozenset({"organization.example"}),
        "budget": budget(),
        "cost_budget_units": 5.0,
        "memory_policy": "task_scoped",
        "memory_retention_class": "ephemeral",
        "guardrail_profile_id": "guardrail-profile.standard",
        "policy_profile_id": "policy-profile.standard",
        "validation_profile_id": "validation-profile.standard",
        "handoff_conditions": ("root_cause_analysis_required",),
        "termination_conditions": ("budget_exhausted", "user_cancelled"),
        "evaluation_suite_ids": ("eval-suite.health-analysis.v1",),
        "supported_domains": ("storage",),
        "known_limitations": ("Does not analyze SAN fabric telemetry.",),
        "compatible_model_ids": ("model.local-llama-70b",),
        "release_reference": "release.2026-09-01",
        "rollback_reference": None,
    }
    defaults.update(overrides)
    return AgentDefinition(**defaults)  # type: ignore[arg-type]


def test_definition_accepts_valid_state() -> None:
    assert definition().role is AgentRole.HEALTH_ANALYSIS_AGENT


def test_definition_requires_positive_version() -> None:
    with pytest.raises(ValueError, match="positive version"):
        definition(version=0)


def test_definition_requires_at_least_one_accepted_task_type() -> None:
    with pytest.raises(ValueError, match="at least one accepted task type"):
        definition(accepted_task_types=())


def test_definition_requires_at_least_one_termination_condition() -> None:
    with pytest.raises(ValueError, match="at least one termination condition"):
        definition(termination_conditions=())


def test_definition_rejects_negative_cost_budget() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        definition(cost_budget_units=-1.0)


def test_definition_change_requires_new_version_true_for_any_material_change() -> None:
    assert (
        definition_change_requires_new_version(
            behavior_changed=False,
            tool_access_changed=True,
            evidence_use_changed=False,
            risk_changed=False,
        )
        is True
    )


def test_definition_change_requires_new_version_false_for_no_material_change() -> None:
    assert (
        definition_change_requires_new_version(
            behavior_changed=False,
            tool_access_changed=False,
            evidence_use_changed=False,
            risk_changed=False,
        )
        is False
    )
