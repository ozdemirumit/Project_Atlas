"""ATLAS-059 SS11/SS12/SS13: the release plan, entry criteria for implementation, and feature
complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import pairwise

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.release.domain.compatibility_types import ReleaseType
from atlas.modules.release.domain.lifecycle_roles import RoleAssignment
from atlas.modules.release.domain.versioning import SemanticVersion


@dataclass(frozen=True, slots=True)
class ReleasePlan:
    """SS11's ten declared elements."""

    plan_id: str
    release_type: ReleaseType
    target_version: SemanticVersion
    goals: tuple[str, ...]
    intended_users: tuple[str, ...]
    included_capabilities: tuple[str, ...]
    excluded_capabilities: tuple[str, ...]
    required_architecture_approvals: tuple[str, ...]
    required_document_approvals: tuple[str, ...]
    supported_deployment_profiles: tuple[str, ...]
    supported_upgrade_profiles: tuple[str, ...]
    compatibility_changes: tuple[str, ...]
    deprecation_changes: tuple[str, ...]
    risk_notes: tuple[str, ...]
    required_test_types: tuple[str, ...]
    feature_complete_date: datetime
    freeze_date: datetime
    candidate_date: datetime
    review_date: datetime
    publication_date: datetime
    support_date: datetime
    owners: tuple[RoleAssignment, ...]
    escalation_paths: tuple[str, ...]
    rollback_or_forward_recovery_strategy: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.plan_id, "plan_id")
        if not self.goals:
            raise ValueError("a release plan requires at least one goal")
        if not self.intended_users:
            raise ValueError("a release plan requires intended users")
        if not self.included_capabilities:
            raise ValueError("a release plan requires included capabilities")
        dates = (
            ("feature_complete_date", self.feature_complete_date),
            ("freeze_date", self.freeze_date),
            ("candidate_date", self.candidate_date),
            ("review_date", self.review_date),
            ("publication_date", self.publication_date),
            ("support_date", self.support_date),
        )
        for field_name, value in dates:
            if value.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        for (_, earlier), (later_name, later) in pairwise(dates):
            if later < earlier:
                raise ValueError(f"{later_name} must not precede the milestone before it")
        if not self.owners:
            raise ValueError("a release plan requires owners")
        if not self.rollback_or_forward_recovery_strategy.strip():
            raise ValueError("a release plan requires a rollback or forward-recovery strategy")


def scope_change_after_freeze_skips_impact_and_schedule_review() -> bool:
    """SS11: "scope change after freeze requires explicit impact and schedule review.\""""
    return False


class EntryCriterion(StrEnum):
    """SS12's seven entry criteria for a capability to enter release implementation."""

    PRODUCT_REQUIREMENT_AND_ACCEPTANCE_CRITERIA_APPROVED = (
        "product_requirement_and_acceptance_criteria_approved"
    )
    ARCHITECTURE_AND_SECURITY_DESIGN_REVIEWED = "architecture_and_security_design_reviewed"
    CONTRACTS_DEFINED = "contracts_defined"
    CAPABILITY_CLASS_RISK_AUDIT_APPROVAL_AND_FAILURE_BEHAVIOR_KNOWN = (
        "capability_class_risk_audit_approval_and_failure_behavior_known"
    )
    TEST_AND_EVALUATION_APPROACH_EXISTS = "test_and_evaluation_approach_exists"
    DEPLOYMENT_MIGRATION_COMPATIBILITY_AND_ROLLBACK_IMPLICATIONS_UNDERSTOOD = (
        "deployment_migration_compatibility_and_rollback_implications_understood"
    )
    REQUIRED_DEPENDENCIES_AND_OWNERS_AVAILABLE = "required_dependencies_and_owners_available"


@dataclass(frozen=True, slots=True)
class EntryCriteriaChecklist:
    capability_reference: str
    satisfied_criteria: frozenset[EntryCriterion]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.capability_reference, "capability_reference")
        missing = set(EntryCriterion) - self.satisfied_criteria
        if missing:
            raise ValueError(
                "an entry criteria checklist requires every criterion, missing "
                f"{sorted(criterion.value for criterion in missing)}"
            )


def draft_exploration_can_be_represented_as_committed_release_scope() -> bool:
    """SS12: "draft exploration can occur earlier, but it cannot be represented as committed
    release scope.\""""
    return False


class FeatureCompleteCriterion(StrEnum):
    """SS13's eight feature-complete criteria."""

    PLANNED_CODE_AND_ARTIFACTS_INTEGRATED = "planned_code_and_artifacts_integrated"
    PUBLIC_CONTRACTS_FROZEN_EXCEPT_APPROVED_CORRECTIONS = (
        "public_contracts_frozen_except_approved_corrections"
    )
    DOCUMENTATION_AND_MIGRATIONS_PRESENT = "documentation_and_migrations_present"
    REQUIRED_SUITES_PASS = "required_suites_pass"
    KNOWN_MISSING_WORK_EXPLICITLY_TRIAGED = "known_missing_work_explicitly_triaged"
    SECURITY_AND_ARCHITECTURE_REVIEWS_HAVE_NO_UNKNOWN_CRITICAL_FINDING = (
        "security_and_architecture_reviews_have_no_unknown_critical_finding"
    )
    DEPLOYMENT_AND_UPGRADE_PATHS_OPERATIONAL_FOR_CANDIDATE_TESTING = (
        "deployment_and_upgrade_paths_operational_for_candidate_testing"
    )
    NEW_FEATURE_WORK_STOPS_FOR_THE_RELEASE_LINE = "new_feature_work_stops_for_the_release_line"


@dataclass(frozen=True, slots=True)
class FeatureCompleteChecklist:
    release_plan_id: str
    satisfied_criteria: frozenset[FeatureCompleteCriterion]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.release_plan_id, "release_plan_id")
        missing = set(FeatureCompleteCriterion) - self.satisfied_criteria
        if missing:
            raise ValueError(
                "a feature-complete checklist requires every criterion, missing "
                f"{sorted(criterion.value for criterion in missing)}"
            )


def feature_complete_means_release_ready() -> bool:
    """SS13: "feature complete does not mean release ready.\""""
    return False
