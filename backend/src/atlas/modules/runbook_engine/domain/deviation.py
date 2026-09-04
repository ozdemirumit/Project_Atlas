"""ATLAS-045 SS26: deviation handling.

SS26: "deviations become feedback candidates, not automatic runbook changes." `DeviationRecord`
is frozen and carries only references (`plan_id`/`step_id`), never a runbook mutation -- turning
a recorded deviation into an actual feedback/revision candidate is the "outcome and improvement"
slice's job (SS27, not yet built in this codebase), not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.plan_generation import DerivedPlan


class DeviationKind(StrEnum):
    PLANNED = "planned"
    UNPLANNED = "unplanned"
    EMERGENCY = "emergency"


class DeviationDecision(StrEnum):
    """SS26: "operator records reason, actual state, impact, and decision.\""""

    CONTINUE = "continue"
    PAUSE = "pause"
    STOP = "stop"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class DeviationRecord:
    deviation_id: str
    plan_id: str
    step_id: str
    kind: DeviationKind
    reason: str
    actual_state: str
    impact: str
    decision: DeviationDecision
    recorded_by: str
    recorded_at: datetime
    new_plan_version_id: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.deviation_id, "deviation_id")
        validate_stable_identifier(self.plan_id, "plan_id")
        validate_stable_identifier(self.step_id, "step_id")
        if not self.reason.strip():
            raise ValueError("a deviation record requires a reason")
        if not self.actual_state.strip():
            raise ValueError("a deviation record requires the actual state")
        if not self.impact.strip():
            raise ValueError("a deviation record requires an impact statement")
        if not self.recorded_by.strip():
            raise ValueError("a deviation record requires who recorded it")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        is_planned = self.kind is DeviationKind.PLANNED
        if is_planned and self.new_plan_version_id is None:
            raise ValueError(
                "SS26: planned deviations create a new plan version -- new_plan_version_id is"
                " required"
            )
        if not is_planned and self.new_plan_version_id is not None:
            raise ValueError("new_plan_version_id is only meaningful for a PLANNED deviation")


def should_pause_for_deviation(
    *, kind: DeviationKind, is_consequential: bool, safe_to_pause: bool
) -> bool:
    """SS26: "unplanned deviation pauses consequential progression where safe.\""""
    return kind is DeviationKind.UNPLANNED and is_consequential and safe_to_pause


def deviation_invalidates_approval(
    *, original_plan: DerivedPlan, deviated_plan: DerivedPlan
) -> bool:
    """SS26: "a different target, parameter, step order, capability, or rollback invalidates
    bound approval." Compares what `DerivedPlan` (slice 11) can actually express -- target and
    bound parameters. Step order, capability, and rollback comparisons would need the plan's
    bound step sequence, which `DerivedPlan` does not carry (it binds parameters/evidence/
    policy/impact, not an ordered step list) -- checked here only for what is real, not
    fabricated for the rest."""
    return (
        original_plan.target_id != deviated_plan.target_id
        or original_plan.bound_parameters != deviated_plan.bound_parameters
    )
