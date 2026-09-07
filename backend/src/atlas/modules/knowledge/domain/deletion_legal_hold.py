"""ATLAS-027 SS24: Deletion and Legal Hold."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class LegalHold:
    """SS24: "Legal hold blocks deletion and is separately authorized.\""""

    hold_id: str
    item_id: str
    authorized_by: str
    reason: str
    placed_at: datetime
    released_at: datetime | None = None
    release_authorized_by: str | None = None

    def __post_init__(self) -> None:
        required = (self.hold_id, self.item_id, self.authorized_by, self.reason)
        if not all(value.strip() for value in required):
            raise ValueError("a legal hold requires identity, authorization, and a reason")
        if self.placed_at.tzinfo is None:
            raise ValueError("legal hold placement time must be timezone-aware")
        if (self.released_at is None) != (self.release_authorized_by is None):
            raise ValueError("releasing a legal hold requires both a time and an authorizer")
        if self.released_at is not None:
            if self.released_at.tzinfo is None:
                raise ValueError("legal hold release time must be timezone-aware")
            if self.released_at < self.placed_at:
                raise ValueError("a legal hold cannot be released before it was placed")

    def is_active_at(self, moment: datetime) -> bool:
        return self.released_at is None or moment < self.released_at


class DeletionRequestState(StrEnum):
    REQUESTED = "requested"
    BLOCKED_BY_LEGAL_HOLD = "blocked_by_legal_hold"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class DeletionRequest:
    """SS24: "Deletion follows source ownership, retention, privacy, and legal-hold policy...
    Completion is trackable and audited.\""""

    request_id: str
    item_id: str
    requested_by: str
    requested_at: datetime
    retention_policy_reference: str
    state: DeletionRequestState
    completed_at: datetime | None = None
    derived_artifacts_removed: bool = False
    tombstone_id: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.request_id,
            self.item_id,
            self.requested_by,
            self.retention_policy_reference,
        )
        if not all(value.strip() for value in required):
            raise ValueError("a deletion request requires identity and a retention policy")
        if self.requested_at.tzinfo is None:
            raise ValueError("deletion request time must be timezone-aware")
        if self.state is DeletionRequestState.COMPLETED:
            if self.completed_at is None or self.completed_at.tzinfo is None:
                raise ValueError("a completed deletion requires a timezone-aware completion time")
            if self.completed_at < self.requested_at:
                raise ValueError("a deletion cannot complete before it was requested")
            if not self.derived_artifacts_removed:
                raise ValueError(
                    "a completed deletion requires derived chunks, embeddings, and caches removed"
                )
            if not (self.tombstone_id is not None and self.tombstone_id.strip()):
                raise ValueError("a completed deletion requires its tombstone reference")
        else:
            if self.completed_at is not None:
                raise ValueError("an incomplete deletion cannot carry a completion time")
            if self.derived_artifacts_removed or self.tombstone_id is not None:
                raise ValueError("only a completed deletion carries removal or tombstone data")


@dataclass(frozen=True, slots=True)
class KnowledgeTombstone:
    """SS24: "Tombstones preserve required traceability without content where permitted." This
    record has no content field at all -- there is nothing here for a tombstone to carry beyond
    the traceability metadata itself, so "without content" is structural, not a convention to
    remember to follow."""

    tombstone_id: str
    item_id: str
    deletion_request_id: str
    deleted_at: datetime
    deleted_by: str
    reason_code: str

    def __post_init__(self) -> None:
        required = (
            self.tombstone_id,
            self.item_id,
            self.deletion_request_id,
            self.deleted_by,
            self.reason_code,
        )
        if not all(value.strip() for value in required):
            raise ValueError("a tombstone requires identity, deletion linkage, and a reason code")
        if self.deleted_at.tzinfo is None:
            raise ValueError("tombstone deletion time must be timezone-aware")


def a_deletion_completes_while_an_active_legal_hold_exists() -> bool:
    """SS24: "Legal hold blocks deletion." Enforced by
    `KnowledgeDeletionService.complete_deletion`, which refuses completion whenever
    `LegalHold.is_active_at` the current time is true for the target item."""
    return False


def a_completed_deletion_leaves_derived_chunks_embeddings_or_caches_behind() -> bool:
    """SS24: "Derived chunks, embeddings, caches, and summaries are removed or restricted."
    `DeletionRequest` makes a `COMPLETED` state without `derived_artifacts_removed=True`
    unconstructable."""
    return False


def a_knowledge_tombstone_retains_the_deleted_item_s_content() -> bool:
    """SS24: "Tombstones preserve required traceability without content where permitted."
    `KnowledgeTombstone` has no content field to retain one in."""
    return False
