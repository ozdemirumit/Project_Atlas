from __future__ import annotations

from typing import Protocol

from atlas.modules.recommendations.domain.models import RecommendationArtifact


class RecommendationProvider(Protocol):
    async def get_recommendation(
        self,
        recommendation_id: str,
        version: int,
        target_id: str,
    ) -> RecommendationArtifact: ...
