"""ATLAS-045 SS18: review and approval.

"Publication approval is distinct from approval to use the runbook on a particular target" --
that second kind is exactly what the already-built `approvals` module governs
(`ApprovalRecord`/`ApprovalPacket`, bound to one target and one recommendation option). This
module covers only the first kind, publication approval, and deliberately does not reach for
`approvals.ApprovalRecord` at all -- conflating the two would blur precisely the distinction SS18
calls out. Slice 1's `RunbookVersionMetadata.__post_init__` already enforces "the author or
generating AI cannot be the sole approver" for the governance-approver role; this module does not
repeat that check.

Reuses `explainability.domain.risk_impact.RiskLevel` for "risk" in "required reviewers vary by
class and risk" rather than a second risk scale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.capabilities import FOUNDATION_CAPABILITY_CLASSES, CapabilityClass
from atlas.modules.explainability.domain.risk_impact import RiskLevel
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.models import RunbookClass


class ReviewerRole(StrEnum):
    """SS18's five reviewer roles."""

    DOMAIN_REVIEWER = "domain_reviewer"
    OPERATIONS_REVIEWER = "operations_reviewer"
    SECURITY_REVIEWER = "security_reviewer"
    SERVICE_OWNER = "service_owner"
    GOVERNANCE_APPROVER = "governance_approver"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class RunbookReview:
    review_id: str
    runbook_id: str
    version_id: str
    reviewer_role: ReviewerRole
    reviewer_id: str
    decision: ReviewDecision
    rationale: str
    reviewed_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.review_id, "review_id")
        validate_stable_identifier(self.runbook_id, "runbook_id")
        validate_stable_identifier(self.version_id, "version_id")
        if not self.rationale.strip():
            raise ValueError("a runbook review requires a rationale")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")


_OPERATIONS_REVIEWER_CLASSES = frozenset(
    {
        RunbookClass.RESTORATION,
        RunbookClass.MAINTENANCE,
        RunbookClass.RECOVERY,
        RunbookClass.SECURITY_RESPONSE,
    }
)
_ELEVATED_RISK_LEVELS = frozenset({RiskLevel.HIGH, RiskLevel.CRITICAL})


def required_reviewer_roles_for(
    *,
    runbook_class: RunbookClass,
    capability_class_ceiling: CapabilityClass,
    risk_level: RiskLevel,
) -> frozenset[ReviewerRole]:
    """SS18: "required reviewers vary by class and risk." A defensible, stated simplification of
    SS18's unspecified exact rule: every runbook always requires a domain reviewer (technical
    correctness/applicability) and a governance approver (publication authorization). Beyond that
    baseline -- operations for classes involving real operational execution; security once the
    capability ceiling clears the foundation tier or risk is high/critical; service owner once
    risk is high/critical, matching "target-specific impact where required.\""""
    roles = {ReviewerRole.DOMAIN_REVIEWER, ReviewerRole.GOVERNANCE_APPROVER}
    if runbook_class in _OPERATIONS_REVIEWER_CLASSES:
        roles.add(ReviewerRole.OPERATIONS_REVIEWER)
    if (
        capability_class_ceiling not in FOUNDATION_CAPABILITY_CLASSES
        or risk_level in _ELEVATED_RISK_LEVELS
    ):
        roles.add(ReviewerRole.SECURITY_REVIEWER)
    if risk_level in _ELEVATED_RISK_LEVELS:
        roles.add(ReviewerRole.SERVICE_OWNER)
    return frozenset(roles)


def has_required_reviews(
    *, reviews: tuple[RunbookReview, ...], required_roles: frozenset[ReviewerRole]
) -> bool:
    approved_roles = {
        review.reviewer_role for review in reviews if review.decision is ReviewDecision.APPROVE
    }
    return required_roles <= approved_roles
