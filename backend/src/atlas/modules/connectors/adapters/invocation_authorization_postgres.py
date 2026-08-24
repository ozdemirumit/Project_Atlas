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

    async def get_in_scope(
        self, *, authorization_id: str, organization_id: str, environment_id: str
    ) -> ConnectorInvocationAuthorizationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationAuthorizationModel).where(
                    ConnectorInvocationAuthorizationModel.authorization_id == authorization_id,
                    ConnectorInvocationAuthorizationModel.organization_id == organization_id,
                    ConnectorInvocationAuthorizationModel.environment_id == environment_id,
                )
            )
            return self._row_to_domain(row) if row else None

    async def get_by_target_session_in_scope(
        self,
        *,
        source_target_session_verification_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationAuthorizationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationAuthorizationModel).where(
                    ConnectorInvocationAuthorizationModel.source_target_session_verification_id
                    == source_target_session_verification_id,
                    ConnectorInvocationAuthorizationModel.organization_id == organization_id,
                    ConnectorInvocationAuthorizationModel.environment_id == environment_id,
                )
            )
            return self._row_to_domain(row) if row else None

    async def get_by_create_key_in_scope(
        self,
        *,
        authorized_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorInvocationAuthorizationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorInvocationAuthorizationModel).where(
                    ConnectorInvocationAuthorizationModel.authorized_by == authorized_by,
                    ConnectorInvocationAuthorizationModel.idempotency_digest == idempotency_digest,
                    ConnectorInvocationAuthorizationModel.organization_id == organization_id,
                    ConnectorInvocationAuthorizationModel.environment_id == environment_id,
                )
            )
            return self._row_to_domain(row) if row else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorInvocationAuthorizationRecord, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ConnectorInvocationAuthorizationModel)
                    .where(
                        ConnectorInvocationAuthorizationModel.organization_id == organization_id,
                        ConnectorInvocationAuthorizationModel.environment_id == environment_id,
                    )
                    .order_by(ConnectorInvocationAuthorizationModel.authorization_id)
                )
            ).all()
            return tuple(self._row_to_domain(row) for row in rows)

    async def add(self, record: ConnectorInvocationAuthorizationRecord) -> bool:
        payload = self._storage_payload(record)
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
                        idempotency_digest=record.idempotency_digest,
                        replay_digest=record.replay_digest,
                        organization_id=record.organization_id,
                        environment_id=record.environment_id,
                        canonical_digest=record.canonical_digest,
                        payload=payload,
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(
        raw: dict[str, Any],
        *,
        replay_digest: str | None = None,
        idempotency_digest: str | None = None,
    ) -> ConnectorInvocationAuthorizationRecord:
        payload = dict(raw)
        legacy_replay = payload.pop("request_fingerprint", None)
        legacy_key = payload.pop("idempotency_key", None)
        payload["replay_digest"] = payload.pop("replay_digest", replay_digest or legacy_replay)
        payload["idempotency_digest"] = payload.pop(
            "idempotency_digest", idempotency_digest or legacy_key
        )
        payload["reused"] = False
        for field in ("authorized_at", "expires_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return ConnectorInvocationAuthorizationRecord(**cast(Any, payload))

    @classmethod
    def _row_to_domain(
        cls, row: ConnectorInvocationAuthorizationModel
    ) -> ConnectorInvocationAuthorizationRecord:
        return cls._to_domain(
            row.payload,
            replay_digest=row.replay_digest,
            idempotency_digest=row.idempotency_digest,
        )

    @staticmethod
    def _storage_payload(record: ConnectorInvocationAuthorizationRecord) -> dict[str, Any]:
        payload = asdict(record)
        for field in ("replay_digest", "idempotency_digest", "reused"):
            payload.pop(field)
        normalized = ConnectorInvocationAuthorizationService._normalize(payload)
        assert isinstance(normalized, dict)
        return cast(dict[str, Any], normalized)
