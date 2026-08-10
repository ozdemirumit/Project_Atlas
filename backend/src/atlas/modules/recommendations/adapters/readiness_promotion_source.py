from __future__ import annotations

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.application.correction_resubmission import (
    RecommendationCorrectionService,
)
from atlas.modules.recommendations.application.correction_resubmission_ports import (
    RecommendationCorrectionError,
)
from atlas.modules.recommendations.application.promotion_ports import RecommendationPromotionError
from atlas.modules.recommendations.application.readiness_ports import (
    RecommendationReadinessPromotionSource,
)
from atlas.modules.recommendations.domain.promotion import (
    PromotedRecommendationArtifact,
    RecommendationPromotionResult,
)


class RecommendationReadinessPromotionSourceRouter:
    def __init__(self, *, primary: RecommendationReadinessPromotionSource) -> None:
        self._primary = primary
        self._correction: RecommendationCorrectionService | None = None

    def register_correction_source(self, source: RecommendationCorrectionService) -> None:
        if self._correction is not None and self._correction is not source:
            raise RuntimeError("recommendation correction source already registered")
        self._correction = source

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationPromotionResult:
        if recommendation_id.startswith("recommendation.corrected-"):
            if self._correction is None:
                raise RecommendationPromotionError("recommendation_promotion_not_found")
            try:
                return await self._correction.get_corrected_promotion(
                    actor=actor,
                    recommendation_id=recommendation_id,
                    browser_session_id=browser_session_id,
                    correlation_id=correlation_id,
                )
            except RecommendationCorrectionError as error:
                raise RecommendationPromotionError("recommendation_promotion_not_found") from error
        return await self._primary.get(
            actor=actor,
            recommendation_id=recommendation_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )

    async def protected_content_source(
        self, *, recommendation_id: str
    ) -> PromotedRecommendationArtifact:
        if recommendation_id.startswith("recommendation.corrected-"):
            if self._correction is None:
                raise RecommendationPromotionError("recommendation_promotion_not_found")
            try:
                return await self._correction.protected_corrected_promotion(
                    recommendation_id=recommendation_id
                )
            except RecommendationCorrectionError as error:
                raise RecommendationPromotionError("recommendation_promotion_not_found") from error
        return await self._primary.protected_content_source(recommendation_id=recommendation_id)
