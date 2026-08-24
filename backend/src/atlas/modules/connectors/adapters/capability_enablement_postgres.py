from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorCapabilityEnablementModel
from atlas.modules.connectors.application.capability_enablement import (
    ConnectorCapabilityEnablementService,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
    ConnectorGovernedCapability,
)


class PostgreSQLConnectorCapabilityEnablementRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorCapabilityEnablementRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, enablement_id: str) -> ConnectorCapabilityEnablementRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorCapabilityEnablementModel, enablement_id)
            return self._to_domain(row.payload) if row else None

    async def get_in_scope(
        self,
        *,
        enablement_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorCapabilityEnablementModel).where(
                    ConnectorCapabilityEnablementModel.enablement_id == enablement_id,
                    ConnectorCapabilityEnablementModel.organization_id == organization_id,
                    ConnectorCapabilityEnablementModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_validation(
        self, *, source_validation_id: str
    ) -> ConnectorCapabilityEnablementRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorCapabilityEnablementModel).where(
                    ConnectorCapabilityEnablementModel.source_validation_id == source_validation_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_validation_in_scope(
        self,
        *,
        source_validation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorCapabilityEnablementModel).where(
                    ConnectorCapabilityEnablementModel.source_validation_id == source_validation_id,
                    ConnectorCapabilityEnablementModel.organization_id == organization_id,
                    ConnectorCapabilityEnablementModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorCapabilityEnablementRecord, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ConnectorCapabilityEnablementModel)
                    .where(
                        ConnectorCapabilityEnablementModel.organization_id == organization_id,
                        ConnectorCapabilityEnablementModel.environment_id == environment_id,
                    )
                    .order_by(ConnectorCapabilityEnablementModel.enablement_id)
                )
            ).all()
            return tuple(self._to_domain(row.payload) for row in rows)

    async def get_by_create_key(
        self, *, enabled_by: str, idempotency_key: str
    ) -> ConnectorCapabilityEnablementRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorCapabilityEnablementModel).where(
                    ConnectorCapabilityEnablementModel.enabled_by == enabled_by,
                    ConnectorCapabilityEnablementModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key_in_scope(
        self,
        *,
        enabled_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorCapabilityEnablementModel).where(
                    ConnectorCapabilityEnablementModel.enabled_by == enabled_by,
                    ConnectorCapabilityEnablementModel.idempotency_key == idempotency_key,
                    ConnectorCapabilityEnablementModel.organization_id == organization_id,
                    ConnectorCapabilityEnablementModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorCapabilityEnablementRecord) -> bool:
        payload = ConnectorCapabilityEnablementService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorCapabilityEnablementModel(
                        enablement_id=record.enablement_id,
                        source_validation_id=record.source_validation_id,
                        instance_id=record.instance_id,
                        capability_profile_id=record.capability_profile_id,
                        enabled_by=record.enabled_by,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorCapabilityEnablementRecord:
        payload = dict(raw)
        payload["capabilities"] = tuple(
            ConnectorGovernedCapability(**item) for item in payload["capabilities"]
        )
        payload["enabled_at"] = datetime.fromisoformat(payload["enabled_at"])
        return ConnectorCapabilityEnablementRecord(**cast(Any, payload))
