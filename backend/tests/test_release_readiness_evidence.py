from __future__ import annotations

import pytest

from atlas.modules.release.domain.readiness_evidence import (
    ReadinessAssessment,
    ReadinessCategory,
    ReadinessCriterionResult,
    ReleaseEvidencePackage,
    false_safe_or_invariant_failure_can_be_accepted_through_aggregate_scoring,
)


def full_results(all_passed: bool = True) -> tuple[ReadinessCriterionResult, ...]:
    return tuple(
        ReadinessCriterionResult(category=category, detail="checked", passed=all_passed)
        for category in ReadinessCategory
    )


def test_readiness_assessment_requires_every_category() -> None:
    with pytest.raises(ValueError, match="every readiness category"):
        ReadinessAssessment(
            candidate_reference="release-candidate.1.5.0-rc.3",
            results=(
                ReadinessCriterionResult(
                    category=ReadinessCategory.PRODUCT, detail="checked", passed=True
                ),
            ),
        )


def test_readiness_assessment_is_ready_true_when_all_pass() -> None:
    assessment = ReadinessAssessment(
        candidate_reference="release-candidate.1.5.0-rc.3", results=full_results(True)
    )
    assert assessment.is_ready is True


def test_readiness_assessment_is_ready_false_when_one_fails() -> None:
    results = tuple(
        ReadinessCriterionResult(category=category, detail="unresolved CVE", passed=False)
        if category is ReadinessCategory.SECURITY_AND_GOVERNANCE
        else ReadinessCriterionResult(category=category, detail="checked", passed=True)
        for category in ReadinessCategory
    )
    assessment = ReadinessAssessment(
        candidate_reference="release-candidate.1.5.0-rc.3", results=results
    )
    assert assessment.is_ready is False


def test_false_safe_never_accepted_through_aggregate_scoring() -> None:
    assert false_safe_or_invariant_failure_can_be_accepted_through_aggregate_scoring() is False


def evidence_package(**overrides: object) -> ReleaseEvidencePackage:
    defaults: dict[str, object] = {
        "package_id": "release-evidence.1.5.0",
        "manifest_reference": "manifest.release.1.5.0",
        "source_reference": "commit.a" * 5,
        "artifact_references": ("artifact.backend.1.5.0",),
        "digest_references": ("sha256:" + "a" * 64,),
        "signature_references": ("signature.backend.1.5.0",),
        "sbom_reference": "sbom.1.5.0",
        "provenance_reference": "provenance.1.5.0",
        "requirement_and_document_versions": ("docs.044:v1.0.0",),
        "component_versions": ("api:v1", "schema:v3"),
        "test_and_evaluation_results": ("test-report.1.5.0: 5540 passed",),
        "security_findings_and_remediation_state": ("No open critical findings.",),
        "operational_evidence": ("performance-report.1.5.0",),
        "deployment_path_evidence": ("upgrade-test.1.4.x-to-1.5.0",),
        "open_defects": (),
        "known_issues": (),
        "exceptions": (),
        "residual_risk_notes": (),
        "reviewer_decisions": ("architecture-owner: approve",),
        "final_approval_reference": "approval.1.5.0",
        "access_control_reference": "access-policy.release-evidence",
        "retention_policy_reference": "retention-policy.release-evidence",
    }
    defaults.update(overrides)
    return ReleaseEvidencePackage(**defaults)  # type: ignore[arg-type]


def test_evidence_package_accepts_valid_state() -> None:
    assert evidence_package().package_id == "release-evidence.1.5.0"


def test_evidence_package_requires_access_control_reference() -> None:
    with pytest.raises(ValueError, match="access-controlled"):
        evidence_package(access_control_reference="")


def test_evidence_package_requires_retention_policy_reference() -> None:
    with pytest.raises(ValueError, match="retained by policy"):
        evidence_package(retention_policy_reference="")


def test_evidence_package_rejects_secret_looking_test_result() -> None:
    with pytest.raises(ValueError, match="secret-free"):
        evidence_package(test_and_evaluation_results=("api_key: AKIAABCDEFGHIJKLMNOP",))
