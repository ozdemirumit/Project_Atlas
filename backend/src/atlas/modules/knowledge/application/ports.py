from __future__ import annotations

from typing import Protocol

from atlas.modules.knowledge.domain.models import RetrievalRequest, RetrievalResult


class KnowledgeRetriever(Protocol):
    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...
