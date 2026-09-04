from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.reasoning.domain.claims import ConfidenceCategory
from atlas.modules.reasoning.domain.framing import (
    FramingAmbiguityDisclosure,
    FramingAmbiguityKind,
    ProblemFrame,
    UrgencyLevel,
)

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
        "available_evidence_classes": ("health_check", "connector_observation"),
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


def test_a_well_formed_frame_constructs_cleanly() -> None:
    example = frame()
    assert example.urgency is UrgencyLevel.MODERATE


def test_rejects_blank_question() -> None:
    with pytest.raises(ValueError, match="question"):
        frame(question="   ")


def test_rejects_no_targets() -> None:
    with pytest.raises(ValueError, match="at least one target"):
        frame(target_ids=())


def test_rejects_naive_first_known_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        frame(first_known_time=NOW.replace(tzinfo=None))


def test_rejects_analysis_window_end_before_start() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        frame(analysis_window_start=NOW, analysis_window_end=NOW - timedelta(hours=1))


def test_rejects_non_positive_required_freshness() -> None:
    with pytest.raises(ValueError, match="positive"):
        frame(required_freshness_seconds=0)


def test_rejects_no_success_conditions() -> None:
    with pytest.raises(ValueError, match="success condition"):
        frame(success_conditions=())


def test_rejects_no_stopping_conditions() -> None:
    with pytest.raises(ValueError, match="stopping condition"):
        frame(stopping_conditions=())


def test_has_disclosed_ambiguity_false_by_default() -> None:
    assert frame().has_disclosed_ambiguity is False


def test_has_disclosed_ambiguity_true_with_a_disclosure() -> None:
    disclosure = FramingAmbiguityDisclosure(
        kind=FramingAmbiguityKind.AMBIGUOUS_TARGET_IDENTITY,
        disclosure="Two targets share the same hostname across environments; both are included.",
    )
    example = frame(ambiguity_disclosures=(disclosure,))
    assert example.has_disclosed_ambiguity is True


def test_ambiguity_disclosure_requires_text() -> None:
    with pytest.raises(ValueError, match="requires text"):
        FramingAmbiguityDisclosure(kind=FramingAmbiguityKind.MIXED_ENVIRONMENTS, disclosure="   ")
