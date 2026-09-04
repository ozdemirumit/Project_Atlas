from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.explainability.domain.failure_behavior import (
    ExplanationReadiness,
    RestrictedEvidenceDisclosure,
    apply_explanation_failure_to_policy_outcome,
    assess_explanation_readiness,
)
from atlas.modules.explainability.domain.models import (
    AudienceProfile,
    EvidenceLink,
    Explanation,
    ExplanationChannel,
    ExplanationDetailLevel,
)
from atlas.modules.explainability.domain.validation import ValidationOutcome, ValidationResult
from atlas.modules.policy_engine.domain.models import PolicyDecisionOutcome

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
        "claims": (),
        "evidence_links": (evidence_link(),),
        "unknowns": (),
        "alternatives": (),
        "recommended_next_step": "Review controller B diagnostics.",
        "redacted": False,
    }
    defaults.update(overrides)
    return Explanation(**defaults)  # type: ignore[arg-type]


def no_disclosure() -> RestrictedEvidenceDisclosure:
    return RestrictedEvidenceDisclosure(omitted_count=0, disclosure="")


def test_restricted_evidence_disclosure_requires_a_statement_when_evidence_was_omitted() -> None:
    with pytest.raises(ValueError, match="safe disclosure"):
        RestrictedEvidenceDisclosure(omitted_count=2, disclosure="   ")


def test_restricted_evidence_disclosure_rejects_a_statement_with_no_omission() -> None:
    with pytest.raises(ValueError, match="actually omitted"):
        RestrictedEvidenceDisclosure(omitted_count=0, disclosure="Some evidence was withheld.")


def test_restricted_evidence_disclosure_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        RestrictedEvidenceDisclosure(omitted_count=-1, disclosure="")


def test_valid_validation_maps_to_ready() -> None:
    assessment = assess_explanation_readiness(
        explanation(),
        validation=ValidationResult(outcome=ValidationOutcome.VALID, violations=()),
        restricted_evidence_disclosure=no_disclosure(),
        renderer_failed=False,
        at=NOW,
        is_consequential=True,
    )
    assert assessment.readiness is ExplanationReadiness.READY
    assert assessment.blocks_consequential_approval_readiness is False


def test_safe_incomplete_maps_to_conflict_explanation() -> None:
    assessment = assess_explanation_readiness(
        explanation(),
        validation=ValidationResult(
            outcome=ValidationOutcome.SAFE_INCOMPLETE,
            violations=("source artifact rca-finding.example has moved from version 1 to 2",),
        ),
        restricted_evidence_disclosure=no_disclosure(),
        renderer_failed=False,
        at=NOW,
        is_consequential=True,
    )
    assert assessment.readiness is ExplanationReadiness.CONFLICT_EXPLANATION


def test_route_to_review_maps_to_blocked() -> None:
    assessment = assess_explanation_readiness(
        explanation(),
        validation=ValidationResult(
            outcome=ValidationOutcome.ROUTE_TO_REVIEW,
            violations=("claim explanation-claim.example has no supporting evidence",),
        ),
        restricted_evidence_disclosure=no_disclosure(),
        renderer_failed=False,
        at=NOW,
        is_consequential=True,
    )
    assert assessment.readiness is ExplanationReadiness.BLOCKED


def test_blocked_readiness_blocks_consequential_approval_readiness() -> None:
    assessment = assess_explanation_readiness(
        explanation(),
        validation=ValidationResult(outcome=ValidationOutcome.ROUTE_TO_REVIEW, violations=("x",)),
        restricted_evidence_disclosure=no_disclosure(),
        renderer_failed=False,
        at=NOW,
        is_consequential=True,
    )
    assert assessment.blocks_consequential_approval_readiness is True


def test_blocked_readiness_does_not_block_when_not_consequential() -> None:
    assessment = assess_explanation_readiness(
        explanation(),
        validation=ValidationResult(outcome=ValidationOutcome.ROUTE_TO_REVIEW, violations=("x",)),
        restricted_evidence_disclosure=no_disclosure(),
        renderer_failed=False,
        at=NOW,
        is_consequential=False,
    )
    assert assessment.blocks_consequential_approval_readiness is False


def test_staleness_is_detected_independently_of_readiness() -> None:
    assessment = assess_explanation_readiness(
        explanation(),
        validation=ValidationResult(outcome=ValidationOutcome.VALID, violations=()),
        restricted_evidence_disclosure=no_disclosure(),
        renderer_failed=False,
        at=NOW + timedelta(hours=2),
        is_consequential=True,
    )
    assert assessment.is_stale is True
    assert assessment.readiness is ExplanationReadiness.READY


def test_renderer_failure_is_carried_through() -> None:
    assessment = assess_explanation_readiness(
        explanation(),
        validation=ValidationResult(outcome=ValidationOutcome.VALID, violations=()),
        restricted_evidence_disclosure=no_disclosure(),
        renderer_failed=True,
        at=NOW,
        is_consequential=True,
    )
    assert assessment.renderer_fallback_required is True


def test_restricted_evidence_disclosure_is_carried_through() -> None:
    disclosure = RestrictedEvidenceDisclosure(
        omitted_count=1, disclosure="Additional restricted context may exist."
    )
    assessment = assess_explanation_readiness(
        explanation(),
        validation=ValidationResult(outcome=ValidationOutcome.VALID, violations=()),
        restricted_evidence_disclosure=disclosure,
        renderer_failed=False,
        at=NOW,
        is_consequential=True,
    )
    assert assessment.restricted_evidence_disclosure.omitted_count == 1


@pytest.mark.parametrize("outcome", list(PolicyDecisionOutcome))
def test_explanation_failure_never_changes_the_policy_outcome(
    outcome: PolicyDecisionOutcome,
) -> None:
    assessment = assess_explanation_readiness(
        explanation(),
        validation=ValidationResult(outcome=ValidationOutcome.ROUTE_TO_REVIEW, violations=("x",)),
        restricted_evidence_disclosure=no_disclosure(),
        renderer_failed=True,
        at=NOW,
        is_consequential=True,
    )
    assert apply_explanation_failure_to_policy_outcome(outcome, assessment=assessment) is outcome
