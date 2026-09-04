from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.ai_agents.domain.handoff import AgentHandoffContract, ToolCallOutcome
from atlas.modules.guardrails.domain.agent_guardrails import AgentBudget, AgentHandoff

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def identity_and_scope(**overrides: object) -> AgentHandoff:
    defaults: dict[str, object] = {
        "from_agent_id": "agent.troubleshooting",
        "to_agent_id": "agent.root-cause",
        "original_identity_id": "subject.operator",
        "original_scope": frozenset({"organization.example"}),
        "handoff_scope": frozenset({"organization.example"}),
    }
    defaults.update(overrides)
    return AgentHandoff(**defaults)  # type: ignore[arg-type]


def budget() -> AgentBudget:
    return AgentBudget(
        max_delegation_depth=1,
        max_fan_out=1,
        max_iterations=5,
        max_tool_calls=10,
        max_retries=2,
        max_context_tokens=16000,
        max_runtime_seconds=60,
    )


def handoff(**overrides: object) -> AgentHandoffContract:
    defaults: dict[str, object] = {
        "handoff_id": "handoff.example",
        "source_agent_version": 1,
        "destination_agent_version": 1,
        "identity_and_scope": identity_and_scope(),
        "task_contract_id": "task.example",
        "purpose": "Rank causal hypotheses for the observed latency deviation.",
        "requested_output_schema": "root-cause-output.v1",
        "facts": ("Controller B latency increased at 11:45 UTC.",),
        "evidence_references": ("evidence.health-check.2026-09-04",),
        "assumptions": ("No concurrent maintenance is scheduled.",),
        "hypotheses": ("Controller B firmware regression.",),
        "unknowns": ("Whether the regression affects controller A.",),
        "data_freshness_note": "Health observations are 3 minutes old.",
        "completed_tool_calls": (
            ToolCallOutcome(tool_id="tool.health-observations", succeeded=True, detail="200 OK"),
        ),
        "failed_tool_calls": (),
        "remaining_budget": budget(),
        "deadline": NOW + timedelta(minutes=5),
        "safety_constraints": ("No destructive actions.",),
        "policy_constraints": ("C1 read-only only.",),
        "user_constraints": ("Respond within 5 minutes.",),
        "correlation_id": "correlation.example",
        "parent_artifact_reference": None,
    }
    defaults.update(overrides)
    return AgentHandoffContract(**defaults)  # type: ignore[arg-type]


def test_handoff_accepts_valid_state() -> None:
    assert handoff().handoff_id == "handoff.example"


def test_handoff_requires_purpose() -> None:
    with pytest.raises(ValueError, match="requires a purpose"):
        handoff(purpose="")


def test_handoff_rejects_scope_expansion() -> None:
    expanded = identity_and_scope(
        handoff_scope=frozenset({"organization.example", "organization.other"})
    )
    with pytest.raises(ValueError, match="cannot expand the original scope"):
        handoff(identity_and_scope=expanded)


def test_handoff_rejects_secret_in_facts() -> None:
    with pytest.raises(ValueError, match="must not contain credentials"):
        handoff(facts=("api_key: AKIAABCDEFGHIJKLMNOP",))


def test_handoff_rejects_secret_in_purpose() -> None:
    with pytest.raises(ValueError, match="must not contain credentials"):
        handoff(purpose="Use api_key: AKIAABCDEFGHIJKLMNOP to authenticate.")


def test_tool_call_outcome_requires_detail() -> None:
    with pytest.raises(ValueError, match="requires a detail"):
        ToolCallOutcome(tool_id="tool.example", succeeded=False, detail="")
