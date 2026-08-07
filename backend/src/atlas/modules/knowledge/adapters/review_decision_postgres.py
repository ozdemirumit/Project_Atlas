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
    OperationalKnowledgeTrackReviewDecisionClaimModel,
    OperationalKnowledgeTrackReviewDecisionModel,
)
from atlas.modules.knowledge.application.review_decision import (
    OperationalKnowledgeTrackReviewDecisionService,
)
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionClaim,
    OperationalKnowledgeTrackReviewDecisionRecord,
)


class PostgreSQLOperationalKnowledgeTrackReviewDecisionRepository:
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
    ) -> PostgreSQLOperationalKnowledgeTrackReviewDecisionRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(
        self, *, decision_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeTrackReviewDecisionModel, decision_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source_presentation(
        self, *, source_finding_presentation_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeTrackReviewDecisionModel).where(
                    OperationalKnowledgeTrackReviewDecisionModel.source_finding_presentation_id
                    == source_finding_presentation_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source_presentation(
        self, *, source_finding_presentation_id: str
    ) -> OperationalKnowledgeTrackReviewDecisionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeTrackReviewDecisionClaimModel).where(
                    OperationalKnowledgeTrackReviewDecisionClaimModel.source_finding_presentation_id
                    == source_finding_presentation_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeTrackReviewDecisionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeTrackReviewDecisionClaimModel).where(
                    OperationalKnowledgeTrackReviewDecisionClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    OperationalKnowledgeTrackReviewDecisionClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def list_by_review_request(
        self, *, review_request_id: str
    ) -> tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(OperationalKnowledgeTrackReviewDecisionModel).where(
                        OperationalKnowledgeTrackReviewDecisionModel.review_request_id
                        == review_request_id
                    )
                )
            ).all()
            return tuple(self._record_to_domain(row.payload) for row in rows)

    async def claim(self, claim: OperationalKnowledgeTrackReviewDecisionClaim) -> bool:
        payload = OperationalKnowledgeTrackReviewDecisionService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeTrackReviewDecisionClaimModel(
                        claim_id=claim.claim_id,
                        source_finding_presentation_id=claim.source_finding_presentation_id,
                        decision_id=claim.decision_id,
                        track_code=claim.track_code,
                        disposition_code=claim.disposition_code,
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

    async def add(self, record: OperationalKnowledgeTrackReviewDecisionRecord) -> bool:
        payload = OperationalKnowledgeTrackReviewDecisionService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeTrackReviewDecisionModel(
                        decision_id=record.decision_id,
                        claim_id=record.claim_id,
                        source_finding_presentation_id=record.source_finding_presentation_id,
                        source_lease_id=record.source_lease_id,
                        source_assignment_set_id=record.source_assignment_set_id,
                        review_request_id=record.review_request_id,
                        track_code=record.track_code,
                        disposition_code=record.disposition_code,
                        knowledge_item_id=record.knowledge_item_id,
                        decided_by_subject_digest=record.decided_by_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeTrackReviewDecisionClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeTrackReviewDecisionClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeTrackReviewDecisionRecord:
        payload = dict(raw)
        payload["basis_codes"] = tuple(payload["basis_codes"])
        for field in ("decided_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return OperationalKnowledgeTrackReviewDecisionRecord(**cast(Any, payload))
