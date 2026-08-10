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
    RecommendationFindingPresentationClaimModel,
    RecommendationFindingPresentationModel,
)
from atlas.modules.recommendations.application.finding_presentation import (
    RecommendationFindingPresentationService,
)
from atlas.modules.recommendations.domain.finding_presentation import (
    RecommendationFindingPresentationClaim,
    RecommendationFindingPresentationRecord,
)


class PostgreSQLRecommendationFindingPresentationRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRecommendationFindingPresentationRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(
        self, *, finding_presentation_id: str
    ) -> RecommendationFindingPresentationRecord | None:
        async with self._sessions() as session:
            row = await session.get(RecommendationFindingPresentationModel, finding_presentation_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source_finding(
        self, *, source_finding_packet_id: str
    ) -> RecommendationFindingPresentationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationFindingPresentationModel).where(
                    RecommendationFindingPresentationModel.source_finding_packet_id
                    == source_finding_packet_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source_finding(
        self, *, source_finding_packet_id: str
    ) -> RecommendationFindingPresentationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationFindingPresentationClaimModel).where(
                    RecommendationFindingPresentationClaimModel.source_finding_packet_id
                    == source_finding_packet_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationFindingPresentationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationFindingPresentationClaimModel).where(
                    RecommendationFindingPresentationClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    RecommendationFindingPresentationClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: RecommendationFindingPresentationClaim) -> bool:
        payload = RecommendationFindingPresentationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationFindingPresentationClaimModel(
                        claim_id=claim.claim_id,
                        source_finding_packet_id=claim.source_finding_packet_id,
                        finding_presentation_id=claim.finding_presentation_id,
                        track_code=claim.track_code,
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

    async def add(self, record: RecommendationFindingPresentationRecord) -> bool:
        payload = RecommendationFindingPresentationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationFindingPresentationModel(
                        finding_presentation_id=record.finding_presentation_id,
                        claim_id=record.claim_id,
                        source_finding_packet_id=record.source_finding_packet_id,
                        source_lease_id=record.source_lease_id,
                        source_presentation_id=record.source_presentation_id,
                        source_assignment_set_id=record.source_assignment_set_id,
                        track_code=record.track_code,
                        recommendation_id=record.recommendation_id,
                        lease_holder_subject_digest=record.lease_holder_subject_digest,
                        finding_content_digest=record.finding_content_digest,
                        finding_count=record.finding_count,
                        finding_bytes=record.finding_bytes,
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
    def _claim_to_domain(raw: dict[str, Any]) -> RecommendationFindingPresentationClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return RecommendationFindingPresentationClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> RecommendationFindingPresentationRecord:
        payload = dict(raw)
        for field in ("presented_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return RecommendationFindingPresentationRecord(**cast(Any, payload))
