"""Lifecycle and conflict tracking for the document-sourced knowledge pipeline.

docs/027_Knowledge_Engine.md SS8 (lifecycle transitions) and SS21 (Conflict and Supersession,
MVP-included) closed against the real, HTTP-reachable ``document_knowledge.py`` /
``document_retrieval.py`` chain -- not the older, synthetic-only ``knowledge/domain/models.py``
``KnowledgeLifecycle`` enum, which remains its own explicit, already-recorded deferral (its
retriever is ``SyntheticOperationalKnowledgeTrustedRetriever``; no real source exists for that
chain yet). That chain has no dedicated per-item entity at all: ``knowledge_item_id`` is only ever
a scattered foreign-key-style field on draft/review/approval/preparation/vector-chunk records, so
nothing in the real pipeline could express "this published item is now suspended" before this
module existed.

SS8 names exactly two transition paths: "Published -> Suspended -> Published" (a real item can be
suspended and later resumed -- ``ACTIVE`` and ``SUSPENDED`` are mutually reachable) and
"Published -> Superseded -> Retired" (one-directional: once an item is superseded by a real
replacement, its only further transition is to ``RETIRED``, which is terminal). "Published" in the
source document is this module's ``ACTIVE`` -- the overwhelming majority of document-sourced
knowledge items are published and never touched again, so ``ACTIVE`` is the implicit default for
any item with no recorded transition at all (see
``DocumentKnowledgeLifecycleService.get_lifecycle``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_MAX_REASON_CHARACTERS = 2000


class DocumentKnowledgeItemLifecycleState(StrEnum):
    """docs/027_Knowledge_Engine.md SS8. ``ACTIVE`` is "Published" under this module's own
    vocabulary -- see the module docstring for why the source document's term is not reused
    verbatim here."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class DocumentKnowledgeConflictType(StrEnum):
    """docs/027_Knowledge_Engine.md SS21. Four real, distinguishable shapes a knowledge conflict
    between two document-sourced items can take -- deliberately not one generic ``CONFLICT``
    value, since the resolver's real remedy differs by shape (e.g. contradictory guidance usually
    needs one item superseded; duplicate coverage usually needs one item retired without
    supersession; a version mismatch usually needs a content update, not a lifecycle change at
    all)."""

    CONTRADICTORY_GUIDANCE = "contradictory_guidance"
    DUPLICATE_COVERAGE = "duplicate_coverage"
    VERSION_MISMATCH = "version_mismatch"
    SCOPE_OVERLAP = "scope_overlap"


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeItemLifecycleRecord:
    """The current lifecycle state of one document-sourced knowledge item.

    One row per ``(knowledge_item_id, organization_id, environment_id)`` -- a mutable
    "current state" record, not an append-only chain like ``DocumentKnowledgeDraft`` /
    ``DocumentKnowledgeReviewDecision`` / ... / ``DocumentKnowledgePublicationPreparation``: SS8
    describes ongoing transitions of an already-published item, not a one-way approval pipeline,
    so there is exactly one row of *current* truth per item rather than an ever-growing chain.

    This dataclass enforces everything a single record can check about itself in isolation:
    identifiers, a real non-empty bounded reason, timezone-aware ordered timestamps, and that
    ``superseded_by_item_id`` is set if and only if ``state`` is ``SUPERSEDED``. It cannot know the
    *prior* state -- whether ``RETIRED`` is really only reached from ``SUPERSEDED``, or whether
    ``SUSPENDED``/``ACTIVE`` are really only reached from each other -- because that requires
    comparing against the previously-persisted record, which is a real state-machine invariant
    enforced by ``DocumentKnowledgeLifecycleService`` against the repository, not by this
    dataclass in isolation.
    """

    knowledge_item_id: str
    organization_id: str
    environment_id: str
    state: DocumentKnowledgeItemLifecycleState
    reason: str
    updated_by: str
    updated_at: datetime
    created_at: datetime
    superseded_by_item_id: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.knowledge_item_id, "knowledge item identifier")
        validate_stable_identifier(self.organization_id, "organization identifier")
        validate_stable_identifier(self.environment_id, "environment identifier")
        validate_stable_identifier(self.updated_by, "updated-by subject identifier")
        if not 1 <= len(self.reason.strip()) <= _MAX_REASON_CHARACTERS:
            raise ValueError("a lifecycle transition requires a real, bounded reason")
        is_superseded = self.state is DocumentKnowledgeItemLifecycleState.SUPERSEDED
        if (self.superseded_by_item_id is not None) != is_superseded:
            raise ValueError("superseded_by_item_id must be set if and only if state is SUPERSEDED")
        if self.superseded_by_item_id is not None:
            validate_stable_identifier(
                self.superseded_by_item_id, "superseding knowledge item identifier"
            )
            if self.superseded_by_item_id == self.knowledge_item_id:
                raise ValueError("an item cannot be superseded by itself")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("lifecycle record timestamps must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("a lifecycle record cannot be updated before it was created")


def canonical_conflict_pair(item_a: str, item_b: str) -> tuple[str, str]:
    """Lexicographic ordering so ``(A, B)`` and ``(B, A)`` are always the same recorded pair.

    A conflict between two items is inherently symmetric -- docs/027 SS21 never distinguishes a
    "first" and "second" item in a conflicting pair -- so without a canonical order, two callers
    who independently discover the same real conflict (e.g. one indexing item A then finding B
    conflicts with it, another indexing B then finding A conflicts with it) could each record it
    under a different id ordering, producing two rows for one real conflict. Chosen over e.g.
    ordering by detection time because it is a pure function of the two ids alone: any caller
    computes the same canonical order without needing to know who else has already looked. Public
    (not module-private) because ``DocumentKnowledgeLifecycleService.record_conflict`` must apply
    the exact same ordering before constructing a ``DocumentKnowledgeConflict``, which requires
    its two item ids to already be in canonical order -- see ``__post_init__`` below.
    """
    return (item_a, item_b) if item_a < item_b else (item_b, item_a)


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeConflict:
    """A detected conflict between two document-sourced knowledge items.

    docs/027_Knowledge_Engine.md SS21, "Conflict and Supersession" -- MVP-included, not excluded.
    Append-only: once detected, a conflict record is never deleted, only ever resolved in place
    (``resolution``/``resolved_by``/``resolved_at``), mirroring this codebase's established
    append-only-with-in-place-resolution pattern for governance records.

    ``knowledge_item_id_a``/``knowledge_item_id_b`` are always stored in canonical (lexicographic)
    order -- see ``canonical_conflict_pair`` -- so the same real pair of items can never be
    recorded as two distinct conflicts differing only in argument order.
    """

    conflict_id: str
    organization_id: str
    environment_id: str
    knowledge_item_id_a: str
    knowledge_item_id_b: str
    conflict_type: DocumentKnowledgeConflictType
    detected_by: str
    detected_at: datetime
    resolution: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.conflict_id, "conflict identifier")
        validate_stable_identifier(self.organization_id, "organization identifier")
        validate_stable_identifier(self.environment_id, "environment identifier")
        validate_stable_identifier(self.knowledge_item_id_a, "knowledge item identifier")
        validate_stable_identifier(self.knowledge_item_id_b, "knowledge item identifier")
        validate_stable_identifier(self.detected_by, "detected-by subject identifier")
        if self.knowledge_item_id_a == self.knowledge_item_id_b:
            raise ValueError("a conflict requires two distinct knowledge items")
        if canonical_conflict_pair(self.knowledge_item_id_a, self.knowledge_item_id_b) != (
            self.knowledge_item_id_a,
            self.knowledge_item_id_b,
        ):
            raise ValueError(
                "knowledge_item_id_a/knowledge_item_id_b must already be in canonical "
                "(lexicographic) order"
            )
        if self.detected_at.tzinfo is None:
            raise ValueError("conflict detection time must be timezone-aware")
        resolution_fields = (self.resolution, self.resolved_by, self.resolved_at)
        some_set = any(field is not None for field in resolution_fields)
        all_set = all(field is not None for field in resolution_fields)
        if some_set and not all_set:
            raise ValueError(
                "resolution, resolved_by, and resolved_at must travel together (all-or-nothing)"
            )
        if self.resolution is not None and self.resolved_by is not None:
            if not self.resolution.strip():
                raise ValueError("a stated resolution cannot be blank")
            validate_stable_identifier(self.resolved_by, "resolved-by subject identifier")
            if self.resolved_at is None or self.resolved_at.tzinfo is None:
                raise ValueError("conflict resolution time must be timezone-aware")
            if self.resolved_at < self.detected_at:
                raise ValueError("a conflict cannot be resolved before it was detected")

    @property
    def is_resolved(self) -> bool:
        return self.resolution is not None


__all__ = [
    "DocumentKnowledgeConflict",
    "DocumentKnowledgeConflictType",
    "DocumentKnowledgeItemLifecycleRecord",
    "DocumentKnowledgeItemLifecycleState",
    "canonical_conflict_pair",
]
