from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.explainability.domain.audience import (
    EmphasisField,
    adapt_audience,
    adapt_detail_level,
    emphasis_for,
)
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


def explanation(**overrides: object) -> Explanation:
    claim = ExplanationClaim(
        claim_id="explanation-claim.example",
        claim_type=ClaimType.FACT,
        statement="The controller reports a degraded status.",
        confidence=ConfidenceLevel.HIGH,
        evidence_references=("evidence.example",),
        contradicting_evidence_references=(),
    )
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
        "claims": (claim,),
        "evidence_links": (link,),
        "unknowns": (),
        "alternatives": (),
        "recommended_next_step": "Review controller B diagnostics.",
        "redacted": False,
    }
    defaults.update(overrides)
    return Explanation(**defaults)  # type: ignore[arg-type]


def test_every_audience_profile_has_a_non_empty_emphasis_list() -> None:
    for audience in AudienceProfile:
        assert emphasis_for(audience) != ()


def test_every_emphasis_field_is_used_by_at_least_one_audience_profile() -> None:
    # VERSIONS is deliberately shared: SS11 independently names "versions" for both the
    # Infrastructure Engineer and the Security/Audit Reviewer profiles -- a real, accurate
    # overlap in the source document, not something this test should treat as a bug.
    used = {field for audience in AudienceProfile for field in emphasis_for(audience)}
    assert used == set(EmphasisField)


def test_versions_is_shared_by_engineer_and_security_reviewer_profiles() -> None:
    assert EmphasisField.VERSIONS in emphasis_for(AudienceProfile.INFRASTRUCTURE_ENGINEER)
    assert EmphasisField.VERSIONS in emphasis_for(AudienceProfile.SECURITY_OR_AUDIT_REVIEWER)


def test_adapt_detail_level_changes_only_the_level() -> None:
    original = explanation()
    adapted = adapt_detail_level(original, target_level=ExplanationDetailLevel.L3_GOVERNANCE)
    assert adapted.detail_level is ExplanationDetailLevel.L3_GOVERNANCE
    assert adapted.claims == original.claims
    assert adapted.evidence_links == original.evidence_links
    assert adapted.summary == original.summary
    assert adapted.audience == original.audience


def test_adapt_audience_changes_only_the_audience() -> None:
    original = explanation()
    adapted = adapt_audience(original, target_audience=AudienceProfile.SECURITY_OR_AUDIT_REVIEWER)
    assert adapted.audience is AudienceProfile.SECURITY_OR_AUDIT_REVIEWER
    assert adapted.claims == original.claims
    assert adapted.evidence_links == original.evidence_links
    assert adapted.summary == original.summary
    assert adapted.detail_level == original.detail_level


@pytest.mark.parametrize("level", list(ExplanationDetailLevel))
def test_adapting_to_every_level_preserves_claims(level: ExplanationDetailLevel) -> None:
    original = explanation()
    adapted = adapt_detail_level(original, target_level=level)
    assert adapted.claims == original.claims
