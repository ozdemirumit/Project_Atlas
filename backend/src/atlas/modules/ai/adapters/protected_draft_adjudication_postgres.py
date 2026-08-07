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
    ProtectedDraftAdjudicationClaimModel,
    ProtectedDraftAdjudicationModel,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationClaim,
    ProtectedDraftAdjudicationRecord,
)


class PostgreSQLProtectedDraftAdjudicationRepository:
    def __init__(
        self, *, engine: AsyncEngine, session_factory: Callable[[], AsyncSession] | None = None
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLProtectedDraftAdjudicationRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, adjudication_id: str) -> ProtectedDraftAdjudicationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ProtectedDraftAdjudicationModel, adjudication_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedDraftAdjudicationClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ProtectedDraftAdjudicationClaimModel).where(
                    ProtectedDraftAdjudicationClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    ProtectedDraftAdjudicationClaimModel.idempotency_digest == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: ProtectedDraftAdjudicationClaim) -> bool:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ProtectedDraftAdjudicationClaimModel(
                        claim_id=claim.claim_id,
                        adjudication_id=claim.adjudication_id,
                        invocation_id=claim.invocation_id,
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

    async def add(self, record: ProtectedDraftAdjudicationRecord) -> bool:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ProtectedDraftAdjudicationModel(
                        adjudication_id=record.adjudication_id,
                        claim_id=record.claim_id,
                        invocation_id=record.invocation_id,
                        consumer_subject_digest=record.consumer_subject_digest,
                        protected_report_reference=record.protected_report_reference,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        expires_at=record.expires_at,
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
    def _claim_to_domain(raw: dict[str, Any]) -> ProtectedDraftAdjudicationClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return ProtectedDraftAdjudicationClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> ProtectedDraftAdjudicationRecord:
        payload = dict(raw)
        payload["adjudicated_at"] = datetime.fromisoformat(str(payload["adjudicated_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        return ProtectedDraftAdjudicationRecord(**cast(Any, payload))
