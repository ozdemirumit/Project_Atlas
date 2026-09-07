"""ATLAS-040 SS22: audit, completing AI Agents.

`record_agent_output` maps `AgentOutputEnvelope` (SS15) onto the platform's own `atlas.core.audit.
AuditRecord`/`AuditSink` -- the seventh subsystem this session to record through that primitive.
The wrapped `ReasoningArtifact.component_versions` already carries "agent and prompt version,
model profile ... graph, knowledge ... policy references" (SS22's own list), so this covers most
of SS22 in one call; `record_termination` audits SS18's termination report as its own event,
separate from output creation, matching this session's established pattern for a distinct-in-time
event.

SS22 also explicitly names "routing, handoff, tool request, authorization, and result references"
as recorded -- `record_agent_routing_decision`, `record_agent_handoff`, and
`record_agent_tool_request` close that remaining coverage, each its own event at the moment the
underlying domain decision is made (SS9's `RoutingDecision`, SS10's `AgentHandoffContract`, and
SS11/SS12's `ToolCallRequest` plus the `effective_authority_grants_access` outcome).
"""

from __future__ import annotations

from datetime import datetime

from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.ai_agents.domain.handoff import AgentHandoffContract
from atlas.modules.ai_agents.domain.output_envelope import AgentOutputEnvelope
from atlas.modules.ai_agents.domain.routing import RoutingDecision
from atlas.modules.ai_agents.domain.termination_concurrency import AgentTerminationReport
from atlas.modules.ai_agents.domain.tool_access import ToolCallRequest


def private_model_reasoning_is_stored() -> bool:
    """SS22: "private model reasoning is not stored. Concise reasoning summaries and evidence
    lineage are retained.\""""
    return False


async def record_agent_output(
    sink: AuditSink,
    envelope: AgentOutputEnvelope,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    versions = envelope.reasoning_artifact.component_versions
    stop_reason = envelope.reasoning_artifact.stop_reason
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.ai_agents.output",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=envelope.created_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=(
                envelope.required_permission_ids[0] if envelope.required_permission_ids else None
            ),
            resource_type="ai_agents.output_envelope",
            scope_reference=envelope.envelope_id,
            decision_id=None,
            outcome="requires_human_review" if envelope.requires_human_review else "completed",
            result_code=f"agent.{envelope.agent_id}.version_{envelope.agent_definition_version}",
            target_metadata=(
                ("task_id", envelope.task_id),
                ("agent_version", versions.agent_version or ""),
                ("prompt_version", versions.prompt_version or ""),
                ("model_version", versions.model_version or ""),
                ("graph_version", versions.graph_version or ""),
                ("knowledge_version", versions.knowledge_version or ""),
                ("policy_version", versions.policy_version or ""),
                ("reasoning_artifact_id", envelope.reasoning_artifact.artifact_id),
                ("stop_reason", stop_reason.value if stop_reason is not None else ""),
            ),
        )
    )


async def record_termination(
    sink: AuditSink,
    report: AgentTerminationReport,
    *,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.ai_agents.termination",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="ai_agents.task",
            scope_reference=report.task_id,
            decision_id=None,
            outcome=report.reason.value,
            result_code=f"termination.{report.reason.value}",
            target_metadata=(
                ("unavailable_evidence_count", str(len(report.unavailable_evidence))),
                ("unresolved_question_count", str(len(report.unresolved_questions))),
                ("safe_next_step_count", str(len(report.safe_next_steps))),
            ),
        )
    )


async def record_agent_routing_decision(
    sink: AuditSink,
    decision: RoutingDecision,
    *,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.ai_agents.routing",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="ai_agents.routing_decision",
            scope_reference=decision.task_id,
            decision_id=None,
            outcome="fallback" if decision.fallback is not None else "routed",
            result_code=(
                f"routing.fallback.{decision.fallback.value}"
                if decision.fallback is not None
                else f"routing.selected_{len(decision.selected_agent_ids)}_agents"
            ),
            target_metadata=(
                ("task_type", decision.factors.task_type),
                ("domain", decision.factors.domain),
                ("risk_level", decision.factors.risk_level),
                ("selected_agent_ids", ",".join(decision.selected_agent_ids)),
            ),
        )
    )


async def record_agent_handoff(
    sink: AuditSink,
    handoff: AgentHandoffContract,
    *,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.ai_agents.handoff",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="ai_agents.handoff_contract",
            scope_reference=handoff.handoff_id,
            decision_id=None,
            outcome="succeeded",
            result_code=f"handoff.{handoff.task_contract_id}",
            target_metadata=(
                ("source_agent_version", str(handoff.source_agent_version)),
                ("destination_agent_version", str(handoff.destination_agent_version)),
                ("completed_tool_call_count", str(len(handoff.completed_tool_calls))),
                ("failed_tool_call_count", str(len(handoff.failed_tool_calls))),
            ),
        )
    )


async def record_agent_tool_request(
    sink: AuditSink,
    request: ToolCallRequest,
    *,
    authorized: bool,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.ai_agents.tool_request",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=request.agent_id,
            actor_type="automation",
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="ai_agents.tool_call_request",
            scope_reference=request.tool_id,
            decision_id=None,
            outcome="granted" if authorized else "denied",
            result_code=f"tool_request.{request.capability_class.value}",
            target_metadata=(
                ("task_id", request.task_id),
                ("target_scope", ",".join(request.target_scope)),
            ),
        )
    )
