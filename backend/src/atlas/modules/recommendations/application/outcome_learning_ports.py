from __future__ import annotations

from typing import Protocol

from atlas.modules.recommendations.domain.outcome_learning import RecommendationOutcomeRecord


class RecommendationOutcomeRepository(Protocol):
    async def create(self, record: RecommendationOutcomeRecord) -> bool:
        """Returns False if an outcome already exists for `record.recommendation_id`."""
        ...

    async def get(self, recommendation_id: str) -> RecommendationOutcomeRecord | None: ...
