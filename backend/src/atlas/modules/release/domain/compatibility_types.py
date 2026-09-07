"""ATLAS-059 SS7/SS8: the compatibility matrix and release types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.release.domain.versioning import SemanticVersion


@dataclass(frozen=True, slots=True)
class CompatibilityMatrixEntry:
    """SS7's ten declared elements. "Compatibility is backed by test evidence and has an owner"
    is a required, non-empty `evidence_references` plus a required `owner`."""

    platform_version: SemanticVersion
    component_versions: tuple[tuple[str, str], ...]
    supported_source_versions_for_upgrade: tuple[str, ...]
    infrastructure_versions: tuple[tuple[str, str], ...]
    api_and_event_major_versions: tuple[str, ...]
    connector_sdk_and_package_compatibility: tuple[str, ...]
    supported_vendor_products: tuple[str, ...]
    model_endpoint_protocol_and_approved_profiles: tuple[str, ...]
    supported_platform_environment_versions: tuple[str, ...]
    deployment_and_offline_bundle_profiles: tuple[str, ...]
    known_incompatible_combinations: tuple[str, ...]
    evidence_references: tuple[str, ...]
    owner: str

    def __post_init__(self) -> None:
        if not self.evidence_references:
            raise ValueError("SS7: compatibility is backed by test evidence")
        if not self.owner.strip():
            raise ValueError("SS7: compatibility has an owner")


class ReleaseType(StrEnum):
    """SS8's ten release types."""

    DEVELOPMENT_SNAPSHOT = "development_snapshot"
    ALPHA = "alpha"
    BETA = "beta"
    RELEASE_CANDIDATE = "release_candidate"
    GENERAL_RELEASE = "general_release"
    SECURITY_RELEASE = "security_release"
    HOTFIX = "hotfix"
    LTS_RELEASE = "lts_release"
    CONNECTOR_RELEASE = "connector_release"
    DOCUMENTATION_RELEASE = "documentation_release"


_PRERELEASE_TYPES = frozenset(
    {
        ReleaseType.DEVELOPMENT_SNAPSHOT,
        ReleaseType.ALPHA,
        ReleaseType.BETA,
        ReleaseType.RELEASE_CANDIDATE,
    }
)


def is_production_supported(release_type: ReleaseType, *, explicitly_stated: bool) -> bool:
    """SS8: "snapshots and prereleases are not production-supported unless explicitly
    stated.\""""
    if release_type in _PRERELEASE_TYPES:
        return explicitly_stated
    return True
