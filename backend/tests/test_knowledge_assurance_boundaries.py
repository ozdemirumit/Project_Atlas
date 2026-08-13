from __future__ import annotations

from pathlib import Path

import pytest

KNOWLEDGE_APPLICATION_MODULES = (
    "evidence_draft.py",
    "draft_review_request.py",
    "reviewer_assignment.py",
    "protected_inspection.py",
    "protected_content.py",
    "review_finding.py",
    "finding_presentation.py",
    "review_decision.py",
    "correction_resubmission.py",
    "final_resolution.py",
    "publication_preparation.py",
    "source_materialization.py",
    "deterministic_chunking.py",
    "embedding_generation.py",
    "index_staging_validation.py",
    "retrieval_index_publication.py",
    "protected_retrieval.py",
)

KNOWLEDGE_ROUTE_MODULES = (
    "evidence_drafts.py",
    "draft_review_requests.py",
    "reviewer_assignments.py",
    "protected_inspections.py",
    "protected_content.py",
    "review_findings.py",
    "finding_presentations.py",
    "review_decisions.py",
    "correction_resubmissions.py",
    "final_resolutions.py",
    "publication_preparations.py",
    "source_materializations.py",
    "deterministic_chunking.py",
    "embedding_generation.py",
    "index_staging_validation.py",
    "retrieval_index_publication.py",
    "protected_retrieval.py",
)

KNOWLEDGE_POLICY_DOMAIN_MODULES = (
    "evidence_draft.py",
    "draft_review_request.py",
    "reviewer_assignment.py",
    "protected_inspection.py",
    "protected_content.py",
    "review_finding.py",
    "finding_presentation.py",
    "review_decision.py",
    "correction_resubmission.py",
    "protected_retrieval.py",
)


@pytest.mark.parametrize("module_name", KNOWLEDGE_APPLICATION_MODULES)
def test_knowledge_services_do_not_embed_global_mfa_gates(module_name: str) -> None:
    application_root = (
        Path(__file__).parents[1] / "src" / "atlas" / "modules" / "knowledge" / "application"
    )
    source = (application_root / module_name).read_text(encoding="utf-8")

    assert "AuthenticationMethod.DEVELOPMENT" not in source
    assert "enterprise_human_hardware_mfa_required" not in source
    assert "required_assurance_level=AssuranceLevel.MULTI_FACTOR" not in source
    assert "required_assurance_level=AssuranceLevel.HARDWARE_BACKED" not in source


@pytest.mark.parametrize("module_name", KNOWLEDGE_ROUTE_MODULES)
def test_knowledge_routes_do_not_reference_removed_mfa_errors(module_name: str) -> None:
    routes_root = Path(__file__).parents[1] / "src" / "atlas" / "api" / "routes"
    source = (routes_root / module_name).read_text(encoding="utf-8")

    assert "mfa_required" not in source


@pytest.mark.parametrize("module_name", KNOWLEDGE_POLICY_DOMAIN_MODULES)
def test_knowledge_policy_domains_allow_optional_step_up(module_name: str) -> None:
    domain_root = Path(__file__).parents[1] / "src" / "atlas" / "modules" / "knowledge" / "domain"
    source = (domain_root / module_name).read_text(encoding="utf-8")

    assert "AssuranceLevel.SINGLE_FACTOR" in source
    assert "AssuranceLevel.MULTI_FACTOR" in source
    assert "AssuranceLevel.HARDWARE_BACKED" in source
    assert "required_assurance_level is not AssuranceLevel.HARDWARE_BACKED" not in source
