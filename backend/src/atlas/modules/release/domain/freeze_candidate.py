"""ATLAS-059 SS14/SS15: freeze policy and the release candidate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.release.domain.versioning import SemanticVersion


class FreezeAllowedChangeKind(StrEnum):
    """SS14: "only [these] enter" during candidate freeze."""

    RELEASE_BLOCKING_FIX = "release_blocking_fix"
    SECURITY_CORRECTION = "security_correction"
    DOCUMENTATION_CHANGE = "documentation_change"
    EVIDENCE_CHANGE = "evidence_change"


@dataclass(frozen=True, slots=True)
class FreezeChange:
    """SS14's declared elements. `has_regression_tests` must be `True` to construct at all --
    "fixes receive regression tests" as a construction-time guarantee."""

    change_id: str
    kind: FreezeAllowedChangeKind
    release_manager_approval: str
    affected_owner_review: str
    is_material: bool
    has_regression_tests: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.change_id, "change_id")
        if not self.release_manager_approval.strip():
            raise ValueError("a freeze change requires release-manager approval")
        if not self.affected_owner_review.strip():
            raise ValueError("a freeze change requires affected-owner review")
        if not self.has_regression_tests:
            raise ValueError("SS14: fixes receive regression tests")


def generated_mass_refactors_are_permitted_during_freeze() -> bool:
    """SS14: "generated mass refactors are prohibited.\""""
    return False


def freeze_change_produces_new_rc_without_rebuild_and_resign() -> bool:
    """SS14: "candidate artifact set is rebuilt and re-signed as a new RC.\""""
    return False


@dataclass(frozen=True, slots=True)
class ReleaseCandidate:
    """SS15's declared elements."""

    candidate_version: SemanticVersion
    source_commit: str
    manifest_reference: str
    compatibility_matrix_reference: str
    artifact_references: tuple[str, ...]
    sbom_reference: str
    provenance_reference: str
    signature_references: tuple[str, ...]
    checksum_references: tuple[str, ...]
    evidence_references: tuple[str, ...]
    draft_release_notes: str
    known_issues: tuple[str, ...]
    open_defects: tuple[str, ...]
    exceptions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_commit.strip():
            raise ValueError("a release candidate requires a source commit")
        if not self.manifest_reference.strip():
            raise ValueError("a release candidate requires a manifest reference")
        if not self.compatibility_matrix_reference.strip():
            raise ValueError("a release candidate requires a compatibility matrix reference")
        if not self.artifact_references:
            raise ValueError("a release candidate requires artifact references")
        if not self.sbom_reference.strip():
            raise ValueError("a release candidate requires an SBOM reference")
        if not self.provenance_reference.strip():
            raise ValueError("a release candidate requires a provenance reference")
        if not self.signature_references:
            raise ValueError("a release candidate requires signatures")
        if not self.checksum_references:
            raise ValueError("a release candidate requires checksums")
        if not self.evidence_references:
            raise ValueError("a release candidate requires evidence")
        if not self.draft_release_notes.strip():
            raise ValueError("a release candidate requires draft release notes")


def rc_can_be_modified_in_place() -> bool:
    """SS15: "an RC is promoted or rejected; it is never modified in place.\""""
    return False
