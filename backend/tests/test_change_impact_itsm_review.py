from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.change_impact.domain.itsm_review import (
    ActualOutcomeRecord,
    ApprovalBinding,
    HumanCorrection,
    HumanCorrectionKind,
    ItsmAttachment,
    ResidualUncertaintyAcceptance,
    accepting_residual_uncertainty_relabels_unknowns_as_safe_or_known,
    itsm_approval_cures_stale_topology_or_failed_preconditions,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def approval_binding(**overrides: object) -> ApprovalBinding:
    defaults: dict[str, object] = {
        "impact_result_id": "impact-result.example",
        "impact_result_version": 1,
        "target_ids": ("target.controller-b",),
        "plan_version": 1,
        "policy_decision_reference": "policy-decision.example",
        "maintenance_window_start": NOW,
        "maintenance_window_end": NOW + timedelta(hours=2),
        "service_owner_acknowledged": False,
        "technical_approval_granted": False,
    }
    defaults.update(overrides)
    return ApprovalBinding(**defaults)  # type: ignore[arg-type]


def test_itsm_approval_never_cures_stale_topology() -> None:
    assert itsm_approval_cures_stale_topology_or_failed_preconditions() is False


def test_itsm_attachment_requires_change_record_reference() -> None:
    with pytest.raises(ValueError, match="ITSM change record reference"):
        ItsmAttachment(
            impact_result_id="impact-result.example",
            impact_result_version=1,
            itsm_change_record_reference="",
            attached_at=NOW,
        )


def test_approval_binding_rejects_inverted_window() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        approval_binding(
            maintenance_window_start=NOW + timedelta(hours=2), maintenance_window_end=NOW
        )


def test_approval_binding_not_fully_approved_with_only_one_flag() -> None:
    binding = approval_binding(service_owner_acknowledged=True, technical_approval_granted=False)
    assert binding.is_fully_approved is False


def test_approval_binding_fully_approved_requires_both_flags() -> None:
    binding = approval_binding(service_owner_acknowledged=True, technical_approval_granted=True)
    assert binding.is_fully_approved is True


def test_actual_outcome_record_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        ActualOutcomeRecord(
            impact_result_id="impact-result.example",
            actual_affected_entity_ids=("target.controller-b",),
            actual_interruption_mode="performance_degradation",
            actual_duration_minutes=-1,
            actual_service_impact_notes=(),
            recorded_at=NOW,
        )


def test_human_correction_requires_rationale() -> None:
    with pytest.raises(ValueError, match="requires a rationale"):
        HumanCorrection(
            correction_id="correction.example",
            impact_result_id="impact-result.example",
            kind=HumanCorrectionKind.SERVICE_OWNERSHIP,
            corrected_by="subject.reviewer",
            rationale="",
            resulting_impact_result_id="impact-result.example",
            resulting_impact_result_version=2,
            corrected_at=NOW,
        )


def test_human_correction_requires_positive_resulting_version() -> None:
    with pytest.raises(ValueError, match="positive resulting version"):
        HumanCorrection(
            correction_id="correction.example",
            impact_result_id="impact-result.example",
            kind=HumanCorrectionKind.TIMING,
            corrected_by="subject.reviewer",
            rationale="Duration estimate understated concurrent backup load.",
            resulting_impact_result_id="impact-result.example",
            resulting_impact_result_version=0,
            corrected_at=NOW,
        )


def test_accepting_residual_uncertainty_never_relabels_unknowns() -> None:
    assert accepting_residual_uncertainty_relabels_unknowns_as_safe_or_known() is False


def test_residual_uncertainty_acceptance_requires_unknowns_note() -> None:
    with pytest.raises(ValueError, match="unknowns note"):
        ResidualUncertaintyAcceptance(
            impact_result_id="impact-result.example",
            accepted_by="subject.approver",
            governance_process_reference="governance.exception.2026-09",
            accepted_unknowns_note="",
            accepted_at=NOW,
        )
