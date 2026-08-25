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
    OperationalKnowledgeCorrectionClaimModel,
    OperationalKnowledgeCorrectionModel,
)
from atlas.modules.knowledge.application.correction_resubmission import (
    OperationalKnowledgeCorrectionService,
)
from atlas.modules.knowledge.domain.correction_resubmission import (
    OperationalKnowledgeCorrectionClaim,
    OperationalKnowledgeCorrectionRecord,
)


class PostgreSQLOperationalKnowledgeCorrectionRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLOperationalKnowledgeCorrectionRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, correction_id: str) -> OperationalKnowledgeCorrectionRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeCorrectionModel, correction_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source_request(
        self, *, source_review_request_id: str
    ) -> OperationalKnowledgeCorrectionRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeCorrectionModel).where(
                    OperationalKnowledgeCorrectionModel.source_review_request_id
                    == source_review_request_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source_request(
        self, *, source_review_request_id: str
    ) -> OperationalKnowledgeCorrectionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeCorrectionClaimModel).where(
                    OperationalKnowledgeCorrectionClaimModel.source_review_request_id
                    == source_review_request_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_by_new_review_request(
        self,
        *,
        new_review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeCorrectionRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeCorrectionModel).where(
                    OperationalKnowledgeCorrectionModel.new_review_request_id
                    == new_review_request_id,
                    OperationalKnowledgeCorrectionModel.organization_id == organization_id,
                    OperationalKnowledgeCorrectionModel.environment_id == environment_id,
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeCorrectionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeCorrectionClaimModel).where(
                    OperationalKnowledgeCorrectionClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    OperationalKnowledgeCorrectionClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeCorrectionClaim) -> bool:
        payload = OperationalKnowledgeCorrectionService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeCorrectionClaimModel(
                        claim_id=claim.claim_id,
                        source_review_request_id=claim.source_review_request_id,
                        correction_id=claim.correction_id,
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

    async def add(self, record: OperationalKnowledgeCorrectionRecord) -> bool:
        payload = OperationalKnowledgeCorrectionService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeCorrectionModel(
                        correction_id=record.correction_id,
                        claim_id=record.claim_id,
                        source_review_request_id=record.source_review_request_id,
                        source_draft_id=record.source_draft_id,
                        knowledge_item_id=record.knowledge_item_id,
                        new_draft_id=record.new_draft_id,
                        new_review_request_id=record.new_review_request_id,
                        corrected_by_subject_digest=record.corrected_by_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeCorrectionClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeCorrectionClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeCorrectionRecord:
        payload = dict(raw)
        payload["source_decision_ids"] = tuple(payload["source_decision_ids"])
        payload["source_decision_digests"] = tuple(payload["source_decision_digests"])
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        return OperationalKnowledgeCorrectionRecord(**cast(Any, payload))
