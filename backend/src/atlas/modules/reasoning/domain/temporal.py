"""ATLAS-041 SS11: temporal reasoning.

Reuses Explainability's `investigation_presentation.ClockQuality` for "clock quality and known
skew are visible" rather than a second clock-quality scale -- the same four levels
(authoritative/synchronized/estimated/unknown) apply unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.explainability.domain.investigation_presentation import ClockQuality
from atlas.modules.identity.domain.models import validate_stable_identifier


class TimelineEventKind(StrEnum):
    """SS11: "a timeline identifies changes, symptoms, alerts, recovery, and data gaps.\""""

    CHANGE = "change"
    SYMPTOM = "symptom"
    ALERT = "alert"
    RECOVERY = "recovery"
    DATA_GAP = "data_gap"


@dataclass(frozen=True, slots=True)
class TemporalEvent:
    """SS11: "Atlas distinguishes occurrence, observation, ingestion, and report times.\""""

    event_id: str
    kind: TimelineEventKind
    description: str
    occurred_at: datetime | None
    observed_at: datetime | None
    ingested_at: datetime | None
    reported_at: datetime
    clock_quality: ClockQuality
    known_skew_seconds: int | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.event_id, "event_id")
        if not self.description.strip():
            raise ValueError("a temporal event requires a description")
        if self.kind is TimelineEventKind.DATA_GAP and self.occurred_at is not None:
            raise ValueError("a data-gap event has no occurrence time by definition")
        for value, name in (
            (self.occurred_at, "occurred_at"),
            (self.observed_at, "observed_at"),
            (self.ingested_at, "ingested_at"),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.reported_at.tzinfo is None:
            raise ValueError("reported_at must be timezone-aware")
        if self.known_skew_seconds is not None and self.known_skew_seconds < 0:
            raise ValueError("known_skew_seconds must not be negative")

    @property
    def has_conflicting_timestamps(self) -> bool:
        """SS11: "conflicting timestamps reduce certainty and may require a new check." A
        conflict exists when the recorded times are out of the order they must follow --
        occurrence precedes observation, which precedes ingestion, which precedes report."""
        times = [
            value
            for value in (self.occurred_at, self.observed_at, self.ingested_at, self.reported_at)
            if value is not None
        ]
        return times != sorted(times)


def observation_order_proves_causation(*, earlier: TemporalEvent, later: TemporalEvent) -> bool:
    """SS11: "later observation does not prove later causation." Always `False` -- a concrete
    call site for the rule, not a convention a caller has to remember unaided."""
    del earlier, later
    return False


def is_temporally_current(
    event: TemporalEvent, *, freshness_limit_seconds: int, now: datetime
) -> bool:
    """SS11: "stale topology or health data is not silently treated as current." Takes `now`
    explicitly rather than reading the wall clock, matching every other freshness check already
    established in this codebase."""
    if now.tzinfo is None:
        raise ValueError("temporal currency check requires a timezone-aware now")
    # observed_at/occurred_at are preferred when known; reported_at is always present and is
    # the guaranteed fallback, so this reference is never None.
    reference_time = event.observed_at or event.occurred_at or event.reported_at
    return (now - reference_time).total_seconds() <= freshness_limit_seconds
