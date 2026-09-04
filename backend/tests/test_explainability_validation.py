from __future__ import annotations

from datetime import UTC, datetime

from atlas.modules.explainability.domain.models import (
    AudienceProfile,
    EvidenceLink,
    Explanation,
    ExplanationChannel,
    ExplanationClaim,
    ExplanationDetailLevel,
)
from atlas.modules.explainability.domain.validation import ValidationOutcome, validate_explanation
from atlas.modules.guardrails.domain.reasoning_guardrails import ClaimType, ConfidenceLevel

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


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
    link = EvidenceLink(
        reference="evidence.example",
        source="health-check.example",
        version="1",
        target_id="target.example",
        observed_at=NOW,
        authority="vendor-documented",
        applicability="storage.health",
    )
    defaults: dict[str, object] = {
        "explanation_id": "explanation.example",
        "version": 1,
        "created_at": NOW,
        "freshness_boundary": None,
        "source_artifact_ids": ("rca-finding.example",),
        "source_artifact_versions": ("1",),
        "audience": AudienceProfile.INFRASTRUCTURE_ENGINEER,
        "channel": ExplanationChannel.CHAT,
        "detail_level": ExplanationDetailLevel.L1_SUMMARY,
        "summary": "Controller B reports a degraded status.",
        "claims": (claim(),),
        "evidence_links": (link,),
        "unknowns": (),
        "alternatives": (),
        "recommended_next_step": "Review controller B diagnostics.",
        "redacted": False,
    }
    defaults.update(overrides)
    return Explanation(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_explanation_with_matching_versions_is_valid() -> None:
    result = validate_explanation(
        explanation(), current_source_artifact_versions={"rca-finding.example": "1"}
    )
    assert result.outcome is ValidationOutcome.VALID
    assert result.passed is True


def test_a_missing_source_artifact_is_safe_incomplete() -> None:
    result = validate_explanation(explanation(), current_source_artifact_versions={})
    assert result.outcome is ValidationOutcome.SAFE_INCOMPLETE
    assert any("no longer available" in v for v in result.violations)


def test_a_moved_source_artifact_version_is_safe_incomplete() -> None:
    result = validate_explanation(
        explanation(), current_source_artifact_versions={"rca-finding.example": "2"}
    )
    assert result.outcome is ValidationOutcome.SAFE_INCOMPLETE
    assert any("moved from version" in v for v in result.violations)


def test_a_fact_claim_with_no_evidence_routes_to_review() -> None:
    gapped = claim(evidence_references=())
    example = explanation(claims=(gapped,))
    result = validate_explanation(
        example, current_source_artifact_versions={"rca-finding.example": "1"}
    )
    assert result.outcome is ValidationOutcome.ROUTE_TO_REVIEW
    assert any("no supporting evidence" in v for v in result.violations)


def test_an_inference_claim_with_no_evidence_does_not_block_validation() -> None:
    inference = claim(
        claim_id="explanation-claim.inference",
        claim_type=ClaimType.INFERENCE,
        evidence_references=(),
    )
    example = explanation(claims=(claim(), inference))
    result = validate_explanation(
        example, current_source_artifact_versions={"rca-finding.example": "1"}
    )
    assert result.outcome is ValidationOutcome.VALID


def test_unsupported_certainty_language_in_the_summary_routes_to_review() -> None:
    example = explanation(summary="This fix is guaranteed to work.")
    result = validate_explanation(
        example, current_source_artifact_versions={"rca-finding.example": "1"}
    )
    assert result.outcome is ValidationOutcome.ROUTE_TO_REVIEW
    assert any("certainty language" in v for v in result.violations)


def test_safe_incomplete_takes_priority_over_review_when_both_apply() -> None:
    gapped = claim(evidence_references=())
    example = explanation(claims=(gapped,))
    result = validate_explanation(example, current_source_artifact_versions={})
    assert result.outcome is ValidationOutcome.SAFE_INCOMPLETE


def test_multiple_review_level_violations_are_all_reported() -> None:
    gapped = claim(evidence_references=())
    example = explanation(claims=(gapped,), summary="This is guaranteed to work.")
    result = validate_explanation(
        example, current_source_artifact_versions={"rca-finding.example": "1"}
    )
    assert len(result.violations) == 2
