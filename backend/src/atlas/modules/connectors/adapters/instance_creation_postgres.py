from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorInstanceRecordModel
from atlas.modules.connectors.application.instance_creation import ConnectorInstanceCreationService
from atlas.modules.connectors.domain.instance_creation import ConnectorInstanceRecord


class PostgreSQLConnectorInstanceRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorInstanceRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, record_id: str) -> ConnectorInstanceRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorInstanceRecordModel, record_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, instance_key: str
    ) -> ConnectorInstanceRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInstanceRecordModel).where(
                    ConnectorInstanceRecordModel.organization_id == organization_id,
                    ConnectorInstanceRecordModel.environment_id == environment_id,
                    ConnectorInstanceRecordModel.instance_key == instance_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> ConnectorInstanceRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInstanceRecordModel).where(
                    ConnectorInstanceRecordModel.created_by == created_by,
                    ConnectorInstanceRecordModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorInstanceRecord) -> bool:
        payload = ConnectorInstanceCreationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        async with self._sessions() as session:
            try:
                session.add(
                    ConnectorInstanceRecordModel(
                        record_id=record.record_id,
                        instance_id=record.instance_id,
                        instance_key=record.instance_key,
                        source_installation_receipt_id=record.source_installation_receipt_id,
                        connector_id=record.connector_id,
                        release_version=record.release_version,
                        created_by=record.created_by,
                        idempotency_key=record.idempotency_key,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        canonical_digest=record.canonical_digest,
                        payload=payload,
                    )
                )
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, Any]) -> ConnectorInstanceRecord:
        payload = dict(raw)
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        return ConnectorInstanceRecord(**cast(Any, payload))
