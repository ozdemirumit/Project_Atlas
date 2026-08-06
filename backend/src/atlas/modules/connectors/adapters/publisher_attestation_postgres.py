from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPublisherAttestationModel
from atlas.modules.connectors.application.publisher_attestation import PublisherAttestationService
from atlas.modules.connectors.domain.publisher_attestation import (
    ConnectorPublisherAttestationReport,
    PublisherAttestationOutcome,
)


class PostgreSQLPublisherAttestationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPublisherAttestationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, report_id: str) -> ConnectorPublisherAttestationReport | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPublisherAttestationModel, report_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_approval(
        self, *, source_approval_request_id: str
    ) -> ConnectorPublisherAttestationReport | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPublisherAttestationModel).where(
                    ConnectorPublisherAttestationModel.source_approval_request_id
                    == source_approval_request_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, verified_by: str, idempotency_key: str
    ) -> ConnectorPublisherAttestationReport | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPublisherAttestationModel).where(
                    ConnectorPublisherAttestationModel.verified_by == verified_by,
                    ConnectorPublisherAttestationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, report: ConnectorPublisherAttestationReport) -> bool:
        payload = PublisherAttestationService._normalize(asdict(report))
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPublisherAttestationModel(
                        report_id=report.report_id,
                        source_approval_request_id=report.source_approval_request_id,
                        verified_by=report.verified_by,
                        idempotency_key=report.idempotency_key,
                        organization_id=report.organization_id,
                        environment_id=report.environment_id,
                        canonical_digest=report.canonical_digest,
                        payload=payload,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, object]) -> ConnectorPublisherAttestationReport:
        payload = dict(raw)
        payload["support_expires_at"] = datetime.fromisoformat(str(payload["support_expires_at"]))
        payload["verified_at"] = datetime.fromisoformat(str(payload["verified_at"]))
        payload["check_codes"] = tuple(cast(list[str], payload["check_codes"]))
        payload["reason_codes"] = tuple(cast(list[str], payload["reason_codes"]))
        payload["outcome"] = PublisherAttestationOutcome(str(payload["outcome"]))
        return ConnectorPublisherAttestationReport(**cast(Any, payload))
