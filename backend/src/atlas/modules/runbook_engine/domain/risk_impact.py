"""ATLAS-045 SS12: risk, impact, and duration.

This is the runbook's own static, authored declaration -- a different bounded context from
`explainability.domain.risk_impact.RiskImpactExplanation`, which renders an already-computed
`ApprovalPacket`'s impact for presentation. SS12's own precedence rule -- "static runbook
estimates are guidance; target-specific current impact analysis takes precedence" -- is given a
concrete call site by `effective_duration_range` rather than left as a convention a caller has to
remember unaided.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class DurationRange:
    minimum_minutes: int
    maximum_minutes: int

    def __post_init__(self) -> None:
        if self.minimum_minutes < 0 or self.maximum_minutes < 0:
            raise ValueError("duration minutes must not be negative")
        if self.minimum_minutes > self.maximum_minutes:
            raise ValueError("minimum_minutes must not exceed maximum_minutes")


def effective_duration_range(
    *, static: DurationRange, target_specific: DurationRange | None
) -> DurationRange:
    """SS12: "static runbook estimates are guidance. Target-specific current impact analysis
    takes precedence.\""""
    return static if target_specific is None else target_specific


@dataclass(frozen=True, slots=True)
class RunbookRiskImpactDuration:
    """SS12's declared elements for one runbook version."""

    runbook_id: str
    version_id: str
    direct_affected_systems: tuple[str, ...]
    transitive_affected_systems: tuple[str, ...]
    affected_services: tuple[str, ...]
    interruption_expected_mode: str
    interruption_range: DurationRange
    preparation_duration: DurationRange
    execution_duration: DurationRange
    stabilization_duration: DurationRange
    validation_duration: DurationRange
    rollback_duration: DurationRange
    recovery_duration: DurationRange
    redundancy_effect: str
    capacity_effect: str
    data_effect: str
    security_effect: str
    compliance_effect: str
    worst_credible_outcome: str
    residual_risk: str
    point_of_no_return_step_id: str | None
    irreversible_step_ids: tuple[str, ...]
    requires_target_specific_impact_analysis: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.runbook_id, "runbook_id")
        validate_stable_identifier(self.version_id, "version_id")
        if not self.interruption_expected_mode.strip():
            raise ValueError("a risk/impact declaration requires an expected interruption mode")
        if not self.worst_credible_outcome.strip():
            raise ValueError("a risk/impact declaration requires a worst credible outcome")
        if not self.residual_risk.strip():
            raise ValueError("a risk/impact declaration requires a residual risk statement")
        if self.point_of_no_return_step_id is not None:
            validate_stable_identifier(
                self.point_of_no_return_step_id, "point_of_no_return_step_id"
            )
