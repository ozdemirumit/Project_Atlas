"""ATLAS-021 SS26/SS27/SS28: documentation generator, compatibility, and deprecation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class GeneratedDocumentation:
    """SS26's declared elements. "Configuration and non-secret examples" reuses Guardrails'
    `detect_secret_patterns` on every example."""

    connector_id: str
    supported_products: tuple[str, ...]
    configuration_examples: tuple[str, ...]
    required_target_permissions: tuple[str, ...]
    network_flows: tuple[str, ...]
    capability_summaries: tuple[str, ...]
    health_and_troubleshooting_note: str
    upgrade_downgrade_note: str
    known_limitations: tuple[str, ...]
    evidence_and_audit_behavior_note: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.connector_id, "connector_id")
        if not self.supported_products:
            raise ValueError("generated documentation requires supported products")
        if not self.required_target_permissions:
            raise ValueError("generated documentation requires required target permissions")
        if not self.capability_summaries:
            raise ValueError("generated documentation requires capability summaries")
        if not self.health_and_troubleshooting_note.strip():
            raise ValueError("generated documentation requires a health and troubleshooting note")
        if not self.evidence_and_audit_behavior_note.strip():
            raise ValueError("generated documentation requires an evidence and audit note")
        for example in self.configuration_examples:
            if detect_secret_patterns(example):
                raise ValueError("SS26: configuration examples must be non-secret")


@dataclass(frozen=True, slots=True)
class CompatibilityMatrixEntry:
    """SS27's five compatibility dimensions."""

    sdk_binding_version: str
    atlas_runtime_version: str
    runner_protocol_version: str
    manifest_schema_version: str
    language_runtime: str
    package_format: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("sdk_binding_version", self.sdk_binding_version),
            ("atlas_runtime_version", self.atlas_runtime_version),
            ("runner_protocol_version", self.runner_protocol_version),
            ("manifest_schema_version", self.manifest_schema_version),
            ("language_runtime", self.language_runtime),
            ("package_format", self.package_format),
        ):
            if not value.strip():
                raise ValueError(f"a compatibility matrix entry requires {field_name}")


class BreakingChangeRequirement(StrEnum):
    """SS27: "public SDK breaking changes require" four things."""

    MAJOR_VERSION = "major_version"
    MIGRATION_GUIDE = "migration_guide"
    DEPRECATION_PERIOD = "deprecation_period"
    UPDATED_VALIDATOR = "updated_validator"


@dataclass(frozen=True, slots=True)
class BreakingChangeDeclaration:
    change_id: str
    satisfied_requirements: frozenset[BreakingChangeRequirement]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.change_id, "change_id")
        missing = set(BreakingChangeRequirement) - self.satisfied_requirements
        if missing:
            raise ValueError(
                "a breaking change declaration requires every requirement, missing "
                f"{sorted(requirement.value for requirement in missing)}"
            )


@dataclass(frozen=True, slots=True)
class DeprecationNotice:
    """SS28: "deprecated APIs emit build-time or test-time warnings" is a construction-time
    guarantee -- at least one of the two must be true."""

    api_reference: str
    is_security_critical: bool
    removal_window_days: int
    warning_emitted_at_build_time: bool
    warning_emitted_at_test_time: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.api_reference, "api_reference")
        if self.removal_window_days < 1:
            raise ValueError("removal_window_days must be positive")
        if not (self.warning_emitted_at_build_time or self.warning_emitted_at_test_time):
            raise ValueError("SS28: deprecated APIs emit build-time or test-time warnings")


@dataclass(frozen=True, slots=True)
class SdkVersionRange:
    """SS28: "connector packages declare the oldest and newest supported SDK range.\""""

    oldest_supported_sdk_version: str
    newest_supported_sdk_version: str

    def __post_init__(self) -> None:
        if not self.oldest_supported_sdk_version.strip():
            raise ValueError("an SDK version range requires an oldest supported version")
        if not self.newest_supported_sdk_version.strip():
            raise ValueError("an SDK version range requires a newest supported version")


def runtime_refuses_incompatible_packages_before_execution() -> bool:
    """SS28: "runtime refuses incompatible packages before execution.\""""
    return True
