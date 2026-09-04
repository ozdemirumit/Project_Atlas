from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.guardrails.domain.models import GuardrailOutcome
from atlas.modules.guardrails.domain.tool_use_guardrails import (
    ToolCallProposal,
    ToolUseLimits,
    decide_tool_call,
    validate_tool_call,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def proposal(**overrides: object) -> ToolCallProposal:
    defaults: dict[str, object] = {
        "proposal_id": "tool-call-proposal.example",
        "tool_id": "tool.storage-health-read",
        "connector_id": "connector.hitachi-ops-center",
        "contract_version": "1.0",
        "agent_id": "agent.diagnostics",
        "task_id": "task.example",
        "target_id": "target.example",
        "target_environment_id": "environment.production",
        "typed_parameters": (("target_id", "target.example"),),
        "timeout_seconds": 30,
        "max_retries": 1,
        "idempotency_key": "idempotency.example",
        "destination_reference": None,
        "proposed_at": NOW,
    }
    defaults.update(overrides)
    return ToolCallProposal(**defaults)  # type: ignore[arg-type]


def limits(**overrides: object) -> ToolUseLimits:
    defaults: dict[str, object] = {
        "max_timeout_seconds": 60,
        "max_retries": 2,
        "allowed_tool_ids": frozenset({"tool.storage-health-read"}),
        "allowed_agent_ids": frozenset({"agent.diagnostics"}),
        "allowed_destination_references": frozenset(),
    }
    defaults.update(overrides)
    return ToolUseLimits(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_proposal_within_limits_has_no_violations() -> None:
    assert validate_tool_call(proposal(), limits=limits()) == ()


def test_a_tool_not_in_the_allowlist_is_a_violation() -> None:
    violations = validate_tool_call(proposal(tool_id="tool.unapproved"), limits=limits())
    assert any("tool.unapproved" in v for v in violations)


def test_an_agent_not_in_the_allowlist_is_a_violation() -> None:
    violations = validate_tool_call(proposal(agent_id="agent.unapproved"), limits=limits())
    assert any("agent.unapproved" in v for v in violations)


def test_no_typed_parameters_is_a_violation() -> None:
    violations = validate_tool_call(proposal(typed_parameters=()), limits=limits())
    assert any("typed parameters" in v for v in violations)


def test_timeout_exceeding_the_limit_is_a_violation() -> None:
    violations = validate_tool_call(
        proposal(timeout_seconds=120), limits=limits(max_timeout_seconds=60)
    )
    assert any("timeout" in v for v in violations)


def test_retries_exceeding_the_limit_is_a_violation() -> None:
    violations = validate_tool_call(proposal(max_retries=5), limits=limits(max_retries=2))
    assert any("retry" in v for v in violations)


def test_an_unallowlisted_destination_is_a_violation() -> None:
    violations = validate_tool_call(
        proposal(destination_reference="destination.unapproved"), limits=limits()
    )
    assert any("destination.unapproved" in v for v in violations)


def test_an_allowlisted_destination_has_no_violation() -> None:
    violations = validate_tool_call(
        proposal(destination_reference="destination.approved"),
        limits=limits(allowed_destination_references=frozenset({"destination.approved"})),
    )
    assert violations == ()


def test_decide_tool_call_passes_a_well_formed_proposal() -> None:
    decision = decide_tool_call(
        proposal(),
        limits=limits(),
        now=NOW,
        decision_id="guardrail-decision.example",
        correlation_id="correlation.example",
    )
    assert decision.outcome is GuardrailOutcome.PASS


def test_decide_tool_call_blocks_an_unapproved_tool() -> None:
    decision = decide_tool_call(
        proposal(tool_id="tool.unapproved"),
        limits=limits(),
        now=NOW,
        decision_id="guardrail-decision.example",
        correlation_id="correlation.example",
    )
    assert decision.outcome is GuardrailOutcome.BLOCK
    assert "tool.unapproved" in decision.detail


def test_proposal_rejects_a_blank_contract_version() -> None:
    with pytest.raises(ValueError, match="contract version"):
        proposal(contract_version="   ")


def test_proposal_rejects_a_blank_idempotency_key() -> None:
    with pytest.raises(ValueError, match="idempotency key"):
        proposal(idempotency_key="   ")


def test_proposal_rejects_a_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        proposal(timeout_seconds=0)


def test_proposal_rejects_a_negative_retry_count() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        proposal(max_retries=-1)


def test_proposal_rejects_a_naive_proposed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        proposal(proposed_at=datetime(2026, 9, 4, 12, 0))


def test_limits_reject_non_positive_max_timeout() -> None:
    with pytest.raises(ValueError, match="max_timeout_seconds"):
        limits(max_timeout_seconds=0)


def test_limits_reject_negative_max_retries() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        limits(max_retries=-1)
