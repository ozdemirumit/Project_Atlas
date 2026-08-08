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
    ProtectedCandidateRiskRecoveryClaimModel,
    ProtectedCandidateRiskRecoveryModel,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryClaim,
    ProtectedCandidateRiskRecoveryRecord,
)


class PostgreSQLProtectedCandidateRiskRecoveryRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLProtectedCandidateRiskRecoveryRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def get(self, *, completion_id: str) -> ProtectedCandidateRiskRecoveryRecord | None:
        async with self._sessions() as session:
            row = await session.get(ProtectedCandidateRiskRecoveryModel, completion_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> ProtectedCandidateRiskRecoveryClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ProtectedCandidateRiskRecoveryClaimModel).where(
                    ProtectedCandidateRiskRecoveryClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    ProtectedCandidateRiskRecoveryClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_impact_analysis(
        self, *, impact_analysis_id: str
    ) -> ProtectedCandidateRiskRecoveryClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ProtectedCandidateRiskRecoveryClaimModel).where(
                    ProtectedCandidateRiskRecoveryClaimModel.impact_analysis_id
                    == impact_analysis_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: ProtectedCandidateRiskRecoveryClaim) -> bool:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ProtectedCandidateRiskRecoveryClaimModel(
                        claim_id=claim.claim_id,
                        completion_id=claim.completion_id,
                        impact_analysis_id=claim.impact_analysis_id,
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

    async def save(self, record: ProtectedCandidateRiskRecoveryRecord) -> None:
        payload = GovernedProtectedModelInvocationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ProtectedCandidateRiskRecoveryModel(
                        completion_id=record.completion_id,
                        claim_id=record.claim_id,
                        impact_analysis_id=record.impact_analysis_id,
                        candidate_set_id=record.candidate_set_id,
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
            raise RuntimeError("protected_candidate_risk_recovery_already_exists") from error

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _claim_to_domain(raw: dict[str, Any]) -> ProtectedCandidateRiskRecoveryClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return ProtectedCandidateRiskRecoveryClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> ProtectedCandidateRiskRecoveryRecord:
        payload = dict(raw)
        for field in (
            "evidence_snapshot_generated_at",
            "completed_at",
            "expires_at",
        ):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return ProtectedCandidateRiskRecoveryRecord(**cast(Any, payload))
