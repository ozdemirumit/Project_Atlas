from __future__ import annotations

from pathlib import Path

import pytest

AI_MODULES = (
    ("knowledge", "model_context_assembly.py"),
    ("ai", "protected_model_invocation.py"),
    ("ai", "protected_draft_adjudication.py"),
    ("ai", "protected_answer_presentation.py"),
    ("ai", "protected_recommendation_candidate_generation.py"),
    ("ai", "protected_candidate_impact_enrichment.py"),
    ("ai", "protected_candidate_risk_recovery_completion.py"),
    ("ai", "protected_recommendation_adjudication.py"),
    ("ai", "protected_recommendation_presentation.py"),
)

AI_ROUTE_MODULES = (
    "model_context_assembly.py",
    "protected_model_invocation.py",
    "protected_draft_adjudication.py",
    "protected_answer_presentations.py",
    "protected_recommendation_candidates.py",
    "protected_candidate_impacts.py",
    "protected_candidate_risk_recovery.py",
    "protected_recommendation_adjudications.py",
    "protected_recommendation_presentations.py",
)


@pytest.mark.parametrize(("module_group", "module_name"), AI_MODULES)
def test_ai_services_do_not_embed_global_mfa_gates(module_group: str, module_name: str) -> None:
    application_root = (
        Path(__file__).parents[1] / "src" / "atlas" / "modules" / module_group / "application"
    )
    source = (application_root / module_name).read_text(encoding="utf-8")

    assert "AuthenticationMethod.DEVELOPMENT" not in source
    assert "enterprise_human_hardware_mfa_required" not in source
    assert "required_assurance_level=AssuranceLevel.MULTI_FACTOR" not in source
    assert "required_assurance_level=AssuranceLevel.HARDWARE_BACKED" not in source


@pytest.mark.parametrize("module_name", AI_ROUTE_MODULES)
def test_ai_routes_do_not_reference_removed_mfa_errors(module_name: str) -> None:
    routes_root = Path(__file__).parents[1] / "src" / "atlas" / "api" / "routes"
    source = (routes_root / module_name).read_text(encoding="utf-8")

    assert "mfa_required" not in source


@pytest.mark.parametrize(("module_group", "module_name"), AI_MODULES)
def test_ai_policy_domains_allow_optional_step_up(module_group: str, module_name: str) -> None:
    domain_root = Path(__file__).parents[1] / "src" / "atlas" / "modules" / module_group / "domain"
    source = (domain_root / module_name).read_text(encoding="utf-8")

    assert "required_assurance_level" in source
    assert "AssuranceLevel.SINGLE_FACTOR" in source
    assert "AssuranceLevel.MULTI_FACTOR" in source
    assert "AssuranceLevel.HARDWARE_BACKED" in source
    assert "required_assurance_level is not AssuranceLevel.HARDWARE_BACKED" not in source
