from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.explainability.domain.risk_impact import RiskLevel
from atlas.modules.runbook_engine.domain.models import RunbookClass
from atlas.modules.runbook_engine.domain.review import (
    ReviewDecision,
    ReviewerRole,
    RunbookReview,
    has_required_reviews,
    required_reviewer_roles_for,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def review(**overrides: object) -> RunbookReview:
    defaults: dict[str, object] = {
        "review_id": "runbook-review.example",
        "runbook_id": "runbook.example",
        "version_id": "runbook-version.example",
        "reviewer_role": ReviewerRole.DOMAIN_REVIEWER,
        "reviewer_id": "subject.domain-reviewer",
        "decision": ReviewDecision.APPROVE,
        "rationale": "The procedure matches the vendor's documented restart sequence.",
        "reviewed_at": NOW,
    }
    defaults.update(overrides)
    return RunbookReview(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_review_constructs_cleanly() -> None:
    example = review()
    assert example.decision is ReviewDecision.APPROVE


def test_review_requires_a_rationale() -> None:
    with pytest.raises(ValueError, match="rationale"):
        review(rationale="   ")


def test_review_rejects_naive_reviewed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        review(reviewed_at=NOW.replace(tzinfo=None))


def test_baseline_requires_domain_reviewer_and_governance_approver() -> None:
    roles = required_reviewer_roles_for(
        runbook_class=RunbookClass.INFORMATIONAL,
        capability_class_ceiling=CapabilityClass.C0_INFORMATIONAL,
        risk_level=RiskLevel.LOW,
    )
    assert roles == {ReviewerRole.DOMAIN_REVIEWER, ReviewerRole.GOVERNANCE_APPROVER}


def test_restoration_class_adds_operations_reviewer() -> None:
    roles = required_reviewer_roles_for(
        runbook_class=RunbookClass.RESTORATION,
        capability_class_ceiling=CapabilityClass.C0_INFORMATIONAL,
        risk_level=RiskLevel.LOW,
    )
    assert ReviewerRole.OPERATIONS_REVIEWER in roles


def test_diagnostic_class_does_not_add_operations_reviewer() -> None:
    roles = required_reviewer_roles_for(
        runbook_class=RunbookClass.DIAGNOSTIC,
        capability_class_ceiling=CapabilityClass.C0_INFORMATIONAL,
        risk_level=RiskLevel.LOW,
    )
    assert ReviewerRole.OPERATIONS_REVIEWER not in roles


def test_non_foundation_capability_ceiling_adds_security_reviewer() -> None:
    roles = required_reviewer_roles_for(
        runbook_class=RunbookClass.INFORMATIONAL,
        capability_class_ceiling=CapabilityClass.C3_CONTROLLED_CHANGE,
        risk_level=RiskLevel.LOW,
    )
    assert ReviewerRole.SECURITY_REVIEWER in roles


def test_high_risk_adds_security_reviewer_and_service_owner() -> None:
    roles = required_reviewer_roles_for(
        runbook_class=RunbookClass.INFORMATIONAL,
        capability_class_ceiling=CapabilityClass.C0_INFORMATIONAL,
        risk_level=RiskLevel.HIGH,
    )
    assert ReviewerRole.SECURITY_REVIEWER in roles
    assert ReviewerRole.SERVICE_OWNER in roles


def test_low_risk_foundation_ceiling_does_not_add_security_or_service_owner() -> None:
    roles = required_reviewer_roles_for(
        runbook_class=RunbookClass.INFORMATIONAL,
        capability_class_ceiling=CapabilityClass.C1_READ_ONLY,
        risk_level=RiskLevel.LOW,
    )
    assert ReviewerRole.SECURITY_REVIEWER not in roles
    assert ReviewerRole.SERVICE_OWNER not in roles


def test_has_required_reviews_true_when_every_role_approved() -> None:
    required = frozenset({ReviewerRole.DOMAIN_REVIEWER, ReviewerRole.GOVERNANCE_APPROVER})
    reviews = (
        review(reviewer_role=ReviewerRole.DOMAIN_REVIEWER, decision=ReviewDecision.APPROVE),
        review(reviewer_role=ReviewerRole.GOVERNANCE_APPROVER, decision=ReviewDecision.APPROVE),
    )
    assert has_required_reviews(reviews=reviews, required_roles=required) is True


def test_has_required_reviews_false_when_a_role_is_missing() -> None:
    required = frozenset({ReviewerRole.DOMAIN_REVIEWER, ReviewerRole.GOVERNANCE_APPROVER})
    reviews = (review(reviewer_role=ReviewerRole.DOMAIN_REVIEWER, decision=ReviewDecision.APPROVE),)
    assert has_required_reviews(reviews=reviews, required_roles=required) is False


def test_has_required_reviews_false_when_a_role_requested_changes_instead_of_approving() -> None:
    required = frozenset({ReviewerRole.DOMAIN_REVIEWER})
    reviews = (
        review(reviewer_role=ReviewerRole.DOMAIN_REVIEWER, decision=ReviewDecision.REQUEST_CHANGES),
    )
    assert has_required_reviews(reviews=reviews, required_roles=required) is False
