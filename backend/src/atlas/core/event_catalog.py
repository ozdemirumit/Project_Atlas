"""ATLAS-016 SS32: the Initial Event Catalog -- schemas for the ten named events, each with one
authoritative owning component (SS9).

"The catalog expands only with named owners and consumers" (SS32's own closing line): every
entry below names its owner explicitly rather than leaving it implicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EventOwner(StrEnum):
    """SS9: "Each event type has one authoritative owning component.\""""

    WORKFLOWS = "workflows"
    CONNECTORS = "connectors"
    KNOWLEDGE = "knowledge"
    APPROVALS = "approvals"
    AI = "ai"


def _require(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class WorkflowRunStarted:
    workflow_run_id: str
    definition_id: str
    definition_version: int
    triggered_by: str
    started_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.workflow_run_id, "workflow_run_id"),
            (self.definition_id, "definition_id"),
            (self.triggered_by, "triggered_by"),
        ):
            _require(value, name)
        _require_aware(self.started_at, "started_at")
        if self.definition_version < 1:
            raise ValueError("definition_version must be positive")


@dataclass(frozen=True, slots=True)
class WorkflowRunCompleted:
    workflow_run_id: str
    definition_id: str
    completed_at: datetime
    outcome_summary: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.workflow_run_id, "workflow_run_id"),
            (self.definition_id, "definition_id"),
            (self.outcome_summary, "outcome_summary"),
        ):
            _require(value, name)
        _require_aware(self.completed_at, "completed_at")


@dataclass(frozen=True, slots=True)
class WorkflowRunFailed:
    workflow_run_id: str
    definition_id: str
    failed_at: datetime
    failure_reason: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.workflow_run_id, "workflow_run_id"),
            (self.definition_id, "definition_id"),
            (self.failure_reason, "failure_reason"),
        ):
            _require(value, name)
        _require_aware(self.failed_at, "failed_at")


@dataclass(frozen=True, slots=True)
class ConnectorCapabilityStarted:
    connector_id: str
    instance_id: str
    capability_id: str
    capability_class: str
    started_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.connector_id, "connector_id"),
            (self.instance_id, "instance_id"),
            (self.capability_id, "capability_id"),
            (self.capability_class, "capability_class"),
        ):
            _require(value, name)
        _require_aware(self.started_at, "started_at")


@dataclass(frozen=True, slots=True)
class ConnectorCapabilityCompleted:
    connector_id: str
    instance_id: str
    capability_id: str
    completed_at: datetime
    result_code: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.connector_id, "connector_id"),
            (self.instance_id, "instance_id"),
            (self.capability_id, "capability_id"),
            (self.result_code, "result_code"),
        ):
            _require(value, name)
        _require_aware(self.completed_at, "completed_at")


@dataclass(frozen=True, slots=True)
class ConnectorCapabilityFailed:
    connector_id: str
    instance_id: str
    capability_id: str
    failed_at: datetime
    failure_reason: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.connector_id, "connector_id"),
            (self.instance_id, "instance_id"),
            (self.capability_id, "capability_id"),
            (self.failure_reason, "failure_reason"),
        ):
            _require(value, name)
        _require_aware(self.failed_at, "failed_at")


@dataclass(frozen=True, slots=True)
class KnowledgeItemPublished:
    item_id: str
    source_draft_id: str
    version: int
    published_at: datetime
    published_by: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.item_id, "item_id"),
            (self.source_draft_id, "source_draft_id"),
            (self.published_by, "published_by"),
        ):
            _require(value, name)
        _require_aware(self.published_at, "published_at")
        if self.version < 1:
            raise ValueError("version must be positive")


@dataclass(frozen=True, slots=True)
class ApprovalRequestCreated:
    request_id: str
    packet_version: int
    requested_by: str
    created_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.request_id, "request_id"),
            (self.requested_by, "requested_by"),
        ):
            _require(value, name)
        _require_aware(self.created_at, "created_at")
        if self.packet_version < 1:
            raise ValueError("packet_version must be positive")


