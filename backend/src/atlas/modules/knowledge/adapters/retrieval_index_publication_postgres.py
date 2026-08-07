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
    OperationalKnowledgeRetrievalPublicationClaimModel,
    OperationalKnowledgeRetrievalPublicationModel,
)
from atlas.modules.knowledge.application.retrieval_index_publication import (
    OperationalKnowledgeRetrievalIndexPublicationService,
)
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    OperationalKnowledgeRetrievalPublicationClaim,
    OperationalKnowledgeRetrievalPublicationRecord,
)


class PostgreSQLOperationalKnowledgeRetrievalPublicationRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(
        cls, database_url: str
    ) -> PostgreSQLOperationalKnowledgeRetrievalPublicationRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(
        self, *, publication_id: str
    ) -> OperationalKnowledgeRetrievalPublicationRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeRetrievalPublicationModel, publication_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_index_staging(
        self, *, index_staging_id: str
    ) -> OperationalKnowledgeRetrievalPublicationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeRetrievalPublicationClaimModel).where(
                    OperationalKnowledgeRetrievalPublicationClaimModel.index_staging_id
                    == index_staging_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeRetrievalPublicationClaim) -> bool:
        payload = OperationalKnowledgeRetrievalIndexPublicationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeRetrievalPublicationClaimModel(
                        claim_id=claim.claim_id,
                        index_staging_id=claim.index_staging_id,
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

    async def add(self, record: OperationalKnowledgeRetrievalPublicationRecord) -> bool:
        payload = OperationalKnowledgeRetrievalIndexPublicationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeRetrievalPublicationModel(
                        publication_id=record.publication_id,
                        claim_id=record.claim_id,
                        index_staging_id=record.index_staging_id,
                        knowledge_item_id=record.knowledge_item_id,
                        publication_steward_subject_digest=(
                            record.publication_steward_subject_digest
                        ),
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeRetrievalPublicationClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeRetrievalPublicationClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeRetrievalPublicationRecord:
        payload = dict(raw)
        payload["published_at"] = datetime.fromisoformat(str(payload["published_at"]))
        payload["upstream_accountable_subject_digests"] = tuple(
            payload["upstream_accountable_subject_digests"]
        )
        return OperationalKnowledgeRetrievalPublicationRecord(**cast(Any, payload))
