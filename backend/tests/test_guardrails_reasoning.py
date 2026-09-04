from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.guardrails.domain.reasoning_guardrails import (
    ClaimType,
    ConfidenceLevel,
    ReasoningClaim,
    ReasoningOutcome,
    evaluate_reasoning_claim,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def claim(**overrides: object) -> ReasoningClaim:
    defaults: dict[str, object] = {
        "claim_id": "reasoning-claim.example",
        "claim_type": ClaimType.FACT,
        "statement": "The controller reports a degraded status.",
        "confidence": ConfidenceLevel.HIGH,
        "target_id": "target.example",
        "target_version": "1.0",
        "applicable_at": NOW,
        "evidence_references": ("evidence.example",),
    }
    defaults.update(overrides)
    return ReasoningClaim(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_fact_claim_is_valid() -> None:
    assert evaluate_reasoning_claim(claim()) is ReasoningOutcome.CLAIM_VALID


@pytest.mark.parametrize(
    "claim_type", [ClaimType.FACT, ClaimType.CALCULATION, ClaimType.CORRELATION]
)
def test_evidence_required_types_without_evidence_are_insufficient(
    claim_type: ClaimType,
) -> None:
    example = claim(claim_type=claim_type, evidence_references=())
    assert example.has_missing_critical_evidence is True
    assert evaluate_reasoning_claim(example) is ReasoningOutcome.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    "claim_type",
    [ClaimType.INFERENCE, ClaimType.HYPOTHESIS, ClaimType.ASSUMPTION, ClaimType.UNKNOWN],
)
def test_softer_claim_types_do_not_require_evidence(claim_type: ClaimType) -> None:
    example = claim(claim_type=claim_type, evidence_references=())
    assert example.has_missing_critical_evidence is False


def test_a_correlation_claim_using_causal_language_is_flagged() -> None:
    example = claim(
        claim_type=ClaimType.CORRELATION,
        statement="The recent firmware change causes the elevated latency.",
    )
    assert example.has_causal_language is True
    assert evaluate_reasoning_claim(example) is ReasoningOutcome.CAUSAL_LANGUAGE_FLAGGED


def test_a_fact_claim_may_legitimately_use_causal_language() -> None:
    example = claim(
        claim_type=ClaimType.FACT, statement="The documented root cause was a failed fan."
    )
    assert example.has_causal_language is False


def test_a_hypothesis_using_causal_language_is_also_flagged() -> None:
    example = claim(
        claim_type=ClaimType.HYPOTHESIS,
        statement="This might be due to the recent configuration change.",
        evidence_references=(),
    )
    assert example.has_causal_language is True
    assert evaluate_reasoning_claim(example) is ReasoningOutcome.CAUSAL_LANGUAGE_FLAGGED


def test_missing_evidence_is_reported_before_causal_language() -> None:
    example = claim(
        claim_type=ClaimType.CORRELATION,
        statement="This causes the failure.",
        evidence_references=(),
    )
    assert evaluate_reasoning_claim(example) is ReasoningOutcome.INSUFFICIENT_EVIDENCE


def test_claim_rejects_a_blank_statement() -> None:
    with pytest.raises(ValueError, match="statement"):
        claim(statement="   ")


def test_claim_rejects_a_blank_target_version() -> None:
    with pytest.raises(ValueError, match="target version"):
        claim(target_version="   ")


def test_claim_rejects_a_naive_applicable_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        claim(applicable_at=datetime(2026, 9, 4, 12, 0))


def test_claim_constructs_without_evidence_rather_than_raising() -> None:
    # Missing evidence is a reportable state (see evaluate_reasoning_claim), not a construction
    # error -- the claim object itself must still be constructible to be reported on at all.
    example = claim(claim_type=ClaimType.FACT, evidence_references=())
    assert example.evidence_references == ()
