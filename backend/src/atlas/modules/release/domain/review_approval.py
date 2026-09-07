"""ATLAS-059 SS18/SS19: the release readiness review and approval."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ReviewStep(StrEnum):
    """SS18's eight-step review sequence."""

    CONFIRM_CANDIDATE_IDENTITY_AND_UNCHANGED_ARTIFACTS = (
        "confirm_candidate_identity_and_unchanged_artifacts"
    )
    REVIEW_SCOPE_AND_ACCEPTANCE = "review_scope_and_acceptance"
    REVIEW_SECURITY_PRIVACY_AI_DATA_MIGRATION_AND_OPERATIONAL_RISK = (
        "review_security_privacy_ai_data_migration_and_operational_risk"
    )
    REVIEW_MANDATORY_TESTS_FAILURES_SKIPS_AND_TRENDS = (
        "review_mandatory_tests_failures_skips_and_trends"
    )
    REVIEW_UPGRADE_ROLLBACK_BACKUP_RESTORE_AND_OFFLINE_PATHS = (
        "review_upgrade_rollback_backup_restore_and_offline_paths"
    )
    REVIEW_KNOWN_ISSUES_AND_CUSTOMER_IMPACT = "review_known_issues_and_customer_impact"
    RESOLVE_OR_ACCEPT_BOUNDED_EXCEPTIONS = "resolve_or_accept_bounded_exceptions"
    RECORD_APPROVE_REJECT_OR_NEEDS_EVIDENCE_DECISION = (
        "record_approve_reject_or_needs_evidence_decision"
    )


REVIEW_STEP_ORDER: tuple[ReviewStep, ...] = (
    ReviewStep.CONFIRM_CANDIDATE_IDENTITY_AND_UNCHANGED_ARTIFACTS,
    ReviewStep.REVIEW_SCOPE_AND_ACCEPTANCE,
    ReviewStep.REVIEW_SECURITY_PRIVACY_AI_DATA_MIGRATION_AND_OPERATIONAL_RISK,
    ReviewStep.REVIEW_MANDATORY_TESTS_FAILURES_SKIPS_AND_TRENDS,
    ReviewStep.REVIEW_UPGRADE_ROLLBACK_BACKUP_RESTORE_AND_OFFLINE_PATHS,
    ReviewStep.REVIEW_KNOWN_ISSUES_AND_CUSTOMER_IMPACT,
    ReviewStep.RESOLVE_OR_ACCEPT_BOUNDED_EXCEPTIONS,
    ReviewStep.RECORD_APPROVE_REJECT_OR_NEEDS_EVIDENCE_DECISION,
)


class ReviewDecision(StrEnum):
    """SS18 step 8: "records approve, reject, or needs-evidence decision.\""""

    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_EVIDENCE = "needs_evidence"


@dataclass(frozen=True, slots=True)
class ReadinessReviewRecord:
    """SS18: "meeting notes do not replace signed or auditable approval records" -- a
    `signed_approval_reference` is a required field, not an afterthought."""

    candidate_reference: str
    completed_steps: tuple[ReviewStep, ...]
    decision: ReviewDecision
    signed_approval_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.candidate_reference, "candidate_reference")
        if set(self.completed_steps) != set(ReviewStep):
            raise ValueError("a readiness review record requires every review step completed")
        if not self.signed_approval_reference.strip():
            raise ValueError(
                "SS18: meeting notes do not replace signed or auditable approval records"
            )


def self_approval_by_automation_ai_author_or_unreviewed_role_is_permitted() -> bool:
    """SS19: "self-approval by build automation, AI, author, or one unreviewed role is
    prohibited.\""""
    return False


def artifact_change_invalidates_approval() -> bool:
    """SS19: "artifact change invalidates approval.\""""
    return True


@dataclass(frozen=True, slots=True)
class ReleaseApproval:
    """SS19's declared elements. `approver_is_human` must be `True` to construct at all --
    "final release approval is made by the designated accountable humans" as a construction-time
    guarantee, mirroring `guardrails.domain.agent_guardrails.is_valid_independent_human_approval`'s
    unconditional check for the same underlying rule in a different subsystem."""

    candidate_digest: str
    evidence_package_reference: str
    approving_identity: str
    approver_is_human: bool
    security_approval_reference: str | None
    architecture_approval_reference: str | None
    quality_recommendation_reference: str
    has_unresolved_security_exception: bool
    is_security_release: bool
    has_compatibility_migration_or_deployment_exception: bool

    def __post_init__(self) -> None:
        if not self.candidate_digest.strip():
            raise ValueError("a release approval requires a candidate digest")
        if not self.evidence_package_reference.strip():
            raise ValueError("a release approval requires an evidence package reference")
        if not self.approving_identity.strip():
            raise ValueError("a release approval requires an approving identity")
        if not self.approver_is_human:
            raise ValueError(
                "SS19: final release approval is made by the designated accountable humans"
            )
        if not self.quality_recommendation_reference.strip():
            raise ValueError("a release approval requires a quality recommendation")
        if (
            self.has_unresolved_security_exception or self.is_security_release
        ) and self.security_approval_reference is None:
            raise ValueError(
                "SS19: security approval is required for unresolved security exceptions or "
                "security releases"
            )
        if (
            self.has_compatibility_migration_or_deployment_exception
            and self.architecture_approval_reference is None
        ):
            raise ValueError(
                "SS19: architecture approval is required for compatibility, migration, or "
                "deployment exceptions"
            )
