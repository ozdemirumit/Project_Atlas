"""ATLAS-044 SS15/SS16: interruption model and duration model.

Reuses `runbook_engine.domain.risk_impact.DurationRange` directly for every range in this module
-- SS16's duration ranges and SS15's per-mode duration ranges are exactly the "minimum/maximum
minutes" shape that type already models and validates (ATLAS-045's own risk_impact module even
anticipates this: its `RunbookRiskImpactDuration` is deliberately "static... guidance" that
"target-specific current impact analysis takes precedence" over -- this module is that
target-specific analysis). SS16's "does not present false minute-level precision" is given a
concrete, checkable requirement: every `DurationEstimate` must carry a non-empty `basis`, so a
range can never be asserted without justification.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.risk_impact import DurationRange


class InterruptionMode(StrEnum):
    """SS15's nine impact modes."""

    NO_EXPECTED_USER_VISIBLE_INTERRUPTION = "no_expected_user_visible_interruption"
    REDUNDANCY_REDUCED_WITHOUT_CURRENT_SERVICE_LOSS = (
        "redundancy_reduced_without_current_service_loss"
    )
    PERFORMANCE_DEGRADATION = "performance_degradation"
    PARTIAL_SERVICE_UNAVAILABILITY = "partial_service_unavailability"
    INTERMITTENT_ERRORS_OR_RECONNECT_BEHAVIOR = "intermittent_errors_or_reconnect_behavior"
    PLANNED_FULL_OUTAGE = "planned_full_outage"
    UNPLANNED_OUTAGE_UNDER_FAILURE_SCENARIO = "unplanned_outage_under_failure_scenario"
    DATA_UNAVAILABILITY_OR_RECOVERY_ONLY_STATE = "data_unavailability_or_recovery_only_state"
    UNKNOWN_DUE_TO_INSUFFICIENT_EVIDENCE = "unknown_due_to_insufficient_evidence"


@dataclass(frozen=True, slots=True)
class InterruptionModeAssessment:
    """SS15: "for every mode, Atlas states trigger, affected scope, duration range, detection,
    and recovery expectation.\""""

    mode: InterruptionMode
    trigger: str
    affected_scope_entity_ids: tuple[str, ...]
    duration_range: DurationRange
    detection: str
    recovery_expectation: str

    def __post_init__(self) -> None:
        if not self.trigger.strip():
            raise ValueError("an interruption mode assessment requires a trigger")
        if not self.affected_scope_entity_ids:
            raise ValueError("an interruption mode assessment requires an affected scope")
        if not self.detection.strip():
            raise ValueError("an interruption mode assessment requires a detection description")
        if not self.recovery_expectation.strip():
            raise ValueError("an interruption mode assessment requires a recovery expectation")


class DurationPhase(StrEnum):
    """SS16's seven duration phases."""

    PREPARATION = "preparation"
    TRANSITION = "transition"
    IMPLEMENTATION = "implementation"
    STABILIZATION = "stabilization"
    VALIDATION = "validation"
    ROLLBACK = "rollback"
    RECOVERY = "recovery"


@dataclass(frozen=True, slots=True)
class DurationEstimate:
    phase: DurationPhase
    duration_range: DurationRange
    basis: str
    comparable_outcome_references: tuple[str, ...]
    vendor_guidance_reference: str | None
    extending_factors: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.basis.strip():
            raise ValueError(
                "a duration estimate requires a basis -- Atlas does not present false "
                "minute-level precision"
            )


@dataclass(frozen=True, slots=True)
class DurationModel:
    change_request_id: str
    target_entity_id: str
    estimates: tuple[DurationEstimate, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.change_request_id, "change_request_id")
        validate_stable_identifier(self.target_entity_id, "target_entity_id")
        if not self.estimates:
            raise ValueError("a duration model requires at least one phase estimate")
        phases = [estimate.phase for estimate in self.estimates]
        if len(phases) != len(set(phases)):
            raise ValueError("a duration model must not repeat a phase")
