from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorTargetSessionVerificationModel
from atlas.modules.connectors.application.target_session import ConnectorTargetSessionService
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetConnectivityCheckResult,
    ConnectorTargetSessionVerificationRecord,
)


class PostgreSQLConnectorTargetSessionRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorTargetSessionRepository:
        return cls(create_async_engine(database_url))

    async def get(self, *, verification_id: str) -> ConnectorTargetSessionVerificationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorTargetSessionVerificationModel, verification_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_runtime_activation(
        self, *, source_runtime_activation_id: str
    ) -> ConnectorTargetSessionVerificationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetSessionVerificationModel).where(
                    ConnectorTargetSessionVerificationModel.source_runtime_activation_id
                    == source_runtime_activation_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, verified_by: str, idempotency_key: str
    ) -> ConnectorTargetSessionVerificationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorTargetSessionVerificationModel).where(
                    ConnectorTargetSessionVerificationModel.verified_by == verified_by,
                    ConnectorTargetSessionVerificationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorTargetSessionVerificationRecord) -> bool:
        payload = ConnectorTargetSessionService._normalize(asdict(record))
        assert isinstance(payload, dict)
        try:
            async with self._sessions() as session:
                session.add(
                    ConnectorTargetSessionVerificationModel(
                        verification_id=record.verification_id,
                        source_runtime_activation_id=record.source_runtime_activation_id,
                        instance_id=record.instance_id,
                        session_profile_id=record.session_profile_id,
                        verified_by=record.verified_by,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorTargetSessionVerificationRecord:
        payload = dict(raw)
        payload["verified_at"] = datetime.fromisoformat(str(payload["verified_at"]))
        payload["connectivity_check_results"] = tuple(
            ConnectorTargetConnectivityCheckResult(**item)
            for item in payload["connectivity_check_results"]
        )
        return ConnectorTargetSessionVerificationRecord(**cast(Any, payload))
