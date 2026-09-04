from __future__ import annotations

import pytest

from atlas.modules.change_impact.domain.data_protection_service import (
    DataProtectionRecoverabilityAnalysis,
    ServiceImpactRecord,
    backup_existence_alone_makes_a_destructive_change_safe,
)


def protection(**overrides: object) -> DataProtectionRecoverabilityAnalysis:
    defaults: dict[str, object] = {
        "change_request_id": "change-request.example",
        "target_entity_id": "target.controller-b",
        "backup_recency": "6 hours ago",
        "backup_status": "current",
        "backup_scope": "full volume",
        "backup_immutable": True,
        "relevant_restore_evidence_reference": "evidence.restore-test.2026-08",
        "replication_mode": "synchronous",
        "replication_lag_seconds": 0.0,
        "replication_consistency": "consistent",
        "replication_failover_state": "ready",
        "snapshot_and_retention_consequences": (),
        "write_ordering_and_consistency_notes": "Application-consistent snapshots enabled.",
        "split_brain_or_divergence_risk": None,
        "recovery_point_objective_seconds": 0,
        "recovery_time_objective_seconds": 900,
        "point_of_no_return_description": None,
        "is_rollback_available": True,
        "is_recovery_available": True,
        "legal_hold_or_retention_constraint": None,
    }
    defaults.update(overrides)
    return DataProtectionRecoverabilityAnalysis(**defaults)  # type: ignore[arg-type]


def service_impact(**overrides: object) -> ServiceImpactRecord:
    defaults: dict[str, object] = {
        "service_id": "service.file-shares",
        "service_name": "Enterprise File Shares",
        "owner": "storage-team",
        "criticality": "high",
        "supporting_graph_path_entity_ids": ("target.controller-b", "target.host-01"),
        "expected_impact_mode": "intermittent",
        "affected_function": "SMB write availability",
        "user_or_location_scope": "site.primary",
        "expected_interruption_minimum_minutes": 2,
        "expected_interruption_maximum_minutes": 5,
        "worst_credible_interruption_minimum_minutes": 5,
        "worst_credible_interruption_maximum_minutes": 30,
        "degradation_and_recovery_dependencies": ("target.controller-a",),
        "relevant_sla_or_calendar_context": "SLA permits 15 minutes of degradation per month.",
        "confidence": "moderate",
        "is_confidence_reduced_by_missing_service_mapping": False,
    }
    defaults.update(overrides)
    return ServiceImpactRecord(**defaults)  # type: ignore[arg-type]


def test_backup_existence_alone_never_makes_a_destructive_change_safe() -> None:
    assert backup_existence_alone_makes_a_destructive_change_safe() is False


def test_protection_analysis_accepts_valid_state() -> None:
    assert protection().backup_status == "current"


def test_protection_analysis_rejects_negative_replication_lag() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        protection(replication_lag_seconds=-1.0)


def test_protection_analysis_requires_rollback_or_recovery_to_be_flagged() -> None:
    with pytest.raises(ValueError, match="flagged explicitly"):
        protection(is_rollback_available=False, is_recovery_available=False)


def test_protection_analysis_requires_write_ordering_notes() -> None:
    with pytest.raises(ValueError, match="write ordering"):
        protection(write_ordering_and_consistency_notes="")


def test_service_impact_record_accepts_valid_state() -> None:
    assert service_impact().service_id == "service.file-shares"


def test_service_impact_record_requires_supporting_graph_path() -> None:
    with pytest.raises(ValueError, match="supporting graph path"):
        service_impact(supporting_graph_path_entity_ids=())


def test_service_impact_record_rejects_inverted_interruption_range() -> None:
    with pytest.raises(ValueError, match="minimum must not exceed maximum"):
        service_impact(
            expected_interruption_minimum_minutes=10, expected_interruption_maximum_minutes=5
        )


def test_service_impact_record_rejects_negative_interruption_minutes() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        service_impact(expected_interruption_minimum_minutes=-1)
