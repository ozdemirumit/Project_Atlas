"""ATLAS-021 SS31/SS32: security requirements and restricted-network development."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class SdkSecurityRequirement(StrEnum):
    """SS31's ten security requirements."""

    DEPENDENCY_PINNING_AND_SCANNING = "dependency_pinning_and_scanning"
    NO_ARBITRARY_PACKAGE_INSTALL_HOOKS_IN_PRODUCTION_BUILD = (
        "no_arbitrary_package_install_hooks_in_production_build"
    )
    NO_EMBEDDED_SECRETS = "no_embedded_secrets"
    RESTRICTED_NETWORK_DURING_BUILD_AND_TEST_WHERE_PRACTICAL = (
        "restricted_network_during_build_and_test_where_practical"
    )
    SAFE_CLIENT_WRAPPERS = "safe_client_wrappers"
    TYPED_CAPABILITY_SCHEMAS = "typed_capability_schemas"
    CLI_ARGUMENT_SAFETY = "cli_argument_safety"
    REDACTED_TELEMETRY = "redacted_telemetry"
    TEST_EVIDENCE_FOR_CAPABILITY_CLASS_AND_SIDE_EFFECTS = (
        "test_evidence_for_capability_class_and_side_effects"
    )
    SIGNED_OR_INTEGRITY_VERIFIABLE_RELEASE_ARTIFACTS = (
        "signed_or_integrity_verifiable_release_artifacts"
    )


@dataclass(frozen=True, slots=True)
class SecurityRequirementCompliance:
    package_reference: str
    satisfied_requirements: frozenset[SdkSecurityRequirement]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.package_reference, "package_reference")
        missing = set(SdkSecurityRequirement) - self.satisfied_requirements
        if missing:
            raise ValueError(
                "a security requirement compliance record requires every requirement, "
                f"missing {sorted(requirement.value for requirement in missing)}"
            )


class RestrictedNetworkCapability(StrEnum):
    """SS32's six restricted-network development capabilities."""

    MIRRORED_LANGUAGE_PACKAGES_AND_TOOLS = "mirrored_language_packages_and_tools"
    OFFLINE_API_DOCUMENTATION_AND_SCHEMAS = "offline_api_documentation_and_schemas"
    LOCAL_MOCK_TARGETS = "local_mock_targets"
    REPRODUCIBLE_TOOLCHAIN_BUNDLE = "reproducible_toolchain_bundle"
    PACKAGE_VALIDATION_WITHOUT_PUBLIC_SERVICES = "package_validation_without_public_services"
    INTERNAL_PACKAGE_AND_CONNECTOR_REGISTRIES = "internal_package_and_connector_registries"


@dataclass(frozen=True, slots=True)
class RestrictedNetworkSupportDeclaration:
    sdk_binding_version: str
    provided_capabilities: frozenset[RestrictedNetworkCapability]

    def __post_init__(self) -> None:
        if not self.sdk_binding_version.strip():
            raise ValueError("a restricted-network support declaration requires an SDK version")
        missing = set(RestrictedNetworkCapability) - self.provided_capabilities
        if missing:
            raise ValueError(
                "a restricted-network support declaration requires every capability, "
                f"missing {sorted(capability.value for capability in missing)}"
            )
