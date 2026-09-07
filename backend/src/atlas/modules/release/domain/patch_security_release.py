"""ATLAS-059 SS26/SS27: the patch/hotfix process and security releases."""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class PatchProcess:
    """SS26's nine declared elements."""

    patch_id: str
    confirmed_defect_or_vulnerability_reference: str
    supported_branches: tuple[str, ...]
    root_cause_assessment: str
    affected_versions: tuple[str, ...]
    regression_test_reference: str
    safety_suite_references: tuple[str, ...]
    compatibility_and_migration_review_reference: str
    patch_candidate_reference: str
    evidence_package_reference: str
    expedited_approval_reference: str
    branch_correction_notes: tuple[str, ...]
    follow_up_reference: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.patch_id, "patch_id")
        if not self.confirmed_defect_or_vulnerability_reference.strip():
            raise ValueError("a patch process requires a confirmed defect or vulnerability")
        if not self.supported_branches:
            raise ValueError("a patch process requires explicit supported branches")
        if not self.root_cause_assessment.strip():
            raise ValueError("a patch process requires a root cause assessment")
        if not self.affected_versions:
            raise ValueError("a patch process requires affected versions")
        if not self.regression_test_reference.strip():
            raise ValueError("a patch process requires a regression test reference")
        if not self.safety_suite_references:
            raise ValueError("a patch process requires relevant full safety suites")
        if not self.compatibility_and_migration_review_reference.strip():
            raise ValueError("a patch process requires a compatibility and migration review")
        if not self.patch_candidate_reference.strip():
            raise ValueError("a patch process requires an immutable patch candidate")
        if not self.evidence_package_reference.strip():
            raise ValueError("a patch process requires an evidence package")
        if not self.expedited_approval_reference.strip():
            raise ValueError("a patch process requires expedited approval")
        if not self.branch_correction_notes:
            raise ValueError(
                "SS26: main and supported branches receive consistent correction or "
                "documented divergence"
            )


def expedited_approval_skips_required_controls() -> bool:
    """SS26: "expedited approval preserves required security, quality, signing, and deployment
    controls.\""""
    return False


@dataclass(frozen=True, slots=True)
class SecurityRelease:
    """SS27's declared elements."""

    release_id: str
    security_owner_identity: str
    embargo_and_disclosure_plan_reference: str
    affected_versions: tuple[str, ...]
    exploitability_assessment: str
    exposure_assessment: str
    compensating_controls: tuple[str, ...]
    advisory_reference: str
    exploit_regression_test_reference: str
    control_bypass_test_reference: str
    signing_keys_rotated: bool
    affected_credentials_rotated: bool
    publication_timing_reference: str
    customer_notification_reference: str
    unsupported_version_guidance: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.release_id, "release_id")
        if not self.security_owner_identity.strip():
            raise ValueError("a security release requires a security owner identity")
        if not self.embargo_and_disclosure_plan_reference.strip():
            raise ValueError("a security release requires an embargo and disclosure plan")
        if not self.affected_versions:
            raise ValueError("a security release requires affected versions")
        if not self.exploitability_assessment.strip():
            raise ValueError("a security release requires an exploitability assessment")
        if not self.exposure_assessment.strip():
            raise ValueError("a security release requires an exposure assessment")
        if not self.advisory_reference.strip():
            raise ValueError("a security release requires an advisory")
        if not self.exploit_regression_test_reference.strip():
            raise ValueError("a security release requires an exploit regression test")
        if not self.control_bypass_test_reference.strip():
            raise ValueError("a security release requires a control bypass test")
        if not self.publication_timing_reference.strip():
            raise ValueError("a security release requires controlled publication timing")
        if not self.customer_notification_reference.strip():
            raise ValueError("a security release requires controlled customer notification")


def vulnerability_details_can_be_exposed_prematurely_in_public_ci_logs() -> bool:
    """SS27: "vulnerability details are not exposed prematurely in public CI logs.\""""
    return False
