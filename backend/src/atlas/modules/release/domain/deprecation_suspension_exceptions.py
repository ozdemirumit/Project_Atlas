"""ATLAS-059 SS34/SS35/SS36: deprecation/end of support, release suspension/recall, and known
issues/exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class DeprecationNotice:
    """SS34's declared elements."""

    affected_item_reference: str
    reason: str
    replacement: str | None
    migration_guidance: str
    first_warning_date: datetime
    removal_or_support_end_date: datetime
    usage_monitoring_reference: str | None
    offline_notice_reference: str

    def __post_init__(self) -> None:
        if not self.affected_item_reference.strip():
            raise ValueError("a deprecation notice requires an affected item reference")
        if not self.reason.strip():
            raise ValueError("a deprecation notice requires a reason")
        if not self.migration_guidance.strip():
            raise ValueError("a deprecation notice requires migration guidance")
        if (
            self.first_warning_date.tzinfo is None
            or self.removal_or_support_end_date.tzinfo is None
        ):
            raise ValueError(
                "first_warning_date and removal_or_support_end_date must be timezone-aware"
            )
        if self.removal_or_support_end_date < self.first_warning_date:
            raise ValueError("removal_or_support_end_date must not precede first_warning_date")
        if not self.offline_notice_reference.strip():
            raise ValueError(
                "SS34: offline customers receive notices in release bundles and support channels"
            )


def security_is_preserved_only_until_stated_support_end() -> bool:
    """SS34: "preserve security until stated support end.\""""
    return True


def removal_skips_compatibility_and_release_review() -> bool:
    """SS34: "removal follows compatibility and release review.\""""
    return False


@dataclass(frozen=True, slots=True)
class EmergencyRetirement:
    """SS34: "emergency retirement is allowed for active security risk with clear
    mitigation.\""""

    affected_item_reference: str
    active_security_risk_reference: str
    mitigation: str

    def __post_init__(self) -> None:
        if not self.affected_item_reference.strip():
            raise ValueError("an emergency retirement requires an affected item reference")
        if not self.active_security_risk_reference.strip():
            raise ValueError("an emergency retirement requires an active security risk")
        if not self.mitigation.strip():
            raise ValueError("SS34: emergency retirement ... requires clear mitigation")


class SuspensionTrigger(StrEnum):
    """SS35's six suspension/recall triggers."""

    SIGNATURE_OR_PROVENANCE_COMPROMISE = "signature_or_provenance_compromise"
    CRITICAL_VULNERABILITY_OR_ISOLATION_FAILURE = "critical_vulnerability_or_isolation_failure"
    DATA_CORRUPTION_OR_UNRECOVERABLE_MIGRATION_DEFECT = (
        "data_corruption_or_unrecoverable_migration_defect"
    )
    AUTHENTICATION_AUTHORIZATION_POLICY_APPROVAL_AUDIT_OR_GUARDRAIL_BYPASS = (
        "authentication_authorization_policy_approval_audit_or_guardrail_bypass"
    )
    UNSAFE_AI_OR_CONNECTOR_BEHAVIOR = "unsafe_ai_or_connector_behavior"
    FAILED_ROLLBACK_OR_RESTORE_ASSUMPTIONS = "failed_rollback_or_restore_assumptions"


class SuspensionResponseAction(StrEnum):
    """SS35's seven possible response actions."""

    SUSPEND_PUBLICATION = "suspend_publication"
    HALT_ROLLOUT = "halt_rollout"
    REVOKE_TRUST = "revoke_trust"
    NOTIFY_CUSTOMERS = "notify_customers"
    PROVIDE_MITIGATION = "provide_mitigation"
    ISSUE_PATCH = "issue_patch"
    RECALL_BUNDLE = "recall_bundle"


@dataclass(frozen=True, slots=True)
class SuspensionEvent:
    release_reference: str
    trigger: SuspensionTrigger
    response_actions: tuple[SuspensionResponseAction, ...]
    evidence_reference: str
    incident_governance_reference: str

    def __post_init__(self) -> None:
        if not self.release_reference.strip():
            raise ValueError("a suspension event requires a release reference")
        if not self.response_actions:
            raise ValueError("a suspension event requires at least one response action")
        if not self.evidence_reference.strip():
            raise ValueError("SS35: evidence is preserved")
        if not self.incident_governance_reference.strip():
            raise ValueError("SS35: incident governance applies")


@dataclass(frozen=True, slots=True)
class ReleaseException:
    """SS36's declared elements. "ATLAS-003 principles and ATLAS-047 invariants cannot be
    accepted as ordinary release exceptions" is the concrete object SS4's `required_gates_can_be_
    waived_without_a_recorded_exception` was defined ahead of -- and here the rule is a genuine
    construction-time impossibility, not a convention: `is_atlas_003_or_047_invariant=True`
    cannot be constructed as a `ReleaseException` at all."""

    exception_id: str
    affected_version: str
    affected_profile: str | None
    affected_component: str
    scenario: str
    severity: str
    realistic_impact: str
    detection: str
    workaround: str | None
    implications: tuple[str, ...]
    owner: str
    fix_target: str | None
    expiry: datetime
    blocks_deployment_or_feature_enablement: bool
    customer_communication_reference: str | None
    acceptance_authority: str
    is_atlas_003_or_047_invariant: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.exception_id, "exception_id")
        if not self.affected_version.strip():
            raise ValueError("a release exception requires an affected version")
        if not self.affected_component.strip():
            raise ValueError("a release exception requires an affected component")
        if not self.scenario.strip():
            raise ValueError("a release exception requires a scenario")
        if not self.severity.strip():
            raise ValueError("a release exception requires a severity")
        if not self.realistic_impact.strip():
            raise ValueError("a release exception requires a realistic impact")
        if not self.detection.strip():
            raise ValueError("a release exception requires detection")
        if not self.owner.strip():
            raise ValueError("a release exception requires an owner")
        if self.expiry.tzinfo is None:
            raise ValueError("expiry must be timezone-aware")
        if not self.acceptance_authority.strip():
            raise ValueError("a release exception requires an acceptance authority")
        if self.is_atlas_003_or_047_invariant:
            raise ValueError(
                "SS36: ATLAS-003 principles and ATLAS-047 invariants cannot be accepted as "
                "ordinary release exceptions"
            )
