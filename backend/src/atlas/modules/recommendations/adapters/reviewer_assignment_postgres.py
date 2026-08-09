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
    RecommendationReviewerAssignmentClaimModel,
    RecommendationReviewerAssignmentRecordModel,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentClaim,
    RecommendationReviewerAssignmentRecord,
)


class PostgreSQLRecommendationReviewerAssignmentRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRecommendationReviewerAssignmentRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, assignment_set_id: str) -> RecommendationReviewerAssignmentRecord | None:
        async with self._sessions() as session:
            row = await session.get(RecommendationReviewerAssignmentRecordModel, assignment_set_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationReviewerAssignmentClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationReviewerAssignmentClaimModel).where(
                    RecommendationReviewerAssignmentClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    RecommendationReviewerAssignmentClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: RecommendationReviewerAssignmentClaim) -> bool:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationReviewerAssignmentClaimModel(
                        claim_id=claim.claim_id,
                        assignment_set_id=claim.assignment_set_id,
                        review_request_id=claim.review_request_id,
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

    async def save(self, record: RecommendationReviewerAssignmentRecord) -> None:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationReviewerAssignmentRecordModel(
                        assignment_set_id=record.assignment_set_id,
                        review_request_id=record.review_request_id,
                        recommendation_id=record.recommendation_id,
                        claim_id=record.claim_id,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        state=record.state,
                        expires_at=record.expires_at,
                        canonical_digest=record.canonical_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
        except IntegrityError as error:
            raise RuntimeError("recommendation_reviewer_assignment_already_exists") from error

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> RecommendationReviewerAssignmentClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return RecommendationReviewerAssignmentClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> RecommendationReviewerAssignmentRecord:
        payload = dict(raw)
        for field in ("assigned_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        payload["track_assignments"] = tuple(
            (item[0], item[1], item[2], item[3], item[4])
            for item in cast(list[list[str]], payload["track_assignments"])
        )
        return RecommendationReviewerAssignmentRecord(**cast(Any, payload))
