from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorInvocationAuthorizationModel
from atlas.modules.connectors.application.invocation_authorization import (
    ConnectorInvocationAuthorizationService,
)
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationRecord,
)


class PostgreSQLConnectorInvocationAuthorizationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorInvocationAuthorizationRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, authorization_id: str) -> ConnectorInvocationAuthorizationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorInvocationAuthorizationModel, authorization_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_target_session(
        self, *, source_target_session_verification_id: str
    ) -> ConnectorInvocationAuthorizationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationAuthorizationModel).where(
                    ConnectorInvocationAuthorizationModel.source_target_session_verification_id
                    == source_target_session_verification_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, authorized_by: str, idempotency_key: str
    ) -> ConnectorInvocationAuthorizationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationAuthorizationModel).where(
                    ConnectorInvocationAuthorizationModel.authorized_by == authorized_by,
                    ConnectorInvocationAuthorizationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorInvocationAuthorizationRecord) -> bool:
        payload = ConnectorInvocationAuthorizationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorInvocationAuthorizationModel(
                        authorization_id=record.authorization_id,
                        source_target_session_verification_id=(
                            record.source_target_session_verification_id
                        ),
                        instance_id=record.instance_id,
                        capability_id=record.capability_id,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorInvocationAuthorizationRecord:
        payload = dict(raw)
        for field in ("authorized_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return ConnectorInvocationAuthorizationRecord(**cast(Any, payload))
