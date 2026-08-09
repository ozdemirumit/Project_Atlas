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
    RecommendationReviewRequestClaimModel,
    RecommendationReviewRequestRecordModel,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestClaim,
    RecommendationReviewRequestRecord,
)


class PostgreSQLRecommendationReviewRequestRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRecommendationReviewRequestRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, review_request_id: str) -> RecommendationReviewRequestRecord | None:
        async with self._sessions() as session:
            row = await session.get(RecommendationReviewRequestRecordModel, review_request_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationReviewRequestClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationReviewRequestClaimModel).where(
                    RecommendationReviewRequestClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    RecommendationReviewRequestClaimModel.idempotency_digest == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: RecommendationReviewRequestClaim) -> bool:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationReviewRequestClaimModel(
                        claim_id=claim.claim_id,
                        review_request_id=claim.review_request_id,
                        recommendation_id=claim.recommendation_id,
                        readiness_assessment_id=claim.readiness_assessment_id,
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

    async def save(self, record: RecommendationReviewRequestRecord) -> None:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationReviewRequestRecordModel(
                        review_request_id=record.review_request_id,
                        recommendation_id=record.recommendation_id,
                        readiness_assessment_id=record.readiness_assessment_id,
                        promotion_id=record.promotion_id,
                        claim_id=record.claim_id,
                        requester_subject_digest=record.requester_subject_digest,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        state=record.state,
                        expires_at=record.expires_at,
                        canonical_digest=record.canonical_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
        except IntegrityError as error:
            raise RuntimeError("recommendation_review_request_already_exists") from error

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> RecommendationReviewRequestClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return RecommendationReviewRequestClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> RecommendationReviewRequestRecord:
        payload = dict(raw)
        for field in ("requested_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        for field in ("track_codes", "queue_ids"):
            payload[field] = tuple(cast(list[str], payload[field]))
        payload["track_statuses"] = tuple(
            (item[0], item[1]) for item in cast(list[list[str]], payload["track_statuses"])
        )
        return RecommendationReviewRequestRecord(**cast(Any, payload))
