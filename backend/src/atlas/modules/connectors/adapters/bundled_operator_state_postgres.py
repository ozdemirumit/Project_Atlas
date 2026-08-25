from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import (
    BundledConnectionConfigurationModel,
    BundledConnectorRuntimeStateModel,
    ConnectorConnectionTestResultModel,
)
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.bundled_runtime_state_ports import (
    BundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorConnectionTestResultRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import (
    BundledConnectorRuntimeState,
)
from atlas.modules.connectors.domain.connection_test import ConnectorConnectionTestResult


def _payload(
    record: BundledConnectionConfiguration
    | ConnectorConnectionTestResult
    | BundledConnectorRuntimeState,
) -> dict[str, Any]:
    payload = asdict(record)
    for key, value in tuple(payload.items()):
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return payload


class PostgreSQLBundledConnectionConfigurationRepository(BundledConnectionConfigurationRepository):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLBundledConnectionConfigurationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[BundledConnectionConfiguration, ...]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(BundledConnectionConfigurationModel)
                .where(
                    BundledConnectionConfigurationModel.organization_id == organization_id,
                    BundledConnectionConfigurationModel.environment_id == environment_id,
                )
                .order_by(BundledConnectionConfigurationModel.instance_id)
            )
            return tuple(self._to_domain(row.payload) for row in rows)

    async def get(
        self, *, organization_id: str, environment_id: str, instance_id: str
    ) -> BundledConnectionConfiguration | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(BundledConnectionConfigurationModel).where(
                    BundledConnectionConfigurationModel.organization_id == organization_id,
                    BundledConnectionConfigurationModel.environment_id == environment_id,
                    BundledConnectionConfigurationModel.instance_id == instance_id,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def put(self, record: BundledConnectionConfiguration) -> None:
        values = {
            "configuration_id": record.configuration_id,
            "organization_id": record.organization_id,
            "environment_id": record.environment_id,
            "connector_id": record.connector_id,
            "instance_id": record.instance_id,
            "configured_at": record.configured_at,
            "payload": _payload(record),
        }
        statement = insert(BundledConnectionConfigurationModel).values(**values)
        statement = statement.on_conflict_do_update(
            constraint="uq_bundled_connection_configurations_scope_instance",
            set_=values,
        )
        async with self._sessions() as session:
            await session.execute(statement)
            await session.commit()

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, Any]) -> BundledConnectionConfiguration:
        payload = dict(raw)
        payload["configured_at"] = datetime.fromisoformat(str(payload["configured_at"]))
        return BundledConnectionConfiguration(**cast(Any, payload))


class PostgreSQLConnectorConnectionTestResultRepository(ConnectorConnectionTestResultRepository):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorConnectionTestResultRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def put(
        self,
        *,
        organization_id: str,
        environment_id: str,
        result: ConnectorConnectionTestResult,
    ) -> None:
        async with self._sessions() as session:
            session.add(
                ConnectorConnectionTestResultModel(
                    test_id=result.test_id,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    connector_id=result.connector_id,
                    instance_id=result.instance_id,
                    outcome=result.outcome,
                    checked_at=result.checked_at,
                    payload=_payload(result),
                )
            )
            await session.commit()

    async def get_latest(
        self,
        *,
        organization_id: str,
        environment_id: str,
        instance_id: str,
    ) -> ConnectorConnectionTestResult | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorConnectionTestResultModel)
                .where(
                    ConnectorConnectionTestResultModel.organization_id == organization_id,
                    ConnectorConnectionTestResultModel.environment_id == environment_id,
                    ConnectorConnectionTestResultModel.instance_id == instance_id,
                )
                .order_by(
                    ConnectorConnectionTestResultModel.checked_at.desc(),
                    ConnectorConnectionTestResultModel.test_id.desc(),
                )
                .limit(1)
            )
            return self._to_domain(row.payload) if row else None

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, Any]) -> ConnectorConnectionTestResult:
        payload = dict(raw)
        payload["checked_at"] = datetime.fromisoformat(str(payload["checked_at"]))
        return ConnectorConnectionTestResult(**cast(Any, payload))


class PostgreSQLBundledConnectorRuntimeStateRepository(BundledConnectorRuntimeStateRepository):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLBundledConnectorRuntimeStateRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(
        self, *, organization_id: str, environment_id: str, instance_id: str
    ) -> BundledConnectorRuntimeState | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(BundledConnectorRuntimeStateModel).where(
                    BundledConnectorRuntimeStateModel.organization_id == organization_id,
                    BundledConnectorRuntimeStateModel.environment_id == environment_id,
                    BundledConnectorRuntimeStateModel.instance_id == instance_id,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def put(self, record: BundledConnectorRuntimeState, *, expected_version: int) -> bool:
        values = {
            "organization_id": record.organization_id,
            "environment_id": record.environment_id,
            "connector_id": record.connector_id,
            "instance_id": record.instance_id,
            "state": record.state,
            "version": record.version,
            "changed_at": record.changed_at,
            "payload": _payload(record),
        }
        async with self._sessions() as session:
            if expected_version == 0:
                try:
                    session.add(BundledConnectorRuntimeStateModel(**values))
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    return False
                return True
            result = cast(
                CursorResult[Any],
                await session.execute(
                    update(BundledConnectorRuntimeStateModel)
                    .where(
                        BundledConnectorRuntimeStateModel.organization_id == record.organization_id,
                        BundledConnectorRuntimeStateModel.environment_id == record.environment_id,
                        BundledConnectorRuntimeStateModel.instance_id == record.instance_id,
                        BundledConnectorRuntimeStateModel.version == expected_version,
                    )
                    .values(**values)
                ),
            )
            await session.commit()
            return result.rowcount == 1

    async def clear(self, *, organization_id: str, environment_id: str, instance_id: str) -> None:
        async with self._sessions() as session:
            await session.execute(
                delete(BundledConnectorRuntimeStateModel).where(
                    BundledConnectorRuntimeStateModel.organization_id == organization_id,
                    BundledConnectorRuntimeStateModel.environment_id == environment_id,
                    BundledConnectorRuntimeStateModel.instance_id == instance_id,
                )
            )
            await session.commit()

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, Any]) -> BundledConnectorRuntimeState:
        payload = dict(raw)
        if payload.get("changed_at") is not None:
            payload["changed_at"] = datetime.fromisoformat(str(payload["changed_at"]))
        return BundledConnectorRuntimeState(**cast(Any, payload))
