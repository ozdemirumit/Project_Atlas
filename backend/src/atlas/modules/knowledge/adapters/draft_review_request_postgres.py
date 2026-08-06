from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    OperationalKnowledgeReviewRequestClaimModel,
    OperationalKnowledgeReviewRequestModel,
)
from atlas.modules.knowledge.application.draft_review_request import (
    OperationalKnowledgeReviewRequestService,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestClaim,
    OperationalKnowledgeReviewRequestRecord,
)


class PostgreSQLOperationalKnowledgeReviewRequestRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLOperationalKnowledgeReviewRequestRepository:
        return cls(create_async_engine(database_url))

    async def get(
        self, *, review_request_id: str
    ) -> OperationalKnowledgeReviewRequestRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeReviewRequestModel, review_request_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source(
        self, *, source_draft_id: str
    ) -> OperationalKnowledgeReviewRequestRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewRequestModel).where(
                    OperationalKnowledgeReviewRequestModel.source_draft_id == source_draft_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source(
        self, *, source_draft_id: str
    ) -> OperationalKnowledgeReviewRequestClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewRequestClaimModel).where(
                    OperationalKnowledgeReviewRequestClaimModel.source_draft_id == source_draft_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> OperationalKnowledgeReviewRequestClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeReviewRequestClaimModel).where(
                    OperationalKnowledgeReviewRequestClaimModel.claimed_by == claimed_by,
                    OperationalKnowledgeReviewRequestClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeReviewRequestClaim) -> bool:
        payload = OperationalKnowledgeReviewRequestService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeReviewRequestClaimModel(
                        claim_id=claim.claim_id,
                        source_draft_id=claim.source_draft_id,
                        review_request_id=claim.review_request_id,
                        claimed_by=claim.claimed_by,
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

    async def add(self, record: OperationalKnowledgeReviewRequestRecord) -> bool:
        payload = OperationalKnowledgeReviewRequestService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeReviewRequestModel(
                        review_request_id=record.review_request_id,
                        claim_id=record.claim_id,
                        source_draft_id=record.source_draft_id,
                        knowledge_item_id=record.knowledge_item_id,
                        requested_by=record.requested_by,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeReviewRequestClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeReviewRequestClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeReviewRequestRecord:
        payload = dict(raw)
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        return OperationalKnowledgeReviewRequestRecord(**cast(Any, payload))
