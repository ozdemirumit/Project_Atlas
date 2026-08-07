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
    OperationalKnowledgeEmbeddingClaimModel,
    OperationalKnowledgeEmbeddingSetModel,
)
from atlas.modules.knowledge.application.embedding_generation import (
    OperationalKnowledgeEmbeddingGenerationService,
)
from atlas.modules.knowledge.domain.embedding_generation import (
    OperationalKnowledgeEmbeddingClaim,
    OperationalKnowledgeEmbeddingRecord,
)


class PostgreSQLOperationalKnowledgeEmbeddingRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLOperationalKnowledgeEmbeddingRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, embedding_set_id: str) -> OperationalKnowledgeEmbeddingRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeEmbeddingSetModel, embedding_set_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_chunk_set(
        self, *, chunk_set_id: str
    ) -> OperationalKnowledgeEmbeddingClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeEmbeddingClaimModel).where(
                    OperationalKnowledgeEmbeddingClaimModel.chunk_set_id == chunk_set_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeEmbeddingClaim) -> bool:
        payload = OperationalKnowledgeEmbeddingGenerationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeEmbeddingClaimModel(
                        claim_id=claim.claim_id,
                        chunk_set_id=claim.chunk_set_id,
                        embedding_set_id=claim.embedding_set_id,
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

    async def add(self, record: OperationalKnowledgeEmbeddingRecord) -> bool:
        payload = OperationalKnowledgeEmbeddingGenerationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeEmbeddingSetModel(
                        embedding_set_id=record.embedding_set_id,
                        claim_id=record.claim_id,
                        chunk_set_id=record.chunk_set_id,
                        materialization_id=record.materialization_id,
                        preparation_id=record.preparation_id,
                        knowledge_item_id=record.knowledge_item_id,
                        embedded_by_subject_digest=record.embedded_by_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeEmbeddingClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeEmbeddingClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeEmbeddingRecord:
        payload = dict(raw)
        payload["embedded_at"] = datetime.fromisoformat(str(payload["embedded_at"]))
        return OperationalKnowledgeEmbeddingRecord(**cast(Any, payload))
