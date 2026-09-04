from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.explainability.domain.investigation_presentation import ClockQuality
from atlas.modules.reasoning.domain.temporal import (
    TemporalEvent,
    TimelineEventKind,
    is_temporally_current,
    observation_order_proves_causation,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def event(**overrides: object) -> TemporalEvent:
    defaults: dict[str, object] = {
        "event_id": "reasoning-temporal-event.example",
        "kind": TimelineEventKind.SYMPTOM,
        "description": "Controller B reported a degraded status.",
        "occurred_at": NOW - timedelta(minutes=10),
        "observed_at": NOW - timedelta(minutes=9),
        "ingested_at": NOW - timedelta(minutes=8),
        "reported_at": NOW,
        "clock_quality": ClockQuality.SYNCHRONIZED,
        "known_skew_seconds": 2,
    }
    defaults.update(overrides)
    return TemporalEvent(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_event_constructs_cleanly() -> None:
    example = event()
    assert example.clock_quality is ClockQuality.SYNCHRONIZED


def test_rejects_blank_description() -> None:
    with pytest.raises(ValueError, match="description"):
        event(description="   ")


def test_data_gap_cannot_carry_an_occurrence_time() -> None:
    with pytest.raises(ValueError, match="no occurrence time"):
        event(kind=TimelineEventKind.DATA_GAP, occurred_at=NOW - timedelta(minutes=10))


def test_data_gap_constructs_without_an_occurrence_time() -> None:
    example = event(kind=TimelineEventKind.DATA_GAP, occurred_at=None)
    assert example.occurred_at is None


def test_rejects_naive_occurred_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        event(occurred_at=(NOW - timedelta(minutes=10)).replace(tzinfo=None))


def test_rejects_naive_reported_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        event(reported_at=NOW.replace(tzinfo=None))


def test_rejects_negative_known_skew() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        event(known_skew_seconds=-1)


def test_known_skew_may_be_none() -> None:
    example = event(known_skew_seconds=None)
    assert example.known_skew_seconds is None


def test_has_conflicting_timestamps_false_for_correctly_ordered_times() -> None:
    assert event().has_conflicting_timestamps is False


def test_has_conflicting_timestamps_true_when_observed_precedes_occurred() -> None:
    example = event(
        occurred_at=NOW - timedelta(minutes=1),
        observed_at=NOW - timedelta(minutes=10),
        ingested_at=NOW - timedelta(minutes=8),
        reported_at=NOW,
    )
    assert example.has_conflicting_timestamps is True


def test_observation_order_never_proves_causation() -> None:
    earlier = event(event_id="reasoning-temporal-event.earlier")
    later = event(
        event_id="reasoning-temporal-event.later",
        occurred_at=NOW - timedelta(minutes=1),
        observed_at=NOW,
        ingested_at=NOW,
        reported_at=NOW,
    )
    assert observation_order_proves_causation(earlier=earlier, later=later) is False


def test_is_temporally_current_within_the_limit() -> None:
    example = event(observed_at=NOW - timedelta(seconds=60))
    assert is_temporally_current(example, freshness_limit_seconds=300, now=NOW) is True


def test_is_temporally_current_beyond_the_limit() -> None:
    example = event(observed_at=NOW - timedelta(seconds=600))
    assert is_temporally_current(example, freshness_limit_seconds=300, now=NOW) is False


def test_is_temporally_current_rejects_naive_now() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        is_temporally_current(event(), freshness_limit_seconds=300, now=NOW.replace(tzinfo=None))


def test_is_temporally_current_falls_back_to_reported_at_when_nothing_else_is_known() -> None:
    example = event(
        kind=TimelineEventKind.DATA_GAP,
        occurred_at=None,
        observed_at=None,
        ingested_at=None,
        reported_at=NOW - timedelta(seconds=600),
    )
    assert is_temporally_current(example, freshness_limit_seconds=300, now=NOW) is False
