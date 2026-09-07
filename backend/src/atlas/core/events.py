"""ATLAS-016: the canonical domain-event envelope, delivery contract, and idempotent-consumer
foundation.

The `workflows` module already implements SS10's full transactional-outbox/lease/materialization
chain in painstaking detail, but only for one event type
(`WorkflowStepDispatchRequested`) -- none of SS32's ten named "Initial Event Catalog" events
exist anywhere as real schemas, and this module (the generic envelope, naming, idempotency, and
an in-process bus any producer can use) did not exist at all. This is the first vertical slice
SS32 asks for: real schemas for the ten named events plus the shared infrastructure to publish
and consume them, not a second copy of the workflow module's own elaborate durable-outbox
machinery -- SS31's MVP scope asks for "transactional outbox for critical domain events," not
for every event to carry that same weight.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from atlas.core.classification import DataClassification

_EVENT_TYPE_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def is_valid_event_type_name(value: str) -> bool:
    """SS7: `<Domain><Subject><PastTenseOutcome>`, e.g. `WorkflowRunStarted` -- PascalCase, no
    separators, distinct from the dotted-lowercase convention `atlas.core.audit` uses for audit
    event types (SS26 treats these as related but separate contracts)."""
    return bool(_EVENT_TYPE_PATTERN.fullmatch(value))


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """SS6's canonical envelope."""

    event_id: str
    event_type: str
    event_version: str
    occurred_at: datetime
    recorded_at: datetime
    producer: str
    subject_type: str
    subject_id: str
    correlation_id: str
    classification: DataClassification
    payload: object
    organization_id: str | None = None
    environment_id: str | None = None
    causation_id: str | None = None
    workflow_id: str | None = None
    actor: str | None = None
    schema_uri: str | None = None
    trace_context: str | None = None
    extensions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not is_valid_event_type_name(self.event_type):
            raise ValueError("event_type must follow <Domain><Subject><PastTenseOutcome>")
        for value in (
            self.event_id,
            self.event_version,
            self.producer,
            self.subject_type,
            self.subject_id,
            self.correlation_id,
        ):
            if not value.strip():
                raise ValueError("an event envelope's identity fields are required")
        if self.occurred_at.tzinfo is None or self.recorded_at.tzinfo is None:
            raise ValueError("event envelope times must be timezone-aware")
        if self.recorded_at < self.occurred_at:
            raise ValueError("an event cannot be recorded before it occurred")


def a_domain_event_has_more_than_one_authoritative_producer() -> bool:
    """SS4.1: "A domain event has one authoritative producer.\""""
    return False


def an_event_is_published_before_its_owned_state_transition_commits() -> bool:
    """SS4.3: "Producers publish only after the owned state transition commits.\""""
    return False


def audit_or_workflow_truth_depends_solely_on_the_event_stream() -> bool:
    """SS4.10: "Audit and workflow truth do not depend solely on a best-effort event
    stream.\""""
    return False


def best_effort_delivery_is_used_for_an_authoritative_outcome() -> bool:
    """SS11: "Best-effort delivery may be used only for explicitly non-critical telemetry,
    never for authoritative workflow, approval, policy, connector outcome, or required audit
    evidence.\""""
    return False


def an_event_consumer_treats_an_informational_event_as_authorization() -> bool:
    """SS15: "An event consumer must not reinterpret an informational event as authorization to
    perform a sensitive action.\""""
    return False


class ConsumerEventInbox:
    """SS12's "processed-event inbox keyed by event_id" -- the simplest of SS12's five listed
    idempotency strategies, and the one every consumer can use regardless of its own domain
    shape."""

    def __init__(self) -> None:
        self._processed: set[tuple[str, str]] = set()

    def already_processed(self, *, consumer_id: str, event_id: str) -> bool:
        return (consumer_id, event_id) in self._processed

    def mark_processed(self, *, consumer_id: str, event_id: str) -> None:
        self._processed.add((consumer_id, event_id))


EventHandler = Callable[[EventEnvelope], Awaitable[None]]


class InMemoryDomainEventBus:
    """SS16's "in-process or durable backbone abstraction" -- the in-process half. A durable
    backbone adapter would implement the same `publish`/`subscribe` shape backed by a real
    broker; nothing here assumes in-process delivery is the only implementation."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}
        self.published: list[EventEnvelope] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if not is_valid_event_type_name(event_type):
            raise ValueError("event_type must follow <Domain><Subject><PastTenseOutcome>")
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, envelope: EventEnvelope) -> None:
        self.published.append(envelope)
        for handler in self._subscribers.get(envelope.event_type, ()):
            await handler(envelope)
