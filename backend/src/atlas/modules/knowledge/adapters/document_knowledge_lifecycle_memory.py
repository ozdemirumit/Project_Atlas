from __future__ import annotations

import asyncio
from collections.abc import Sequence

from atlas.modules.knowledge.domain.document_knowledge_lifecycle import (
    DocumentKnowledgeConflict,
    DocumentKnowledgeItemLifecycleRecord,
    DocumentKnowledgeItemLifecycleState,
)

_LifecycleKey = tuple[str, str, str]
_ConflictKey = tuple[str, str, str]


class InMemoryDocumentKnowledgeLifecycleRepository:
    def __init__(self) -> None:
        self._lifecycles: dict[_LifecycleKey, DocumentKnowledgeItemLifecycleRecord] = {}
        self._conflicts: dict[_ConflictKey, DocumentKnowledgeConflict] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _lifecycle_key(
        knowledge_item_id: str, organization_id: str, environment_id: str
    ) -> _LifecycleKey:
        return (knowledge_item_id, organization_id, environment_id)

    @staticmethod
    def _conflict_key(conflict_id: str, organization_id: str, environment_id: str) -> _ConflictKey:
        return (conflict_id, organization_id, environment_id)

    async def get_lifecycle(
        self, *, knowledge_item_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeItemLifecycleRecord | None:
        return self._lifecycles.get(
            self._lifecycle_key(knowledge_item_id, organization_id, environment_id)
        )

    async def put_lifecycle(
        self,
        *,
        expected: DocumentKnowledgeItemLifecycleRecord | None,
        replacement: DocumentKnowledgeItemLifecycleRecord,
    ) -> bool:
        async with self._lock:
            key = self._lifecycle_key(
                replacement.knowledge_item_id,
                replacement.organization_id,
                replacement.environment_id,
            )
            if self._lifecycles.get(key) != expected:
                return False
            self._lifecycles[key] = replacement
            return True

    async def get_active_states(
        self,
        *,
        knowledge_item_ids: Sequence[str],
        organization_id: str,
        environment_id: str,
    ) -> frozenset[str]:
        active: set[str] = set()
        for item_id in set(knowledge_item_ids):
            record = self._lifecycles.get(
                self._lifecycle_key(item_id, organization_id, environment_id)
            )
            if record is None or record.state is DocumentKnowledgeItemLifecycleState.ACTIVE:
                active.add(item_id)
        return frozenset(active)

    async def add_conflict(self, conflict: DocumentKnowledgeConflict) -> bool:
        async with self._lock:
            key = self._conflict_key(
                conflict.conflict_id, conflict.organization_id, conflict.environment_id
            )
            if key in self._conflicts:
                return False
            self._conflicts[key] = conflict
            return True

    async def get_conflict(
        self, *, conflict_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeConflict | None:
        return self._conflicts.get(self._conflict_key(conflict_id, organization_id, environment_id))

    async def update_conflict(
        self,
        *,
        expected: DocumentKnowledgeConflict,
        replacement: DocumentKnowledgeConflict,
    ) -> bool:
        async with self._lock:
            key = self._conflict_key(
                expected.conflict_id, expected.organization_id, expected.environment_id
            )
            if self._conflicts.get(key) != expected:
                return False
            self._conflicts[key] = replacement
            return True

    async def list_conflicts_for_item(
        self, *, knowledge_item_id: str, organization_id: str, environment_id: str
    ) -> tuple[DocumentKnowledgeConflict, ...]:
        return tuple(
            conflict
            for conflict in self._conflicts.values()
            if conflict.organization_id == organization_id
            and conflict.environment_id == environment_id
            and knowledge_item_id in (conflict.knowledge_item_id_a, conflict.knowledge_item_id_b)
        )

    async def close(self) -> None:
        return None
