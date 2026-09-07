from __future__ import annotations

import pytest

from atlas.modules.release.domain.freeze_candidate import (
    FreezeAllowedChangeKind,
    FreezeChange,
    ReleaseCandidate,
    freeze_change_produces_new_rc_without_rebuild_and_resign,
    generated_mass_refactors_are_permitted_during_freeze,
    rc_can_be_modified_in_place,
)
from atlas.modules.release.domain.versioning import PrereleaseLabel, SemanticVersion


def freeze_change(**overrides: object) -> FreezeChange:
    defaults: dict[str, object] = {
        "change_id": "freeze-change.example",
        "kind": FreezeAllowedChangeKind.RELEASE_BLOCKING_FIX,
        "release_manager_approval": "subject.release-manager",
        "affected_owner_review": "subject.platform-owner",
        "is_material": False,
        "has_regression_tests": True,
    }
    defaults.update(overrides)
    return FreezeChange(**defaults)  # type: ignore[arg-type]


def test_freeze_change_requires_regression_tests() -> None:
    with pytest.raises(ValueError, match="regression tests"):
        freeze_change(has_regression_tests=False)


def test_freeze_change_accepts_valid_state() -> None:
    assert freeze_change().kind is FreezeAllowedChangeKind.RELEASE_BLOCKING_FIX


def test_generated_mass_refactors_never_permitted_during_freeze() -> None:
    assert generated_mass_refactors_are_permitted_during_freeze() is False


def test_freeze_change_never_skips_rebuild_and_resign() -> None:
    assert freeze_change_produces_new_rc_without_rebuild_and_resign() is False


def candidate_version() -> SemanticVersion:
    return SemanticVersion(
        major=1,
        minor=5,
        patch=0,
        prerelease_label=PrereleaseLabel.RC,
        prerelease_number=3,
        build_metadata=None,
    )


def candidate(**overrides: object) -> ReleaseCandidate:
    defaults: dict[str, object] = {
        "candidate_version": candidate_version(),
        "source_commit": "a" * 40,
        "manifest_reference": "manifest.release.1.5.0-rc.3",
        "compatibility_matrix_reference": "compat-matrix.1.5.0",
        "artifact_references": ("artifact.backend.1.5.0", "artifact.frontend.1.5.0"),
        "sbom_reference": "sbom.1.5.0-rc.3",
        "provenance_reference": "provenance.1.5.0-rc.3",
        "signature_references": ("signature.backend.1.5.0",),
        "checksum_references": ("checksum.backend.1.5.0",),
        "evidence_references": ("evidence.test-suite.1.5.0-rc.3",),
        "draft_release_notes": "Adds Change Impact and AI Agents support.",
        "known_issues": (),
        "open_defects": (),
        "exceptions": (),
    }
    defaults.update(overrides)
    return ReleaseCandidate(**defaults)  # type: ignore[arg-type]


def test_candidate_accepts_valid_state() -> None:
    assert candidate().source_commit == "a" * 40


def test_candidate_requires_artifact_references() -> None:
    with pytest.raises(ValueError, match="artifact references"):
        candidate(artifact_references=())


def test_candidate_requires_signatures() -> None:
    with pytest.raises(ValueError, match="requires signatures"):
        candidate(signature_references=())


def test_candidate_requires_evidence() -> None:
    with pytest.raises(ValueError, match="requires evidence"):
        candidate(evidence_references=())


def test_rc_never_modified_in_place() -> None:
    assert rc_can_be_modified_in_place() is False
