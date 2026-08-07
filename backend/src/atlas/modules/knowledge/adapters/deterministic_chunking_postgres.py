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
    OperationalKnowledgeChunkingClaimModel,
    OperationalKnowledgeChunkSetModel,
)
from atlas.modules.knowledge.application.deterministic_chunking import (
    OperationalKnowledgeDeterministicChunkingService,
)
from atlas.modules.knowledge.domain.deterministic_chunking import (
    OperationalKnowledgeChunkingClaim,
    OperationalKnowledgeChunkingRecord,
)


class PostgreSQLOperationalKnowledgeChunkingRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLOperationalKnowledgeChunkingRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, chunk_set_id: str) -> OperationalKnowledgeChunkingRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeChunkSetModel, chunk_set_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_materialization(
        self, *, materialization_id: str
    ) -> OperationalKnowledgeChunkingClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeChunkingClaimModel).where(
                    OperationalKnowledgeChunkingClaimModel.materialization_id == materialization_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeChunkingClaim) -> bool:
        payload = OperationalKnowledgeDeterministicChunkingService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeChunkingClaimModel(
                        claim_id=claim.claim_id,
                        materialization_id=claim.materialization_id,
                        chunk_set_id=claim.chunk_set_id,
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

    async def add(self, record: OperationalKnowledgeChunkingRecord) -> bool:
        payload = OperationalKnowledgeDeterministicChunkingService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeChunkSetModel(
                        chunk_set_id=record.chunk_set_id,
                        claim_id=record.claim_id,
                        materialization_id=record.materialization_id,
                        preparation_id=record.preparation_id,
                        resolution_id=record.resolution_id,
                        source_draft_id=record.source_draft_id,
                        knowledge_item_id=record.knowledge_item_id,
                        chunked_by_subject_digest=record.chunked_by_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeChunkingClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeChunkingClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeChunkingRecord:
        payload = dict(raw)
        payload["chunked_at"] = datetime.fromisoformat(str(payload["chunked_at"]))
        return OperationalKnowledgeChunkingRecord(**cast(Any, payload))
