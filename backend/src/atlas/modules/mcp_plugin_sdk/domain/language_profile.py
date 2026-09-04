"""ATLAS-021 SS8: language profiles, completing the MCP Plugin SDK's modeled contract surface.

"Other language profiles must pass the same contract suite" needs no special-casing here: every
`LanguageProfile` instance is validated by the same single `__post_init__`, regardless of which
language it declares -- there is no separate, looser validator a second profile could use.

This subsystem has no dedicated audit slice, unlike Reasoning/Decision Engine/Change Impact/
AI Agents: SS19 states plainly that "connector handlers do not write directly to the audit
store... the platform owns authoritative actor, authorization, policy, and approval references,"
and SS22's Audit Metadata API (`telemetry_audit.AuditMetadataSubmission`) already covers the one
thing an SDK-authored connector contributes to audit -- structured execution metadata handed to
the runner/gateway, not a direct write. Building a second `application/audit.py` here would
invent a write path this document deliberately does not give the SDK.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.identity.domain.models import validate_stable_identifier


def language_profile_requires_adr_before_implementation() -> bool:
    """SS8: "a Python-first SDK is a candidate ... but requires an ADR before implementation.\""""
    return True


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    """SS8's eight declared elements."""

    profile_id: str
    supported_language: str
    supported_runtime_versions: tuple[str, ...]
    project_layout_reference: str
    package_manager: str
    sdk_binding_version: str
    dependency_lock_requirement: str
    static_analysis_and_formatting_tools: tuple[str, ...]
    test_runner: str
    package_format: str
    entry_point_convention: str
    runner_base_image_or_prerequisites: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.profile_id, "profile_id")
        if not self.supported_language.strip():
            raise ValueError("a language profile requires a supported language")
        if not self.supported_runtime_versions:
            raise ValueError("a language profile requires at least one supported runtime version")
        if not self.project_layout_reference.strip():
            raise ValueError("a language profile requires a project layout reference")
        if not self.package_manager.strip():
            raise ValueError("a language profile requires a package manager")
        if not self.sdk_binding_version.strip():
            raise ValueError("a language profile requires an SDK binding version")
        if not self.dependency_lock_requirement.strip():
            raise ValueError("a language profile requires a dependency-lock requirement")
        if not self.static_analysis_and_formatting_tools:
            raise ValueError(
                "a language profile requires at least one static analysis or formatting tool"
            )
        if not self.test_runner.strip():
            raise ValueError("a language profile requires a test runner")
        if not self.package_format.strip():
            raise ValueError("a language profile requires a package format")
        if not self.entry_point_convention.strip():
            raise ValueError("a language profile requires an entry point convention")
        if not self.runner_base_image_or_prerequisites.strip():
            raise ValueError(
                "a language profile requires a runner base image or runtime prerequisites"
            )
