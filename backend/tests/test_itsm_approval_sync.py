from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.itsm.domain.approval_sync import (
    ItsmApprovalInvalidationTrigger,
    ItsmApprovalMappingMode,
    ItsmExternalApprovalBinding,
    approval_conflict_allows_consequential_progress,
    comment_text_or_generic_ticket_state_constitutes_approval,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def test_comment_text_never_constitutes_approval() -> None:
    assert comment_text_or_generic_ticket_state_constitutes_approval() is False


def test_approval_conflict_never_allows_consequential_progress() -> None:
    assert approval_conflict_allows_consequential_progress() is False


def test_mapping_mode_has_three_members() -> None:
    assert len(ItsmApprovalMappingMode) == 3


def test_invalidation_trigger_has_six_members() -> None:
    assert len(ItsmApprovalInvalidationTrigger) == 6


def _build(**overrides: object) -> ItsmExternalApprovalBinding:
    defaults: dict[str, object] = {
        "binding_id": "binding.example-001",
        "profile_id": "profile.example-001",
        "external_approval_record_id": "external.approval-001",
        "external_record_version": "version.1",
        "eligible_approver_reference": "subject.approver",
        "approving_subject_reference": "subject.approver",
        "exact_plan_reference": "plan.example-001",
        "exact_plan_version": "plan.example-001.v1",
        "validated_at": NOW,
        "atlas_approval_reference": None,
    }
    defaults.update(overrides)
    return ItsmExternalApprovalBinding(**defaults)  # type: ignore[arg-type]


def test_valid_binding_builds() -> None:
    binding = _build()
    assert binding.approving_subject_reference == binding.eligible_approver_reference


def test_binding_requires_eligible_approver() -> None:
    with pytest.raises(ValueError, match="approver be eligible"):
        _build(approving_subject_reference="subject.someone-else")
