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
    ProtectedAnswerPresentationClaimModel,
    ProtectedAnswerPresentationModel,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_answer_presentation import (
    ProtectedAnswerPresentationClaim,
    ProtectedAnswerPresentationRecord,
)


class PostgreSQLProtectedAnswerPresentationRepository:
    def __init__(
        self, *, engine: AsyncEngine, session_factory: Callable[[], AsyncSession] | None = None
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLProtectedAnswerPresentationRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, presentation_id: str) -> ProtectedAnswerPresentationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ProtectedAnswerPresentationModel, presentation_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedAnswerPresentationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ProtectedAnswerPresentationClaimModel).where(
                    ProtectedAnswerPresentationClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    ProtectedAnswerPresentationClaimModel.idempotency_digest == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_adjudication(
        self, *, adjudication_id: str
    ) -> ProtectedAnswerPresentationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ProtectedAnswerPresentationClaimModel).where(
                    ProtectedAnswerPresentationClaimModel.adjudication_id == adjudication_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: ProtectedAnswerPresentationClaim) -> bool:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ProtectedAnswerPresentationClaimModel(
                        claim_id=claim.claim_id,
                        presentation_id=claim.presentation_id,
                        adjudication_id=claim.adjudication_id,
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

    async def save(self, record: ProtectedAnswerPresentationRecord) -> None:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ProtectedAnswerPresentationModel(
                        presentation_id=record.presentation_id,
                        claim_id=record.claim_id,
                        adjudication_id=record.adjudication_id,
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
            raise RuntimeError("protected_answer_presentation_already_exists") from error

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> ProtectedAnswerPresentationClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return ProtectedAnswerPresentationClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> ProtectedAnswerPresentationRecord:
        payload = dict(raw)
        payload["presented_at"] = datetime.fromisoformat(str(payload["presented_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        return ProtectedAnswerPresentationRecord(**cast(Any, payload))
