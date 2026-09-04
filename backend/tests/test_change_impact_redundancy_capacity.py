from __future__ import annotations

import pytest

from atlas.modules.change_impact.domain.redundancy_capacity import (
    CapacityAndPerformanceAnalysis,
    CapacityEstimate,
    QuorumState,
    RedundancyAnalysis,
    configured_redundancy_is_assumed_operational_without_evidence,
)


def redundancy(**overrides: object) -> RedundancyAnalysis:
    defaults: dict[str, object] = {
        "change_request_id": "change-request.example",
        "target_entity_id": "target.controller-b",
        "normal_redundancy_level": "dual_controller",
        "maintenance_redundancy_level": "single_controller",
        "removed_by_change_entity_ids": ("target.controller-b",),
        "existing_degraded_or_failed_entity_ids": (),
        "failover_eligibility": "eligible",
        "failover_readiness": "ready",
        "recent_failover_test_evidence_reference": "evidence.failover-test.2026-08",
        "shared_fate_notes": (),
        "quorum_state": QuorumState(
            quorum_state="healthy",
            witness_state="reachable",
            replication_state="synchronized",
            synchronization_state="in_sync",
        ),
        "remaining_path_capacity_summary": "Controller A can absorb full load for 4 hours.",
        "single_points_of_failure_created_entity_ids": ("target.controller-a",),
        "evidence_references": ("evidence.health-check.2026-09-04",),
    }
    defaults.update(overrides)
    return RedundancyAnalysis(**defaults)  # type: ignore[arg-type]


def estimate(**overrides: object) -> CapacityEstimate:
    defaults: dict[str, object] = {
        "metric": "iops",
        "unit": "iops",
        "formula": "current_iops * (1 + failover_load_factor)",
        "assumptions": ("failover_load_factor derived from last 30 days peak",),
        "minimum_estimate": 8000.0,
        "maximum_estimate": 12000.0,
        "telemetry_available": True,
    }
    defaults.update(overrides)
    return CapacityEstimate(**defaults)  # type: ignore[arg-type]


def capacity(**overrides: object) -> CapacityAndPerformanceAnalysis:
    defaults: dict[str, object] = {
        "change_request_id": "change-request.example",
        "target_entity_id": "target.controller-b",
        "estimates": (estimate(),),
        "workload_concurrency_notes": "Batch backup job runs concurrently at 02:00 UTC.",
        "business_peak_period_notes": "Avoid month-end close, 2026-09-30.",
        "rate_limit_and_vendor_threshold_notes": ("Vendor caps failover IOPS burst at 15000.",),
        "performance_effect_of_validation_and_rollback": (
            "Post-failover validation adds roughly 5% read latency for ten minutes."
        ),
        "measurement_coverage": "90% of volumes have five-minute telemetry.",
        "measurement_age_seconds": 120,
        "aggregation_limitations": ("Latency is averaged, not p99.",),
    }
    defaults.update(overrides)
    return CapacityAndPerformanceAnalysis(**defaults)  # type: ignore[arg-type]


def test_redundancy_analysis_accepts_valid_state() -> None:
    assert redundancy().failover_readiness == "ready"


def test_redundancy_analysis_requires_evidence() -> None:
    with pytest.raises(ValueError, match="requires current evidence"):
        redundancy(evidence_references=())


def test_configured_redundancy_is_never_assumed_operational_without_evidence() -> None:
    assert configured_redundancy_is_assumed_operational_without_evidence() is False


def test_quorum_state_requires_quorum_state() -> None:
    with pytest.raises(ValueError, match="requires a quorum_state"):
        QuorumState(
            quorum_state="",
            witness_state=None,
            replication_state=None,
            synchronization_state=None,
        )


def test_capacity_estimate_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        estimate(minimum_estimate=12000.0, maximum_estimate=8000.0)


def test_capacity_estimate_requires_formula() -> None:
    with pytest.raises(ValueError, match="requires a formula"):
        estimate(formula="")


def test_capacity_analysis_requires_at_least_one_estimate() -> None:
    with pytest.raises(ValueError, match="at least one estimate"):
        capacity(estimates=())


def test_capacity_analysis_rejects_negative_measurement_age() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        capacity(measurement_age_seconds=-1)
