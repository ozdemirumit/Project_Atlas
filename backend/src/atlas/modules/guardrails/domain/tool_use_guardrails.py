"""ATLAS-047 SS15: tool-use guardrails.

Capability class, policy, and approval checks already belong to Policy Engine (ATLAS-025) and the
connector invocation-authorization path this codebase already has -- this module covers what is
specific to a tool-call *proposal* itself: allowlist membership (tool, agent), typed-parameter
presence, and resource/destination bounds. SS15: "denied calls are not sent to the tool. The model
receives a bounded safe denial reason and cannot retry through a different undeclared tool" --
`decide_tool_call`'s BLOCK decision is that one bounded reason, and nothing here ever re-attempts
a denied proposal against a different tool_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.guardrails.domain.models import (
    GuardrailClass,
    GuardrailDecision,
    GuardrailOutcome,
)
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class ToolCallProposal:
    proposal_id: str
    tool_id: str
    connector_id: str
    contract_version: str
    agent_id: str
    task_id: str
    target_id: str
    target_environment_id: str
    typed_parameters: tuple[tuple[str, str], ...]
    timeout_seconds: int
    max_retries: int
    idempotency_key: str
    destination_reference: str | None
    proposed_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.proposal_id, "proposal_id")
        validate_stable_identifier(self.tool_id, "tool_id")
        validate_stable_identifier(self.connector_id, "connector_id")
        validate_stable_identifier(self.agent_id, "agent_id")
        validate_stable_identifier(self.task_id, "task_id")
        validate_stable_identifier(self.target_id, "target_id")
        validate_stable_identifier(self.target_environment_id, "target_environment_id")
        if not self.contract_version.strip():
            raise ValueError("a tool call proposal requires a contract version")
        if not self.idempotency_key.strip():
            raise ValueError("a tool call proposal requires an idempotency key")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.proposed_at.tzinfo is None:
            raise ValueError("proposed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ToolUseLimits:
    max_timeout_seconds: int
    max_retries: int
    allowed_tool_ids: frozenset[str]
    allowed_agent_ids: frozenset[str]
    allowed_destination_references: frozenset[str]

    def __post_init__(self) -> None:
        if self.max_timeout_seconds < 1:
            raise ValueError("max_timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")


def validate_tool_call(proposal: ToolCallProposal, *, limits: ToolUseLimits) -> tuple[str, ...]:
    violations: list[str] = []
    if proposal.tool_id not in limits.allowed_tool_ids:
        violations.append(f"tool {proposal.tool_id} is not in the approved tool allowlist")
    if proposal.agent_id not in limits.allowed_agent_ids:
        violations.append(f"agent {proposal.agent_id} is not authorized for this tool")
    if not proposal.typed_parameters:
        violations.append("proposal has no typed parameters to validate against a schema")
    if proposal.timeout_seconds > limits.max_timeout_seconds:
        violations.append(f"timeout exceeds the maximum of {limits.max_timeout_seconds} seconds")
    if proposal.max_retries > limits.max_retries:
        violations.append(f"retry count exceeds the maximum of {limits.max_retries}")
    if (
        proposal.destination_reference is not None
        and proposal.destination_reference not in limits.allowed_destination_references
    ):
        violations.append(f"destination {proposal.destination_reference} is not in the allowlist")
    return tuple(violations)


def decide_tool_call(
    proposal: ToolCallProposal,
    *,
    limits: ToolUseLimits,
    now: datetime,
    decision_id: str,
    correlation_id: str,
) -> GuardrailDecision:
    violations = validate_tool_call(proposal, limits=limits)
    if violations:
        return GuardrailDecision(
            decision_id=decision_id,
            decided_at=now,
            rule_id="guardrail-rule.tool-call-validation",
            rule_version=1,
            guardrail_class=GuardrailClass.PLATFORM_MINIMUM,
            input_reference=proposal.proposal_id,
            outcome=GuardrailOutcome.BLOCK,
            reason_code="tool_call_denied",
            detail="; ".join(violations),
            evidence_references=(),
            detector_version="tool-use-guardrails.v1",
            required_next_action=(
                "Propose a call to an approved, allowlisted tool within configured bounds."
            ),
            correlation_id=correlation_id,
        )
    return GuardrailDecision(
        decision_id=decision_id,
        decided_at=now,
        rule_id="guardrail-rule.tool-call-validation",
        rule_version=1,
        guardrail_class=GuardrailClass.PLATFORM_MINIMUM,
        input_reference=proposal.proposal_id,
        outcome=GuardrailOutcome.PASS,
        reason_code="tool_call_approved",
        detail="The proposal is within every checked allowlist and bound.",
        evidence_references=(),
        detector_version="tool-use-guardrails.v1",
        required_next_action="None.",
        correlation_id=correlation_id,
    )
