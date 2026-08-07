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
    OperationalKnowledgeRetrievalClaimModel,
    OperationalKnowledgeRetrievalModel,
)
from atlas.modules.knowledge.application.protected_retrieval import (
    OperationalKnowledgeProtectedRetrievalService,
)
from atlas.modules.knowledge.domain.protected_retrieval import (
    OperationalKnowledgeRetrievalClaim,
    OperationalKnowledgeRetrievalRecord,
)


class PostgreSQLOperationalKnowledgeRetrievalRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLOperationalKnowledgeRetrievalRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, retrieval_id: str) -> OperationalKnowledgeRetrievalRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeRetrievalModel, retrieval_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeRetrievalClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeRetrievalClaimModel).where(
                    OperationalKnowledgeRetrievalClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    OperationalKnowledgeRetrievalClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeRetrievalClaim) -> bool:
        payload = OperationalKnowledgeProtectedRetrievalService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeRetrievalClaimModel(
                        claim_id=claim.claim_id,
                        retrieval_id=claim.retrieval_id,
                        publication_id=claim.publication_id,
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

    async def add(self, record: OperationalKnowledgeRetrievalRecord) -> bool:
        payload = OperationalKnowledgeProtectedRetrievalService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeRetrievalModel(
                        retrieval_id=record.retrieval_id,
                        claim_id=record.claim_id,
                        publication_id=record.publication_id,
                        knowledge_item_id=record.knowledge_item_id,
                        consumer_subject_digest=record.consumer_subject_digest,
                        protected_artifact_reference=record.protected_artifact_reference,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        expires_at=record.expires_at,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeRetrievalClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeRetrievalClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeRetrievalRecord:
        payload = dict(raw)
        payload["retrieved_at"] = datetime.fromisoformat(str(payload["retrieved_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        return OperationalKnowledgeRetrievalRecord(**cast(Any, payload))
