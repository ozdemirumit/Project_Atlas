from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.decision_engine.domain.conflicts import (
    ConflictKind,
    DecisionConflict,
    can_summarize_conflict_as_consensus,
)
from atlas.modules.decision_engine.domain.hypotheses import DecisionConfidenceCategory
from atlas.modules.reasoning.domain.evidence_gaps import (
    ConflictingEvidenceSide,
    EvidenceConflictRecord,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


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


def evidence_conflict(**overrides: object) -> EvidenceConflictRecord:
    defaults: dict[str, object] = {
        "conflict_id": "decision-conflict.example",
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


def decision_conflict(**overrides: object) -> DecisionConflict:
    defaults: dict[str, object] = {
        "conflict": evidence_conflict(),
        "kind": ConflictKind.PRODUCT_VERSION,
        "resulting_confidence_category": DecisionConfidenceCategory.LOW,
        "recommended_discriminating_validation_step": "Query the installed firmware version.",
    }
    defaults.update(overrides)
    return DecisionConflict(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_decision_conflict_constructs_cleanly() -> None:
    example = decision_conflict()
    assert example.kind is ConflictKind.PRODUCT_VERSION


def test_requires_a_recommended_discriminating_validation_step() -> None:
    with pytest.raises(ValueError, match="discriminating validation step"):
        decision_conflict(recommended_discriminating_validation_step="   ")


def test_rejects_high_confidence_for_an_unresolved_conflict() -> None:
    with pytest.raises(ValueError, match="LOW or INSUFFICIENT"):
        decision_conflict(resulting_confidence_category=DecisionConfidenceCategory.HIGH)


def test_rejects_medium_confidence_for_an_unresolved_conflict() -> None:
    with pytest.raises(ValueError, match="LOW or INSUFFICIENT"):
        decision_conflict(resulting_confidence_category=DecisionConfidenceCategory.MEDIUM)


def test_accepts_insufficient_confidence_for_an_unresolved_conflict() -> None:
    example = decision_conflict(
        resulting_confidence_category=DecisionConfidenceCategory.INSUFFICIENT
    )
    assert example.resulting_confidence_category is DecisionConfidenceCategory.INSUFFICIENT


def test_conflict_kind_covers_all_five_named_categories() -> None:
    assert len(ConflictKind) == 5


def test_conflict_can_never_be_summarized_as_consensus() -> None:
    assert can_summarize_conflict_as_consensus() is False
