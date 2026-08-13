from __future__ import annotations

from pathlib import Path

import pytest

PACKAGE_APPLICATION_MODULES = (
    "acquisition.py",
    "authority_behavior_validation.py",
    "content_policy_scan.py",
    "contract_validation.py",
    "final_validation.py",
    "lab_self_test.py",
    "license_analysis.py",
    "malware_analysis.py",
    "package_approval.py",
    "package_installation.py",
    "package_registration.py",
    "package_signing.py",
    "publisher_attestation.py",
    "registry_publication.py",
    "runner_validation.py",
    "schema_semantics_validation.py",
    "static_dependency_analysis.py",
    "supply_chain_inventory.py",
    "validation_intake.py",
    "vulnerability_analysis.py",
)

PACKAGE_ROUTE_MODULES = (
    "authority_behavior_validations.py",
    "connector_validations.py",
    "connectors.py",
    "content_policy_scans.py",
    "contract_validations.py",
    "final_validations.py",
    "lab_self_tests.py",
    "license_analyses.py",
    "malware_analyses.py",
    "mcp_builder.py",
    "package_approvals.py",
    "package_installations.py",
    "package_registrations.py",
    "package_signing.py",
    "publisher_attestations.py",
    "registry_publications.py",
    "runner_validations.py",
    "schema_semantics_validations.py",
    "static_dependency_analyses.py",
    "supply_chain_inventories.py",
    "vulnerability_analyses.py",
)


@pytest.mark.parametrize("module_name", PACKAGE_APPLICATION_MODULES)
def test_package_services_do_not_embed_global_mfa_gates(module_name: str) -> None:
    application_root = (
        Path(__file__).parents[1] / "src" / "atlas" / "modules" / "connectors" / "application"
    )
    source = (application_root / module_name).read_text(encoding="utf-8")

    assert "enterprise_human_mfa_required" not in source
    assert "AuthenticationMethod.DEVELOPMENT" not in source
    assert "required_assurance_level=AssuranceLevel.MULTI_FACTOR" not in source
    assert "required_assurance_level=AssuranceLevel.HARDWARE_BACKED" not in source


@pytest.mark.parametrize("module_name", PACKAGE_ROUTE_MODULES)
def test_package_routes_do_not_reference_removed_mfa_errors(module_name: str) -> None:
    routes_root = Path(__file__).parents[1] / "src" / "atlas" / "api" / "routes"
    source = (routes_root / module_name).read_text(encoding="utf-8")

    assert "enterprise_human_mfa_required" not in source
