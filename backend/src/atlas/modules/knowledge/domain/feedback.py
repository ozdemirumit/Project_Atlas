"""ATLAS-027 SS22: Feedback.

"Feedback creates a triaged work item. It does not directly modify rank, approval, or content."
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class FeedbackKind(StrEnum):
    """SS22's six named things a consumer may report."""

    INCORRECT_OR_OUTDATED = "incorrect_or_outdated"
    WRONG_APPLICABILITY = "wrong_applicability"
    MISSING_EVIDENCE = "missing_evidence"
    ACCESS_CONCERN = "access_concern"
    UNSAFE_OR_AMBIGUOUS_PROCEDURE = "unsafe_or_ambiguous_procedure"
    RECOMMENDATION_OUTCOME = "recommendation_outcome"


class FeedbackWorkItemState(StrEnum):
    OPEN = "open"
    TRIAGED = "triaged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


@dataclass(frozen=True, slots=True)
class KnowledgeFeedback:
    feedback_id: str
    item_id: str
    item_version: str
    kind: FeedbackKind
    submitted_by: str
    submitted_at: datetime
    description: str
    state: FeedbackWorkItemState
    triaged_by: str | None = None
    triaged_at: datetime | None = None
    resolution_notes: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.feedback_id,
            self.item_id,
            self.item_version,
            self.submitted_by,
            self.description,
        )
        if not all(value.strip() for value in required):
            raise ValueError("knowledge feedback identity, target, and description are required")
        if self.submitted_at.tzinfo is None:
            raise ValueError("feedback submission time must be timezone-aware")
        if self.triaged_at is not None and self.triaged_at.tzinfo is None:
            raise ValueError("feedback triage time must be timezone-aware")
        triage_fields = (self.triaged_by, self.triaged_at)
        if self.state is FeedbackWorkItemState.OPEN:
            if any(value is not None for value in triage_fields) or self.resolution_notes:
                raise ValueError("open feedback cannot carry triage or resolution data")
        elif any(value is None for value in triage_fields):
            raise ValueError("triaged feedback requires who and when it was triaged")
        if self.state in (FeedbackWorkItemState.RESOLVED, FeedbackWorkItemState.DISMISSED):
            if not (self.resolution_notes is not None and self.resolution_notes.strip()):
                raise ValueError("resolved or dismissed feedback requires resolution notes")
        elif self.resolution_notes is not None:
            raise ValueError("only resolved or dismissed feedback carries resolution notes")
        if self.triaged_at is not None and self.triaged_at < self.submitted_at:
            raise ValueError("feedback cannot be triaged before it was submitted")


def submitting_knowledge_feedback_directly_modifies_item_rank_approval_or_content() -> bool:
    """SS22: "Feedback creates a triaged work item. It does not directly modify rank, approval,
    or content." `KnowledgeFeedback` has no relationship to `KnowledgeChunk`'s rank, approval, or
    content fields other than the item/version identifiers it refers to -- submitting one cannot
    reach into and mutate the item it is about."""
    return False
