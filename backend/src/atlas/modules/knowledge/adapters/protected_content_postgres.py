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
    OperationalKnowledgeProtectedContentClaimModel,
    OperationalKnowledgeProtectedContentModel,
)
from atlas.modules.knowledge.application.protected_content import (
    OperationalKnowledgeProtectedContentService,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentClaim,
    OperationalKnowledgeProtectedContentRecord,
)


class PostgreSQLOperationalKnowledgeProtectedContentRepository:
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
    ) -> PostgreSQLOperationalKnowledgeProtectedContentRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(
        self, *, presentation_id: str
    ) -> OperationalKnowledgeProtectedContentRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeProtectedContentModel, presentation_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source_lease(
        self, *, source_lease_id: str
    ) -> OperationalKnowledgeProtectedContentRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeProtectedContentModel).where(
                    OperationalKnowledgeProtectedContentModel.source_lease_id == source_lease_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source_lease(
        self, *, source_lease_id: str
    ) -> OperationalKnowledgeProtectedContentClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeProtectedContentClaimModel).where(
                    OperationalKnowledgeProtectedContentClaimModel.source_lease_id
                    == source_lease_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeProtectedContentClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeProtectedContentClaimModel).where(
                    OperationalKnowledgeProtectedContentClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    OperationalKnowledgeProtectedContentClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeProtectedContentClaim) -> bool:
        payload = OperationalKnowledgeProtectedContentService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeProtectedContentClaimModel(
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

    async def add(self, record: OperationalKnowledgeProtectedContentRecord) -> bool:
        payload = OperationalKnowledgeProtectedContentService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeProtectedContentModel(
                        presentation_id=record.presentation_id,
                        claim_id=record.claim_id,
                        source_lease_id=record.source_lease_id,
                        source_assignment_set_id=record.source_assignment_set_id,
                        track_code=record.track_code,
                        knowledge_item_id=record.knowledge_item_id,
                        lease_holder_subject_digest=record.lease_holder_subject_digest,
                        presented_content_digest=record.presented_content_digest,
                        content_bytes=record.content_bytes,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeProtectedContentClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeProtectedContentClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeProtectedContentRecord:
        payload = dict(raw)
        for field in ("presented_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return OperationalKnowledgeProtectedContentRecord(**cast(Any, payload))
