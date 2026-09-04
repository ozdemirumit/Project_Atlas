"""ATLAS-044 SS11/SS12: redundancy analysis and capacity/performance analysis.

`RedundancyAnalysis` is a new, richer type rather than a reuse of
`decision_engine.domain.impact.ProtectionStateSummary` -- that type is deliberately a coarse,
"where modeled" four-string presentation summary for a decision record, while SS11 asks for a
real analysis (removed components, degraded elements, failover readiness with evidence, shared
fate, quorum/witness/replication state, SPOFs created). `CapacityEstimate` gives SS12's own
"estimates use units, formulas, assumptions, and ranges. Lack of telemetry is visible" a concrete,
structural home: an estimate cannot be constructed without a unit, a formula, and a range, and
`telemetry_available` is always a present field, never an implicit assumption.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.identity.domain.models import validate_stable_identifier


def configured_redundancy_is_assumed_operational_without_evidence() -> bool:
    """SS11: "configured redundancy is not assumed operational without current evidence
    appropriate to risk.\""""
    return False


@dataclass(frozen=True, slots=True)
class QuorumState:
    quorum_state: str
    witness_state: str | None
    replication_state: str | None
    synchronization_state: str | None

    def __post_init__(self) -> None:
        if not self.quorum_state.strip():
            raise ValueError("a quorum state requires a quorum_state")


@dataclass(frozen=True, slots=True)
class RedundancyAnalysis:
    change_request_id: str
    target_entity_id: str
    normal_redundancy_level: str
    maintenance_redundancy_level: str
    removed_by_change_entity_ids: tuple[str, ...]
    existing_degraded_or_failed_entity_ids: tuple[str, ...]
    failover_eligibility: str
    failover_readiness: str
    recent_failover_test_evidence_reference: str | None
    shared_fate_notes: tuple[str, ...]
    quorum_state: QuorumState | None
    remaining_path_capacity_summary: str
    single_points_of_failure_created_entity_ids: tuple[str, ...]
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.change_request_id, "change_request_id")
        validate_stable_identifier(self.target_entity_id, "target_entity_id")
        if not self.normal_redundancy_level.strip():
            raise ValueError("a redundancy analysis requires a normal redundancy level")
        if not self.maintenance_redundancy_level.strip():
            raise ValueError("a redundancy analysis requires a maintenance redundancy level")
        if not self.failover_eligibility.strip():
            raise ValueError("a redundancy analysis requires failover eligibility")
        if not self.failover_readiness.strip():
            raise ValueError("a redundancy analysis requires failover readiness")
        if not self.remaining_path_capacity_summary.strip():
            raise ValueError("a redundancy analysis requires a remaining path capacity summary")
        if not self.evidence_references:
            raise ValueError(
                "a redundancy analysis requires current evidence -- configured redundancy is "
                "not assumed operational without it"
            )


@dataclass(frozen=True, slots=True)
class CapacityEstimate:
    """SS12: "estimates use units, formulas, assumptions, and ranges. Lack of telemetry is
    visible." Every field this sentence names is a required, always-present field here."""

    metric: str
    unit: str
    formula: str
    assumptions: tuple[str, ...]
    minimum_estimate: float
    maximum_estimate: float
    telemetry_available: bool

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("a capacity estimate requires a metric")
        if not self.unit.strip():
            raise ValueError("a capacity estimate requires a unit")
        if not self.formula.strip():
            raise ValueError("a capacity estimate requires a formula")
        if self.minimum_estimate > self.maximum_estimate:
            raise ValueError("minimum_estimate must not exceed maximum_estimate")


@dataclass(frozen=True, slots=True)
class CapacityAndPerformanceAnalysis:
    change_request_id: str
    target_entity_id: str
    estimates: tuple[CapacityEstimate, ...]
    workload_concurrency_notes: str
    business_peak_period_notes: str | None
    rate_limit_and_vendor_threshold_notes: tuple[str, ...]
    performance_effect_of_validation_and_rollback: str
    measurement_coverage: str
    measurement_age_seconds: int | None
    aggregation_limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.change_request_id, "change_request_id")
        validate_stable_identifier(self.target_entity_id, "target_entity_id")
        if not self.estimates:
            raise ValueError("a capacity and performance analysis requires at least one estimate")
        if not self.workload_concurrency_notes.strip():
            raise ValueError("a capacity and performance analysis requires concurrency notes")
        if not self.performance_effect_of_validation_and_rollback.strip():
            raise ValueError(
                "a capacity and performance analysis requires the performance effect of "
                "diagnostics, validation, and rollback"
            )
        if not self.measurement_coverage.strip():
            raise ValueError("a capacity and performance analysis requires measurement coverage")
        if self.measurement_age_seconds is not None and self.measurement_age_seconds < 0:
            raise ValueError("measurement_age_seconds must not be negative")
