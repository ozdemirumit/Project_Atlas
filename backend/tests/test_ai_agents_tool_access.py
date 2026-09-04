from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.ai_agents.domain.tool_access import (
    EffectiveAuthorityInputs,
    ToolCallRequest,
    ToolOutputEnvelope,
    approval_can_expand_effective_authority,
    effective_authority_grants_access,
    is_available_to_agents,
    is_normal_agent_access_baseline,
    requires_explicit_design_and_possible_approval,
    tool_output_is_trusted,
)


@pytest.mark.parametrize(
    ("capability_class", "expected"),
    [
        (CapabilityClass.C0_INFORMATIONAL, True),
        (CapabilityClass.C1_READ_ONLY, True),
        (CapabilityClass.C2_DIAGNOSTIC, True),
        (CapabilityClass.C3_CONTROLLED_CHANGE, False),
        (CapabilityClass.C4_SERVICE_IMPACTING, False),
        (CapabilityClass.C5_DESTRUCTIVE, False),
    ],
)
def test_is_available_to_agents(capability_class: CapabilityClass, expected: bool) -> None:
    assert is_available_to_agents(capability_class) is expected


@pytest.mark.parametrize(
    ("capability_class", "expected"),
    [
        (CapabilityClass.C0_INFORMATIONAL, True),
        (CapabilityClass.C1_READ_ONLY, True),
        (CapabilityClass.C2_DIAGNOSTIC, False),
    ],
)
def test_is_normal_agent_access_baseline(capability_class: CapabilityClass, expected: bool) -> None:
    assert is_normal_agent_access_baseline(capability_class) is expected


def test_requires_explicit_design_only_for_c2() -> None:
    assert requires_explicit_design_and_possible_approval(CapabilityClass.C2_DIAGNOSTIC) is True
    assert requires_explicit_design_and_possible_approval(CapabilityClass.C1_READ_ONLY) is False


def test_tool_call_request_requires_target_scope() -> None:
    with pytest.raises(ValueError, match="target scope"):
        ToolCallRequest(
            tool_id="tool.example",
            agent_id="agent.example",
            task_id="task.example",
            typed_parameters=(),
            target_scope=(),
            timeout_seconds=5.0,
            idempotency_key=None,
            correlation_id="correlation.example",
            capability_class=CapabilityClass.C1_READ_ONLY,
        )


def test_tool_call_request_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        ToolCallRequest(
            tool_id="tool.example",
            agent_id="agent.example",
            task_id="task.example",
            typed_parameters=(),
            target_scope=("target.example",),
            timeout_seconds=0.0,
            idempotency_key=None,
            correlation_id="correlation.example",
            capability_class=CapabilityClass.C1_READ_ONLY,
        )


def grants(**overrides: object) -> EffectiveAuthorityInputs:
    defaults: dict[str, object] = {
        "authenticated_user_scope_grants": True,
        "service_identity_permission_grants": True,
        "agent_definition_allowlist_grants": True,
        "task_contract_grants": True,
        "workflow_constraint_grants": True,
        "policy_and_guardrail_grants": True,
        "tool_and_connector_capability_grants": True,
        "current_environment_state_grants": True,
    }
    defaults.update(overrides)
    return EffectiveAuthorityInputs(**defaults)  # type: ignore[arg-type]


def test_effective_authority_true_when_every_element_grants() -> None:
    assert effective_authority_grants_access(grants()) is True


def test_effective_authority_false_when_any_element_denies() -> None:
    assert effective_authority_grants_access(grants(policy_and_guardrail_grants=False)) is False


def test_approval_never_expands_effective_authority() -> None:
    assert approval_can_expand_effective_authority() is False


def test_tool_output_never_trusted() -> None:
    assert tool_output_is_trusted() is False


def test_tool_output_envelope_rejects_exceeding_size_bound() -> None:
    with pytest.raises(ValueError, match="exceeds its size bound"):
        ToolOutputEnvelope(
            tool_id="tool.example",
            raw_size_bytes=2000,
            size_bound_bytes=1000,
            classification=DataClassification.INTERNAL,
            normalized=True,
            prompt_injection_scan_passed=True,
        )
