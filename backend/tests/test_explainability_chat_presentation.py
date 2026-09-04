from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.explainability.domain.chat_presentation import (
    ChatAcknowledgement,
    ChatAcknowledgementKind,
    ChatEvidenceSummary,
    ChatResponseExplanation,
    build_chat_response,
    summarize_evidence_for_chat,
)
from atlas.modules.explainability.domain.confidence import ConfidenceExplanation
from atlas.modules.explainability.domain.models import (
    AudienceProfile,
    EvidenceLink,
    Explanation,
    ExplanationChannel,
    ExplanationDetailLevel,
)
from atlas.modules.guardrails.domain.reasoning_guardrails import ConfidenceLevel

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def evidence_link(**overrides: object) -> EvidenceLink:
    defaults: dict[str, object] = {
        "reference": "evidence.example",
        "source": "health-check.example",
        "version": "1",
        "target_id": "target.example",
        "observed_at": NOW,
        "authority": "vendor-documented",
        "applicability": "Controller B reports a degraded status.",
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


def confidence(**overrides: object) -> ConfidenceExplanation:
    defaults: dict[str, object] = {
        "category": ConfidenceLevel.HIGH,
        "category_definition": "High confidence: multiple independent, current signals agree.",
        "supporting_factors": ("Matches a known, resolved fault pattern.",),
        "limiting_factors": ("The vendor advisory predates this firmware version.",),
        "remaining_alternatives": (),
        "missing_or_conflicting_evidence": (),
        "what_would_change_the_category": "A repeat occurrence after the fix would lower it.",
        "is_confirmed": False,
        "domain_criteria_met": False,
    }
    defaults.update(overrides)
    return ConfidenceExplanation(**defaults)  # type: ignore[arg-type]


def test_summarize_evidence_for_chat_caps_inline_items_at_five() -> None:
    summary = summarize_evidence_for_chat(tuple(f"evidence {i}" for i in range(8)))
    assert len(summary.inline_items) == 5
    assert summary.total_evidence_count == 8
    assert summary.has_more is True


def test_summarize_evidence_for_chat_with_few_items_has_no_more() -> None:
    summary = summarize_evidence_for_chat(("evidence 1",))
    assert summary.has_more is False


def test_chat_evidence_summary_rejects_more_than_five_inline_items() -> None:
    with pytest.raises(ValueError, match="capped"):
        ChatEvidenceSummary(
            inline_items=tuple(f"evidence {i}" for i in range(6)), total_evidence_count=6
        )


def test_chat_evidence_summary_rejects_a_total_smaller_than_inline_items() -> None:
    with pytest.raises(ValueError, match="cannot be smaller"):
        ChatEvidenceSummary(inline_items=("a", "b"), total_evidence_count=1)


def test_build_chat_response_pulls_direct_assessment_from_the_explanation_summary() -> None:
    response = build_chat_response(
        explanation(),
        confidence=confidence(),
        affected_scope=None,
        expandable_details_reference="explanation.example",
    )
    assert response.direct_assessment == "Controller B reports a degraded status."
    assert response.recommended_next_safe_step == "Review controller B diagnostics."


def test_build_chat_response_uses_the_first_limiting_factor() -> None:
    response = build_chat_response(
        explanation(),
        confidence=confidence(),
        affected_scope=None,
        expandable_details_reference="explanation.example",
    )
    assert response.important_limitation == "The vendor advisory predates this firmware version."


def test_build_chat_response_falls_back_when_no_limiting_factors() -> None:
    response = build_chat_response(
        explanation(),
        confidence=confidence(limiting_factors=()),
        affected_scope=None,
        expandable_details_reference="explanation.example",
    )
    assert response.important_limitation == "No material limitation identified."


def test_build_chat_response_rejects_a_non_chat_explanation() -> None:
    with pytest.raises(ValueError, match="CHAT-channel"):
        build_chat_response(
            explanation(channel=ExplanationChannel.REPORT),
            confidence=confidence(),
            affected_scope=None,
            expandable_details_reference="explanation.example",
        )


def _response(**overrides: object) -> ChatResponseExplanation:
    base = build_chat_response(
        explanation(),
        confidence=confidence(),
        affected_scope=None,
        expandable_details_reference="explanation.example",
    )
    defaults: dict[str, object] = {
        "direct_assessment": base.direct_assessment,
        "key_evidence": base.key_evidence,
        "confidence": base.confidence,
        "important_limitation": base.important_limitation,
        "affected_scope": base.affected_scope,
        "recommended_next_safe_step": base.recommended_next_safe_step,
        "expandable_details_reference": base.expandable_details_reference,
    }
    defaults.update(overrides)
    return ChatResponseExplanation(**defaults)  # type: ignore[arg-type]


def test_rejects_blank_direct_assessment() -> None:
    with pytest.raises(ValueError, match="direct assessment"):
        _response(direct_assessment="   ")


def test_rejects_blank_recommended_next_safe_step() -> None:
    with pytest.raises(ValueError, match="next safe step"):
        _response(recommended_next_safe_step="   ")


def test_rejects_blank_expandable_details_reference() -> None:
    with pytest.raises(ValueError, match="expandable details"):
        _response(expandable_details_reference="   ")


def test_chat_acknowledgement_never_constitutes_approval() -> None:
    acknowledgement = ChatAcknowledgement(
        kind=ChatAcknowledgementKind.UNDERSTOOD, acknowledged_by="subject.requester"
    )
    assert acknowledgement.constitutes_approval is False


def test_chat_acknowledgement_requires_who_acknowledged_it() -> None:
    with pytest.raises(ValueError, match="who acknowledged"):
        ChatAcknowledgement(kind=ChatAcknowledgementKind.SEEN, acknowledged_by="   ")
