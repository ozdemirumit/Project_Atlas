from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.feedback import KnowledgeFeedback


class InMemoryKnowledgeFeedbackRepository:
    def __init__(self) -> None:
        self._records: dict[str, KnowledgeFeedback] = {}
        self._lock = asyncio.Lock()

    async def create(self, feedback: KnowledgeFeedback) -> None:
        async with self._lock:
            if feedback.feedback_id in self._records:
                raise ValueError("feedback identity already exists")
            self._records[feedback.feedback_id] = feedback

    async def get(self, feedback_id: str) -> KnowledgeFeedback | None:
        async with self._lock:
            return self._records.get(feedback_id)

    async def update(self, feedback: KnowledgeFeedback) -> None:
        async with self._lock:
            if feedback.feedback_id not in self._records:
                raise ValueError("feedback identity does not exist")
            self._records[feedback.feedback_id] = feedback

    async def list_for_item(self, item_id: str) -> tuple[KnowledgeFeedback, ...]:
        async with self._lock:
            return tuple(item for item in self._records.values() if item.item_id == item_id)
