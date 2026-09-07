from __future__ import annotations

import asyncio

from atlas.modules.ai.domain.model_lifecycle import ModelLifecycleStage, ModelVersionChangeRecord


class InMemoryModelLifecycleRepository:
    def __init__(self) -> None:
        self._stages: dict[str, ModelLifecycleStage] = {}
        self._change_records: list[ModelVersionChangeRecord] = []
        self._lock = asyncio.Lock()

    async def get_stage(self, model_id: str) -> ModelLifecycleStage | None:
        async with self._lock:
            return self._stages.get(model_id)

    async def save_stage(self, model_id: str, stage: ModelLifecycleStage) -> None:
        async with self._lock:
            self._stages[model_id] = stage

    async def save_change_record(self, record: ModelVersionChangeRecord) -> None:
        async with self._lock:
            self._change_records.append(record)
