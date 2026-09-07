"""ATLAS-059 SS20/SS21: the release manifest and release notes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.release.domain.versioning import SemanticVersion


class SupportStatus(StrEnum):
    """SS20/SS32's five support-status phases."""

    FULL_SUPPORT = "full_support"
    MAINTENANCE = "maintenance"
    SECURITY_ONLY = "security_only"
    DEPRECATED = "deprecated"
    END_OF_SUPPORT = "end_of_support"


@dataclass(frozen=True, slots=True)
class ManifestArtifactEntry:
    name: str
    version: str
    digest: str
    signature: str
    source: str
    required: bool

    def __post_init__(self) -> None:
        for field_name, value in (
            ("name", self.name),
            ("version", self.version),
            ("digest", self.digest),
            ("signature", self.signature),
            ("source", self.source),
        ):
            if not value.strip():
                raise ValueError(f"a manifest artifact entry requires {field_name}")


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """SS20's eleven declared elements."""

    release_version: SemanticVersion
    channel: str
    release_date: datetime
    support_status: SupportStatus
    artifacts: tuple[ManifestArtifactEntry, ...]
    compatibility_matrix_reference: str
    supported_install_paths: tuple[str, ...]
    supported_upgrade_paths: tuple[str, ...]
    configuration_version: str
    migration_version: str
    component_versions: tuple[tuple[str, str], ...]
    sbom_reference: str
    provenance_reference: str
    release_notes_reference: str
    known_issues_references: tuple[str, ...]
    security_advisory_references: tuple[str, ...]
    offline_bundle_contents_reference: str | None
    offline_bundle_verification_profile: str | None
    approval_reference: str
    evidence_reference: str

    def __post_init__(self) -> None:
        if not self.channel.strip():
            raise ValueError("a release manifest requires a channel")
        if self.release_date.tzinfo is None:
            raise ValueError("release_date must be timezone-aware")
        if not self.artifacts:
            raise ValueError("a release manifest requires artifacts")
        if not self.compatibility_matrix_reference.strip():
            raise ValueError("a release manifest requires a compatibility matrix reference")
        if not self.configuration_version.strip():
            raise ValueError("a release manifest requires a configuration version")
        if not self.migration_version.strip():
            raise ValueError("a release manifest requires a migration version")
        if not self.sbom_reference.strip():
            raise ValueError("a release manifest requires an SBOM reference")
        if not self.provenance_reference.strip():
            raise ValueError("a release manifest requires a provenance reference")
        if not self.release_notes_reference.strip():
            raise ValueError("a release manifest requires a release notes reference")
        if not self.approval_reference.strip():
            raise ValueError("a release manifest requires an approval reference")
        if not self.evidence_reference.strip():
            raise ValueError("a release manifest requires an evidence reference")


@dataclass(frozen=True, slots=True)
class ReleaseNotes:
    """SS21's eleven declared elements. "AI can draft notes, but accountable owners verify
    every claim" -- `drafted_by_ai=True` requires a non-`None` `verified_by_accountable_owner`."""

    summary: str
    intended_use: str
    new_capabilities_and_behavior_changes: tuple[str, ...]
    security_and_privacy_changes: tuple[str, ...]
    ai_model_retrieval_and_guardrail_changes: tuple[str, ...]
    contract_changes: tuple[str, ...]
    deployment_and_resource_changes: tuple[str, ...]
    compatibility_deprecation_and_removed_support: tuple[str, ...]
    upgrade_prerequisites_and_expected_duration: str
    rollback_or_recovery_constraints: str
    known_issues_workarounds_and_residual_risk: tuple[str, ...]
    documentation_and_support_links: tuple[str, ...]
    drafted_by_ai: bool
    verified_by_accountable_owner: str | None

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("release notes require a summary")
        if not self.intended_use.strip():
            raise ValueError("release notes require an intended use")
        if not self.upgrade_prerequisites_and_expected_duration.strip():
            raise ValueError("release notes require upgrade prerequisites and expected duration")
        if not self.rollback_or_recovery_constraints.strip():
            raise ValueError("release notes require rollback or recovery constraints")
        if self.drafted_by_ai and self.verified_by_accountable_owner is None:
            raise ValueError("SS21: AI can draft notes, but accountable owners verify every claim")
