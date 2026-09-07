"""ATLAS-043 SS24: Outcome Learning.

"After a human-executed or future governed action, Atlas records: exact recommendation and plan
version used, deviations from plan, actual start/duration/interruption/affected scope, success/
partial success/failure/rollback/recovery, actual root cause and validation where known, new
incidents or side effects, reviewer lessons and follow-up." No part of this codebase currently
executes a recommendation -- this module records what a human reports happened, after the fact.
ATLAS-027 governs converting an outcome into organizational knowledge; that conversion is out of
this module's scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class OutcomeResult(StrEnum):
    """SS24: "success, partial success, failure, rollback, or recovery.\""""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    ROLLED_BACK = "rolled_back"
    RECOVERED = "recovered"


@dataclass(frozen=True, slots=True)
class RecommendationOutcomeRecord:
    outcome_id: str
    recommendation_id: str
    recommendation_version: int
    plan_option_id: str
    recorded_by: str
    recorded_at: datetime
    deviations_from_plan: tuple[str, ...]
    actual_started_at: datetime
    actual_duration_minutes: int
    actual_interruption_minutes: int | None
    affected_scope: tuple[str, ...]
    result: OutcomeResult
    actual_root_cause: str | None
    root_cause_validated: bool
    new_incidents: tuple[str, ...]
    side_effects: tuple[str, ...]
    reviewer_lessons: str
    follow_up: tuple[str, ...]

    def __post_init__(self) -> None:
        for value, label in (
            (self.outcome_id, "outcome_id"),
            (self.recommendation_id, "recommendation_id"),
            (self.plan_option_id, "plan_option_id"),
            (self.recorded_by, "recorded_by"),
        ):
            validate_stable_identifier(value, label)
        if self.recommendation_version < 1:
            raise ValueError("recommendation outcome version must be positive")
        if self.actual_started_at.tzinfo is None or self.recorded_at.tzinfo is None:
            raise ValueError("recommendation outcome timestamps must be timezone-aware")
        if self.recorded_at < self.actual_started_at:
            raise ValueError("recommendation outcome cannot be recorded before it started")
        if self.actual_duration_minutes < 0:
            raise ValueError("actual duration cannot be negative")
        if self.actual_interruption_minutes is not None and self.actual_interruption_minutes < 0:
            raise ValueError("actual interruption cannot be negative")
        if not self.reviewer_lessons.strip():
            raise ValueError("recommendation outcome requires reviewer lessons")
        if self.root_cause_validated and not (
            self.actual_root_cause is not None and self.actual_root_cause.strip()
        ):
            raise ValueError("a validated root cause requires the root cause itself")


def an_outcome_record_is_persisted_before_the_recommendation_it_describes_started() -> bool:
    """SS24: outcome learning always follows an actual start; `RecommendationOutcomeRecord`
    structurally forbids `recorded_at` preceding `actual_started_at`."""
    return False
