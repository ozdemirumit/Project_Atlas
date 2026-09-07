"""ATLAS-059 SS4/SS5/SS6: release principles, the versioning model, and independent artifact
versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


def published_artifact_contents_can_change_under_same_version_or_digest() -> bool:
    """SS4: "published artifact contents never change under the same version or digest.\""""
    return False


def semantic_compatibility_is_inferred_from_version_numbers_alone() -> bool:
    """SS4: "semantic compatibility is documented, not inferred from version numbers
    alone.\""""
    return False


def promotion_rebuilds_artifacts_instead_of_reusing_signed_digests() -> bool:
    """SS4: "build once and promote the same signed digests.\""""
    return False


def required_gates_can_be_waived_without_a_recorded_exception() -> bool:
    """SS4: "required safety, security, audit, migration, backup, and restore gates cannot be
    waived casually." The concrete, checkable form of "casually" is: never without a recorded
    exception -- see `known_issues.ReleaseException` (SS36)."""
    return False


def ai_quality_improvement_can_offset_a_failed_invariant_guardrail() -> bool:
    """SS4: "AI quality improvement cannot offset a failed invariant guardrail.\""""
    return False


def offline_customers_receive_lesser_integrity_or_evidence() -> bool:
    """SS4: "offline customers receive equivalent integrity and evidence.\""""
    return False


def version_changes_follow_marketing_preference_over_impact_analysis() -> bool:
    """SS5: "version changes follow impact analysis, not marketing preference.\""""
    return False


class PrereleaseLabel(StrEnum):
    """SS5: "prerelease labels include `alpha`, `beta`, and `rc.N`.\""""

    ALPHA = "alpha"
    BETA = "beta"
    RC = "rc"


@dataclass(frozen=True, slots=True)
class SemanticVersion:
    """SS5: `MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]`, modeled structurally rather than as a raw
    string so a caller cannot construct a malformed version string by hand."""

    major: int
    minor: int
    patch: int
    prerelease_label: PrereleaseLabel | None
    prerelease_number: int | None
    build_metadata: str | None

    def __post_init__(self) -> None:
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("major, minor, and patch must not be negative")
        if self.prerelease_label is None and self.prerelease_number is not None:
            raise ValueError("prerelease_number is only meaningful with a prerelease_label")
        if self.prerelease_label is PrereleaseLabel.RC and self.prerelease_number is None:
            raise ValueError("an rc prerelease requires a prerelease_number (rc.N)")
        if self.prerelease_number is not None and self.prerelease_number < 0:
            raise ValueError("prerelease_number must not be negative")

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease_label is not None:
            version += f"-{self.prerelease_label.value}"
            if self.prerelease_number is not None:
                version += f".{self.prerelease_number}"
        if self.build_metadata is not None:
            version += f"+{self.build_metadata}"
        return version

    @property
    def is_prerelease(self) -> bool:
        return self.prerelease_label is not None


class VersionedArtifactCategory(StrEnum):
    """SS6's eleven independently-versioned artifact categories."""

    BACKEND_AND_FRONTEND_APPLICATIONS = "backend_and_frontend_applications"
    PUBLIC_AND_INTERNAL_APIS = "public_and_internal_apis"
    EVENT_AND_SCHEMA_CONTRACTS = "event_and_schema_contracts"
    DATABASE_MIGRATIONS_AND_SCHEMA_RANGE = "database_migrations_and_schema_range"
    CONNECTOR_GATEWAY_SDK_AND_CONNECTOR_PACKAGES = "connector_gateway_sdk_and_connector_packages"
    WORKFLOW_AND_POLICY_SCHEMAS_AND_SEED_PACKAGES = "workflow_and_policy_schemas_and_seed_packages"
    AGENT_PROMPT_MODEL_PROFILE_GUARDRAIL_AND_EVALUATION_PACKAGES = (
        "agent_prompt_model_profile_guardrail_and_evaluation_packages"
    )
    RUNBOOKS_KNOWLEDGE_PACKS_REPORTS_AND_MAPPINGS = "runbooks_knowledge_packs_reports_and_mappings"
    DEPLOYMENT_CHARTS_CONFIGURATION_SCHEMA_AND_BOOTSTRAP_TOOLS = (
        "deployment_charts_configuration_schema_and_bootstrap_tools"
    )
    DOCUMENTATION_SET = "documentation_set"
    OFFLINE_BUNDLE_FORMAT = "offline_bundle_format"


@dataclass(frozen=True, slots=True)
class ArtifactVersionPin:
    category: VersionedArtifactCategory
    identifier: str
    version: SemanticVersion

    def __post_init__(self) -> None:
        validate_stable_identifier(self.identifier, "identifier")
