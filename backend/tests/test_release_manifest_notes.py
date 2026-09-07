from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.release.domain.manifest_notes import (
    ManifestArtifactEntry,
    ReleaseManifest,
    ReleaseNotes,
    SupportStatus,
)
from atlas.modules.release.domain.versioning import SemanticVersion

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def release_version() -> SemanticVersion:
    return SemanticVersion(
        major=1,
        minor=5,
        patch=0,
        prerelease_label=None,
        prerelease_number=None,
        build_metadata=None,
    )


def artifact_entry(**overrides: object) -> ManifestArtifactEntry:
    defaults: dict[str, object] = {
        "name": "backend",
        "version": "1.5.0",
        "digest": "sha256:" + "a" * 64,
        "signature": "signature.backend.1.5.0",
        "source": "commit.a" * 5,
        "required": True,
    }
    defaults.update(overrides)
    return ManifestArtifactEntry(**defaults)  # type: ignore[arg-type]


def test_artifact_entry_requires_digest() -> None:
    with pytest.raises(ValueError, match="requires digest"):
        artifact_entry(digest="")


def manifest(**overrides: object) -> ReleaseManifest:
    defaults: dict[str, object] = {
        "release_version": release_version(),
        "channel": "general",
        "release_date": NOW,
        "support_status": SupportStatus.FULL_SUPPORT,
        "artifacts": (artifact_entry(),),
        "compatibility_matrix_reference": "compat-matrix.1.5.0",
        "supported_install_paths": ("linux_lab",),
        "supported_upgrade_paths": ("1.4.x",),
        "configuration_version": "config.v3",
        "migration_version": "migration.0180",
        "component_versions": (("model", "gpt-oss.v1"), ("policy", "policy-set.v5")),
        "sbom_reference": "sbom.1.5.0",
        "provenance_reference": "provenance.1.5.0",
        "release_notes_reference": "release-notes.1.5.0",
        "known_issues_references": (),
        "security_advisory_references": (),
        "offline_bundle_contents_reference": "offline-bundle.1.5.0",
        "offline_bundle_verification_profile": "verification-profile.1.5.0",
        "approval_reference": "approval.1.5.0",
        "evidence_reference": "release-evidence.1.5.0",
    }
    defaults.update(overrides)
    return ReleaseManifest(**defaults)  # type: ignore[arg-type]


def test_manifest_accepts_valid_state() -> None:
    assert manifest().channel == "general"


def test_manifest_requires_timezone_aware_release_date() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        manifest(release_date=datetime(2026, 9, 4, 12, 0))


def test_manifest_requires_artifacts() -> None:
    with pytest.raises(ValueError, match="requires artifacts"):
        manifest(artifacts=())


def test_manifest_requires_approval_reference() -> None:
    with pytest.raises(ValueError, match="requires an approval reference"):
        manifest(approval_reference="")


def notes(**overrides: object) -> ReleaseNotes:
    defaults: dict[str, object] = {
        "summary": "Adds Change Impact and AI Agents support.",
        "intended_use": "Storage operations teams diagnosing controller degradation.",
        "new_capabilities_and_behavior_changes": ("Change Impact analysis is now available.",),
        "security_and_privacy_changes": (),
        "ai_model_retrieval_and_guardrail_changes": (),
        "contract_changes": (),
        "deployment_and_resource_changes": (),
        "compatibility_deprecation_and_removed_support": (),
        "upgrade_prerequisites_and_expected_duration": "No prerequisites; ~10 minutes.",
        "rollback_or_recovery_constraints": "Roll back to 1.4.2 if smoke tests fail.",
        "known_issues_workarounds_and_residual_risk": (),
        "documentation_and_support_links": ("docs.044",),
        "drafted_by_ai": False,
        "verified_by_accountable_owner": None,
    }
    defaults.update(overrides)
    return ReleaseNotes(**defaults)  # type: ignore[arg-type]


def test_notes_accepts_valid_state() -> None:
    assert notes().summary.startswith("Adds Change Impact")


def test_notes_ai_drafted_requires_verification() -> None:
    with pytest.raises(ValueError, match="accountable owners verify every claim"):
        notes(drafted_by_ai=True, verified_by_accountable_owner=None)


def test_notes_ai_drafted_with_verification_accepted() -> None:
    result = notes(drafted_by_ai=True, verified_by_accountable_owner="subject.release-manager")
    assert result.drafted_by_ai is True
