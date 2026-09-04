from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.ai_agents.domain.task_contract import (
    TaskContract,
    is_ambiguous_target_scope_or_purpose,
)
from atlas.modules.guardrails.domain.agent_guardrails import AgentBudget

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


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


def contract(**overrides: object) -> TaskContract:
    defaults: dict[str, object] = {
        "task_id": "task.example",
        "user_request": "why is controller B slow",
        "normalized_intent": "Diagnose performance degradation on target.controller-b.",
        "authenticated_subject_id": "subject.operator",
        "permitted_organizational_scope": frozenset({"organization.example"}),
        "target_ids": ("target.controller-b",),
        "environment_id": "environment.production",
        "time_range_start": NOW - timedelta(hours=2),
        "time_range_end": NOW,
        "requested_outcome": "Identify the cause of the latency increase.",
        "acceptable_artifact_types": ("health_analysis_report",),
        "allowed_data_classes": (DataClassification.INTERNAL,),
        "allowed_tool_capabilities": ("c0_c1_observations", "graph"),
        "capability_class_ceiling": CapabilityClass.C1_READ_ONLY,
        "required_freshness_seconds": 300,
        "required_evidence_quality": "moderate",
        "budget": budget(),
        "requires_human_review": False,
        "requires_approval": False,
        "cancellation_token": "cancellation.task.example",
        "expires_at": NOW + timedelta(minutes=10),
        "correlation_id": "correlation.example",
        "created_at": NOW,
    }
    defaults.update(overrides)
    return TaskContract(**defaults)  # type: ignore[arg-type]


def test_contract_accepts_valid_state() -> None:
    assert contract().task_id == "task.example"


def test_contract_requires_normalized_intent() -> None:
    with pytest.raises(ValueError, match="normalized intent"):
        contract(normalized_intent="")


def test_contract_rejects_expiry_before_creation() -> None:
    with pytest.raises(ValueError, match="expires_at must be after created_at"):
        contract(expires_at=NOW - timedelta(minutes=1))


def test_contract_rejects_inverted_time_range() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        contract(time_range_start=NOW, time_range_end=NOW - timedelta(hours=1))


def test_contract_requires_at_least_one_target_data_class() -> None:
    with pytest.raises(ValueError, match="at least one allowed data class"):
        contract(allowed_data_classes=())


def test_is_ambiguous_true_without_target() -> None:
    assert is_ambiguous_target_scope_or_purpose(contract(target_ids=())) is True


def test_is_ambiguous_true_without_environment() -> None:
    assert is_ambiguous_target_scope_or_purpose(contract(environment_id=None)) is True


def test_is_ambiguous_true_when_intent_not_normalized() -> None:
    result = contract(normalized_intent="why is controller B slow")
    assert is_ambiguous_target_scope_or_purpose(result) is True


def test_is_ambiguous_false_for_resolved_contract() -> None:
    assert is_ambiguous_target_scope_or_purpose(contract()) is False
