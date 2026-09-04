from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.modules.reasoning.application.audit import (
    exact_model_output_reproduction_is_promised,
    record_human_correction,
    record_reasoning_artifact,
)
from atlas.modules.reasoning.domain.artifact import (
    ComponentVersions,
    ReasoningArtifact,
    StopReason,
)
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


def artifact(**overrides: object) -> ReasoningArtifact:
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
        "alternatives": ("Resource saturation on controller B.",),
        "stop_reason": StopReason.DOMAIN_CONFIRMATION_MET,
        "recommended_next_evidence": None,
        "component_versions": ComponentVersions(
            agent_version="reasoning-agent.v1",
            model_version="model.v3",
            prompt_version="prompt.v2",
            tool_version=None,
            graph_version="graph-snapshot.v3",
            knowledge_version=None,
            policy_version=None,
        ),
        "created_at": NOW,
    }
    defaults.update(overrides)
    return ReasoningArtifact(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_reasoning_artifact() -> None:
    sink = RecordingAuditSink()
    await record_reasoning_artifact(
        sink,
        artifact(),
        tool_call_count=3,
        resulting_decision_references=("decision.example",),
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.reasoning.artifact.domain_confirmation_met"
    assert event.result_code == "reasoning_artifact.version_1"
    assert event.scope_reference == "reasoning-frame.example"
    assert ("tool_call_count", "3") in event.target_metadata
    assert ("agent_version", "reasoning-agent.v1") in event.target_metadata


@pytest.mark.asyncio
async def test_record_reasoning_artifact_in_progress_when_no_stop_reason() -> None:
    sink = RecordingAuditSink()
    await record_reasoning_artifact(
        sink,
        artifact(stop_reason=None),
        tool_call_count=0,
        resulting_decision_references=(),
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.reasoning.artifact.in_progress"
    assert event.outcome == "in_progress"


@pytest.mark.asyncio
async def test_record_human_correction() -> None:
    sink = RecordingAuditSink()
    await record_human_correction(
        sink,
        artifact_id="reasoning-artifact.example",
        new_version_id="reasoning-artifact.example.v2",
        corrected_by="subject.domain-expert",
        correction_note="Corrected the onset time based on syslog evidence.",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.reasoning.human_correction"
    assert event.subject_id == "subject.domain-expert"
    assert ("new_version_id", "reasoning-artifact.example.v2") in event.target_metadata


def test_exact_model_output_reproduction_is_never_promised() -> None:
    assert exact_model_output_reproduction_is_promised() is False
