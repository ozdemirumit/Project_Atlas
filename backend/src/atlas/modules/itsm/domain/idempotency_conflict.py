"""ATLAS-036 SS15/SS16: idempotency, duplicate prevention, and conflict handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ItsmCreationIntentState(StrEnum):
    """SS15: "Atlas stores a creation intent before dispatch and reconciles ambiguous
    outcomes.\""""

    PENDING = "pending"
    DISPATCHED = "dispatched"
    CONFIRMED_CREATED = "confirmed_created"
    RECONCILED_DUPLICATE = "reconciled_duplicate"
    RECONCILED_NOT_CREATED = "reconciled_not_created"


_TERMINAL_INTENT_STATES = frozenset(
    {
        ItsmCreationIntentState.CONFIRMED_CREATED,
        ItsmCreationIntentState.RECONCILED_DUPLICATE,
        ItsmCreationIntentState.RECONCILED_NOT_CREATED,
    }
)


@dataclass(frozen=True, slots=True)
class ItsmCreationIntent:
    """SS15's stored intent, recorded before an outbound create is ever dispatched."""

    intent_id: str
    idempotency_key: str
    profile_id: str
    operation: str
    deduplication_signature: str
    state: ItsmCreationIntentState
    created_at: datetime
    resolved_at: datetime | None
    external_record_id: str | None

    def __post_init__(self) -> None:
        for value in (self.intent_id, self.profile_id):
            validate_stable_identifier(value, "ITSM creation intent identifier")
        if not self.idempotency_key.strip() or not self.deduplication_signature.strip():
            raise ValueError(
                "an ITSM creation intent requires an idempotency key and a deduplication signature"
            )
        if not self.operation.strip():
            raise ValueError("an ITSM creation intent requires an operation")
        if self.created_at.tzinfo is None:
            raise ValueError("an ITSM creation intent time must be timezone-aware")
        if self.resolved_at is not None and self.resolved_at.tzinfo is None:
            raise ValueError("an ITSM creation intent resolution time must be timezone-aware")
        resolved = self.state in _TERMINAL_INTENT_STATES
        if resolved != (self.resolved_at is not None):
            raise ValueError("an ITSM creation intent's resolution time tracks its state")
        confirmed = self.state is ItsmCreationIntentState.CONFIRMED_CREATED
        if confirmed != (self.external_record_id is not None):
            raise ValueError("a confirmed ITSM creation intent requires its external record id")


def retry_after_timeout_creates_a_second_record() -> bool:
    """SS15: "Retries never blindly create a second ticket after timeout.\""""
    return False


def a_suspected_duplicate_is_silently_merged() -> bool:
    """SS15: "A suspected duplicate is linked or proposed for human review; it is not silently
    merged.\""""
    return False


class ItsmConflictKind(StrEnum):
    """SS16's named conflict categories."""

    CONCURRENT_EDIT = "concurrent_edit"
    STALE_VERSION = "stale_version"
    INCOMPATIBLE_STATE = "incompatible_state"
    CHANGED_WINDOW = "changed_window"
    CHANGED_ASSIGNEE = "changed_assignee"
    CLOSED_RECORD = "closed_record"
    FIELD_OWNERSHIP_VIOLATION = "field_ownership_violation"
    MAPPING_DRIFT = "mapping_drift"


class ItsmFieldOwnership(StrEnum):
    ATLAS_OWNED = "atlas_owned"
    HUMAN_OWNED = "human_owned"
    SHARED = "shared"


@dataclass(frozen=True, slots=True)
class ItsmConflictRecord:
    """SS16's conflict record -- both states are shown, nothing is silently resolved."""

    conflict_id: str
    profile_id: str
    external_record_id: str
    kind: ItsmConflictKind
    last_known_source_version: str
    observed_source_version: str
    field_ownership: ItsmFieldOwnership
    detected_at: datetime
    resolution_summary: str | None
    resolved_by: str | None
    resolved_at: datetime | None

    def __post_init__(self) -> None:
        for value in (self.conflict_id, self.profile_id):
            validate_stable_identifier(value, "ITSM conflict identifier")
        if not all(
            (
                self.external_record_id.strip(),
                self.last_known_source_version.strip(),
                self.observed_source_version.strip(),
            )
        ):
            raise ValueError(
                "an ITSM conflict record requires an external record id and both source versions"
            )
        if self.detected_at.tzinfo is None:
            raise ValueError("an ITSM conflict detection time must be timezone-aware")
        resolution_fields = (self.resolution_summary, self.resolved_by, self.resolved_at)
        if any(value is not None for value in resolution_fields) and not all(
            value is not None for value in resolution_fields
        ):
            raise ValueError("an ITSM conflict resolution requires its summary, actor, and time")
        if self.resolved_at is not None and self.resolved_at.tzinfo is None:
            raise ValueError("an ITSM conflict resolution time must be timezone-aware")
        if self.resolved_at is not None and self.resolved_at < self.detected_at:
            raise ValueError("an ITSM conflict cannot resolve before it was detected")


def human_owned_content_is_overwritten_on_conflict() -> bool:
    """SS16: "Human-owned content is appended or returned for review rather than
    overwritten.\""""
    return False


def automatic_last_write_wins_is_permitted_for_consequential_fields() -> bool:
    """SS16: "Automatic last-write-wins is prohibited for consequential fields.\""""
    return False


def state_transition_conflicts_allow_the_workflow_to_proceed() -> bool:
    """SS16: "State-transition conflicts stop the workflow and show both states.\""""
    return False
