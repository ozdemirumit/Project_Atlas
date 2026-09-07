from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.outcome_learning import (
    OutcomeResult,
    RecommendationOutcomeRecord,
)


class RecommendationOutcomeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_version: int = Field(ge=1)
    plan_option_id: str = Field(min_length=1, max_length=128)
    recorded_by: str = Field(min_length=1, max_length=128)
    deviations_from_plan: list[str] = Field(default_factory=list)
    actual_started_at: datetime
    actual_duration_minutes: int = Field(ge=0)
    actual_interruption_minutes: int | None = Field(default=None, ge=0)
    affected_scope: list[str] = Field(default_factory=list)
    result: OutcomeResult
    actual_root_cause: str | None = None
    root_cause_validated: bool = False
    new_incidents: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    reviewer_lessons: str = Field(min_length=1)
    follow_up: list[str] = Field(default_factory=list)


class RecommendationOutcomeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_id: str
    recommendation_id: str
    recommendation_version: int
    plan_option_id: str
    recorded_by: str
    recorded_at: datetime
    deviations_from_plan: list[str]
    actual_started_at: datetime
    actual_duration_minutes: int
    actual_interruption_minutes: int | None
    affected_scope: list[str]
    result: OutcomeResult
    actual_root_cause: str | None
    root_cause_validated: bool
    new_incidents: list[str]
    side_effects: list[str]
    reviewer_lessons: str
    follow_up: list[str]

    @classmethod
    def from_domain(cls, record: RecommendationOutcomeRecord) -> RecommendationOutcomeData:
        return cls(
            outcome_id=record.outcome_id,
            recommendation_id=record.recommendation_id,
            recommendation_version=record.recommendation_version,
            plan_option_id=record.plan_option_id,
            recorded_by=record.recorded_by,
            recorded_at=record.recorded_at,
            deviations_from_plan=list(record.deviations_from_plan),
            actual_started_at=record.actual_started_at,
            actual_duration_minutes=record.actual_duration_minutes,
            actual_interruption_minutes=record.actual_interruption_minutes,
            affected_scope=list(record.affected_scope),
            result=record.result,
            actual_root_cause=record.actual_root_cause,
            root_cause_validated=record.root_cause_validated,
            new_incidents=list(record.new_incidents),
            side_effects=list(record.side_effects),
            reviewer_lessons=record.reviewer_lessons,
            follow_up=list(record.follow_up),
        )


class RecommendationOutcomeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: RecommendationOutcomeData
    meta: ResponseMeta
