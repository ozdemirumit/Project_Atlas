from __future__ import annotations

from typing import Protocol

from atlas.modules.knowledge.domain.feedback import KnowledgeFeedback


class KnowledgeFeedbackRepository(Protocol):
    async def create(self, feedback: KnowledgeFeedback) -> None: ...

    async def get(self, feedback_id: str) -> KnowledgeFeedback | None: ...

    async def update(self, feedback: KnowledgeFeedback) -> None: ...

    async def list_for_item(self, item_id: str) -> tuple[KnowledgeFeedback, ...]: ...
