from __future__ import annotations

import pytest

from atlas.modules.change_impact.domain.plan_step import (
    CumulativePlanAnalysis,
    PlanStepAnalysis,
    earliest_irreversible_step,
)
from atlas.modules.change_impact.domain.scenario_risk import RiskLevel
from atlas.modules.runbook_engine.domain.risk_impact import DurationRange


def step(**overrides: object) -> PlanStepAnalysis:
    defaults: dict[str, object] = {
        "step_id": "change-step.example",
        "target_entity_id": "target.controller-b",
        "effect": "Controller B fails over to controller A.",
        "duration_range": DurationRange(minimum_minutes=1, maximum_minutes=5),
        "risk_level": RiskLevel.MODERATE,
        "checkpoint": "Controller A reports controller B offline.",
        "is_irreversible": False,
        "remains_active_if_stopped_here": True,
        "temporary_state_description": "Controller B is offline, controller A is active.",
        "shared_dependencies_with_parallel_steps": (),
        "combined_load_note": None,
    }
    defaults.update(overrides)
    return PlanStepAnalysis(**defaults)  # type: ignore[arg-type]


def plan(**overrides: object) -> CumulativePlanAnalysis:
    defaults: dict[str, object] = {
        "change_request_id": "change-request.example",
        "plan_version": 1,
        "step_analyses": (step(),),
    }
    defaults.update(overrides)
    return CumulativePlanAnalysis(**defaults)  # type: ignore[arg-type]


def test_plan_step_analysis_accepts_valid_state() -> None:
    assert step().effect.startswith("Controller B")


def test_plan_step_analysis_requires_effect() -> None:
    with pytest.raises(ValueError, match="requires an effect"):
        step(effect="")


def test_plan_step_analysis_requires_checkpoint() -> None:
    with pytest.raises(ValueError, match="requires a checkpoint"):
        step(checkpoint="")


def test_earliest_irreversible_step_returns_none_when_all_reversible() -> None:
    assert earliest_irreversible_step((step(), step(step_id="change-step.two"))) is None


def test_earliest_irreversible_step_returns_first_irreversible() -> None:
    first = step(step_id="change-step.one", is_irreversible=True)
    second = step(step_id="change-step.two", is_irreversible=False)
    assert earliest_irreversible_step((first, second)) is first


def test_earliest_irreversible_step_not_hidden_by_later_safe_step() -> None:
    irreversible = step(step_id="change-step.destroy", is_irreversible=True)
    safe = step(step_id="change-step.validate", is_irreversible=False)
    assert earliest_irreversible_step((irreversible, safe)) is irreversible


def test_cumulative_plan_analysis_requires_at_least_one_step() -> None:
    with pytest.raises(ValueError, match="at least one step analysis"):
        plan(step_analyses=())


def test_cumulative_plan_analysis_rejects_duplicate_step() -> None:
    with pytest.raises(ValueError, match="must not repeat a step"):
        plan(step_analyses=(step(), step()))


def test_cumulative_plan_analysis_requires_positive_plan_version() -> None:
    with pytest.raises(ValueError, match="positive plan version"):
        plan(plan_version=0)
