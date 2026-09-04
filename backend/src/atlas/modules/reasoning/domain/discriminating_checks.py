"""ATLAS-041 SS15: discriminating checks.

Reuses `atlas.core.capabilities.CapabilityClass` for the capability-class dimension rather than a
new enum. "Does not repeat already sufficient evidence without reason" is not enforced here: it
requires comparing a check's expected evidence against what is already known sufficient, which is
caller-level context this object's own shape does not carry -- stated honestly rather than faked.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier

_CAPABILITY_CLASS_RANK: dict[CapabilityClass, int] = {
    CapabilityClass.C0_INFORMATIONAL: 0,
    CapabilityClass.C1_READ_ONLY: 1,
    CapabilityClass.C2_DIAGNOSTIC: 2,
    CapabilityClass.C3_CONTROLLED_CHANGE: 3,
    CapabilityClass.C4_SERVICE_IMPACTING: 4,
    CapabilityClass.C5_DESTRUCTIVE: 5,
}


@dataclass(frozen=True, slots=True)
class ExpectedResultUnderHypothesis:
    hypothesis_id: str
    expected_result: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.hypothesis_id, "hypothesis_id")
        if not self.expected_result.strip():
            raise ValueError("an expected result requires text")


@dataclass(frozen=True, slots=True)
class DiscriminatingCheck:
    """SS15's declared elements, minus the authorization/ceiling check (a cross-object
    comparison exposed as `is_within_capability_ceiling` below, not a stored field)."""

    check_id: str
    capability_class: CapabilityClass
    target_id: str
    bounded_duration_seconds: int
    bounded_load: str
    bounded_output: str
    bounded_data_exposure: str
    expected_results: tuple[ExpectedResultUnderHypothesis, ...]
    avoids_service_change: bool
    stop_condition: str
    timeout_seconds: int
    failure_behavior: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.check_id, "check_id")
        validate_stable_identifier(self.target_id, "target_id")
        if self.bounded_duration_seconds < 1:
            raise ValueError("bounded_duration_seconds must be positive")
        if not self.bounded_load.strip():
            raise ValueError("a discriminating check requires a bounded load statement")
        if not self.bounded_output.strip():
            raise ValueError("a discriminating check requires a bounded output statement")
        if not self.bounded_data_exposure.strip():
            raise ValueError("a discriminating check requires a bounded data exposure statement")
        if len(self.expected_results) < 2:
            raise ValueError(
                "SS15: states expected results under each leading hypothesis -- a genuinely"
                " discriminating check needs at least two hypotheses' expected results"
            )
        if not self.stop_condition.strip():
            raise ValueError("a discriminating check requires a stop condition")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if not self.failure_behavior.strip():
            raise ValueError("a discriminating check requires failure behavior")


def is_within_capability_ceiling(*, check: DiscriminatingCheck, ceiling: CapabilityClass) -> bool:
    """SS15: "is authorized and within the task capability ceiling.\""""
    return _CAPABILITY_CLASS_RANK[check.capability_class] <= _CAPABILITY_CLASS_RANK[ceiling]


@dataclass(frozen=True, slots=True)
class CheckRankingFactors:
    """SS15: "Atlas ranks checks by information gain, safety, freshness, cost, and time." Each
    factor is normalized to [0.0, 1.0] so the composite ranking (`rank_checks`) is a plain,
    deterministic sum/difference -- "using deterministic support where feasible" applied to the
    ranking mechanism itself."""

    information_gain: float
    safety: float
    freshness: float
    cost: float
    time: float

    def __post_init__(self) -> None:
        for value, name in (
            (self.information_gain, "information_gain"),
            (self.safety, "safety"),
            (self.freshness, "freshness"),
            (self.cost, "cost"),
            (self.time, "time"),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0.0, 1.0]")


def rank_checks(
    checks: tuple[tuple[DiscriminatingCheck, CheckRankingFactors], ...],
) -> tuple[DiscriminatingCheck, ...]:
    """Higher information gain, safety, and freshness rank first; higher cost and time rank
    last."""

    def _score(pair: tuple[DiscriminatingCheck, CheckRankingFactors]) -> float:
        factors = pair[1]
        return (
            factors.information_gain
            + factors.safety
            + factors.freshness
            - factors.cost
            - factors.time
        )

    return tuple(check for check, _ in sorted(checks, key=_score, reverse=True))
