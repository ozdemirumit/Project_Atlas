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
    OperationalKnowledgePublicationPreparationClaimModel,
    OperationalKnowledgePublicationPreparationModel,
)
from atlas.modules.knowledge.application.publication_preparation import (
    OperationalKnowledgePublicationPreparationService,
)
from atlas.modules.knowledge.domain.publication_preparation import (
    OperationalKnowledgePublicationPreparationClaim,
    OperationalKnowledgePublicationPreparationRecord,
)


class PostgreSQLOperationalKnowledgePublicationPreparationRepository:
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
    ) -> PostgreSQLOperationalKnowledgePublicationPreparationRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(
        self, *, preparation_id: str
    ) -> OperationalKnowledgePublicationPreparationRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgePublicationPreparationModel, preparation_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_resolution(
        self, *, resolution_id: str
    ) -> OperationalKnowledgePublicationPreparationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgePublicationPreparationModel).where(
                    OperationalKnowledgePublicationPreparationModel.resolution_id == resolution_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_resolution(
        self, *, resolution_id: str
    ) -> OperationalKnowledgePublicationPreparationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgePublicationPreparationClaimModel).where(
                    OperationalKnowledgePublicationPreparationClaimModel.resolution_id
                    == resolution_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgePublicationPreparationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgePublicationPreparationClaimModel).where(
                    OperationalKnowledgePublicationPreparationClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    OperationalKnowledgePublicationPreparationClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgePublicationPreparationClaim) -> bool:
        payload = OperationalKnowledgePublicationPreparationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgePublicationPreparationClaimModel(
                        claim_id=claim.claim_id,
                        resolution_id=claim.resolution_id,
                        preparation_id=claim.preparation_id,
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

    async def add(self, record: OperationalKnowledgePublicationPreparationRecord) -> bool:
        payload = OperationalKnowledgePublicationPreparationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgePublicationPreparationModel(
                        preparation_id=record.preparation_id,
                        claim_id=record.claim_id,
                        resolution_id=record.resolution_id,
                        review_request_id=record.review_request_id,
                        source_draft_id=record.source_draft_id,
                        knowledge_item_id=record.knowledge_item_id,
                        prepared_by_subject_digest=record.prepared_by_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgePublicationPreparationClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgePublicationPreparationClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgePublicationPreparationRecord:
        payload = dict(raw)
        payload["prepared_at"] = datetime.fromisoformat(str(payload["prepared_at"]))
        return OperationalKnowledgePublicationPreparationRecord(**cast(Any, payload))
