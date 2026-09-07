from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.release.domain.compatibility_types import ReleaseType
from atlas.modules.release.domain.lifecycle_roles import ReleaseRole, RoleAssignment
from atlas.modules.release.domain.plan_readiness_gates import (
    EntryCriteriaChecklist,
    EntryCriterion,
    FeatureCompleteChecklist,
    FeatureCompleteCriterion,
    ReleasePlan,
    draft_exploration_can_be_represented_as_committed_release_scope,
    feature_complete_means_release_ready,
    scope_change_after_freeze_skips_impact_and_schedule_review,
)
from atlas.modules.release.domain.versioning import SemanticVersion

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def target_version() -> SemanticVersion:
    return SemanticVersion(
        major=1,
        minor=5,
        patch=0,
        prerelease_label=None,
        prerelease_number=None,
        build_metadata=None,
    )


def plan(**overrides: object) -> ReleasePlan:
    defaults: dict[str, object] = {
        "plan_id": "release-plan.1.5.0",
        "release_type": ReleaseType.GENERAL_RELEASE,
        "target_version": target_version(),
        "goals": ("Ship Change Impact and AI Agents support.",),
        "intended_users": ("storage-operations",),
        "included_capabilities": ("change_impact", "ai_agents"),
        "excluded_capabilities": (),
        "required_architecture_approvals": ("adr.change-impact",),
        "required_document_approvals": ("docs.044", "docs.040"),
        "supported_deployment_profiles": ("linux_lab",),
        "supported_upgrade_profiles": ("1.4.x",),
        "compatibility_changes": (),
        "deprecation_changes": (),
        "risk_notes": ("No security-relevant behavior change.",),
        "required_test_types": ("evaluation", "lab"),
        "feature_complete_date": NOW,
        "freeze_date": NOW + timedelta(days=1),
        "candidate_date": NOW + timedelta(days=2),
        "review_date": NOW + timedelta(days=3),
        "publication_date": NOW + timedelta(days=4),
        "support_date": NOW + timedelta(days=5),
        "owners": (
            RoleAssignment(role=ReleaseRole.RELEASE_MANAGER, assigned_identity="subject.rm"),
        ),
        "escalation_paths": ("escalation.release-management",),
        "rollback_or_forward_recovery_strategy": "Roll back to 1.4.2 if smoke tests fail.",
    }
    defaults.update(overrides)
    return ReleasePlan(**defaults)  # type: ignore[arg-type]


def test_plan_accepts_valid_state() -> None:
    assert plan().plan_id == "release-plan.1.5.0"


def test_plan_requires_chronological_dates() -> None:
    with pytest.raises(ValueError, match="must not precede the milestone before it"):
        plan(freeze_date=NOW - timedelta(days=1))


def test_plan_requires_owners() -> None:
    with pytest.raises(ValueError, match="requires owners"):
        plan(owners=())


def test_plan_requires_rollback_strategy() -> None:
    with pytest.raises(ValueError, match="rollback or forward-recovery strategy"):
        plan(rollback_or_forward_recovery_strategy="")


def test_scope_change_after_freeze_never_skips_review() -> None:
    assert scope_change_after_freeze_skips_impact_and_schedule_review() is False


def test_entry_criteria_checklist_requires_every_criterion() -> None:
    with pytest.raises(ValueError, match="every criterion"):
        EntryCriteriaChecklist(
            capability_reference="capability.change-impact",
            satisfied_criteria=frozenset(
                {EntryCriterion.PRODUCT_REQUIREMENT_AND_ACCEPTANCE_CRITERIA_APPROVED}
            ),
        )


def test_entry_criteria_checklist_accepts_full_set() -> None:
    checklist = EntryCriteriaChecklist(
        capability_reference="capability.change-impact",
        satisfied_criteria=frozenset(EntryCriterion),
    )
    assert checklist.capability_reference == "capability.change-impact"


def test_draft_exploration_never_counts_as_committed_scope() -> None:
    assert draft_exploration_can_be_represented_as_committed_release_scope() is False


def test_feature_complete_checklist_requires_every_criterion() -> None:
    with pytest.raises(ValueError, match="every criterion"):
        FeatureCompleteChecklist(
            release_plan_id="release-plan.1.5.0",
            satisfied_criteria=frozenset(
                {FeatureCompleteCriterion.PLANNED_CODE_AND_ARTIFACTS_INTEGRATED}
            ),
        )


def test_feature_complete_never_means_release_ready() -> None:
    assert feature_complete_means_release_ready() is False
