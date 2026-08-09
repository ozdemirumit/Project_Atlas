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
    RecommendationReadinessAssessmentModel,
    RecommendationReadinessClaimModel,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.recommendations.domain.readiness import (
    RecommendationReadinessAssessment,
    RecommendationReadinessClaim,
)


class PostgreSQLRecommendationReadinessRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRecommendationReadinessRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, assessment_id: str) -> RecommendationReadinessAssessment | None:
        async with self._sessions() as session:
            row = await session.get(RecommendationReadinessAssessmentModel, assessment_id)
            return self._assessment_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationReadinessClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationReadinessClaimModel).where(
                    RecommendationReadinessClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    RecommendationReadinessClaimModel.idempotency_digest == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: RecommendationReadinessClaim) -> bool:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationReadinessClaimModel(
                        claim_id=claim.claim_id,
                        assessment_id=claim.assessment_id,
                        recommendation_id=claim.recommendation_id,
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

    async def save(self, assessment: RecommendationReadinessAssessment) -> None:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(assessment))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationReadinessAssessmentModel(
                        assessment_id=assessment.assessment_id,
                        recommendation_id=assessment.recommendation_id,
                        promotion_id=assessment.promotion_id,
                        claim_id=assessment.claim_id,
                        consumer_subject_digest=assessment.consumer_subject_digest,
                        organization_id=assessment.organization_id,
                        environment_id=assessment.environment_id,
                        evaluation_outcome=assessment.evaluation_outcome,
                        expires_at=assessment.expires_at,
                        canonical_digest=assessment.canonical_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
        except IntegrityError as error:
            raise RuntimeError("recommendation_readiness_already_exists") from error

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> RecommendationReadinessClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return RecommendationReadinessClaim(**cast(Any, payload))

    @staticmethod
    def _assessment_to_domain(raw: dict[str, Any]) -> RecommendationReadinessAssessment:
        payload = dict(raw)
        for field in ("assessed_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        payload["reason_codes"] = tuple(cast(list[str], payload["reason_codes"]))
        return RecommendationReadinessAssessment(**cast(Any, payload))
