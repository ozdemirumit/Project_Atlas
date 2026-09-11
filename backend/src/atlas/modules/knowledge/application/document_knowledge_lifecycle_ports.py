from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from atlas.modules.knowledge.application.document_knowledge_ports import (
    DocumentKnowledgeError,
    DocumentKnowledgePermissionAuthorizer,
)
from atlas.modules.knowledge.domain.document_knowledge_lifecycle import (
    DocumentKnowledgeConflict,
    DocumentKnowledgeItemLifecycleRecord,
)

__all__ = [
    "DocumentKnowledgeError",
    "DocumentKnowledgeLifecycleReader",
    "DocumentKnowledgeLifecycleRepository",
    "DocumentKnowledgePermissionAuthorizer",
]


class DocumentKnowledgeLifecycleReader(Protocol):
    """Read-only view onto lifecycle state, used only to filter retrieval results at the one
    point they would otherwise reach a caller (SS13). Deliberately narrower than
    ``DocumentKnowledgeLifecycleRepository`` below -- retrieval never writes lifecycle state, and
    keeping the port narrow means ``document_retrieval.py`` never gains write access it has no
    use for. Any object satisfying the richer repository Protocol below also satisfies this one
    structurally (both are ``Protocol``s; no inheritance required).
    """

    async def get_active_states(
        self,
        *,
        knowledge_item_ids: Sequence[str],
        organization_id: str,
        environment_id: str,
    ) -> frozenset[str]:
        """Returns the subset of ``knowledge_item_ids`` whose current lifecycle state is
        ``ACTIVE`` -- either from an explicit ``ACTIVE`` record, or (the overwhelming common
        case) because no record exists at all, which defaults to ``ACTIVE``. Every id NOT in the
        returned set is suspended, superseded, or retired and must not reach a caller."""
        ...


class DocumentKnowledgeLifecycleRepository(DocumentKnowledgeLifecycleReader, Protocol):
    async def get_lifecycle(
        self, *, knowledge_item_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeItemLifecycleRecord | None: ...

    async def put_lifecycle(
        self,
        *,
        expected: DocumentKnowledgeItemLifecycleRecord | None,
        replacement: DocumentKnowledgeItemLifecycleRecord,
    ) -> bool:
        """Compare-and-swap write of the one current-state row for
        ``replacement.knowledge_item_id``. ``expected`` is the record the caller last read (or
        ``None`` if no record existed yet, i.e. the item was implicitly ``ACTIVE``); the write
        succeeds only if the row still matches ``expected`` at write time, mirroring
        ``OperationResourceRepository.update``'s optimistic-concurrency shape."""
        ...

    async def add_conflict(self, conflict: DocumentKnowledgeConflict) -> bool: ...

    async def get_conflict(
        self, *, conflict_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeConflict | None: ...

    async def update_conflict(
        self,
        *,
        expected: DocumentKnowledgeConflict,
        replacement: DocumentKnowledgeConflict,
    ) -> bool: ...

    async def list_conflicts_for_item(
        self, *, knowledge_item_id: str, organization_id: str, environment_id: str
    ) -> tuple[DocumentKnowledgeConflict, ...]: ...

    async def close(self) -> None: ...
