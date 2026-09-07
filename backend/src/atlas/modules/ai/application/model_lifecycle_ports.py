from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.model_lifecycle import ModelLifecycleStage, ModelVersionChangeRecord


class ModelLifecycleRepository(Protocol):
    async def get_stage(self, model_id: str) -> ModelLifecycleStage | None: ...

    async def save_stage(self, model_id: str, stage: ModelLifecycleStage) -> None: ...

    async def save_change_record(self, record: ModelVersionChangeRecord) -> None: ...
