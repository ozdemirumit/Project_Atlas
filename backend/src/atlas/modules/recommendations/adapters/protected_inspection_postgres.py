from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    RecommendationProtectedInspectionClaimModel,
    RecommendationProtectedInspectionRecordModel,
)
from atlas.modules.recommendations.application.protected_inspection import (
    RecommendationProtectedInspectionService,
)
from atlas.modules.recommendations.domain.protected_inspection import (
    RecommendationProtectedInspectionClaim,
    RecommendationProtectedInspectionRecord,
)


class PostgreSQLRecommendationProtectedInspectionRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRecommendationProtectedInspectionRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, lease_id: str) -> RecommendationProtectedInspectionRecord | None:
        async with self._sessions() as session:
            row = await session.get(RecommendationProtectedInspectionRecordModel, lease_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> RecommendationProtectedInspectionRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationProtectedInspectionRecordModel).where(
                    RecommendationProtectedInspectionRecordModel.source_assignment_set_id
                    == source_assignment_set_id,
                    RecommendationProtectedInspectionRecordModel.track_code == track_code,
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> RecommendationProtectedInspectionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationProtectedInspectionClaimModel).where(
                    RecommendationProtectedInspectionClaimModel.source_assignment_set_id
                    == source_assignment_set_id,
                    RecommendationProtectedInspectionClaimModel.track_code == track_code,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> RecommendationProtectedInspectionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(RecommendationProtectedInspectionClaimModel).where(
                    RecommendationProtectedInspectionClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    RecommendationProtectedInspectionClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: RecommendationProtectedInspectionClaim) -> bool:
        payload = RecommendationProtectedInspectionService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationProtectedInspectionClaimModel(
                        claim_id=claim.claim_id,
                        source_assignment_set_id=claim.source_assignment_set_id,
                        track_code=claim.track_code,
                        lease_id=claim.lease_id,
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

    async def add(self, record: RecommendationProtectedInspectionRecord) -> bool:
        payload = RecommendationProtectedInspectionService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    RecommendationProtectedInspectionRecordModel(
                        lease_id=record.lease_id,
                        claim_id=record.claim_id,
                        source_assignment_set_id=record.source_assignment_set_id,
                        track_code=record.track_code,
                        recommendation_id=record.recommendation_id,
                        lease_holder_subject_digest=record.lease_holder_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> RecommendationProtectedInspectionClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return RecommendationProtectedInspectionClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> RecommendationProtectedInspectionRecord:
        payload = dict(raw)
        for field in ("issued_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return RecommendationProtectedInspectionRecord(**cast(Any, payload))
