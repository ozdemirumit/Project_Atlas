from __future__ import annotations

import pytest

from atlas.modules.decision_engine.domain.hypotheses import (
    DecisionConfidenceCategory,
    DecisionHypothesis,
    EvidenceStrengthAssessment,
    EvidenceStrengthDimension,
    model_rhetorical_certainty_affects_evidence_strength,
    rank_hypotheses_without_hiding,
)
from atlas.modules.reasoning.domain.quality import QualityRating

_CONFIDENCE_RANK = {
    DecisionConfidenceCategory.HIGH: 3,
    DecisionConfidenceCategory.MEDIUM: 2,
    DecisionConfidenceCategory.LOW: 1,
    DecisionConfidenceCategory.INSUFFICIENT: 0,
}


def hypothesis(**overrides: object) -> DecisionHypothesis:
    defaults: dict[str, object] = {
        "hypothesis_id": "decision-hypothesis.example",
        "description": "Fabric instability may be the initiating cause.",
        "causal_or_dependency_path": ("target.fabric-a", "target.example"),
        "supporting_evidence_ids": ("evidence.example",),
        "contradicting_evidence_ids": (),
        "missing_evidence": ("Path error counters on fabric B.",),
        "alternative_explanations": ("Resource saturation on controller B.",),
        "validation_steps": ("Query path error counters on both fabrics.",),
        "confidence_category": DecisionConfidenceCategory.MEDIUM,
        "confidence_basis": "One independent evidence unit supports this.",
        "potential_impact_if_true": "Extended redundancy loss if unresolved.",
    }
    defaults.update(overrides)
    return DecisionHypothesis(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_hypothesis_constructs_cleanly() -> None:
    example = hypothesis()
    assert example.confidence_category is DecisionConfidenceCategory.MEDIUM


def test_rejects_blank_description() -> None:
    with pytest.raises(ValueError, match="description"):
        hypothesis(description="   ")


def test_rejects_blank_confidence_basis() -> None:
    with pytest.raises(ValueError, match="confidence basis"):
        hypothesis(confidence_basis="   ")


def test_rejects_blank_potential_impact() -> None:
    with pytest.raises(ValueError, match="potential impact"):
        hypothesis(potential_impact_if_true="   ")


def test_rank_hypotheses_without_hiding_preserves_every_hypothesis() -> None:
    low = hypothesis(
        hypothesis_id="decision-hypothesis.low", confidence_category=DecisionConfidenceCategory.LOW
    )
    high = hypothesis(
        hypothesis_id="decision-hypothesis.high",
        confidence_category=DecisionConfidenceCategory.HIGH,
    )
    ranked = rank_hypotheses_without_hiding((low, high), confidence_rank=_CONFIDENCE_RANK)
    assert len(ranked) == 2
    assert {h.hypothesis_id for h in ranked} == {
        "decision-hypothesis.low",
        "decision-hypothesis.high",
    }


def test_rank_hypotheses_without_hiding_orders_by_confidence() -> None:
    low = hypothesis(
        hypothesis_id="decision-hypothesis.low", confidence_category=DecisionConfidenceCategory.LOW
    )
    high = hypothesis(
        hypothesis_id="decision-hypothesis.high",
        confidence_category=DecisionConfidenceCategory.HIGH,
    )
    ranked = rank_hypotheses_without_hiding((low, high), confidence_rank=_CONFIDENCE_RANK)
    assert ranked[0].hypothesis_id == "decision-hypothesis.high"


def test_rank_hypotheses_without_hiding_keeps_insufficient_confidence_visible() -> None:
    insufficient = hypothesis(
        hypothesis_id="decision-hypothesis.insufficient",
        confidence_category=DecisionConfidenceCategory.INSUFFICIENT,
    )
    ranked = rank_hypotheses_without_hiding((insufficient,), confidence_rank=_CONFIDENCE_RANK)
    assert ranked == (insufficient,)


def test_evidence_strength_assessment_constructs_cleanly() -> None:
    example = EvidenceStrengthAssessment(
        evidence_id="evidence.example",
        dimension=EvidenceStrengthDimension.SOURCE_AUTHORITY_AND_INTEGRITY,
        rating=QualityRating.STRONG,
        note="Directly observed via a governed connector.",
    )
    assert example.rating is QualityRating.STRONG


def test_evidence_strength_assessment_requires_a_note() -> None:
    with pytest.raises(ValueError, match="requires a note"):
        EvidenceStrengthAssessment(
            evidence_id="evidence.example",
            dimension=EvidenceStrengthDimension.FRESHNESS,
            rating=QualityRating.WEAK,
            note="   ",
        )


def test_model_rhetorical_certainty_never_affects_evidence_strength() -> None:
    assert model_rhetorical_certainty_affects_evidence_strength() is False