@dataclass(frozen=True, slots=True)
class ApprovalGranted:
    request_id: str
    decision_id: str
    reviewer_id: str
    granted_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.request_id, "request_id"),
            (self.decision_id, "decision_id"),
            (self.reviewer_id, "reviewer_id"),
        ):
            _require(value, name)
        _require_aware(self.granted_at, "granted_at")


@dataclass(frozen=True, slots=True)
class AIRecommendationGenerated:
    recommendation_id: str
    source_case_id: str
    version: int
    generated_at: datetime
    option_count: int

    def __post_init__(self) -> None:
        for value, name in (
            (self.recommendation_id, "recommendation_id"),
            (self.source_case_id, "source_case_id"),
        ):
            _require(value, name)
        _require_aware(self.generated_at, "generated_at")
        if self.version < 1:
            raise ValueError("version must be positive")
        if self.option_count < 0:
            raise ValueError("option_count cannot be negative")


@dataclass(frozen=True, slots=True)
class EventCatalogEntry:
    event_type: str
    owner: EventOwner
    description: str
    payload_type: type


DOMAIN_EVENT_CATALOG: tuple[EventCatalogEntry, ...] = (
    EventCatalogEntry(
        event_type="WorkflowRunStarted",
        owner=EventOwner.WORKFLOWS,
        description="A workflow run began executing its definition.",
        payload_type=WorkflowRunStarted,
    ),
    EventCatalogEntry(
        event_type="WorkflowRunCompleted",
        owner=EventOwner.WORKFLOWS,
        description="A workflow run reached a successful terminal state.",
        payload_type=WorkflowRunCompleted,
    ),
    EventCatalogEntry(
        event_type="WorkflowRunFailed",
        owner=EventOwner.WORKFLOWS,
        description="A workflow run reached a failed terminal state.",
        payload_type=WorkflowRunFailed,
    ),
    EventCatalogEntry(
        event_type="ConnectorCapabilityStarted",
        owner=EventOwner.CONNECTORS,
        description="A connector capability invocation began.",
        payload_type=ConnectorCapabilityStarted,
    ),
    EventCatalogEntry(
        event_type="ConnectorCapabilityCompleted",
        owner=EventOwner.CONNECTORS,
        description="A connector capability invocation completed successfully.",
        payload_type=ConnectorCapabilityCompleted,
    ),
    EventCatalogEntry(
        event_type="ConnectorCapabilityFailed",
        owner=EventOwner.CONNECTORS,
        description="A connector capability invocation failed.",
        payload_type=ConnectorCapabilityFailed,
    ),
    EventCatalogEntry(
        event_type="KnowledgeItemPublished",
        owner=EventOwner.KNOWLEDGE,
        description="A knowledge item was published to the active index.",
        payload_type=KnowledgeItemPublished,
    ),
    EventCatalogEntry(
        event_type="ApprovalRequestCreated",
        owner=EventOwner.APPROVALS,
        description="An immutable approval packet was created and submitted.",
        payload_type=ApprovalRequestCreated,
    ),
    EventCatalogEntry(
        event_type="ApprovalGranted",
        owner=EventOwner.APPROVALS,
        description="An eligible reviewer approved an approval request.",
        payload_type=ApprovalGranted,
    ),
    EventCatalogEntry(
        event_type="AIRecommendationGenerated",
        owner=EventOwner.AI,
        description="A governed recommendation artifact was generated.",
        payload_type=AIRecommendationGenerated,
    ),
)

_CATALOG_BY_TYPE: dict[str, EventCatalogEntry] = {
    entry.event_type: entry for entry in DOMAIN_EVENT_CATALOG
}


def event_catalog_entry(event_type: str) -> EventCatalogEntry:
    try:
        return _CATALOG_BY_TYPE[event_type]
    except KeyError as exc:
        raise KeyError(f"{event_type!r} is not a registered domain event type") from exc


def another_component_publishes_an_event_claiming_a_different_owners_authoritative_state() -> bool:
    """SS9: "Other components cannot publish an event that claims another component's
    authoritative state change. They may publish a separate observation or integration event in
    their own namespace.\""""
    return False
