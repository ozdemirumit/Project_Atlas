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
    RecommendationCorrectionClaimModel,
    RecommendationCorrectionModel,
)
from atlas.modules.recommendations.application.correction_resubmission import (
    RecommendationCorrectionService,
)
from atlas.modules.recommendations.domain.correction_resubmission import (
    RecommendationCorrectionClaim,
    RecommendationCorrectionRecord,
)


class PostgreSQLRecommendationCorrectionRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRecommendationCorrectionRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, correction_id: str) -> RecommendationCorrectionRecord | None:
        async with self._sessions() as session:
            row = await session.get(RecommendationCorrectionModel, correction_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source_request(
        self, *, source_review_request_id: str
    ) -> RecommendationCorrectionRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationCorrectionModel).where(
                    RecommendationCorrectionModel.source_review_request_id
                    == source_review_request_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_by_new_recommendation(
        self, *, new_recommendation_id: str
    ) -> RecommendationCorrectionRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationCorrectionModel).where(
                    RecommendationCorrectionModel.new_recommendation_id == new_recommendation_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source_request(
        self, *, source_review_request_id: str
    ) -> RecommendationCorrectionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationCorrectionClaimModel).where(
                    RecommendationCorrectionClaimModel.source_review_request_id
                    == source_review_request_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationCorrectionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationCorrectionClaimModel).where(
                    RecommendationCorrectionClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    RecommendationCorrectionClaimModel.idempotency_digest == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: RecommendationCorrectionClaim) -> bool:
        payload = RecommendationCorrectionService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationCorrectionClaimModel(
                        claim_id=claim.claim_id,
                        source_review_request_id=claim.source_review_request_id,
                        correction_id=claim.correction_id,
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

    async def add(self, record: RecommendationCorrectionRecord) -> bool:
        payload = RecommendationCorrectionService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationCorrectionModel(
                        correction_id=record.correction_id,
                        claim_id=record.claim_id,
                        source_review_request_id=record.source_review_request_id,
                        source_recommendation_id=record.source_recommendation_id,
                        new_recommendation_id=record.new_recommendation_id,
                        new_promotion_id=record.new_promotion_id,
                        corrected_by_subject_digest=record.corrected_by_subject_digest,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        canonical_digest=record.canonical_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> RecommendationCorrectionClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return RecommendationCorrectionClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> RecommendationCorrectionRecord:
        payload = dict(raw)
        payload["source_decision_ids"] = tuple(payload["source_decision_ids"])
        payload["source_decision_digests"] = tuple(payload["source_decision_digests"])
        for field in ("created_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return RecommendationCorrectionRecord(**cast(Any, payload))
