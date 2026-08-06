from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    OperationalEvidenceKnowledgeDraftClaimModel,
    OperationalEvidenceKnowledgeDraftModel,
)
from atlas.modules.knowledge.application.evidence_draft import (
    OperationalEvidenceKnowledgeDraftService,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    OperationalEvidenceKnowledgeDraftClaim,
    OperationalEvidenceKnowledgeDraftRecord,
)


class PostgreSQLOperationalEvidenceKnowledgeDraftRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLOperationalEvidenceKnowledgeDraftRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, draft_id: str) -> OperationalEvidenceKnowledgeDraftRecord | None:
        async with self._sessions() as session:
            row = await session.get(OperationalEvidenceKnowledgeDraftModel, draft_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_source(
        self, *, source_ingestion_id: str
    ) -> OperationalEvidenceKnowledgeDraftRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalEvidenceKnowledgeDraftModel).where(
                    OperationalEvidenceKnowledgeDraftModel.source_ingestion_id
                    == source_ingestion_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_source(
        self, *, source_ingestion_id: str
    ) -> OperationalEvidenceKnowledgeDraftClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalEvidenceKnowledgeDraftClaimModel).where(
                    OperationalEvidenceKnowledgeDraftClaimModel.source_ingestion_id
                    == source_ingestion_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> OperationalEvidenceKnowledgeDraftClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OperationalEvidenceKnowledgeDraftClaimModel).where(
                    OperationalEvidenceKnowledgeDraftClaimModel.claimed_by == claimed_by,
                    OperationalEvidenceKnowledgeDraftClaimModel.idempotency_digest
                    == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: OperationalEvidenceKnowledgeDraftClaim) -> bool:
        payload = OperationalEvidenceKnowledgeDraftService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalEvidenceKnowledgeDraftClaimModel(
                        claim_id=claim.claim_id,
                        source_ingestion_id=claim.source_ingestion_id,
                        draft_id=claim.draft_id,
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

    async def add(self, record: OperationalEvidenceKnowledgeDraftRecord) -> bool:
        payload = OperationalEvidenceKnowledgeDraftService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    OperationalEvidenceKnowledgeDraftModel(
                        draft_id=record.draft_id,
                        claim_id=record.claim_id,
                        source_ingestion_id=record.source_ingestion_id,
                        instance_id=record.instance_id,
                        capability_id=record.capability_id,
                        evidence_package_id=record.evidence_package_id,
                        curated_by=record.curated_by,
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
    def _claim_to_domain(raw: dict[str, Any]) -> OperationalEvidenceKnowledgeDraftClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return OperationalEvidenceKnowledgeDraftClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> OperationalEvidenceKnowledgeDraftRecord:
        payload = dict(raw)
        for field in ("observed_from", "observed_to", "created_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return OperationalEvidenceKnowledgeDraftRecord(**cast(Any, payload))
