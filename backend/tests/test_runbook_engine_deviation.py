from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.runbook_engine.domain.deviation import (
    DeviationDecision,
    DeviationKind,
    DeviationRecord,
    deviation_invalidates_approval,
    should_pause_for_deviation,
)
from atlas.modules.runbook_engine.domain.plan_generation import DerivedPlan, PlanOutputKind

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def deviation(**overrides: object) -> DeviationRecord:
    defaults: dict[str, object] = {
        "deviation_id": "runbook-deviation.example",
        "plan_id": "runbook-plan.example",
        "step_id": "runbook-step.example",
        "kind": DeviationKind.UNPLANNED,
        "reason": "Controller B did not respond to the initial restart command.",
        "actual_state": "Controller B remains in a degraded state after one restart attempt.",
        "impact": "Extended redundancy loss beyond the estimated duration.",
        "decision": DeviationDecision.PAUSE,
        "recorded_by": "subject.operator",
        "recorded_at": NOW,
        "new_plan_version_id": None,
    }
    defaults.update(overrides)
    return DeviationRecord(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_deviation_constructs_cleanly() -> None:
    example = deviation()
    assert example.kind is DeviationKind.UNPLANNED


def test_rejects_blank_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        deviation(reason="   ")


def test_rejects_blank_actual_state() -> None:
    with pytest.raises(ValueError, match="actual state"):
        deviation(actual_state="   ")


def test_rejects_blank_impact() -> None:
    with pytest.raises(ValueError, match="impact statement"):
        deviation(impact="   ")


def test_planned_deviation_requires_a_new_plan_version() -> None:
    with pytest.raises(ValueError, match="new_plan_version_id is required"):
        deviation(kind=DeviationKind.PLANNED, new_plan_version_id=None)


def test_planned_deviation_constructs_with_a_new_plan_version() -> None:
    example = deviation(kind=DeviationKind.PLANNED, new_plan_version_id="runbook-plan.example-v2")
    assert example.new_plan_version_id == "runbook-plan.example-v2"


def test_unplanned_deviation_cannot_carry_a_new_plan_version() -> None:
    with pytest.raises(ValueError, match="only meaningful for a PLANNED"):
        deviation(kind=DeviationKind.UNPLANNED, new_plan_version_id="runbook-plan.example-v2")


def test_emergency_deviation_constructs_without_a_new_plan_version() -> None:
    example = deviation(kind=DeviationKind.EMERGENCY, new_plan_version_id=None)
    assert example.kind is DeviationKind.EMERGENCY


def test_should_pause_for_unplanned_consequential_safe_deviation() -> None:
    assert (
        should_pause_for_deviation(
            kind=DeviationKind.UNPLANNED, is_consequential=True, safe_to_pause=True
        )
        is True
    )


def test_should_not_pause_for_planned_deviation() -> None:
    assert (
        should_pause_for_deviation(
            kind=DeviationKind.PLANNED, is_consequential=True, safe_to_pause=True
        )
        is False
    )


def test_should_not_pause_when_not_consequential() -> None:
    assert (
        should_pause_for_deviation(
            kind=DeviationKind.UNPLANNED, is_consequential=False, safe_to_pause=True
        )
        is False
    )


def test_should_not_pause_when_not_safe_to_pause() -> None:
    assert (
        should_pause_for_deviation(
            kind=DeviationKind.UNPLANNED, is_consequential=True, safe_to_pause=False
        )
        is False
    )


def plan(**overrides: object) -> DerivedPlan:
    defaults: dict[str, object] = {
        "plan_id": "runbook-plan.example",
        "kind": PlanOutputKind.HUMAN_CHECKLIST,
        "source_runbook_id": "runbook.example",
        "source_version_id": "runbook-version.example",
        "target_id": "target.example",
        "bound_parameters": (("controller_id", "controller-b"),),
        "bound_evidence_references": ("evidence.example",),
        "bound_policy_decision_id": None,
        "bound_impact_analysis_reference": None,
        "created_at": NOW,
        "created_by": "subject.requester",
    }
    defaults.update(overrides)
    return DerivedPlan(**defaults)  # type: ignore[arg-type]


def test_deviation_invalidates_approval_on_target_change() -> None:
    original = plan()
    deviated = plan(target_id="target.other")
    assert deviation_invalidates_approval(original_plan=original, deviated_plan=deviated) is True


def test_deviation_invalidates_approval_on_parameter_change() -> None:
    original = plan()
    deviated = plan(bound_parameters=(("controller_id", "controller-a"),))
    assert deviation_invalidates_approval(original_plan=original, deviated_plan=deviated) is True


def test_deviation_does_not_invalidate_approval_when_unchanged() -> None:
    original = plan()
    deviated = plan()
    assert deviation_invalidates_approval(original_plan=original, deviated_plan=deviated) is False
