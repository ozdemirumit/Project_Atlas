from __future__ import annotations

import asyncio

from atlas.modules.recommendations.domain.outcome_learning import RecommendationOutcomeRecord


class InMemoryRecommendationOutcomeRepository:
    def __init__(self) -> None:
        self._records: dict[str, RecommendationOutcomeRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, record: RecommendationOutcomeRecord) -> bool:
        async with self._lock:
            if record.recommendation_id in self._records:
                return False
            self._records[record.recommendation_id] = record
            return True

    async def get(self, recommendation_id: str) -> RecommendationOutcomeRecord | None:
        async with self._lock:
            return self._records.get(recommendation_id)
