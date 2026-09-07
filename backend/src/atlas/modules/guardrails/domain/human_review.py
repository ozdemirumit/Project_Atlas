"""ATLAS-047 SS28: Human Review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ReviewerDecision(StrEnum):
    UPHOLD = "uphold"
    OVERTURN = "overturn"
    ESCALATE = "escalate"
    REQUEST_MORE_EVIDENCE = "request_more_evidence"


@dataclass(frozen=True, slots=True)
class DetectedElement:
    """SS28: "Detected sensitive, unsafe, ambiguous, or conflicting elements with redaction.\""""

    kind: str
    description: str
    redacted: bool

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.description.strip():
            raise ValueError("a detected element requires a kind and a description")
        if not self.redacted:
            raise ValueError("a detected element displayed to a reviewer must be redacted")


@dataclass(frozen=True, slots=True)
class HumanReviewQueueEntry:
    """SS28's exact queue-display contract."""

    entry_id: str
    triggered_rule_id: str
    safe_rationale: str
    request_reference: str
    bounded_context_reference: str
    detected_elements: tuple[DetectedElement, ...]
    proposed_disposition: str
    proposed_impact: str
    related_policy_reference: str | None
    related_approval_reference: str | None
    related_connector_reference: str | None
    related_audit_reference: str
    allowed_decisions: tuple[ReviewerDecision, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.entry_id, "entry_id")
        validate_stable_identifier(self.triggered_rule_id, "triggered_rule_id")
        required = (
            self.safe_rationale,
            self.request_reference,
            self.bounded_context_reference,
            self.proposed_disposition,
            self.proposed_impact,
            self.related_audit_reference,
        )
        if not all(value.strip() for value in required):
            raise ValueError("a human review queue entry requires the full SS28 display contract")
        if not self.allowed_decisions or len(set(self.allowed_decisions)) != len(
            self.allowed_decisions
        ):
            raise ValueError("a queue entry requires at least one distinct allowed decision")
        if self.created_at.tzinfo is None:
            raise ValueError("human review queue entry time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class HumanReviewResolution:
    """SS28: "Reviewers cannot reveal secrets, expand scope beyond their role, or mark
    deterministic denial as model preference." Each of the three is a required-`False` field --
    a resolution that did any of them is unconstructable, not merely discouraged."""

    entry_id: str
    decision: ReviewerDecision
    reviewed_by: str
    reviewed_at: datetime
    rationale: str
    revealed_a_secret: bool = False
    expanded_scope_beyond_role: bool = False
    treated_deterministic_denial_as_model_preference: bool = False

    def __post_init__(self) -> None:
        validate_stable_identifier(self.entry_id, "entry_id")
        validate_stable_identifier(self.reviewed_by, "reviewed_by")
        if not self.rationale.strip():
            raise ValueError("a human review resolution requires a rationale")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("human review resolution time must be timezone-aware")
        if self.revealed_a_secret:
            raise ValueError("a reviewer cannot reveal a secret")
        if self.expanded_scope_beyond_role:
            raise ValueError("a reviewer cannot expand scope beyond their role")
        if self.treated_deterministic_denial_as_model_preference:
            raise ValueError("a reviewer cannot mark a deterministic denial as model preference")


def a_human_reviewer_overturns_an_invariant_class_deterministic_block() -> bool:
    """SS28: "mark deterministic denial as model preference." Enforced by
    `GuardrailReviewService.resolve`, which refuses an `OVERTURN` decision whenever the
    triggering decision's `guardrail_class` is `GuardrailClass.INVARIANT` -- SS7 already frames
    an invariant as something that "must always hold", so a human review cannot reclassify one
    as a mere model preference."""
    return False
