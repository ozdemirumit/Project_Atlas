"""ATLAS-043 SS24: Outcome Learning application service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.recommendations.application.outcome_learning_ports import (
    RecommendationOutcomeRepository,
)
from atlas.modules.recommendations.domain.outcome_learning import (
    OutcomeResult,
    RecommendationOutcomeRecord,
)

OUTCOME_RECORDED_RESULT_CODE = "recommendation_outcome_recorded"


class RecommendationOutcomeError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RecommendationOutcomeService:
    """SS24: records what a human reports happened after a recommendation was acted on. Never
    executes anything and never mutates the recommendation it describes -- `RecommendationArtifact`
    is immutable and versioned, and this module has no execution authority (SS21)."""

    def __init__(
        self,
        *,
        repository: RecommendationOutcomeRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def record_outcome(
        self,
        *,
        recommendation_id: str,
        recommendation_version: int,
        plan_option_id: str,
        recorded_by: str,
        deviations_from_plan: tuple[str, ...],
        actual_started_at: datetime,
        actual_duration_minutes: int,
        actual_interruption_minutes: int | None,
        affected_scope: tuple[str, ...],
        result: OutcomeResult,
        actual_root_cause: str | None,
        root_cause_validated: bool,
        new_incidents: tuple[str, ...],
        side_effects: tuple[str, ...],
        reviewer_lessons: str,
        follow_up: tuple[str, ...],
        correlation_id: str,
    ) -> RecommendationOutcomeRecord:
        try:
            record = RecommendationOutcomeRecord(
                outcome_id=f"outcome.{uuid4().hex}",
                recommendation_id=recommendation_id,
                recommendation_version=recommendation_version,
                plan_option_id=plan_option_id,
                recorded_by=recorded_by,
                recorded_at=self._clock(),
                deviations_from_plan=deviations_from_plan,
                actual_started_at=actual_started_at,
                actual_duration_minutes=actual_duration_minutes,
                actual_interruption_minutes=actual_interruption_minutes,
                affected_scope=affected_scope,
                result=result,
                actual_root_cause=actual_root_cause,
                root_cause_validated=root_cause_validated,
                new_incidents=new_incidents,
                side_effects=side_effects,
                reviewer_lessons=reviewer_lessons,
                follow_up=follow_up,
            )
        except ValueError as error:
            raise RecommendationOutcomeError("recommendation_outcome_invalid") from error
        if not await self._repository.create(record):
            raise RecommendationOutcomeError("recommendation_outcome_already_recorded")
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendations.outcome.recorded",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=recorded_by,
                actor_type=None,
                authentication_method=None,
                assurance_level=None,
                permission_id=None,
                resource_type="resource.recommendation.outcome",
                scope_reference=recommendation_id,
                decision_id=None,
                outcome="succeeded",
                result_code=OUTCOME_RECORDED_RESULT_CODE,
                target_subject_id=recommendation_id,
            )
        )
        return record

    async def get_outcome(self, recommendation_id: str) -> RecommendationOutcomeRecord | None:
        return await self._repository.get(recommendation_id)
