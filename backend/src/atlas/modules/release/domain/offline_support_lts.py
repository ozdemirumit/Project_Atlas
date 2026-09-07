"""ATLAS-059 SS31/SS32/SS33: offline release, support policy, and long-term support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.release.domain.manifest_notes import SupportStatus


def offline_bundle_content_can_diverge_from_approved_manifest() -> bool:
    """SS31: "bundle content exactly matches the approved manifest.\""""
    return False


class OfflineBundleContentKind(StrEnum):
    """SS31's eleven required offline bundle contents."""

    IMAGES = "images"
    PACKAGES = "packages"
    MODELS = "models"
    SCHEMAS = "schemas"
    MIGRATIONS = "migrations"
    DEPLOYMENT_ASSETS = "deployment_assets"
    DOCUMENTATION = "documentation"
    SBOM = "sbom"
    PROVENANCE = "provenance"
    CHECKSUMS = "checksums"
    VERIFICATION_TOOLS = "verification_tools"


@dataclass(frozen=True, slots=True)
class OfflineBundle:
    """SS31's declared elements."""

    bundle_id: str
    manifest_reference: str
    included_content_kinds: frozenset[OfflineBundleContentKind]
    malware_scanned: bool
    signed: bool
    encrypted: bool
    custody_ready: bool
    offline_import_test_reference: str
    offline_clean_install_or_upgrade_test_reference: str
    public_callback_scan_reference: str
    missing_dependency_scan_reference: str
    security_metadata_freshness_statement: str
    known_limitations: tuple[str, ...]
    excludes_production_secrets: bool
    excludes_customer_configuration: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.bundle_id, "bundle_id")
        if not self.manifest_reference.strip():
            raise ValueError("an offline bundle requires a manifest reference")
        missing = set(OfflineBundleContentKind) - self.included_content_kinds
        if missing:
            raise ValueError(
                "an offline bundle requires every content kind, missing "
                f"{sorted(kind.value for kind in missing)}"
            )
        if not self.malware_scanned:
            raise ValueError("SS31: bundle is malware-scanned")
        if not self.signed:
            raise ValueError("SS31: bundle is ... signed")
        if not self.custody_ready:
            raise ValueError("SS31: bundle is ... custody-ready")
        if not self.offline_import_test_reference.strip():
            raise ValueError("an offline bundle requires an offline import test")
        if not self.offline_clean_install_or_upgrade_test_reference.strip():
            raise ValueError("an offline bundle requires a clean install or upgrade test")
        if not self.public_callback_scan_reference.strip():
            raise ValueError("an offline bundle requires a public callback scan")
        if not self.missing_dependency_scan_reference.strip():
            raise ValueError("an offline bundle requires a missing dependency scan")
        if not self.security_metadata_freshness_statement.strip():
            raise ValueError("an offline bundle requires a security metadata freshness statement")
        if not self.excludes_production_secrets:
            raise ValueError("SS31: production secrets ... are excluded")
        if not self.excludes_customer_configuration:
            raise ValueError("SS31: ... customer configuration are excluded")


@dataclass(frozen=True, slots=True)
class SupportDeclaration:
    """SS32's declared elements."""

    release_reference: str
    support_start_date: datetime
    support_end_date: datetime
    current_phase: SupportStatus
    supported_versions: tuple[str, ...]
    patch_eligible: bool
    upgrade_paths: tuple[str, ...]
    minimum_destination_version: str
    backup_and_restore_compatibility_reference: str
    known_limitations: tuple[str, ...]
    service_objectives: tuple[str, ...]
    contact_and_escalation_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.release_reference, "release_reference")
        if self.support_start_date.tzinfo is None or self.support_end_date.tzinfo is None:
            raise ValueError("support_start_date and support_end_date must be timezone-aware")
        if self.support_end_date < self.support_start_date:
            raise ValueError("support_end_date must not precede support_start_date")
        if not self.supported_versions:
            raise ValueError("a support declaration requires supported versions")
        if not self.upgrade_paths:
            raise ValueError("a support declaration requires upgrade paths")
        if not self.minimum_destination_version.strip():
            raise ValueError("a support declaration requires a minimum destination version")
        if not self.backup_and_restore_compatibility_reference.strip():
            raise ValueError("a support declaration requires backup and restore compatibility")
        if not self.contact_and_escalation_reference.strip():
            raise ValueError("a support declaration requires a contact and escalation process")


def support_implies_compatibility_with_unlisted_combinations() -> bool:
    """SS32: "support does not imply compatibility with unlisted combinations.\""""
    return False


class LtsRequirement(StrEnum):
    """SS33's eight LTS requirements."""

    STABLE_ARCHITECTURE_AND_MIGRATION_BASELINE = "stable_architecture_and_migration_baseline"
    EXTENDED_SECURITY_AND_CRITICAL_DEFECT_PATCH_COMMITMENT = (
        "extended_security_and_critical_defect_patch_commitment"
    )
    RESTRICTED_CHANGE_POLICY = "restricted_change_policy"
    LONG_LIVED_DEPENDENCY_AND_PLATFORM_SUPPORT = "long_lived_dependency_and_platform_support"
    TESTED_OFFLINE_DISTRIBUTION = "tested_offline_distribution"
    DOCUMENTED_CONNECTOR_AND_MODEL_COMPATIBILITY_POLICY = (
        "documented_connector_and_model_compatibility_policy"
    )
    PERIODIC_BACKUP_RESTORE_UPGRADE_AND_SECURITY_VALIDATION = (
        "periodic_backup_restore_upgrade_and_security_validation"
    )
    CLEAR_TRANSITION_TO_NEXT_LTS = "clear_transition_to_next_lts"


@dataclass(frozen=True, slots=True)
class LtsDesignation:
    """SS33's declared elements. "LTS designation is a product and engineering commitment, not
    a label" is enforced by requiring a real `engineering_commitment_reference` alongside every
    one of SS33's eight requirements."""

    release_reference: str
    satisfied_requirements: frozenset[LtsRequirement]
    engineering_commitment_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.release_reference, "release_reference")
        missing = set(LtsRequirement) - self.satisfied_requirements
        if missing:
            raise ValueError(
                "an LTS designation requires every requirement, missing "
                f"{sorted(requirement.value for requirement in missing)}"
            )
        if not self.engineering_commitment_reference.strip():
            raise ValueError(
                "SS33: LTS designation is a product and engineering commitment, not a label"
            )
