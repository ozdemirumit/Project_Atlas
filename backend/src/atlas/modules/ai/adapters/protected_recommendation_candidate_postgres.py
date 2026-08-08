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
    ProtectedRecommendationCandidateClaimModel,
    ProtectedRecommendationCandidateModel,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateClaim,
    ProtectedRecommendationCandidateRecord,
)


class PostgreSQLProtectedRecommendationCandidateRepository:
    def __init__(
        self, *, engine: AsyncEngine, session_factory: Callable[[], AsyncSession] | None = None
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLProtectedRecommendationCandidateRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, candidate_set_id: str) -> ProtectedRecommendationCandidateRecord | None:
        async with self._sessions() as session:
            row = await session.get(ProtectedRecommendationCandidateModel, candidate_set_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedRecommendationCandidateClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ProtectedRecommendationCandidateClaimModel).where(
                    ProtectedRecommendationCandidateClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    ProtectedRecommendationCandidateClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_presentation(
        self, *, presentation_id: str
    ) -> ProtectedRecommendationCandidateClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ProtectedRecommendationCandidateClaimModel).where(
                    ProtectedRecommendationCandidateClaimModel.presentation_id == presentation_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: ProtectedRecommendationCandidateClaim) -> bool:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ProtectedRecommendationCandidateClaimModel(
                        claim_id=claim.claim_id,
                        candidate_set_id=claim.candidate_set_id,
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

    async def save(self, record: ProtectedRecommendationCandidateRecord) -> None:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ProtectedRecommendationCandidateModel(
                        candidate_set_id=record.candidate_set_id,
                        claim_id=record.claim_id,
                        presentation_id=record.presentation_id,
                        consumer_subject_digest=record.consumer_subject_digest,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        expires_at=record.expires_at,
                        canonical_digest=record.canonical_digest,
                        payload=cast(dict[str, Any], payload),
                    )
                )
                await session.commit()
        except IntegrityError as error:
            raise RuntimeError("protected_recommendation_candidate_set_already_exists") from error

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> ProtectedRecommendationCandidateClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return ProtectedRecommendationCandidateClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> ProtectedRecommendationCandidateRecord:
        payload = dict(raw)
        payload["candidate_categories"] = tuple(payload["candidate_categories"])
        payload["generated_at"] = datetime.fromisoformat(str(payload["generated_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        return ProtectedRecommendationCandidateRecord(**cast(Any, payload))
