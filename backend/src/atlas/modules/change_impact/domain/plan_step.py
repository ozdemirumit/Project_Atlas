"""ATLAS-044 SS23: plan-step analysis.

Reuses `runbook_engine.domain.risk_impact.DurationRange` for per-step duration and
`change_impact.domain.scenario_risk.RiskLevel` for per-step risk, rather than parallel scales --
both already exist in this module for exactly this purpose. SS23's "reordering requires a new plan
and impact version" and "parameter or target changes invalidate affected analysis" are process
rules about *when* to recalculate, not properties of one step analysis itself; they are handled by
SS25's recalculation triggers in `change_impact.domain.freshness`, not duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.change_impact.domain.scenario_risk import RiskLevel
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.risk_impact import DurationRange


@dataclass(frozen=True, slots=True)
class PlanStepAnalysis:
    """SS23: "each step has target, effect, duration, risk, and checkpoint." "Temporary states
    between steps are included" is `temporary_state_description`; "stop and rollback points
    identify which prior steps remain active" is `remains_active_if_stopped_here`."""

    step_id: str
    target_entity_id: str
    effect: str
    duration_range: DurationRange
    risk_level: RiskLevel
    checkpoint: str
    is_irreversible: bool
    remains_active_if_stopped_here: bool
    temporary_state_description: str | None
    shared_dependencies_with_parallel_steps: tuple[str, ...]
    combined_load_note: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.step_id, "step_id")
        validate_stable_identifier(self.target_entity_id, "target_entity_id")
        if not self.effect.strip():
            raise ValueError("a plan step analysis requires an effect")
        if not self.checkpoint.strip():
            raise ValueError("a plan step analysis requires a checkpoint")


def earliest_irreversible_step(
    step_analyses: tuple[PlanStepAnalysis, ...],
) -> PlanStepAnalysis | None:
    """SS23: "a later safe step does not hide earlier irreversible impact." `step_analyses` is
    expected in plan order (matching `ChangeStepSpec.order`); returns the first irreversible step,
    if any, so a caller presenting cumulative risk cannot let a later, safer step overwrite it."""
    for step in step_analyses:
        if step.is_irreversible:
            return step
    return None


@dataclass(frozen=True, slots=True)
class CumulativePlanAnalysis:
    """SS23: "multi-step changes are analyzed both per step and cumulatively.\""""

    change_request_id: str
    plan_version: int
    step_analyses: tuple[PlanStepAnalysis, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.change_request_id, "change_request_id")
        if self.plan_version < 1:
            raise ValueError("a cumulative plan analysis requires a positive plan version")
        if not self.step_analyses:
            raise ValueError("a cumulative plan analysis requires at least one step analysis")
        step_ids = [step.step_id for step in self.step_analyses]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("a cumulative plan analysis must not repeat a step")
