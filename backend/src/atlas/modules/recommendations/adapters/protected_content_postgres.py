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
    RecommendationProtectedContentClaimModel,
    RecommendationProtectedContentModel,
)
from atlas.modules.recommendations.application.protected_content import (
    RecommendationProtectedContentService,
)
from atlas.modules.recommendations.domain.protected_content import (
    RecommendationProtectedContentClaim,
    RecommendationProtectedContentRecord,
)


class PostgreSQLRecommendationProtectedContentRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRecommendationProtectedContentRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, presentation_id: str) -> RecommendationProtectedContentRecord | None:
        async with self._sessions() as session:
            row = await session.get(RecommendationProtectedContentModel, presentation_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source_lease(
        self, *, source_lease_id: str
    ) -> RecommendationProtectedContentRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationProtectedContentModel).where(
                    RecommendationProtectedContentModel.source_lease_id == source_lease_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source_lease(
        self, *, source_lease_id: str
    ) -> RecommendationProtectedContentClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationProtectedContentClaimModel).where(
                    RecommendationProtectedContentClaimModel.source_lease_id == source_lease_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationProtectedContentClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationProtectedContentClaimModel).where(
                    RecommendationProtectedContentClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    RecommendationProtectedContentClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: RecommendationProtectedContentClaim) -> bool:
        payload = RecommendationProtectedContentService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationProtectedContentClaimModel(
                        claim_id=claim.claim_id,
                        source_lease_id=claim.source_lease_id,
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

    async def add(self, record: RecommendationProtectedContentRecord) -> bool:
        payload = RecommendationProtectedContentService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationProtectedContentModel(
                        presentation_id=record.presentation_id,
                        claim_id=record.claim_id,
                        source_lease_id=record.source_lease_id,
                        source_assignment_set_id=record.source_assignment_set_id,
                        track_code=record.track_code,
                        recommendation_id=record.recommendation_id,
                        lease_holder_subject_digest=record.lease_holder_subject_digest,
                        presented_content_digest=record.presented_content_digest,
                        content_bytes=record.protected_content_bytes_returned,
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
    def _claim_to_domain(raw: dict[str, Any]) -> RecommendationProtectedContentClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return RecommendationProtectedContentClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> RecommendationProtectedContentRecord:
        payload = dict(raw)
        for field in ("presented_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return RecommendationProtectedContentRecord(**cast(Any, payload))
