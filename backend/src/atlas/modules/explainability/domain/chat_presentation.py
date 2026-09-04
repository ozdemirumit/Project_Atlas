"""ATLAS-046 SS19: chat presentation.

Assembles SS19's fixed six-part chat structure from pieces already built in this subsystem --
`Explanation` (SS6) for the direct assessment, evidence links, and recommended next safe step;
`ConfidenceExplanation` (SS12) for confidence and its most important limitation;
`RiskImpactExplanation` (SS16) for affected scope -- rather than a new dedicated capture of the
same facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.explainability.domain.confidence import ConfidenceExplanation
from atlas.modules.explainability.domain.models import Explanation, ExplanationChannel
from atlas.modules.explainability.domain.risk_impact import RiskImpactExplanation

_MAX_INLINE_EVIDENCE_ITEMS = 5


@dataclass(frozen=True, slots=True)
class ChatEvidenceSummary:
    """SS19: "long evidence inventories are summarized with drill-down.\""""

    inline_items: tuple[str, ...]
    total_evidence_count: int

    def __post_init__(self) -> None:
        if len(self.inline_items) > _MAX_INLINE_EVIDENCE_ITEMS:
            raise ValueError(
                f"chat evidence must be capped at {_MAX_INLINE_EVIDENCE_ITEMS} inline items,"
                " with the remainder reachable by drill-down"
            )
        if self.total_evidence_count < len(self.inline_items):
            raise ValueError("total evidence count cannot be smaller than the inline items shown")

    @property
    def has_more(self) -> bool:
        return self.total_evidence_count > len(self.inline_items)


def summarize_evidence_for_chat(evidence_texts: tuple[str, ...]) -> ChatEvidenceSummary:
    return ChatEvidenceSummary(
        inline_items=evidence_texts[:_MAX_INLINE_EVIDENCE_ITEMS],
        total_evidence_count=len(evidence_texts),
    )


def _important_limitation_from(confidence: ConfidenceExplanation) -> str:
    if confidence.limiting_factors:
        return confidence.limiting_factors[0]
    return "No material limitation identified."


@dataclass(frozen=True, slots=True)
class ChatResponseExplanation:
    """SS19's fixed six-part chat structure, in order: direct assessment, key evidence,
    confidence and important limitation, affected scope, recommended next safe step, and a
    reference to expandable details."""

    direct_assessment: str
    key_evidence: ChatEvidenceSummary
    confidence: ConfidenceExplanation
    important_limitation: str
    affected_scope: RiskImpactExplanation | None
    recommended_next_safe_step: str
    expandable_details_reference: str

    def __post_init__(self) -> None:
        if not self.direct_assessment.strip():
            raise ValueError("a chat response requires a direct assessment")
        if not self.important_limitation.strip():
            raise ValueError("a chat response requires an important limitation statement")
        if not self.recommended_next_safe_step.strip():
            raise ValueError("a chat response requires a recommended next safe step")
        if not self.expandable_details_reference.strip():
            raise ValueError("a chat response requires a reference to its expandable details")


def build_chat_response(
    explanation: Explanation,
    *,
    confidence: ConfidenceExplanation,
    affected_scope: RiskImpactExplanation | None,
    expandable_details_reference: str,
) -> ChatResponseExplanation:
    if explanation.channel is not ExplanationChannel.CHAT:
        raise ValueError("a chat response can only be built from a CHAT-channel explanation")
    return ChatResponseExplanation(
        direct_assessment=explanation.summary,
        key_evidence=summarize_evidence_for_chat(
            tuple(link.applicability for link in explanation.evidence_links)
        ),
        confidence=confidence,
        important_limitation=_important_limitation_from(confidence),
        affected_scope=affected_scope,
        recommended_next_safe_step=explanation.recommended_next_step,
        expandable_details_reference=expandable_details_reference,
    )


class ChatAcknowledgementKind(StrEnum):
    SEEN = "seen"
    UNDERSTOOD = "understood"
    WILL_FOLLOW_UP = "will_follow_up"


@dataclass(frozen=True, slots=True)
class ChatAcknowledgement:
    """SS19: "chat acknowledgement is never interpreted as formal approval." A deliberately
    distinct type from `approvals.domain.models.ApprovalOutcome` -- nothing in this module can
    construct or accept an `ApprovalOutcome` from a chat acknowledgement, and
    `constitutes_approval` gives that sentence a concrete, always-False call site rather than
    leaving it as a convention a caller has to remember unaided."""

    kind: ChatAcknowledgementKind
    acknowledged_by: str

    def __post_init__(self) -> None:
        if not self.acknowledged_by.strip():
            raise ValueError("a chat acknowledgement requires who acknowledged it")

    @property
    def constitutes_approval(self) -> bool:
        return False
