from __future__ import annotations

import pytest

from atlas.modules.release.domain.versioning import (
    ArtifactVersionPin,
    PrereleaseLabel,
    SemanticVersion,
    VersionedArtifactCategory,
    ai_quality_improvement_can_offset_a_failed_invariant_guardrail,
    offline_customers_receive_lesser_integrity_or_evidence,
    promotion_rebuilds_artifacts_instead_of_reusing_signed_digests,
    published_artifact_contents_can_change_under_same_version_or_digest,
    required_gates_can_be_waived_without_a_recorded_exception,
    semantic_compatibility_is_inferred_from_version_numbers_alone,
    version_changes_follow_marketing_preference_over_impact_analysis,
)


@pytest.mark.parametrize(
    "checker",
    [
        published_artifact_contents_can_change_under_same_version_or_digest,
        semantic_compatibility_is_inferred_from_version_numbers_alone,
        promotion_rebuilds_artifacts_instead_of_reusing_signed_digests,
        required_gates_can_be_waived_without_a_recorded_exception,
        ai_quality_improvement_can_offset_a_failed_invariant_guardrail,
        offline_customers_receive_lesser_integrity_or_evidence,
        version_changes_follow_marketing_preference_over_impact_analysis,
    ],
)
def test_release_principle_prohibitions_are_always_false(checker: object) -> None:
    assert checker() is False  # type: ignore[operator]


def test_semantic_version_str_without_prerelease() -> None:
    version = SemanticVersion(
        major=1,
        minor=2,
        patch=3,
        prerelease_label=None,
        prerelease_number=None,
        build_metadata=None,
    )
    assert str(version) == "1.2.3"
    assert version.is_prerelease is False


def test_semantic_version_str_with_rc_prerelease() -> None:
    version = SemanticVersion(
        major=2,
        minor=0,
        patch=0,
        prerelease_label=PrereleaseLabel.RC,
        prerelease_number=3,
        build_metadata=None,
    )
    assert str(version) == "2.0.0-rc.3"
    assert version.is_prerelease is True


def test_semantic_version_str_with_build_metadata() -> None:
    version = SemanticVersion(
        major=1,
        minor=0,
        patch=0,
        prerelease_label=PrereleaseLabel.BETA,
        prerelease_number=None,
        build_metadata="a1b2c3d",
    )
    assert str(version) == "1.0.0-beta+a1b2c3d"


def test_semantic_version_rc_requires_prerelease_number() -> None:
    with pytest.raises(ValueError, match="requires a prerelease_number"):
        SemanticVersion(
            major=1,
            minor=0,
            patch=0,
            prerelease_label=PrereleaseLabel.RC,
            prerelease_number=None,
            build_metadata=None,
        )


def test_semantic_version_rejects_prerelease_number_without_label() -> None:
    with pytest.raises(ValueError, match="only meaningful with a prerelease_label"):
        SemanticVersion(
            major=1,
            minor=0,
            patch=0,
            prerelease_label=None,
            prerelease_number=1,
            build_metadata=None,
        )


def test_semantic_version_rejects_negative_components() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        SemanticVersion(
            major=-1,
            minor=0,
            patch=0,
            prerelease_label=None,
            prerelease_number=None,
            build_metadata=None,
        )


def test_artifact_version_pin_validates_identifier() -> None:
    pin = ArtifactVersionPin(
        category=VersionedArtifactCategory.BACKEND_AND_FRONTEND_APPLICATIONS,
        identifier="artifact.backend",
        version=SemanticVersion(
            major=1,
            minor=4,
            patch=0,
            prerelease_label=None,
            prerelease_number=None,
            build_metadata=None,
        ),
    )
    assert pin.category is VersionedArtifactCategory.BACKEND_AND_FRONTEND_APPLICATIONS


def test_versioned_artifact_category_has_eleven_members() -> None:
    assert len(VersionedArtifactCategory) == 11
