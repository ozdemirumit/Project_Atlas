"""ATLAS-046 SS16: risk and impact explanation.

Reuses the already-built `approvals.domain.models.ApprovalPacket`'s risk/impact fields (blast
radius, interruption modes, duration ranges, recovery) as its source of truth rather than
re-capturing the same data a second time -- `risk_impact_from_approval_packet` renders that
existing data into SS16's explanation shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.approvals.domain.models import ApprovalPacket


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class RiskLabel:
    """SS16: "risk labels include rationale and are not represented by color alone.\""""

    level: RiskLevel
    rationale: str

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise ValueError("a risk label requires a rationale, not color alone (SS16)")


@dataclass(frozen=True, slots=True)
class RiskImpactExplanation:
    affected_components: tuple[str, ...]
    affected_services: tuple[str, ...]
    overall_risk: RiskLabel
    interruption_expected_mode: str
    interruption_worst_credible_mode: str
    duration_minimum_minutes: int
    duration_maximum_minutes: int
    recovery_duration_minimum_minutes: int
    recovery_duration_maximum_minutes: int
    assumptions: tuple[str, ...]
    graph_gaps: tuple[str, ...]
    preconditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    rollback_feasible: bool

    def __post_init__(self) -> None:
        if self.duration_minimum_minutes < 0 or self.duration_maximum_minutes < 0:
            raise ValueError("duration minutes must not be negative")
        if self.duration_minimum_minutes > self.duration_maximum_minutes:
            raise ValueError("duration_minimum_minutes must not exceed duration_maximum_minutes")
        if self.recovery_duration_minimum_minutes < 0 or self.recovery_duration_maximum_minutes < 0:
            raise ValueError("recovery duration minutes must not be negative")
        if self.recovery_duration_minimum_minutes > self.recovery_duration_maximum_minutes:
            raise ValueError(
                "recovery_duration_minimum_minutes must not exceed"
                " recovery_duration_maximum_minutes"
            )
        if not self.interruption_expected_mode.strip():
            raise ValueError("a risk/impact explanation requires an expected interruption mode")
        if not self.interruption_worst_credible_mode.strip():
            raise ValueError(
                "a risk/impact explanation requires a worst-credible interruption mode"
            )


def risk_impact_from_approval_packet(
    packet: ApprovalPacket, *, overall_risk: RiskLabel
) -> RiskImpactExplanation:
    """`overall_risk` is supplied separately since `ApprovalPacket.overall_risk` is a plain
    string, not a rationale-bearing `RiskLabel` -- the caller, who already has both the raw
    string and its supporting rationale, supplies the properly-typed version."""
    return RiskImpactExplanation(
        affected_components=packet.affected_components,
        affected_services=packet.possibly_affected_services,
        overall_risk=overall_risk,
        interruption_expected_mode=packet.interruption_expected_mode,
        interruption_worst_credible_mode=packet.interruption_worst_credible_mode,
        duration_minimum_minutes=packet.duration_minimum_minutes,
        duration_maximum_minutes=packet.duration_maximum_minutes,
        recovery_duration_minimum_minutes=packet.recovery_duration_minimum_minutes,
        recovery_duration_maximum_minutes=packet.recovery_duration_maximum_minutes,
        assumptions=packet.assumptions,
        graph_gaps=packet.impact_gaps,
        preconditions=packet.preconditions,
        stop_conditions=packet.stop_conditions,
        rollback_feasible=packet.rollback_feasible,
    )
