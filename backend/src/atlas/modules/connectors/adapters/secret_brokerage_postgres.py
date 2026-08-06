from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorSecretBrokerageAuthorizationModel
from atlas.modules.connectors.application.secret_brokerage import (
    ConnectorSecretBrokerageService,
)
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)


class PostgreSQLConnectorSecretBrokerageRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorSecretBrokerageRepository:
        return cls(create_async_engine(database_url))

    async def get(
        self, *, authorization_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorSecretBrokerageAuthorizationModel, authorization_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_runtime_trust(
        self, *, source_runtime_trust_grant_id: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorSecretBrokerageAuthorizationModel).where(
                    ConnectorSecretBrokerageAuthorizationModel.source_runtime_trust_grant_id
                    == source_runtime_trust_grant_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, authorized_by: str, idempotency_key: str
    ) -> ConnectorSecretBrokerageAuthorizationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorSecretBrokerageAuthorizationModel).where(
                    ConnectorSecretBrokerageAuthorizationModel.authorized_by == authorized_by,
                    ConnectorSecretBrokerageAuthorizationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorSecretBrokerageAuthorizationRecord) -> bool:
        payload = ConnectorSecretBrokerageService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorSecretBrokerageAuthorizationModel(
                        authorization_id=record.authorization_id,
                        source_runtime_trust_grant_id=record.source_runtime_trust_grant_id,
                        instance_id=record.instance_id,
                        brokerage_profile_id=record.brokerage_profile_id,
                        authorized_by=record.authorized_by,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorSecretBrokerageAuthorizationRecord:
        payload = dict(raw)
        for field in ("next_rotation_at", "authorized_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return ConnectorSecretBrokerageAuthorizationRecord(**cast(Any, payload))
