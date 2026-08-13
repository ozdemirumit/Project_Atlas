from __future__ import annotations

from pathlib import Path

import pytest

RECOMMENDATION_REVIEW_MODULES = (
    "promotion.py",
    "readiness.py",
    "review_request.py",
    "reviewer_assignment.py",
    "protected_inspection.py",
    "protected_content.py",
    "human_review_finding.py",
    "finding_presentation.py",
    "review_decision.py",
    "correction_resubmission.py",
    "final_disposition.py",
)

RECOMMENDATION_REVIEW_ROUTE_MODULES = (
    "recommendation_promotions.py",
    "recommendation_readiness.py",
    "recommendation_review_requests.py",
    "recommendation_reviewer_assignments.py",
    "recommendation_protected_inspections.py",
    "recommendation_protected_contents.py",
    "recommendation_human_review_findings.py",
    "recommendation_finding_presentations.py",
    "recommendation_review_decisions.py",
    "recommendation_correction_resubmissions.py",
    "final_recommendation_dispositions.py",
)


@pytest.mark.parametrize("module_name", RECOMMENDATION_REVIEW_MODULES)
def test_recommendation_review_services_do_not_embed_global_mfa_gates(
    module_name: str,
) -> None:
    root = Path(__file__).parents[1] / "src" / "atlas" / "modules" / "recommendations"
    source = (root / "application" / module_name).read_text(encoding="utf-8")

    assert "AuthenticationMethod.DEVELOPMENT" not in source
    assert "enterprise_human_hardware_mfa_required" not in source
    assert "required_assurance_level=AssuranceLevel.MULTI_FACTOR" not in source
    assert "required_assurance_level=AssuranceLevel.HARDWARE_BACKED" not in source


@pytest.mark.parametrize("module_name", RECOMMENDATION_REVIEW_ROUTE_MODULES)
def test_recommendation_review_routes_do_not_reference_removed_mfa_errors(
    module_name: str,
) -> None:
    root = Path(__file__).parents[1] / "src" / "atlas" / "api" / "routes"
    source = (root / module_name).read_text(encoding="utf-8")

    assert "mfa_required" not in source


@pytest.mark.parametrize("module_name", RECOMMENDATION_REVIEW_MODULES)
def test_recommendation_review_policy_domains_allow_optional_step_up(
    module_name: str,
) -> None:
    root = Path(__file__).parents[1] / "src" / "atlas" / "modules" / "recommendations"
    source = (root / "domain" / module_name).read_text(encoding="utf-8")

    assert "required_assurance_level" in source
    assert "AssuranceLevel.SINGLE_FACTOR" in source
    assert "AssuranceLevel.MULTI_FACTOR" in source
    assert "AssuranceLevel.HARDWARE_BACKED" in source
    assert "required_assurance_level is not AssuranceLevel.HARDWARE_BACKED" not in source
