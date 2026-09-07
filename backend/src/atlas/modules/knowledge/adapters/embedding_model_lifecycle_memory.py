from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.embedding_model_lifecycle import EmbeddingModelLifecycleStage


class InMemoryEmbeddingModelLifecycleRepository:
    def __init__(self) -> None:
        self._stages: dict[str, EmbeddingModelLifecycleStage] = {}
        self._lock = asyncio.Lock()

    async def get_stage(self, model_id: str) -> EmbeddingModelLifecycleStage | None:
        async with self._lock:
            return self._stages.get(model_id)

    async def save_stage(self, model_id: str, stage: EmbeddingModelLifecycleStage) -> None:
        async with self._lock:
            self._stages[model_id] = stage
