from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.release.domain.manifest_notes import SupportStatus
from atlas.modules.release.domain.offline_support_lts import (
    LtsDesignation,
    LtsRequirement,
    OfflineBundle,
    OfflineBundleContentKind,
    SupportDeclaration,
    offline_bundle_content_can_diverge_from_approved_manifest,
    support_implies_compatibility_with_unlisted_combinations,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def offline_bundle(**overrides: object) -> OfflineBundle:
    defaults: dict[str, object] = {
        "bundle_id": "offline-bundle.1.5.0",
        "manifest_reference": "manifest.release.1.5.0",
        "included_content_kinds": frozenset(OfflineBundleContentKind),
        "malware_scanned": True,
        "signed": True,
        "encrypted": True,
        "custody_ready": True,
        "offline_import_test_reference": "test.offline-import.1.5.0",
        "offline_clean_install_or_upgrade_test_reference": "test.offline-clean-install.1.5.0",
        "public_callback_scan_reference": "scan.public-callback.1.5.0",
        "missing_dependency_scan_reference": "scan.missing-dependency.1.5.0",
        "security_metadata_freshness_statement": "Security metadata current as of 2026-09-04.",
        "known_limitations": (),
        "excludes_production_secrets": True,
        "excludes_customer_configuration": True,
    }
    defaults.update(overrides)
    return OfflineBundle(**defaults)  # type: ignore[arg-type]


def test_offline_bundle_content_never_diverges_from_manifest() -> None:
    assert offline_bundle_content_can_diverge_from_approved_manifest() is False


def test_offline_bundle_requires_every_content_kind() -> None:
    with pytest.raises(ValueError, match="every content kind"):
        offline_bundle(included_content_kinds=frozenset({OfflineBundleContentKind.IMAGES}))


def test_offline_bundle_requires_malware_scan() -> None:
    with pytest.raises(ValueError, match="malware-scanned"):
        offline_bundle(malware_scanned=False)


def test_offline_bundle_requires_excluding_production_secrets() -> None:
    with pytest.raises(ValueError, match="production secrets"):
        offline_bundle(excludes_production_secrets=False)


def test_offline_bundle_accepts_valid_state() -> None:
    assert offline_bundle().bundle_id == "offline-bundle.1.5.0"


def support_declaration(**overrides: object) -> SupportDeclaration:
    defaults: dict[str, object] = {
        "release_reference": "release.1.5.0",
        "support_start_date": NOW,
        "support_end_date": NOW + timedelta(days=365),
        "current_phase": SupportStatus.FULL_SUPPORT,
        "supported_versions": ("platform:1.5.0", "connector-sdk:1.0.x"),
        "patch_eligible": True,
        "upgrade_paths": ("1.4.x",),
        "minimum_destination_version": "1.5.0",
        "backup_and_restore_compatibility_reference": "backup-compat.1.5.0",
        "known_limitations": (),
        "service_objectives": ("99.9% availability",),
        "contact_and_escalation_reference": "support-contact.atlas",
    }
    defaults.update(overrides)
    return SupportDeclaration(**defaults)  # type: ignore[arg-type]


def test_support_declaration_rejects_inverted_dates() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        support_declaration(support_end_date=NOW - timedelta(days=1))


def test_support_declaration_requires_contact_and_escalation() -> None:
    with pytest.raises(ValueError, match="contact and escalation process"):
        support_declaration(contact_and_escalation_reference="")


def test_support_never_implies_compatibility_with_unlisted_combinations() -> None:
    assert support_implies_compatibility_with_unlisted_combinations() is False


def lts_designation(**overrides: object) -> LtsDesignation:
    defaults: dict[str, object] = {
        "release_reference": "release.1.5.0",
        "satisfied_requirements": frozenset(LtsRequirement),
        "engineering_commitment_reference": "engineering-commitment.1.5.0-lts",
    }
    defaults.update(overrides)
    return LtsDesignation(**defaults)  # type: ignore[arg-type]


def test_lts_designation_requires_every_requirement() -> None:
    with pytest.raises(ValueError, match="every requirement"):
        lts_designation(
            satisfied_requirements=frozenset(
                {LtsRequirement.STABLE_ARCHITECTURE_AND_MIGRATION_BASELINE}
            )
        )


def test_lts_designation_requires_engineering_commitment() -> None:
    with pytest.raises(ValueError, match="not a label"):
        lts_designation(engineering_commitment_reference="")


def test_lts_designation_accepts_valid_state() -> None:
    assert lts_designation().release_reference == "release.1.5.0"
