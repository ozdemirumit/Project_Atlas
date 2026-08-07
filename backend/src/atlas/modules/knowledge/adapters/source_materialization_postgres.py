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
    OperationalKnowledgeSourceMaterializationClaimModel,
    OperationalKnowledgeSourceMaterializationModel,
)
from atlas.modules.knowledge.application.source_materialization import (
    OperationalKnowledgeSourceMaterializationService,
)
from atlas.modules.knowledge.domain.source_materialization import (
    OperationalKnowledgeSourceMaterializationClaim,
    OperationalKnowledgeSourceMaterializationRecord,
)


class PostgreSQLOperationalKnowledgeSourceMaterializationRepository:
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
    ) -> PostgreSQLOperationalKnowledgeSourceMaterializationRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(
        self, *, materialization_id: str
    ) -> OperationalKnowledgeSourceMaterializationRecord | None:
        async with self._sessions() as session:
            row = await session.get(
                OperationalKnowledgeSourceMaterializationModel, materialization_id
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_preparation(
        self, *, preparation_id: str
    ) -> OperationalKnowledgeSourceMaterializationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeSourceMaterializationClaimModel).where(
                    OperationalKnowledgeSourceMaterializationClaimModel.preparation_id
                    == preparation_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeSourceMaterializationClaim) -> bool:
        payload = OperationalKnowledgeSourceMaterializationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeSourceMaterializationClaimModel(
                        claim_id=claim.claim_id,
                        preparation_id=claim.preparation_id,
                        materialization_id=claim.materialization_id,
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

    async def add(self, record: OperationalKnowledgeSourceMaterializationRecord) -> bool:
        payload = OperationalKnowledgeSourceMaterializationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeSourceMaterializationModel(
                        materialization_id=record.materialization_id,
                        claim_id=record.claim_id,
                        preparation_id=record.preparation_id,
                        resolution_id=record.resolution_id,
                        source_draft_id=record.source_draft_id,
                        knowledge_item_id=record.knowledge_item_id,
                        materialized_by_subject_digest=record.materialized_by_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeSourceMaterializationClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeSourceMaterializationClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeSourceMaterializationRecord:
        payload = dict(raw)
        payload["materialized_at"] = datetime.fromisoformat(str(payload["materialized_at"]))
        return OperationalKnowledgeSourceMaterializationRecord(**cast(Any, payload))
