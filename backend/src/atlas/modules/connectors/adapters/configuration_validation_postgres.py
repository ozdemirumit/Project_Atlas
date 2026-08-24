from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorConfigurationValidationModel
from atlas.modules.connectors.application.configuration_validation import (
    ConnectorConfigurationValidationService,
)
from atlas.modules.connectors.domain.configuration_validation import (
    ConnectorConfigurationValidationRecord,
)


class PostgreSQLConnectorConfigurationValidationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorConfigurationValidationRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, validation_id: str) -> ConnectorConfigurationValidationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorConfigurationValidationModel, validation_id)
            return self._to_domain(row.payload) if row else None

    async def get_in_scope(
        self,
        *,
        validation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorConfigurationValidationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorConfigurationValidationModel).where(
                    ConnectorConfigurationValidationModel.validation_id == validation_id,
                    ConnectorConfigurationValidationModel.organization_id == organization_id,
                    ConnectorConfigurationValidationModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_assignment(
        self, *, source_assignment_id: str
    ) -> ConnectorConfigurationValidationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorConfigurationValidationModel).where(
                    ConnectorConfigurationValidationModel.source_assignment_id
                    == source_assignment_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_assignment_in_scope(
        self,
        *,
        source_assignment_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorConfigurationValidationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorConfigurationValidationModel).where(
                    ConnectorConfigurationValidationModel.source_assignment_id
                    == source_assignment_id,
                    ConnectorConfigurationValidationModel.organization_id == organization_id,
                    ConnectorConfigurationValidationModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorConfigurationValidationRecord, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ConnectorConfigurationValidationModel)
                    .where(
                        ConnectorConfigurationValidationModel.organization_id == organization_id,
                        ConnectorConfigurationValidationModel.environment_id == environment_id,
                    )
                    .order_by(ConnectorConfigurationValidationModel.validation_id)
                )
            ).all()
            return tuple(self._to_domain(row.payload) for row in rows)

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorConfigurationValidationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorConfigurationValidationModel).where(
                    ConnectorConfigurationValidationModel.validated_by == validated_by,
                    ConnectorConfigurationValidationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key_in_scope(
        self,
        *,
        validated_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorConfigurationValidationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorConfigurationValidationModel).where(
                    ConnectorConfigurationValidationModel.validated_by == validated_by,
                    ConnectorConfigurationValidationModel.idempotency_key == idempotency_key,
                    ConnectorConfigurationValidationModel.organization_id == organization_id,
                    ConnectorConfigurationValidationModel.environment_id == environment_id,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorConfigurationValidationRecord) -> bool:
        payload = ConnectorConfigurationValidationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorConfigurationValidationModel(
                        validation_id=record.validation_id,
                        source_assignment_id=record.source_assignment_id,
                        instance_id=record.instance_id,
                        evidence_id=record.evidence_id,
                        validated_by=record.validated_by,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorConfigurationValidationRecord:
        payload = dict(raw)
        payload["completed_checks"] = tuple(payload["completed_checks"])
        for field in ("evidence_observed_at", "validated_at"):
            payload[field] = datetime.fromisoformat(payload[field])
        return ConnectorConfigurationValidationRecord(**cast(Any, payload))
