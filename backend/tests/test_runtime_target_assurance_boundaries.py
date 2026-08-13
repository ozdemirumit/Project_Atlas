from __future__ import annotations

from pathlib import Path

import pytest

RUNTIME_TARGET_APPLICATION_MODULES = (
    "target_configuration.py",
    "credential_assignment.py",
    "configuration_validation.py",
    "capability_enablement.py",
    "runtime_trust.py",
    "secret_brokerage.py",
    "runtime_activation.py",
    "target_session.py",
    "invocation_authorization.py",
    "bounded_invocation.py",
    "invocation_evidence.py",
)

RUNTIME_TARGET_ROUTE_MODULES = (
    "target_configuration.py",
    "credential_assignments.py",
    "configuration_validations.py",
    "capability_enablements.py",
    "runtime_trust_grants.py",
    "secret_brokerage_authorizations.py",
    "runtime_activations.py",
    "target_session_verifications.py",
    "invocation_authorizations.py",
    "bounded_invocations.py",
    "invocation_evidence.py",
)

RUNTIME_TARGET_DOMAIN_MODULES = RUNTIME_TARGET_APPLICATION_MODULES


@pytest.mark.parametrize("module_name", RUNTIME_TARGET_APPLICATION_MODULES)
def test_runtime_target_services_do_not_embed_global_mfa_gates(module_name: str) -> None:
    application_root = (
        Path(__file__).parents[1] / "src" / "atlas" / "modules" / "connectors" / "application"
    )
    source = (application_root / module_name).read_text(encoding="utf-8")

    assert "enterprise_human_mfa_required" not in source
    assert "AuthenticationMethod.DEVELOPMENT" not in source
    assert "required_assurance_level=AssuranceLevel.MULTI_FACTOR" not in source
    assert "required_assurance_level=AssuranceLevel.HARDWARE_BACKED" not in source


@pytest.mark.parametrize("module_name", RUNTIME_TARGET_ROUTE_MODULES)
def test_runtime_target_routes_do_not_reference_removed_mfa_errors(module_name: str) -> None:
    routes_root = Path(__file__).parents[1] / "src" / "atlas" / "api" / "routes"
    source = (routes_root / module_name).read_text(encoding="utf-8")

    assert "enterprise_human_mfa_required" not in source


@pytest.mark.parametrize("module_name", RUNTIME_TARGET_DOMAIN_MODULES)
def test_runtime_target_policy_domains_allow_single_factor(module_name: str) -> None:
    domain_root = Path(__file__).parents[1] / "src" / "atlas" / "modules" / "connectors" / "domain"
    source = (domain_root / module_name).read_text(encoding="utf-8")

    assert "AssuranceLevel.SINGLE_FACTOR" in source
    assert "required_assurance_level is not AssuranceLevel.HARDWARE_BACKED" not in source
