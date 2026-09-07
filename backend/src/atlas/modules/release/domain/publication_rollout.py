"""ATLAS-059 SS22/SS23: publication and rollout."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.release.domain.manifest_notes import SupportStatus


def publication_includes_unapproved_or_unsigned_artifacts() -> bool:
    """SS22: "publish only approved signed artifacts and manifest.\""""
    return False


class PublicationArtifactKind(StrEnum):
    """SS22: "publish checksums, signatures, SBOM, provenance, compatibility, documentation,
    and release notes.\""""

    CHECKSUMS = "checksums"
    SIGNATURES = "signatures"
    SBOM = "sbom"
    PROVENANCE = "provenance"
    COMPATIBILITY = "compatibility"
    DOCUMENTATION = "documentation"
    RELEASE_NOTES = "release_notes"


@dataclass(frozen=True, slots=True)
class PublicationRecord:
    """SS22's declared elements."""

    manifest_reference: str
    published_artifact_kinds: frozenset[PublicationArtifactKind]
    protected_tag_reference: str
    mirrored_enterprise_channels: tuple[str, ...]
    offline_bundle_reference: str | None
    download_path_verified: bool
    offline_import_path_verified: bool
    announced_support_status: SupportStatus
    announced_deprecation_date: datetime | None
    publication_audit_event_reference: str
    artifact_location_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.manifest_reference.strip():
            raise ValueError("a publication record requires a manifest reference")
        missing = set(PublicationArtifactKind) - self.published_artifact_kinds
        if missing:
            raise ValueError(
                "a publication record requires every published artifact kind, missing "
                f"{sorted(kind.value for kind in missing)}"
            )
        if not self.protected_tag_reference.strip():
            raise ValueError("a publication record requires a protected tag reference")
        if not self.download_path_verified:
            raise ValueError("SS22: verify download ... paths")
        if not self.offline_import_path_verified:
            raise ValueError("SS22: verify ... offline import paths")
        if not self.publication_audit_event_reference.strip():
            raise ValueError("a publication record requires a publication audit event reference")
        if not self.artifact_location_references:
            raise ValueError("a publication record requires artifact locations")


@dataclass(frozen=True, slots=True)
class RolloutPlan:
    """SS23: "rollout plan identifies environments, cohorts, timing, owners, metrics, abort,
    and rollback criteria.\""""

    environments: tuple[str, ...]
    cohorts: tuple[str, ...]
    timing: str
    owners: tuple[str, ...]
    metrics: tuple[str, ...]
    abort_criteria: tuple[str, ...]
    rollback_criteria: tuple[str, ...]
    artifact_digest: str
    uses_canary_or_phased_rollout: bool
    monitored_signals: tuple[str, ...]
    customer_or_environment_differences: tuple[str, ...]
    production_change_approval_reference: str

    def __post_init__(self) -> None:
        if not self.environments:
            raise ValueError("a rollout plan requires environments")
        if not self.timing.strip():
            raise ValueError("a rollout plan requires timing")
        if not self.owners:
            raise ValueError("a rollout plan requires owners")
        if not self.abort_criteria:
            raise ValueError("a rollout plan requires abort criteria")
        if not self.rollback_criteria:
            raise ValueError("a rollout plan requires rollback criteria")
        if not self.artifact_digest.strip():
            raise ValueError("a rollout plan requires an artifact digest")
        if not self.monitored_signals:
            raise ValueError("a rollout plan requires monitored signals")
        if not self.production_change_approval_reference.strip():
            raise ValueError(
                "SS23: production change approval is separate from product release approval, "
                "and is required here"
            )


def ai_can_initiate_or_approve_rollout() -> bool:
    """SS23: "Atlas AI cannot initiate or approve rollout.\""""
    return False


def production_change_approval_is_the_same_as_product_release_approval() -> bool:
    """SS23: "production change approval is separate from product release approval.\""""
    return False
