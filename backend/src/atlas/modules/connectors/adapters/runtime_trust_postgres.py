from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorRuntimeTrustGrantModel
from atlas.modules.connectors.application.runtime_trust import ConnectorRuntimeTrustService
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord


class PostgreSQLConnectorRuntimeTrustRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorRuntimeTrustRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, grant_id: str) -> ConnectorRuntimeTrustGrantRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorRuntimeTrustGrantModel, grant_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_enablement(
        self, *, source_enablement_id: str
    ) -> ConnectorRuntimeTrustGrantRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeTrustGrantModel).where(
                    ConnectorRuntimeTrustGrantModel.source_enablement_id == source_enablement_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, granted_by: str, idempotency_key: str
    ) -> ConnectorRuntimeTrustGrantRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeTrustGrantModel).where(
                    ConnectorRuntimeTrustGrantModel.granted_by == granted_by,
                    ConnectorRuntimeTrustGrantModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorRuntimeTrustGrantRecord) -> bool:
        payload = ConnectorRuntimeTrustService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorRuntimeTrustGrantModel(
                        grant_id=record.grant_id,
                        source_enablement_id=record.source_enablement_id,
                        instance_id=record.instance_id,
                        runtime_profile_id=record.runtime_profile_id,
                        granted_by=record.granted_by,
                        idempotency_key=record.idempotency_key,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorRuntimeTrustGrantRecord:
        payload = dict(raw)
        payload["granted_at"] = datetime.fromisoformat(payload["granted_at"])
        return ConnectorRuntimeTrustGrantRecord(**cast(Any, payload))
