from __future__ import annotations

import pytest

from atlas.modules.mcp_plugin_sdk.domain.security_restricted_network import (
    RestrictedNetworkCapability,
    RestrictedNetworkSupportDeclaration,
    SdkSecurityRequirement,
    SecurityRequirementCompliance,
)


def test_security_requirement_compliance_requires_every_requirement() -> None:
    with pytest.raises(ValueError, match="every requirement"):
        SecurityRequirementCompliance(
            package_reference="connector.example.storage:v1.0.0",
            satisfied_requirements=frozenset(
                {SdkSecurityRequirement.DEPENDENCY_PINNING_AND_SCANNING}
            ),
        )


def test_security_requirement_compliance_accepts_full_set() -> None:
    compliance = SecurityRequirementCompliance(
        package_reference="connector.example.storage:v1.0.0",
        satisfied_requirements=frozenset(SdkSecurityRequirement),
    )
    assert compliance.package_reference == "connector.example.storage:v1.0.0"


def test_restricted_network_support_requires_every_capability() -> None:
    with pytest.raises(ValueError, match="every capability"):
        RestrictedNetworkSupportDeclaration(
            sdk_binding_version="1.0.0",
            provided_capabilities=frozenset({RestrictedNetworkCapability.LOCAL_MOCK_TARGETS}),
        )


def test_restricted_network_support_accepts_full_set() -> None:
    declaration = RestrictedNetworkSupportDeclaration(
        sdk_binding_version="1.0.0",
        provided_capabilities=frozenset(RestrictedNetworkCapability),
    )
    assert declaration.sdk_binding_version == "1.0.0"


def test_restricted_network_support_requires_sdk_binding_version() -> None:
    with pytest.raises(ValueError, match="requires an SDK version"):
        RestrictedNetworkSupportDeclaration(
            sdk_binding_version="",
            provided_capabilities=frozenset(RestrictedNetworkCapability),
        )
