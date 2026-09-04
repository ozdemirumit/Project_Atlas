from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.explainability.domain.challenge_and_correction import (
    ChallengeOrCorrection,
    ChallengeOrCorrectionKind,
    CorrectedFieldKind,
    FieldCorrection,
    ResultingArtifactKind,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def challenge(**overrides: object) -> ChallengeOrCorrection:
    defaults: dict[str, object] = {
        "challenge_id": "challenge.example",
        "kind": ChallengeOrCorrectionKind.HUMAN_REVIEW_REQUESTED,
        "target_explanation_id": "explanation.example",
        "target_claim_id": None,
        "field_correction": None,
        "note": "Please have a human review this explanation before I act on it.",
        "submitted_by": "subject.requester",
        "submitted_at": NOW,
        "resulting_artifact_kind": ResultingArtifactKind.REVIEW_ITEM,
    }
    defaults.update(overrides)
    return ChallengeOrCorrection(**defaults)  # type: ignore[arg-type]


def field_correction(**overrides: object) -> FieldCorrection:
    defaults: dict[str, object] = {
        "field": CorrectedFieldKind.VERSION,
        "previous_value": "6.1.0",
        "corrected_value": "6.1.1",
    }
    defaults.update(overrides)
    return FieldCorrection(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_challenge_constructs_cleanly() -> None:
    example = challenge()
    assert example.kind is ChallengeOrCorrectionKind.HUMAN_REVIEW_REQUESTED


@pytest.mark.parametrize(
    "kind",
    [
        ChallengeOrCorrectionKind.CLAIM_MARKED_INCORRECT,
        ChallengeOrCorrectionKind.CLAIM_MARKED_UNCLEAR,
        ChallengeOrCorrectionKind.CLAIM_MARKED_STALE,
        ChallengeOrCorrectionKind.CLAIM_MARKED_UNSUPPORTED,
    ],
)
def test_claim_targeted_kinds_require_a_claim_id(kind: ChallengeOrCorrectionKind) -> None:
    with pytest.raises(ValueError, match="requires the claim_id"):
        challenge(kind=kind, target_claim_id=None)


def test_claim_targeted_kind_constructs_with_a_claim_id() -> None:
    example = challenge(
        kind=ChallengeOrCorrectionKind.CLAIM_MARKED_UNSUPPORTED,
        target_claim_id="explanation-claim.example",
    )
    assert example.target_claim_id == "explanation-claim.example"


def test_human_review_requested_does_not_require_a_claim_id() -> None:
    example = challenge(kind=ChallengeOrCorrectionKind.HUMAN_REVIEW_REQUESTED)
    assert example.target_claim_id is None


def test_correction_supplied_requires_a_field_correction() -> None:
    with pytest.raises(ValueError, match="requires a field_correction"):
        challenge(
            kind=ChallengeOrCorrectionKind.CORRECTION_SUPPLIED,
            resulting_artifact_kind=ResultingArtifactKind.CORRECTION_ARTIFACT,
        )


def test_correction_supplied_constructs_with_a_field_correction() -> None:
    example = challenge(
        kind=ChallengeOrCorrectionKind.CORRECTION_SUPPLIED,
        field_correction=field_correction(),
        resulting_artifact_kind=ResultingArtifactKind.CORRECTION_ARTIFACT,
    )
    assert example.field_correction is not None
    assert example.field_correction.field is CorrectedFieldKind.VERSION


def test_a_non_correction_kind_cannot_carry_a_field_correction() -> None:
    with pytest.raises(ValueError, match="only meaningful for a CORRECTION_SUPPLIED"):
        challenge(
            kind=ChallengeOrCorrectionKind.HUMAN_REVIEW_REQUESTED,
            field_correction=field_correction(),
        )


def test_requires_who_submitted_it() -> None:
    with pytest.raises(ValueError, match="who submitted"):
        challenge(submitted_by="   ")


def test_requires_a_note() -> None:
    with pytest.raises(ValueError, match="note"):
        challenge(note="   ")


def test_rejects_naive_submitted_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        challenge(submitted_at=NOW.replace(tzinfo=None))


def test_field_correction_requires_both_values() -> None:
    with pytest.raises(ValueError, match="both a previous and a corrected value"):
        field_correction(corrected_value="   ")


def test_field_correction_requires_an_actual_change() -> None:
    with pytest.raises(ValueError, match="actual change"):
        field_correction(previous_value="6.1.0", corrected_value="6.1.0")
