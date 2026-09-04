from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.ai_agents.domain.output_envelope import AgentOutputEnvelope
from atlas.modules.reasoning.domain.artifact import ComponentVersions, ReasoningArtifact
from atlas.modules.reasoning.domain.claims import ConfidenceCategory
from atlas.modules.reasoning.domain.confidence import ConfidenceAssessment
from atlas.modules.reasoning.domain.framing import ProblemFrame, UrgencyLevel

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


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
        "alternatives": ("Resource saturation on controller B.",),
        "stop_reason": None,
        "recommended_next_evidence": "Path error counters on both fabrics.",
        "component_versions": ComponentVersions(
            agent_version="reasoning-agent.v1",
            model_version=None,
            prompt_version=None,
            tool_version=None,
            graph_version="graph-snapshot.v3",
            knowledge_version=None,
            policy_version=None,
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


def test_envelope_accepts_valid_state() -> None:
    assert envelope().agent_id == "agent.root-cause"


def test_envelope_requires_positive_agent_definition_version() -> None:
    with pytest.raises(ValueError, match="positive agent definition version"):
        envelope(agent_definition_version=0)


def test_envelope_requires_request_summary() -> None:
    with pytest.raises(ValueError, match="requires a request summary"):
        envelope(request_summary="")


def test_envelope_requires_timezone_aware_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        envelope(created_at=datetime(2026, 9, 4, 12, 0))


def test_envelope_wraps_real_reasoning_artifact() -> None:
    result = envelope()
    assert result.reasoning_artifact.current_conclusion == (
        "Fabric instability is the leading candidate cause."
    )
