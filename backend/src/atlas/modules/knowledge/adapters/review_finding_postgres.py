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
    OperationalKnowledgeReviewFindingClaimModel,
    OperationalKnowledgeReviewFindingModel,
)
from atlas.modules.knowledge.application.review_finding import (
    OperationalKnowledgeReviewFindingService,
)
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingClaim,
    OperationalKnowledgeReviewFindingRecord,
)


class PostgreSQLOperationalKnowledgeReviewFindingRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLOperationalKnowledgeReviewFindingRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(
        self, *, finding_packet_id: str
    ) -> OperationalKnowledgeReviewFindingRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeReviewFindingModel, finding_packet_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source_presentation(
        self, *, source_presentation_id: str
    ) -> OperationalKnowledgeReviewFindingRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewFindingModel).where(
                    OperationalKnowledgeReviewFindingModel.source_presentation_id
                    == source_presentation_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source_presentation(
        self, *, source_presentation_id: str
    ) -> OperationalKnowledgeReviewFindingClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewFindingClaimModel).where(
                    OperationalKnowledgeReviewFindingClaimModel.source_presentation_id
                    == source_presentation_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeReviewFindingClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewFindingClaimModel).where(
                    OperationalKnowledgeReviewFindingClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    OperationalKnowledgeReviewFindingClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeReviewFindingClaim) -> bool:
        payload = OperationalKnowledgeReviewFindingService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeReviewFindingClaimModel(
                        claim_id=claim.claim_id,
                        source_presentation_id=claim.source_presentation_id,
                        finding_packet_id=claim.finding_packet_id,
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

    async def add(self, record: OperationalKnowledgeReviewFindingRecord) -> bool:
        payload = OperationalKnowledgeReviewFindingService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeReviewFindingModel(
                        finding_packet_id=record.finding_packet_id,
                        claim_id=record.claim_id,
                        source_lease_id=record.source_lease_id,
                        source_presentation_id=record.source_presentation_id,
                        source_assignment_set_id=record.source_assignment_set_id,
                        track_code=record.track_code,
                        knowledge_item_id=record.knowledge_item_id,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeReviewFindingClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeReviewFindingClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeReviewFindingRecord:
        payload = dict(raw)
        for field in ("created_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return OperationalKnowledgeReviewFindingRecord(**cast(Any, payload))
