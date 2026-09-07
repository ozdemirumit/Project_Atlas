from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.core.events import (
    ConsumerEventInbox,
    EventEnvelope,
    InMemoryDomainEventBus,
    a_domain_event_has_more_than_one_authoritative_producer,
    an_event_consumer_treats_an_informational_event_as_authorization,
    an_event_is_published_before_its_owned_state_transition_commits,
    audit_or_workflow_truth_depends_solely_on_the_event_stream,
    best_effort_delivery_is_used_for_an_authoritative_outcome,
    is_valid_event_type_name,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def test_absolute_rules_are_all_false() -> None:
    assert a_domain_event_has_more_than_one_authoritative_producer() is False
    assert an_event_is_published_before_its_owned_state_transition_commits() is False
    assert audit_or_workflow_truth_depends_solely_on_the_event_stream() is False
    assert best_effort_delivery_is_used_for_an_authoritative_outcome() is False
    assert an_event_consumer_treats_an_informational_event_as_authorization() is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("WorkflowRunStarted", True),
        ("IdentityAuthenticationSucceeded", True),
        ("A", True),
        ("workflow.run.started", False),
        ("workflowRunStarted", False),
        ("Workflow_Run_Started", False),
        ("", False),
    ],
)
def test_is_valid_event_type_name(value: str, expected: bool) -> None:
    assert is_valid_event_type_name(value) is expected


def _envelope(**overrides: object) -> EventEnvelope:
    defaults: dict[str, object] = {
        "event_id": "evt_example-001",
        "event_type": "WorkflowRunStarted",
        "event_version": "1.0",
        "occurred_at": NOW,
        "recorded_at": NOW,
        "producer": "workflows",
        "subject_type": "workflow_run",
        "subject_id": "workflow-run.example-001",
        "correlation_id": "correlation.example",
        "classification": DataClassification.INTERNAL,
        "payload": {"example": "payload"},
    }
    defaults.update(overrides)
    return EventEnvelope(**defaults)  # type: ignore[arg-type]


def test_envelope_builds_with_valid_fields() -> None:
    envelope = _envelope()
    assert envelope.event_type == "WorkflowRunStarted"


def test_envelope_rejects_invalid_event_type_name() -> None:
    with pytest.raises(ValueError, match="PastTenseOutcome"):
        _envelope(event_type="workflow.run.started")


def test_envelope_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _envelope(occurred_at=datetime(2026, 9, 7, 12, 0))


def test_envelope_rejects_recorded_before_occurred() -> None:
    with pytest.raises(ValueError, match="cannot be recorded before"):
        _envelope(recorded_at=NOW - timedelta(minutes=1))


def test_envelope_rejects_blank_identity_fields() -> None:
    with pytest.raises(ValueError, match="identity fields are required"):
        _envelope(producer="  ")


def test_consumer_inbox_tracks_processed_events_independently_per_consumer() -> None:
    inbox = ConsumerEventInbox()
    assert inbox.already_processed(consumer_id="consumer.a", event_id="evt_001") is False
    inbox.mark_processed(consumer_id="consumer.a", event_id="evt_001")
    assert inbox.already_processed(consumer_id="consumer.a", event_id="evt_001") is True
    assert inbox.already_processed(consumer_id="consumer.b", event_id="evt_001") is False


@pytest.mark.asyncio
async def test_bus_dispatches_published_events_to_subscribers() -> None:
    bus = InMemoryDomainEventBus()
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    bus.subscribe("WorkflowRunStarted", handler)
    envelope = _envelope()
    await bus.publish(envelope)

    assert received == [envelope]
    assert bus.published == [envelope]


@pytest.mark.asyncio
async def test_bus_does_not_dispatch_to_subscribers_of_a_different_event_type() -> None:
    bus = InMemoryDomainEventBus()
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    bus.subscribe("WorkflowRunCompleted", handler)
    await bus.publish(_envelope(event_type="WorkflowRunStarted"))

    assert received == []


def test_bus_subscribe_rejects_invalid_event_type_name() -> None:
    bus = InMemoryDomainEventBus()

    async def handler(envelope: EventEnvelope) -> None:
        del envelope

    with pytest.raises(ValueError, match="PastTenseOutcome"):
        bus.subscribe("workflow.run.started", handler)
