from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.recommendations.adapters.outcome_learning_memory import (
    InMemoryRecommendationOutcomeRepository,
)
from atlas.modules.recommendations.application.outcome_learning import (
    RecommendationOutcomeError,
    RecommendationOutcomeService,
)
from atlas.modules.recommendations.domain.outcome_learning import (
    OutcomeResult,
    RecommendationOutcomeRecord,
    an_outcome_record_is_persisted_before_the_recommendation_it_describes_started,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
STARTED = NOW - timedelta(hours=2)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[RecommendationOutcomeService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = RecommendationOutcomeService(
        repository=InMemoryRecommendationOutcomeRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def _kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "recommendation_id": "recommendation.storage-remediation.primary",
        "recommendation_version": 1,
        "plan_option_id": "option.remediation.a",
        "recorded_by": "subject.operator.primary",
        "deviations_from_plan": (),
        "actual_started_at": STARTED,
        "actual_duration_minutes": 45,
        "actual_interruption_minutes": 5,
        "affected_scope": ("asset.storage.a",),
        "result": OutcomeResult.SUCCESS,
        "actual_root_cause": "Failed controller path, confirmed via vendor diagnostics.",
        "root_cause_validated": True,
        "new_incidents": (),
        "side_effects": (),
        "reviewer_lessons": "Runbook step 3 needed an extra verification pause.",
        "follow_up": ("Update runbook step 3 guidance.",),
        "correlation_id": "correlation.test",
    }
    values.update(overrides)
    return values


def test_absolute_rule_is_false() -> None:
    assert an_outcome_record_is_persisted_before_the_recommendation_it_describes_started() is False


@pytest.mark.asyncio
async def test_record_outcome_persists_and_audits() -> None:
    service, audit_sink = _service()
    record = await service.record_outcome(**_kwargs())  # type: ignore[arg-type]
    assert isinstance(record, RecommendationOutcomeRecord)
    assert record.result is OutcomeResult.SUCCESS
    stored = await service.get_outcome("recommendation.storage-remediation.primary")
    assert stored == record
    assert any(item.result_code == "recommendation_outcome_recorded" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_record_outcome_rejects_a_duplicate_for_the_same_recommendation() -> None:
    service, _audit = _service()
    await service.record_outcome(**_kwargs())  # type: ignore[arg-type]
    with pytest.raises(RecommendationOutcomeError, match="recommendation_outcome_already_recorded"):
        await service.record_outcome(**_kwargs())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_outcome_rejects_recorded_before_started() -> None:
    service, _audit = _service()
    with pytest.raises(RecommendationOutcomeError, match="recommendation_outcome_invalid"):
        await service.record_outcome(
            **_kwargs(actual_started_at=NOW + timedelta(hours=1))  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_record_outcome_requires_reviewer_lessons() -> None:
    service, _audit = _service()
    with pytest.raises(RecommendationOutcomeError, match="recommendation_outcome_invalid"):
        await service.record_outcome(**_kwargs(reviewer_lessons="   "))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_outcome_requires_root_cause_text_when_validated() -> None:
    service, _audit = _service()
    with pytest.raises(RecommendationOutcomeError, match="recommendation_outcome_invalid"):
        await service.record_outcome(
            **_kwargs(actual_root_cause=None, root_cause_validated=True)  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_get_outcome_returns_none_when_unrecorded() -> None:
    service, _audit = _service()
    assert await service.get_outcome("recommendation.no-such-one") is None
