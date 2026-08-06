from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    OperationalKnowledgeProtectedInspectionClaimModel,
    OperationalKnowledgeProtectedInspectionModel,
)
from atlas.modules.knowledge.application.protected_inspection import (
    OperationalKnowledgeProtectedInspectionService,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionClaim,
    OperationalKnowledgeProtectedInspectionRecord,
)


class PostgreSQLOperationalKnowledgeProtectedInspectionRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(
        cls, database_url: str
    ) -> PostgreSQLOperationalKnowledgeProtectedInspectionRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, lease_id: str) -> OperationalKnowledgeProtectedInspectionRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalKnowledgeProtectedInspectionModel, lease_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> OperationalKnowledgeProtectedInspectionRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeProtectedInspectionModel).where(
                    OperationalKnowledgeProtectedInspectionModel.source_assignment_set_id
                    == source_assignment_set_id,
                    OperationalKnowledgeProtectedInspectionModel.track_code == track_code,
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source_track(
        self, *, source_assignment_set_id: str, track_code: str
    ) -> OperationalKnowledgeProtectedInspectionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeProtectedInspectionClaimModel).where(
                    OperationalKnowledgeProtectedInspectionClaimModel.source_assignment_set_id
                    == source_assignment_set_id,
                    OperationalKnowledgeProtectedInspectionClaimModel.track_code == track_code,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by_subject_digest: str, idempotency_digest: str
    ) -> OperationalKnowledgeProtectedInspectionClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalKnowledgeProtectedInspectionClaimModel).where(
                    OperationalKnowledgeProtectedInspectionClaimModel.claimed_by_subject_digest
                    == claimed_by_subject_digest,
                    OperationalKnowledgeProtectedInspectionClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalKnowledgeProtectedInspectionClaim) -> bool:
        payload = OperationalKnowledgeProtectedInspectionService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeProtectedInspectionClaimModel(
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

    async def add(self, record: OperationalKnowledgeProtectedInspectionRecord) -> bool:
        payload = OperationalKnowledgeProtectedInspectionService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalKnowledgeProtectedInspectionModel(
                        lease_id=record.lease_id,
                        claim_id=record.claim_id,
                        source_assignment_set_id=record.source_assignment_set_id,
                        track_code=record.track_code,
                        knowledge_item_id=record.knowledge_item_id,
                        lease_holder_subject_digest=record.lease_holder_subject_digest,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeProtectedInspectionClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalKnowledgeProtectedInspectionClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalKnowledgeProtectedInspectionRecord:
        payload = dict(raw)
        for field in ("issued_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return OperationalKnowledgeProtectedInspectionRecord(**cast(Any, payload))
