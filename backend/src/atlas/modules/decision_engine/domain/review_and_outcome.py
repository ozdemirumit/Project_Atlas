"""ATLAS-024 SS21/SS22: human review and feedback/outcome learning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ReviewActionKind(StrEnum):
    """SS21's six reviewer actions (the "confirm or reject findings" bullet counted as two
    distinct actions, since confirming and rejecting are opposite outcomes needing separate
    attribution)."""

    CONFIRM_FINDING = "confirm_finding"
    REJECT_FINDING = "reject_finding"
    ADD_EVIDENCE = "add_evidence"
    CORRECT_TARGET_OR_APPLICABILITY = "correct_target_or_applicability"
    RERANK_HYPOTHESES = "rerank_hypotheses"
    REJECT_RECOMMENDATION = "reject_recommendation"
    REQUEST_REANALYSIS = "request_reanalysis"


@dataclass(frozen=True, slots=True)
class HumanReviewAction:
    """SS21: "human changes are attributed and create a reviewed version or annotation; they do
    not erase generated history." Reference-only, matching this session's established "reference
    only, never mutates the source" pattern (`InvestigationAnnotation`, `ChallengeOrCorrection`,
    `OperatorRecordedResult`) -- there is no field through which recording one could erase or
    rewrite the finding/hypothesis/recommendation it targets."""

    action_id: str
    kind: ReviewActionKind
    target_reference: str
    reviewer_id: str
    reviewed_at: datetime
    reason: str
    resulting_reviewed_version_id: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.action_id, "action_id")
        validate_stable_identifier(self.target_reference, "target_reference")
        if not self.reviewer_id.strip():
            raise ValueError("a human review action requires who reviewed it")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if not self.reason.strip():
            raise ValueError("a human review action requires a reason")


class OutcomeQualityLabel(StrEnum):
    """SS22: "false positive, false negative, or missing evidence.\""""

    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    MISSING_EVIDENCE = "missing_evidence"


@dataclass(frozen=True, slots=True)
class DecisionOutcomeRecord:
    """SS22's five declared elements."""

    outcome_id: str
    decision_id: str
    confirmed_hypothesis_id: str | None
    selected_candidate_id: str | None
    actual_impact: str | None
    actual_duration_minutes: int | None
    actual_service_interruption: str | None
    validation_outcome: str | None
    recovery_outcome: str | None
    quality_labels: tuple[OutcomeQualityLabel, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.outcome_id, "outcome_id")
        validate_stable_identifier(self.decision_id, "decision_id")
        if self.actual_duration_minutes is not None and self.actual_duration_minutes < 0:
            raise ValueError("actual_duration_minutes must not be negative")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")


def outcome_data_authorizes_automatic_model_training() -> bool:
    """SS22: "outcome data is governed operational history and evaluation input, not automatic
    model training." Always `False`."""
    return False
