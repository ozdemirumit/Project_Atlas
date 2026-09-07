from __future__ import annotations

import pytest

from atlas.modules.release.domain.review_approval import (
    REVIEW_STEP_ORDER,
    ReadinessReviewRecord,
    ReleaseApproval,
    ReviewDecision,
    ReviewStep,
    artifact_change_invalidates_approval,
    self_approval_by_automation_ai_author_or_unreviewed_role_is_permitted,
)


def test_review_step_order_has_eight_steps() -> None:
    assert len(REVIEW_STEP_ORDER) == 8
    assert len(set(REVIEW_STEP_ORDER)) == 8


def review_record(**overrides: object) -> ReadinessReviewRecord:
    defaults: dict[str, object] = {
        "candidate_reference": "release-candidate.1.5.0-rc.3",
        "completed_steps": REVIEW_STEP_ORDER,
        "decision": ReviewDecision.APPROVE,
        "signed_approval_reference": "signed-approval.1.5.0-rc.3",
    }
    defaults.update(overrides)
    return ReadinessReviewRecord(**defaults)  # type: ignore[arg-type]


def test_readiness_review_record_requires_every_step() -> None:
    with pytest.raises(ValueError, match="every review step completed"):
        review_record(completed_steps=(ReviewStep.REVIEW_SCOPE_AND_ACCEPTANCE,))


def test_readiness_review_record_requires_signed_approval_reference() -> None:
    with pytest.raises(ValueError, match="do not replace signed or auditable approval records"):
        review_record(signed_approval_reference="")


def test_self_approval_never_permitted() -> None:
    assert self_approval_by_automation_ai_author_or_unreviewed_role_is_permitted() is False


def test_artifact_change_always_invalidates_approval() -> None:
    assert artifact_change_invalidates_approval() is True


def approval(**overrides: object) -> ReleaseApproval:
    defaults: dict[str, object] = {
        "candidate_digest": "sha256:" + "a" * 64,
        "evidence_package_reference": "release-evidence.1.5.0",
        "approving_identity": "subject.product-owner",
        "approver_is_human": True,
        "security_approval_reference": None,
        "architecture_approval_reference": None,
        "quality_recommendation_reference": "quality-recommendation.1.5.0",
        "has_unresolved_security_exception": False,
        "is_security_release": False,
        "has_compatibility_migration_or_deployment_exception": False,
    }
    defaults.update(overrides)
    return ReleaseApproval(**defaults)  # type: ignore[arg-type]


def test_approval_accepts_valid_state() -> None:
    assert approval().approving_identity == "subject.product-owner"


def test_approval_rejects_non_human_approver() -> None:
    with pytest.raises(ValueError, match="designated accountable humans"):
        approval(approver_is_human=False)


def test_approval_requires_security_approval_for_security_release() -> None:
    with pytest.raises(ValueError, match="security approval is required"):
        approval(is_security_release=True, security_approval_reference=None)


def test_approval_accepts_security_release_with_security_approval() -> None:
    result = approval(
        is_security_release=True, security_approval_reference="security-approval.1.5.0"
    )
    assert result.is_security_release is True


def test_approval_requires_architecture_approval_for_compatibility_exception() -> None:
    with pytest.raises(ValueError, match="architecture approval is required"):
        approval(
            has_compatibility_migration_or_deployment_exception=True,
            architecture_approval_reference=None,
        )
