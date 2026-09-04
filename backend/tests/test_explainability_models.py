from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.explainability.domain.models import (
    AudienceProfile,
    EvidenceLink,
    Explanation,
    ExplanationChannel,
    ExplanationClaim,
    ExplanationDetailLevel,
)
from atlas.modules.guardrails.domain.reasoning_guardrails import ClaimType, ConfidenceLevel

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def evidence_link(**overrides: object) -> EvidenceLink:
    defaults: dict[str, object] = {
        "reference": "evidence.example",
        "source": "health-check.example",
        "version": "1",
        "target_id": "target.example",
        "observed_at": NOW,
        "authority": "vendor-documented",
        "applicability": "storage.health",
    }
    defaults.update(overrides)
    return EvidenceLink(**defaults)  # type: ignore[arg-type]


def claim(**overrides: object) -> ExplanationClaim:
    defaults: dict[str, object] = {
        "claim_id": "explanation-claim.example",
        "claim_type": ClaimType.FACT,
        "statement": "The controller reports a degraded status.",
        "confidence": ConfidenceLevel.HIGH,
        "evidence_references": ("evidence.example",),
        "contradicting_evidence_references": (),
    }
    defaults.update(overrides)
    return ExplanationClaim(**defaults)  # type: ignore[arg-type]


def explanation(**overrides: object) -> Explanation:
    defaults: dict[str, object] = {
        "explanation_id": "explanation.example",
        "version": 1,
        "created_at": NOW,
        "freshness_boundary": NOW + timedelta(hours=1),
        "source_artifact_ids": ("rca-finding.example",),
        "source_artifact_versions": ("1",),
        "audience": AudienceProfile.INFRASTRUCTURE_ENGINEER,
        "channel": ExplanationChannel.CHAT,
        "detail_level": ExplanationDetailLevel.L1_SUMMARY,
        "summary": "Controller B reports a degraded status.",
        "claims": (claim(),),
        "evidence_links": (evidence_link(),),
        "unknowns": (),
        "alternatives": (),
        "recommended_next_step": "Review controller B diagnostics.",
        "redacted": False,
    }
    defaults.update(overrides)
    return Explanation(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_claim_with_evidence_is_not_a_gap() -> None:
    assert claim().is_evidence_gap is False


def test_a_claim_without_evidence_is_a_gap() -> None:
    example = claim(evidence_references=())
    assert example.is_evidence_gap is True


def test_a_claim_with_contradicting_evidence_reports_it() -> None:
    example = claim(contradicting_evidence_references=("evidence.conflicting",))
    assert example.has_contradicting_evidence is True


def test_claim_rejects_a_blank_statement() -> None:
    with pytest.raises(ValueError, match="statement"):
        claim(statement="   ")


def test_evidence_link_rejects_blank_fields() -> None:
    with pytest.raises(ValueError, match="source"):
        evidence_link(source="   ")
    with pytest.raises(ValueError, match="version"):
        evidence_link(version="   ")
    with pytest.raises(ValueError, match="authority"):
        evidence_link(authority="   ")
    with pytest.raises(ValueError, match="applicability"):
        evidence_link(applicability="   ")


def test_evidence_link_rejects_a_naive_observed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evidence_link(observed_at=datetime(2026, 9, 4, 12, 0))


def test_a_well_formed_explanation_constructs_cleanly() -> None:
    example = explanation()
    assert example.evidence_gaps == ()


def test_evidence_gaps_reports_only_gap_claims() -> None:
    gapped = claim(claim_id="explanation-claim.gap", evidence_references=())
    example = explanation(claims=(claim(), gapped))
    assert example.evidence_gaps == (gapped,)


def test_explanation_requires_at_least_one_source_artifact() -> None:
    with pytest.raises(ValueError, match="at least one source artifact"):
        explanation(source_artifact_ids=(), source_artifact_versions=())


def test_explanation_requires_a_version_per_source_artifact() -> None:
    with pytest.raises(ValueError, match="exactly one recorded version"):
        explanation(
            source_artifact_ids=("rca-finding.a", "rca-finding.b"),
            source_artifact_versions=("1",),
        )


def test_explanation_rejects_a_non_positive_version() -> None:
    with pytest.raises(ValueError, match="version must be positive"):
        explanation(version=0)


def test_explanation_rejects_blank_summary_and_next_step() -> None:
    with pytest.raises(ValueError, match="summary"):
        explanation(summary="   ")
    with pytest.raises(ValueError, match="next step"):
        explanation(recommended_next_step="   ")


def test_explanation_rejects_a_naive_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        explanation(created_at=datetime(2026, 9, 4, 12, 0))


def test_is_stale_before_the_boundary_is_false() -> None:
    example = explanation(freshness_boundary=NOW + timedelta(hours=1))
    assert example.is_stale(at=NOW) is False


def test_is_stale_after_the_boundary_is_true() -> None:
    example = explanation(freshness_boundary=NOW + timedelta(hours=1))
    assert example.is_stale(at=NOW + timedelta(hours=2)) is True


def test_no_freshness_boundary_is_never_stale() -> None:
    example = explanation(freshness_boundary=None)
    assert example.is_stale(at=NOW + timedelta(days=365)) is False
