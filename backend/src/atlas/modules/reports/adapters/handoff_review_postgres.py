from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ItsmHandoffHumanReviewModel
from atlas.modules.reports.domain.handoff_review import (
    ItsmHandoffHumanReview,
    ItsmHandoffReviewOutcome,
)


class PostgreSQLItsmHandoffReviewRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLItsmHandoffReviewRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, review_id: str) -> ItsmHandoffHumanReview | None:
        async with self._sessions() as session:
            row = await session.get(ItsmHandoffHumanReviewModel, review_id)
            return self._to_domain(row) if row else None

    async def get_by_handoff(self, *, handoff_draft_id: str) -> ItsmHandoffHumanReview | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ItsmHandoffHumanReviewModel).where(
                    ItsmHandoffHumanReviewModel.handoff_draft_id == handoff_draft_id
                )
            )
            return self._to_domain(row) if row else None

    async def get_by_create_key(
        self, *, reviewer_id: str, idempotency_key: str
    ) -> ItsmHandoffHumanReview | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ItsmHandoffHumanReviewModel).where(
                    ItsmHandoffHumanReviewModel.reviewer_id == reviewer_id,
                    ItsmHandoffHumanReviewModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row else None

    async def add(self, review: ItsmHandoffHumanReview) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(ItsmHandoffHumanReviewModel(**self._values(review)))
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _values(review: ItsmHandoffHumanReview) -> dict[str, Any]:
        return {
            "review_id": review.review_id,
            "schema_version": review.schema_version,
            "version": review.version,
            "outcome": review.outcome.value,
            "report_id": review.report_id,
            "report_version": review.report_version,
            "report_digest": review.report_digest,
            "handoff_draft_id": review.handoff_draft_id,
            "handoff_digest": review.handoff_digest,
            "handoff_idempotency_key": review.handoff_idempotency_key,
            "incident_reference": review.incident_reference,
            "operation": review.operation,
            "requester_id": review.requester_id,
            "reviewer_id": review.reviewer_id,
            "reviewer_role_id": review.reviewer_role_id,
            "organization_id": review.organization_id,
            "environment_id": review.environment_id,
            "site_id": review.site_id,
            "rationale": review.rationale,
            "acknowledged_review_only": review.acknowledged_review_only,
            "request_fingerprint": review.request_fingerprint,
            "idempotency_key": review.idempotency_key,
            "canonical_digest": review.canonical_digest,
            "decided_at": review.decided_at,
            "expires_at": review.expires_at,
        }

    @staticmethod
    def _to_domain(row: ItsmHandoffHumanReviewModel) -> ItsmHandoffHumanReview:
        outcome = ItsmHandoffReviewOutcome(row.outcome)
        return ItsmHandoffHumanReview(
            review_id=row.review_id,
            schema_version=row.schema_version,
            version=row.version,
            outcome=outcome,
            report_id=row.report_id,
            report_version=row.report_version,
            report_digest=row.report_digest,
            handoff_draft_id=row.handoff_draft_id,
            handoff_digest=row.handoff_digest,
            handoff_idempotency_key=row.handoff_idempotency_key,
            incident_reference=row.incident_reference,
            operation=row.operation,
            requester_id=row.requester_id,
            reviewer_id=row.reviewer_id,
            reviewer_role_id=row.reviewer_role_id,
            organization_id=row.organization_id,
            environment_id=row.environment_id,
            site_id=row.site_id,
            rationale=row.rationale,
            acknowledged_review_only=row.acknowledged_review_only,
            request_fingerprint=row.request_fingerprint,
            idempotency_key=row.idempotency_key,
            canonical_digest=row.canonical_digest,
            decided_at=row.decided_at,
            expires_at=row.expires_at,
            review_complete=outcome is ItsmHandoffReviewOutcome.ACCEPT,
        )
