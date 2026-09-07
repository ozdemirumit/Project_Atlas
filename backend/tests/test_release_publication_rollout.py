from __future__ import annotations

import pytest

from atlas.modules.release.domain.manifest_notes import SupportStatus
from atlas.modules.release.domain.publication_rollout import (
    PublicationArtifactKind,
    PublicationRecord,
    RolloutPlan,
    ai_can_initiate_or_approve_rollout,
    production_change_approval_is_the_same_as_product_release_approval,
    publication_includes_unapproved_or_unsigned_artifacts,
)


def publication(**overrides: object) -> PublicationRecord:
    defaults: dict[str, object] = {
        "manifest_reference": "manifest.release.1.5.0",
        "published_artifact_kinds": frozenset(PublicationArtifactKind),
        "protected_tag_reference": "tag.v1.5.0",
        "mirrored_enterprise_channels": ("enterprise-mirror.primary",),
        "offline_bundle_reference": "offline-bundle.1.5.0",
        "download_path_verified": True,
        "offline_import_path_verified": True,
        "announced_support_status": SupportStatus.FULL_SUPPORT,
        "announced_deprecation_date": None,
        "publication_audit_event_reference": "audit-event.publication.1.5.0",
        "artifact_location_references": ("registry.atlas/backend:1.5.0",),
    }
    defaults.update(overrides)
    return PublicationRecord(**defaults)  # type: ignore[arg-type]


def test_publication_never_includes_unapproved_or_unsigned_artifacts() -> None:
    assert publication_includes_unapproved_or_unsigned_artifacts() is False


def test_publication_requires_every_artifact_kind() -> None:
    with pytest.raises(ValueError, match="every published artifact kind"):
        publication(published_artifact_kinds=frozenset({PublicationArtifactKind.CHECKSUMS}))


def test_publication_requires_download_path_verification() -> None:
    with pytest.raises(ValueError, match="verify download"):
        publication(download_path_verified=False)


def test_publication_requires_offline_import_verification() -> None:
    with pytest.raises(ValueError, match="offline import paths"):
        publication(offline_import_path_verified=False)


def test_publication_accepts_valid_state() -> None:
    assert publication().protected_tag_reference == "tag.v1.5.0"


def rollout(**overrides: object) -> RolloutPlan:
    defaults: dict[str, object] = {
        "environments": ("staging", "production"),
        "cohorts": ("internal", "beta-customers"),
        "timing": "2026-09-10T09:00:00Z start, phased over 3 days",
        "owners": ("subject.release-manager",),
        "metrics": ("error_rate", "latency_p99"),
        "abort_criteria": ("error_rate > 1%",),
        "rollback_criteria": ("error_rate > 5% for 10 minutes",),
        "artifact_digest": "sha256:" + "a" * 64,
        "uses_canary_or_phased_rollout": True,
        "monitored_signals": ("health", "security", "audit", "error", "performance"),
        "customer_or_environment_differences": (),
        "production_change_approval_reference": "production-change.1.5.0",
    }
    defaults.update(overrides)
    return RolloutPlan(**defaults)  # type: ignore[arg-type]


def test_rollout_accepts_valid_state() -> None:
    assert rollout().uses_canary_or_phased_rollout is True


def test_rollout_requires_abort_criteria() -> None:
    with pytest.raises(ValueError, match="requires abort criteria"):
        rollout(abort_criteria=())


def test_rollout_requires_production_change_approval() -> None:
    with pytest.raises(ValueError, match="separate from product release approval"):
        rollout(production_change_approval_reference="")


def test_ai_can_never_initiate_or_approve_rollout() -> None:
    assert ai_can_initiate_or_approve_rollout() is False


def test_production_change_approval_never_same_as_release_approval() -> None:
    assert production_change_approval_is_the_same_as_product_release_approval() is False
