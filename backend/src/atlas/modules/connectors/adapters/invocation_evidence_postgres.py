from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    ConnectorInvocationEvidenceClaimModel,
    ConnectorInvocationEvidenceModel,
)
from atlas.modules.connectors.application.invocation_evidence import (
    ConnectorInvocationEvidenceService,
)
from atlas.modules.connectors.domain.invocation_evidence import (
    ConnectorInvocationEvidenceClaim,
    ConnectorInvocationEvidenceRecord,
)


class PostgreSQLConnectorInvocationEvidenceRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorInvocationEvidenceRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, ingestion_id: str) -> ConnectorInvocationEvidenceRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorInvocationEvidenceModel, ingestion_id)
            return self._record_to_domain(row.payload) if row else None

    async def get_by_invocation(
        self, *, source_invocation_id: str
    ) -> ConnectorInvocationEvidenceRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationEvidenceModel).where(
                    ConnectorInvocationEvidenceModel.source_invocation_id == source_invocation_id
                )
            )
            return self._record_to_domain(row.payload) if row else None

    async def get_claim_by_invocation(
        self, *, source_invocation_id: str
    ) -> ConnectorInvocationEvidenceClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationEvidenceClaimModel).where(
                    ConnectorInvocationEvidenceClaimModel.source_invocation_id
                    == source_invocation_id
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def get_claim_by_idempotency(
        self, *, claimed_by: str, idempotency_digest: str
    ) -> ConnectorInvocationEvidenceClaim | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationEvidenceClaimModel).where(
                    ConnectorInvocationEvidenceClaimModel.claimed_by == claimed_by,
                    ConnectorInvocationEvidenceClaimModel.idempotency_digest == idempotency_digest,
                )
            )
            return self._claim_to_domain(row.payload) if row else None

    async def claim(self, claim: ConnectorInvocationEvidenceClaim) -> bool:
        payload = ConnectorInvocationEvidenceService._normalize(asdict(claim))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorInvocationEvidenceClaimModel(
                        claim_id=claim.claim_id,
                        source_invocation_id=claim.source_invocation_id,
                        ingestion_id=claim.ingestion_id,
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

    async def add(self, record: ConnectorInvocationEvidenceRecord) -> bool:
        payload = ConnectorInvocationEvidenceService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorInvocationEvidenceModel(
                        ingestion_id=record.ingestion_id,
                        claim_id=record.claim_id,
                        source_invocation_id=record.source_invocation_id,
                        instance_id=record.instance_id,
                        capability_id=record.capability_id,
                        evidence_package_id=record.evidence_package_id,
                        ingested_by=record.ingested_by,
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
    def _claim_to_domain(raw: dict[str, Any]) -> ConnectorInvocationEvidenceClaim:
        payload = dict(raw)
        payload["claimed_at"] = datetime.fromisoformat(str(payload["claimed_at"]))
        return ConnectorInvocationEvidenceClaim(**cast(Any, payload))

    @staticmethod
    def _record_to_domain(raw: dict[str, Any]) -> ConnectorInvocationEvidenceRecord:
        payload = dict(raw)
        for field in ("observed_from", "observed_to", "ingested_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return ConnectorInvocationEvidenceRecord(**cast(Any, payload))
