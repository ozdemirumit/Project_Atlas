from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorTargetConfigurationBindingModel
from atlas.modules.connectors.application.target_configuration import (
    ConnectorTargetConfigurationService,
)
from atlas.modules.connectors.domain.target_configuration import (
    ConnectorTargetConfigurationBinding,
)


class PostgreSQLConnectorTargetConfigurationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorTargetConfigurationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, binding_id: str) -> ConnectorTargetConfigurationBinding | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorTargetConfigurationBindingModel, binding_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_instance(
        self, *, source_instance_record_id: str
    ) -> ConnectorTargetConfigurationBinding | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetConfigurationBindingModel).where(
                    ConnectorTargetConfigurationBindingModel.source_instance_record_id
                    == source_instance_record_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorTargetConfigurationBinding, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ConnectorTargetConfigurationBindingModel)
                    .where(
                        ConnectorTargetConfigurationBindingModel.organization_id == organization_id,
                        ConnectorTargetConfigurationBindingModel.environment_id == environment_id,
                    )
                    .order_by(ConnectorTargetConfigurationBindingModel.binding_id)
                )
            ).all()
            return tuple(self._to_domain(row.payload) for row in rows)

    async def get_by_create_key(
        self, *, bound_by: str, idempotency_key: str
    ) -> ConnectorTargetConfigurationBinding | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetConfigurationBindingModel).where(
                    ConnectorTargetConfigurationBindingModel.bound_by == bound_by,
                    ConnectorTargetConfigurationBindingModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, binding: ConnectorTargetConfigurationBinding) -> bool:
        payload = ConnectorTargetConfigurationService._normalize(asdict(binding))
        assert isinstance(payload, dict)
        async with self._sessions() as session:
            try:
                session.add(
                    ConnectorTargetConfigurationBindingModel(
                        binding_id=binding.binding_id,
                        source_instance_record_id=binding.source_instance_record_id,
                        instance_id=binding.instance_id,
                        target_profile_id=binding.target_profile_id,
                        target_id=binding.target_id,
                        bound_by=binding.bound_by,
                        idempotency_key=binding.idempotency_key,
                        organization_id=binding.organization_id,
                        environment_id=binding.environment_id,
                        canonical_digest=binding.canonical_digest,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorTargetConfigurationBinding:
        payload = dict(raw)
        payload["bound_at"] = datetime.fromisoformat(str(payload["bound_at"]))
        return ConnectorTargetConfigurationBinding(**cast(Any, payload))
