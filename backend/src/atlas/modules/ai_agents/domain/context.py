"""ATLAS-040 SS13: context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import validate_stable_identifier


class ContextSourceKind(StrEnum):
    """SS13's seven context source kinds."""

    USER_REQUEST_AND_CONVERSATION_STATE = "user_request_and_conversation_state"
    TASK_CONTRACT = "task_contract"
    GRAPH_ENTITIES_AND_RELATIONSHIPS = "graph_entities_and_relationships"
    HEALTH_AND_CONNECTOR_OBSERVATIONS = "health_and_connector_observations"
    KNOWLEDGE_EXCERPTS_WITH_CITATIONS = "knowledge_excerpts_with_citations"
    WORKFLOW_DECISION_POLICY_OR_APPROVAL_REFERENCE = (
        "workflow_decision_policy_or_approval_reference"
    )
    PRIOR_AGENT_ARTIFACT = "prior_agent_artifact"


class ContextItemLabel(StrEnum):
    """SS13: "stale, conflicting, untrusted, or generated content is labeled." `NONE` is content
    needing no such label."""

    NONE = "none"
    STALE = "stale"
    CONFLICTING = "conflicting"
    UNTRUSTED = "untrusted"
    GENERATED = "generated"


@dataclass(frozen=True, slots=True)
class ContextItem:
    """SS13: "context records source, version, observation time, classification, and
    authorization.\""""

    item_id: str
    source_kind: ContextSourceKind
    source_reference: str
    version: str
    observed_at: datetime
    classification: DataClassification
    authorized_principals: frozenset[str]
    labels: tuple[ContextItemLabel, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.item_id, "item_id")
        if not self.source_reference.strip():
            raise ValueError("a context item requires a source reference")
        if not self.version.strip():
            raise ValueError("a context item requires a version")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.authorized_principals:
            raise ValueError("a context item requires an access policy")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("a context item must not repeat a label")
        if len(self.labels) > 1 and ContextItemLabel.NONE in self.labels:
            raise ValueError("NONE cannot be combined with other labels")


def is_authorized_for(item: ContextItem, *, principal: str) -> bool:
    return principal in item.authorized_principals


@dataclass(frozen=True, slots=True)
class AssembledContext:
    task_id: str
    items: tuple[ContextItem, ...]
    assembled_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.task_id, "task_id")
        if not self.items:
            raise ValueError("an assembled context requires at least one item")
        if self.assembled_at.tzinfo is None:
            raise ValueError("assembled_at must be timezone-aware")

    @property
    def flagged_items(self) -> tuple[ContextItem, ...]:
        """Items carrying a real label -- stale, conflicting, untrusted, or generated content a
        consumer must weigh explicitly rather than treat as plain fact."""
        return tuple(item for item in self.items if item.labels != (ContextItemLabel.NONE,))
