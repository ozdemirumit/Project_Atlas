from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorRuntimeActivationModel
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
)
from atlas.modules.connectors.domain.runtime_activation import (
    ConnectorRuntimeActivationRecord,
    ConnectorRuntimeHealthProbeResult,
)


class PostgreSQLConnectorRuntimeActivationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorRuntimeActivationRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, activation_id: str) -> ConnectorRuntimeActivationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorRuntimeActivationModel, activation_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_brokerage_authorization(
        self, *, source_brokerage_authorization_id: str
    ) -> ConnectorRuntimeActivationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeActivationModel).where(
                    ConnectorRuntimeActivationModel.source_brokerage_authorization_id
                    == source_brokerage_authorization_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, activated_by: str, idempotency_key: str
    ) -> ConnectorRuntimeActivationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRuntimeActivationModel).where(
                    ConnectorRuntimeActivationModel.activated_by == activated_by,
                    ConnectorRuntimeActivationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorRuntimeActivationRecord) -> bool:
        payload = ConnectorRuntimeActivationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorRuntimeActivationModel(
                        activation_id=record.activation_id,
                        source_brokerage_authorization_id=(
                            record.source_brokerage_authorization_id
                        ),
                        instance_id=record.instance_id,
                        activation_profile_id=record.activation_profile_id,
                        activated_by=record.activated_by,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorRuntimeActivationRecord:
        payload = dict(raw)
        for field in ("activated_at", "healthy_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        payload["health_probe_results"] = tuple(
            ConnectorRuntimeHealthProbeResult(**item) for item in payload["health_probe_results"]
        )
        return ConnectorRuntimeActivationRecord(**cast(Any, payload))
