from __future__ import annotations

from typing import Protocol

from atlas.modules.knowledge.domain.embedding_model_lifecycle import EmbeddingModelLifecycleStage


class EmbeddingModelLifecycleRepository(Protocol):
    async def get_stage(self, model_id: str) -> EmbeddingModelLifecycleStage | None: ...

    async def save_stage(self, model_id: str, stage: EmbeddingModelLifecycleStage) -> None: ...
