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
    OperationalKnowledgeIndexClaimModel,
    OperationalKnowledgeIndexStagingModel,
)
from atlas.modules.knowledge.application.index_staging_validation import (
    OperationalKnowledgeIndexStagingValidationService,
)
from atlas.modules.knowledge.domain.index_staging_validation import (
    OperationalKnowledgeIndexClaim,
    OperationalKnowledgeIndexRecord,
)


class PostgreSQLOperationalKnowledgeIndexRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLOperationalKnowledgeIndexRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, index_staging_id: str) -> OperationalKnowledgeIndexRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeIndexStagingModel, index_staging_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_embedding_set(
        self, *, embedding_set_id: str
    ) -> OperationalKnowledgeIndexClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeIndexClaimModel).where(
                    OperationalKnowledgeIndexClaimModel.embedding_set_id == embedding_set_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeIndexClaim) -> bool:
        payload = OperationalKnowledgeIndexStagingValidationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeIndexClaimModel(
                        claim_id=claim.claim_id,
                        embedding_set_id=claim.embedding_set_id,
                        index_staging_id=claim.index_staging_id,
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

    async def add(self, record: OperationalKnowledgeIndexRecord) -> bool:
        payload = OperationalKnowledgeIndexStagingValidationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeIndexStagingModel(
                        index_staging_id=record.index_staging_id,
                        claim_id=record.claim_id,
                        embedding_set_id=record.embedding_set_id,
                        chunk_set_id=record.chunk_set_id,
                        knowledge_item_id=record.knowledge_item_id,
                        index_steward_subject_digest=record.index_steward_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeIndexClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeIndexClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeIndexRecord:
        payload = dict(raw)
        payload["validated_at"] = datetime.fromisoformat(str(payload["validated_at"]))
        payload["upstream_accountable_subject_digests"] = tuple(
            payload["upstream_accountable_subject_digests"]
        )
        return OperationalKnowledgeIndexRecord(**cast(Any, payload))
