"""ATLAS-046 SS25: challenge and correction.

SS25's "it does not silently retrain the model or alter an approved record" is given real teeth
structurally: `ChallengeOrCorrection` never carries a mutation of the artifact it targets, only a
`target_explanation_id`/`target_claim_id` reference plus its own separate identity, attribution,
and timestamp -- the same "reference only, never a mutation" pattern
`investigation_presentation.InvestigationAnnotation` already established for its narrower,
investigation-view-scoped subset of these same actions (claim challenge, topology challenge,
contrary evidence). This module is the general, cross-channel SS25 concept covering all seven
listed actions, including two that have nothing to do with investigation topology (request a
different explanation depth, ask what evidence would change the conclusion) -- it does not
replace that narrower type.

"Feedback ... creates a new artifact or review item" -- `resulting_artifact_kind` makes that
requirement a checkable, non-optional field rather than an unstated convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ChallengeOrCorrectionKind(StrEnum):
    """SS25's seven listed user actions (the four claim-quality complaints counted separately,
    since each requires its own target claim)."""

    CLAIM_MARKED_INCORRECT = "claim_marked_incorrect"
    CLAIM_MARKED_UNCLEAR = "claim_marked_unclear"
    CLAIM_MARKED_STALE = "claim_marked_stale"
    CLAIM_MARKED_UNSUPPORTED = "claim_marked_unsupported"
    TOPOLOGY_OR_RELATIONSHIP_CHALLENGE = "topology_or_relationship_challenge"
    CONTRARY_EVIDENCE_SUPPLIED = "contrary_evidence_supplied"
    CORRECTION_SUPPLIED = "correction_supplied"
    DEPTH_CHANGE_REQUESTED = "depth_change_requested"
    EVIDENCE_THAT_WOULD_CHANGE_CONCLUSION_REQUESTED = (
        "evidence_that_would_change_conclusion_requested"
    )
    HUMAN_REVIEW_REQUESTED = "human_review_requested"


_CLAIM_TARGETED_KINDS = frozenset(
    {
        ChallengeOrCorrectionKind.CLAIM_MARKED_INCORRECT,
        ChallengeOrCorrectionKind.CLAIM_MARKED_UNCLEAR,
        ChallengeOrCorrectionKind.CLAIM_MARKED_STALE,
        ChallengeOrCorrectionKind.CLAIM_MARKED_UNSUPPORTED,
    }
)


class CorrectedFieldKind(StrEnum):
    """SS25: "correct target, time, unit, product, or version.\""""

    TARGET = "target"
    TIME = "time"
    UNIT = "unit"
    PRODUCT = "product"
    VERSION = "version"


class ResultingArtifactKind(StrEnum):
    """SS25: feedback "creates a new artifact or review item," never a silent model retrain or a
    mutation of an approved record."""

    REVIEW_ITEM = "review_item"
    CORRECTION_ARTIFACT = "correction_artifact"
    EXPLANATION_REGENERATION_REQUEST = "explanation_regeneration_request"


@dataclass(frozen=True, slots=True)
class FieldCorrection:
    """Populated only when `kind is CORRECTION_SUPPLIED`."""

    field: CorrectedFieldKind
    previous_value: str
    corrected_value: str

    def __post_init__(self) -> None:
        if not self.previous_value.strip() or not self.corrected_value.strip():
            raise ValueError("a field correction requires both a previous and a corrected value")
        if self.previous_value == self.corrected_value:
            raise ValueError("a field correction requires an actual change in value")


@dataclass(frozen=True, slots=True)
class ChallengeOrCorrection:
    challenge_id: str
    kind: ChallengeOrCorrectionKind
    target_explanation_id: str
    target_claim_id: str | None
    field_correction: FieldCorrection | None
    note: str
    submitted_by: str
    submitted_at: datetime
    resulting_artifact_kind: ResultingArtifactKind

    def __post_init__(self) -> None:
        validate_stable_identifier(self.challenge_id, "challenge_id")
        validate_stable_identifier(self.target_explanation_id, "target_explanation_id")
        if self.target_claim_id is not None:
            validate_stable_identifier(self.target_claim_id, "target_claim_id")
        if not self.submitted_by.strip():
            raise ValueError("a challenge or correction requires who submitted it")
        if self.submitted_at.tzinfo is None:
            raise ValueError("a challenge or correction's submitted_at must be timezone-aware")
        if not self.note.strip():
            raise ValueError("a challenge or correction requires a note")
        if self.kind in _CLAIM_TARGETED_KINDS and self.target_claim_id is None:
            raise ValueError(f"a {self.kind.value} challenge requires the claim_id it targets")
        is_correction = self.kind is ChallengeOrCorrectionKind.CORRECTION_SUPPLIED
        if is_correction and self.field_correction is None:
            raise ValueError("a correction requires a field_correction")
        if not is_correction and self.field_correction is not None:
            raise ValueError(
                "field_correction is only meaningful for a CORRECTION_SUPPLIED challenge"
            )
