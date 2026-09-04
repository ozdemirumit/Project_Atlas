from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.reasoning.domain.evidence_gaps import (
    ConflictingEvidenceSide,
    EvidenceConflictRecord,
    MissingEvidenceDisclosure,
    MissingEvidenceReason,
    model_output_can_override_deterministic_result,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def disclosure(**overrides: object) -> MissingEvidenceDisclosure:
    defaults: dict[str, object] = {
        "description": "Host queue depth telemetry is unavailable.",
        "why_it_matters": "It would help confirm resource saturation as a contributing factor.",
        "reason": MissingEvidenceReason.UNAVAILABLE,
        "weakened_conclusion_ids": ("reasoning-hypothesis.example",),
        "safest_useful_next_check_reference": "check.host-queue-depth",
        "partial_answer_appropriate": True,
    }
    defaults.update(overrides)
    return MissingEvidenceDisclosure(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_disclosure_constructs_cleanly() -> None:
    example = disclosure()
    assert example.reason is MissingEvidenceReason.UNAVAILABLE


def test_disclosure_requires_a_description() -> None:
    with pytest.raises(ValueError, match="description"):
        disclosure(description="   ")


def test_disclosure_requires_why_it_matters() -> None:
    with pytest.raises(ValueError, match="why it matters"):
        disclosure(why_it_matters="   ")


def conflict_side(**overrides: object) -> ConflictingEvidenceSide:
    defaults: dict[str, object] = {
        "evidence_id": "evidence.vendor-guide",
        "source": "vendor documentation",
        "applicability": "Applies to firmware 6.1.x.",
        "authority": "vendor-documented",
        "observed_at": NOW,
    }
    defaults.update(overrides)
    return ConflictingEvidenceSide(**defaults)  # type: ignore[arg-type]


def test_conflicting_evidence_side_constructs_cleanly() -> None:
    example = conflict_side()
    assert example.authority == "vendor-documented"


def test_conflicting_evidence_side_requires_a_source() -> None:
    with pytest.raises(ValueError, match="source"):
        conflict_side(source="   ")


def test_conflicting_evidence_side_rejects_naive_observed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        conflict_side(observed_at=NOW.replace(tzinfo=None))


def conflict(**overrides: object) -> EvidenceConflictRecord:
    defaults: dict[str, object] = {
        "conflict_id": "reasoning-evidence-conflict.example",
        "sides": (
            conflict_side(evidence_id="evidence.vendor-guide"),
            conflict_side(
                evidence_id="evidence.internal-runbook",
                source="internal runbook",
                authority="internal-documented",
            ),
        ),
        "likely_reconciliation_path": "Confirm which firmware version is actually installed.",
    }
    defaults.update(overrides)
    return EvidenceConflictRecord(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_conflict_constructs_cleanly() -> None:
    example = conflict()
    assert len(example.sides) == 2


def test_conflict_requires_at_least_two_sides() -> None:
    with pytest.raises(ValueError, match="at least two sides"):
        conflict(sides=(conflict_side(),))


def test_conflict_requires_a_reconciliation_path() -> None:
    with pytest.raises(ValueError, match="reconciliation path"):
        conflict(likely_reconciliation_path="   ")


def test_conflict_record_has_no_selected_side_field() -> None:
    """SS20: "does not silently choose the text most convenient to the recommendation" --
    enforced by absence: there is no field on the record that could name a winning side."""
    example = conflict()
    assert not hasattr(example, "selected_side")
    assert not hasattr(example, "winning_evidence_id")


def test_model_output_never_overrides_deterministic_result() -> None:
    assert model_output_can_override_deterministic_result() is False
