from __future__ import annotations

import pytest

from atlas.modules.change_impact.domain.interruption_duration import (
    DurationEstimate,
    DurationModel,
    DurationPhase,
    InterruptionMode,
    InterruptionModeAssessment,
)
from atlas.modules.runbook_engine.domain.risk_impact import DurationRange


def assessment(**overrides: object) -> InterruptionModeAssessment:
    defaults: dict[str, object] = {
        "mode": InterruptionMode.PERFORMANCE_DEGRADATION,
        "trigger": "Controller B failover redirects load to controller A.",
        "affected_scope_entity_ids": ("target.controller-a",),
        "duration_range": DurationRange(minimum_minutes=2, maximum_minutes=10),
        "detection": "Latency alert on controller A.",
        "recovery_expectation": "Latency returns to baseline once controller B rejoins.",
    }
    defaults.update(overrides)
    return InterruptionModeAssessment(**defaults)  # type: ignore[arg-type]


def estimate(**overrides: object) -> DurationEstimate:
    defaults: dict[str, object] = {
        "phase": DurationPhase.TRANSITION,
        "duration_range": DurationRange(minimum_minutes=1, maximum_minutes=5),
        "basis": "Median of the last 12 controller failovers in this environment.",
        "comparable_outcome_references": ("change.controller-failover.2026-06-01",),
        "vendor_guidance_reference": "vendor.doc.failover-timing",
        "extending_factors": ("Concurrent backup job in progress.",),
    }
    defaults.update(overrides)
    return DurationEstimate(**defaults)  # type: ignore[arg-type]


def model(**overrides: object) -> DurationModel:
    defaults: dict[str, object] = {
        "change_request_id": "change-request.example",
        "target_entity_id": "target.controller-b",
        "estimates": (estimate(),),
    }
    defaults.update(overrides)
    return DurationModel(**defaults)  # type: ignore[arg-type]


def test_interruption_mode_has_nine_members() -> None:
    assert len(InterruptionMode) == 9


def test_assessment_requires_trigger() -> None:
    with pytest.raises(ValueError, match="requires a trigger"):
        assessment(trigger="")


def test_assessment_requires_affected_scope() -> None:
    with pytest.raises(ValueError, match="affected scope"):
        assessment(affected_scope_entity_ids=())


def test_duration_phase_has_seven_members() -> None:
    assert len(DurationPhase) == 7


def test_duration_estimate_requires_basis() -> None:
    with pytest.raises(ValueError, match="false minute-level precision"):
        estimate(basis="")


def test_duration_model_requires_at_least_one_estimate() -> None:
    with pytest.raises(ValueError, match="at least one phase estimate"):
        model(estimates=())


def test_duration_model_rejects_duplicate_phase() -> None:
    with pytest.raises(ValueError, match="must not repeat a phase"):
        model(estimates=(estimate(), estimate()))


def test_duration_model_accepts_multiple_distinct_phases() -> None:
    result = model(
        estimates=(
            estimate(phase=DurationPhase.PREPARATION),
            estimate(phase=DurationPhase.TRANSITION),
        )
    )
    assert len(result.estimates) == 2
