from __future__ import annotations

import pytest

from atlas.modules.release.domain.patch_security_release import (
    PatchProcess,
    SecurityRelease,
    expedited_approval_skips_required_controls,
    vulnerability_details_can_be_exposed_prematurely_in_public_ci_logs,
)


def patch(**overrides: object) -> PatchProcess:
    defaults: dict[str, object] = {
        "patch_id": "patch.1.4.3",
        "confirmed_defect_or_vulnerability_reference": "defect.controller-b-timeout",
        "supported_branches": ("main", "release/1.4"),
        "root_cause_assessment": "Timeout was too short for slow vendor endpoints.",
        "affected_versions": ("1.4.0", "1.4.1", "1.4.2"),
        "regression_test_reference": "test.controller-b-timeout-regression",
        "safety_suite_references": ("safety-suite.storage",),
        "compatibility_and_migration_review_reference": "review.patch.1.4.3",
        "patch_candidate_reference": "patch-candidate.1.4.3",
        "evidence_package_reference": "release-evidence.1.4.3",
        "expedited_approval_reference": "expedited-approval.1.4.3",
        "branch_correction_notes": ("main: corrected", "release/1.4: corrected"),
        "follow_up_reference": "follow-up.1.4.3",
    }
    defaults.update(overrides)
    return PatchProcess(**defaults)  # type: ignore[arg-type]


def test_patch_accepts_valid_state() -> None:
    assert patch().patch_id == "patch.1.4.3"


def test_patch_requires_supported_branches() -> None:
    with pytest.raises(ValueError, match="explicit supported branches"):
        patch(supported_branches=())


def test_patch_requires_branch_correction_notes() -> None:
    with pytest.raises(ValueError, match="consistent correction or"):
        patch(branch_correction_notes=())


def test_expedited_approval_never_skips_required_controls() -> None:
    assert expedited_approval_skips_required_controls() is False


def security_release(**overrides: object) -> SecurityRelease:
    defaults: dict[str, object] = {
        "release_id": "security-release.1.4.3",
        "security_owner_identity": "subject.security-owner",
        "embargo_and_disclosure_plan_reference": "embargo-plan.1.4.3",
        "affected_versions": ("1.4.0", "1.4.1", "1.4.2"),
        "exploitability_assessment": "Requires authenticated network access.",
        "exposure_assessment": "Limited to environments with public API exposure.",
        "compensating_controls": ("WAF rule enabled.",),
        "advisory_reference": "advisory.2026-09-04",
        "exploit_regression_test_reference": "test.exploit-regression.1.4.3",
        "control_bypass_test_reference": "test.control-bypass.1.4.3",
        "signing_keys_rotated": False,
        "affected_credentials_rotated": False,
        "publication_timing_reference": "publication-timing.1.4.3",
        "customer_notification_reference": "customer-notification.1.4.3",
        "unsupported_version_guidance": ("Upgrade to 1.4.3 or apply mitigation X.",),
    }
    defaults.update(overrides)
    return SecurityRelease(**defaults)  # type: ignore[arg-type]


def test_security_release_accepts_valid_state() -> None:
    assert security_release().release_id == "security-release.1.4.3"


def test_security_release_requires_advisory() -> None:
    with pytest.raises(ValueError, match="requires an advisory"):
        security_release(advisory_reference="")


def test_security_release_requires_exploit_regression_test() -> None:
    with pytest.raises(ValueError, match="exploit regression test"):
        security_release(exploit_regression_test_reference="")


def test_vulnerability_details_never_exposed_prematurely() -> None:
    assert vulnerability_details_can_be_exposed_prematurely_in_public_ci_logs() is False
