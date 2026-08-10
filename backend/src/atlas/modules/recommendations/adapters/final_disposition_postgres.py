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
    FinalRecommendationDispositionClaimModel,
    FinalRecommendationDispositionModel,
)
from atlas.modules.recommendations.application.final_disposition import (
    FinalRecommendationDispositionService,
)
from atlas.modules.recommendations.domain.final_disposition import (
    FinalRecommendationDispositionClaim,
    FinalRecommendationDispositionRecord,
)


class PostgreSQLFinalRecommendationDispositionRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLFinalRecommendationDispositionRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, disposition_id: str) -> FinalRecommendationDispositionRecord | None:
        async with self._sessions() as session:
            row = await session.get(FinalRecommendationDispositionModel, disposition_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_review_request(
        self, *, review_request_id: str
    ) -> FinalRecommendationDispositionRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(FinalRecommendationDispositionModel).where(
                    FinalRecommendationDispositionModel.review_request_id == review_request_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_review_request(
        self, *, review_request_id: str
    ) -> FinalRecommendationDispositionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(FinalRecommendationDispositionClaimModel).where(
                    FinalRecommendationDispositionClaimModel.review_request_id == review_request_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> FinalRecommendationDispositionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(FinalRecommendationDispositionClaimModel).where(
                    FinalRecommendationDispositionClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    FinalRecommendationDispositionClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: FinalRecommendationDispositionClaim) -> bool:
        payload = FinalRecommendationDispositionService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    FinalRecommendationDispositionClaimModel(
                        claim_id=claim.claim_id,
                        review_request_id=claim.review_request_id,
                        disposition_id=claim.disposition_id,
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

    async def add(self, record: FinalRecommendationDispositionRecord) -> bool:
        payload = FinalRecommendationDispositionService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    FinalRecommendationDispositionModel(
                        disposition_id=record.disposition_id,
                        claim_id=record.claim_id,
                        review_request_id=record.review_request_id,
                        recommendation_id=record.recommendation_id,
                        disposition_code=record.disposition_code,
                        approved_by_subject_digest=record.approved_by_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> FinalRecommendationDispositionClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return FinalRecommendationDispositionClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> FinalRecommendationDispositionRecord:
        payload = dict(raw)
        payload["decision_ids"] = tuple(payload["decision_ids"])
        payload["decision_digests"] = tuple(payload["decision_digests"])
        payload["basis_codes"] = tuple(payload["basis_codes"])
        payload["resolved_at"] = datetime.fromisoformat(str(payload["resolved_at"]))
        return FinalRecommendationDispositionRecord(**cast(Any, payload))
