from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.modules.ai_agents.application.audit import (
    private_model_reasoning_is_stored,
    record_agent_output,
    record_termination,
)
from atlas.modules.ai_agents.domain.output_envelope import AgentOutputEnvelope
from atlas.modules.ai_agents.domain.termination_concurrency import (
    AgentTerminationReason,
    AgentTerminationReport,
)
from atlas.modules.reasoning.domain.artifact import ComponentVersions, ReasoningArtifact
from atlas.modules.reasoning.domain.claims import ConfidenceCategory
from atlas.modules.reasoning.domain.confidence import ConfidenceAssessment
from atlas.modules.reasoning.domain.framing import ProblemFrame, UrgencyLevel

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.recorded: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.recorded.append(event)


def frame(**overrides: object) -> ProblemFrame:
    defaults: dict[str, object] = {
        "frame_id": "reasoning-frame.example",
        "question": "Why did controller B degrade?",
        "desired_decision": "Whether a restart is safe to recommend.",
        "target_ids": ("target.example",),
        "business_service_ids": ("service.file-shares",),
        "environment_id": "environment.production",
        "site_id": "site.example",
        "organizational_boundary": "organization.example",
        "symptom": "Controller B reports degraded status.",
        "expected_state": "Both controllers report healthy.",
        "actual_state": "Controller B reports degraded, controller A reports healthy.",
        "first_known_time": NOW - timedelta(hours=1),
        "analysis_window_start": NOW - timedelta(hours=2),
        "analysis_window_end": NOW,
        "timezone": "UTC",
        "current_impact": "No customer-facing impact observed yet.",
        "urgency": UrgencyLevel.MODERATE,
        "available_evidence_classes": ("health_check",),
        "inaccessible_evidence_classes": (),
        "required_freshness_seconds": 300,
        "required_confidence": ConfidenceCategory.MODERATE,
        "capability_class_ceiling": CapabilityClass.C2_DIAGNOSTIC,
        "success_conditions": ("A root-cause hypothesis is supported by independent evidence.",),
        "stopping_conditions": ("No further safe diagnostic checks remain.",),
        "ambiguity_disclosures": (),
    }
    defaults.update(overrides)
    return ProblemFrame(**defaults)  # type: ignore[arg-type]


def confidence(**overrides: object) -> ConfidenceAssessment:
    defaults: dict[str, object] = {
        "category": ConfidenceCategory.MODERATE,
        "supporting_factors": ("Two independent evidence units support the claim.",),
        "reducing_factors": (),
        "important_unknowns": (),
        "what_would_change_it": "A confirmed path-failure event would raise confidence.",
        "numeric_score": None,
        "numeric_score_calibration_reference": None,
    }
    defaults.update(overrides)
    return ConfidenceAssessment(**defaults)  # type: ignore[arg-type]


def reasoning_artifact(**overrides: object) -> ReasoningArtifact:
    defaults: dict[str, object] = {
        "artifact_id": "reasoning-artifact.example",
        "version": 1,
        "prior_version_id": None,
        "frame": frame(),
        "evidence_inventory": (),
        "quality_assessments": (),
        "timeline": (),
        "claims": (),
        "hypotheses": (),
        "assumptions": (),
        "unknowns": (),
        "conflicts": (),
        "excluded_evidence_ids": (),
        "selected_checks": (),
        "check_results": (),
        "confidence": confidence(),
        "current_conclusion": "Fabric instability is the leading candidate cause.",
        "alternatives": (),
        "stop_reason": None,
        "recommended_next_evidence": None,
        "component_versions": ComponentVersions(
            agent_version="root-cause-agent.v1",
            model_version="model.local-llama-70b",
            prompt_version="root-cause.v3",
            tool_version=None,
            graph_version="graph-snapshot.v3",
            knowledge_version="knowledge.v5",
            policy_version="policy-set.v2",
        ),
        "created_at": NOW,
    }
    defaults.update(overrides)
    return ReasoningArtifact(**defaults)  # type: ignore[arg-type]


def envelope(**overrides: object) -> AgentOutputEnvelope:
    defaults: dict[str, object] = {
        "envelope_id": "output-envelope.example",
        "agent_id": "agent.root-cause",
        "agent_definition_version": 1,
        "task_id": "task.example",
        "correlation_id": "correlation.example",
        "request_summary": "Why did controller B degrade?",
        "reasoning_artifact": reasoning_artifact(),
        "affected_component_ids": ("target.controller-b",),
        "affected_service_ids": ("service.file-shares",),
        "recommendation_reference": None,
        "impact_result_reference": None,
        "required_permission_ids": ("permission.storage.read",),
        "required_policy_references": (),
        "requires_human_review": False,
        "created_at": NOW,
    }
    defaults.update(overrides)
    return AgentOutputEnvelope(**defaults)  # type: ignore[arg-type]


def test_private_model_reasoning_never_stored() -> None:
    assert private_model_reasoning_is_stored() is False


@pytest.mark.asyncio
async def test_record_agent_output() -> None:
    sink = RecordingAuditSink()
    await record_agent_output(
        sink,
        envelope(),
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.ai_agents.output"
    assert event.result_code == "agent.agent.root-cause.version_1"
    assert ("prompt_version", "root-cause.v3") in event.target_metadata
    assert ("graph_version", "graph-snapshot.v3") in event.target_metadata
    assert event.outcome == "completed"


@pytest.mark.asyncio
async def test_record_agent_output_reflects_human_review_requirement() -> None:
    sink = RecordingAuditSink()
    await record_agent_output(
        sink,
        envelope(requires_human_review=True),
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert sink.recorded[0].outcome == "requires_human_review"


@pytest.mark.asyncio
async def test_record_termination() -> None:
    sink = RecordingAuditSink()
    report = AgentTerminationReport(
        task_id="task.example",
        reason=AgentTerminationReason.BUDGET_EXHAUSTED,
        completed_work_summary="Retrieved health observations for controller B.",
        unavailable_evidence=("Path error counters unavailable.",),
        unresolved_questions=(),
        safe_next_steps=("Retry with an extended time budget.",),
    )
    await record_termination(
        sink,
        report,
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.ai_agents.termination"
    assert event.outcome == "budget_exhausted"
    assert ("unavailable_evidence_count", "1") in event.target_metadata
