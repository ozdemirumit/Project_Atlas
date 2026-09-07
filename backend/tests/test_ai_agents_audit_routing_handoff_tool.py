from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.modules.ai_agents.application.audit import (
    record_agent_handoff,
    record_agent_routing_decision,
    record_agent_tool_request,
)
from atlas.modules.ai_agents.domain.handoff import AgentHandoffContract
from atlas.modules.ai_agents.domain.routing import RouterFallback, RoutingDecision, RoutingFactors
from atlas.modules.ai_agents.domain.tool_access import ToolCallRequest
from atlas.modules.guardrails.domain.agent_guardrails import AgentBudget, AgentHandoff

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.recorded: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.recorded.append(event)


def _factors(**overrides: object) -> RoutingFactors:
    values: dict[str, object] = {
        "task_type": "root_cause_analysis",
        "domain": "storage",
        "risk_level": "moderate",
        "evidence_need": "health_observations",
        "available_validated_agent_ids": ("agent.root-cause",),
    }
    values.update(overrides)
    return RoutingFactors(**values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_agent_routing_decision_with_selected_agents() -> None:
    sink = RecordingAuditSink()
    decision = RoutingDecision(
        task_id="task.example",
        selected_agent_ids=("agent.root-cause",),
        factors=_factors(),
        fallback=None,
        rationale="Root-cause agent is validated for the storage domain.",
    )
    await record_agent_routing_decision(
        sink,
        decision,
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.routing",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.ai_agents.routing"
    assert event.outcome == "routed"
    assert ("selected_agent_ids", "agent.root-cause") in event.target_metadata


@pytest.mark.asyncio
async def test_record_agent_routing_decision_with_fallback() -> None:
    sink = RecordingAuditSink()
    decision = RoutingDecision(
        task_id="task.example",
        selected_agent_ids=(),
        factors=_factors(),
        fallback=RouterFallback.HUMAN_CLARIFICATION,
        rationale="No validated agent exists for this domain.",
    )
    await record_agent_routing_decision(
        sink,
        decision,
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.routing",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.outcome == "fallback"
    assert event.result_code == "routing.fallback.human_clarification"


@pytest.mark.asyncio
async def test_record_agent_handoff() -> None:
    sink = RecordingAuditSink()
    handoff = AgentHandoffContract(
        handoff_id="handoff.example",
        source_agent_version=1,
        destination_agent_version=1,
        identity_and_scope=AgentHandoff(
            from_agent_id="agent.root-cause",
            to_agent_id="agent.recommendation",
            original_identity_id="identity.subject.example",
            original_scope=frozenset({"scope.storage.read"}),
            handoff_scope=frozenset({"scope.storage.read"}),
        ),
        task_contract_id="task-contract.example",
        purpose="Hand off confirmed findings for recommendation generation.",
        requested_output_schema="schema.recommendation.v1",
        facts=("Controller B reports degraded status.",),
        evidence_references=("evidence.health-check.001",),
        assumptions=(),
        hypotheses=(),
        unknowns=(),
        data_freshness_note="Evidence collected within the last five minutes.",
        completed_tool_calls=(),
        failed_tool_calls=(),
        remaining_budget=AgentBudget(
            max_delegation_depth=2,
            max_fan_out=3,
            max_iterations=10,
            max_tool_calls=20,
            max_retries=3,
            max_context_tokens=8000,
            max_runtime_seconds=120,
        ),
        deadline=NOW + timedelta(minutes=10),
        safety_constraints=(),
        policy_constraints=(),
        user_constraints=(),
        correlation_id="correlation.example",
        parent_artifact_reference=None,
    )
    await record_agent_handoff(
        sink,
        handoff,
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.handoff",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.ai_agents.handoff"
    assert event.scope_reference == "handoff.example"
    assert ("source_agent_version", "1") in event.target_metadata


@pytest.mark.asyncio
async def test_record_agent_tool_request_granted_and_denied() -> None:
    sink = RecordingAuditSink()
    request = ToolCallRequest(
        tool_id="tool.hitachi.health-read",
        agent_id="agent.root-cause",
        task_id="task.example",
        typed_parameters=(("target_id", "asset.storage.a"),),
        target_scope=("asset.storage.a",),
        timeout_seconds=30.0,
        idempotency_key=None,
        correlation_id="correlation.example",
        capability_class=CapabilityClass.C1_READ_ONLY,
    )
    await record_agent_tool_request(
        sink,
        request,
        authorized=True,
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.tool-request.1",
        producer="test-producer",
        producer_version="0.0.0",
    )
    await record_agent_tool_request(
        sink,
        request,
        authorized=False,
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.tool-request.2",
        producer="test-producer",
        producer_version="0.0.0",
    )
    granted, denied = sink.recorded
    assert granted.outcome == "granted"
    assert denied.outcome == "denied"
    assert granted.event_type == "atlas.ai_agents.tool_request"
    assert granted.subject_id == "agent.root-cause"
