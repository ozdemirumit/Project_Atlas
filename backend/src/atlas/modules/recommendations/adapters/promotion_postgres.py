from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    PromotedRecommendationArtifactModel,
    RecommendationPromotionClaimModel,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    PresentedRecommendationOption,
    PresentedRecommendationStep,
)
from atlas.modules.recommendations.domain.promotion import (
    PromotedRecommendationArtifact,
    RecommendationPromotionClaim,
)


class PostgreSQLRecommendationPromotionRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRecommendationPromotionRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, recommendation_id: str) -> PromotedRecommendationArtifact | None:
        async with self._sessions() as session:
            row = await session.get(PromotedRecommendationArtifactModel, recommendation_id)
            return self._artifact_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationPromotionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationPromotionClaimModel).where(
                    RecommendationPromotionClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    RecommendationPromotionClaimModel.idempotency_digest == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: RecommendationPromotionClaim) -> bool:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationPromotionClaimModel(
                        claim_id=claim.claim_id,
                        promotion_id=claim.promotion_id,
                        recommendation_id=claim.recommendation_id,
                        presentation_id=claim.presentation_id,
                        claimed_by_subject_digest=claim.claimed_by_subject_digest,
                        idempotency_digest=claim.idempotency_digest,
                        organization_id=claim.organization_id,
                        environment_id=claim.environment_id,
                        canonical_digest=claim.canonical_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def save(self, artifact: PromotedRecommendationArtifact) -> None:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(artifact))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    PromotedRecommendationArtifactModel(
                        recommendation_id=artifact.recommendation_id,
                        promotion_id=artifact.promotion_id,
                        claim_id=artifact.claim_id,
                        presentation_id=artifact.presentation_id,
                        consumer_subject_digest=artifact.consumer_subject_digest,
                        organization_id=artifact.organization_id,
                        environment_id=artifact.environment_id,
                        expires_at=artifact.expires_at,
                        canonical_digest=artifact.canonical_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
        except IntegrityError as error:
            raise RuntimeError("recommendation_promotion_already_exists") from error

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> RecommendationPromotionClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return RecommendationPromotionClaim(**cast(Any, payload))

    @staticmethod
    def _artifact_to_domain(raw: dict[str, Any]) -> PromotedRecommendationArtifact:
        payload = dict(raw)
        for field in ("promoted_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        options: list[PresentedRecommendationOption] = []
        for raw_option in cast(list[dict[str, Any]], payload["options"]):
            option = dict(raw_option)
            option["steps"] = tuple(
                PresentedRecommendationStep(**cast(Any, raw_step))
                for raw_step in cast(list[dict[str, Any]], option["steps"])
            )
            for field in (
                "evidence_references",
                "assumptions",
                "unknowns",
                "evidence_gaps",
                "applicability_limits",
                "support_reasons",
            ):
                option[field] = tuple(cast(list[str], option[field]))
            options.append(PresentedRecommendationOption(**cast(Any, option)))
        payload["options"] = tuple(options)
        payload["evidence_needs"] = tuple(cast(list[str], payload["evidence_needs"]))
        return PromotedRecommendationArtifact(**cast(Any, payload))
