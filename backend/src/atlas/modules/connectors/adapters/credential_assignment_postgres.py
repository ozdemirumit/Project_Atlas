from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorCredentialAssignmentModel
from atlas.modules.connectors.application.credential_assignment import (
    ConnectorCredentialAssignmentService,
)
from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentRecord,
)


class PostgreSQLConnectorCredentialAssignmentRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorCredentialAssignmentRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, assignment_id: str) -> ConnectorCredentialAssignmentRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorCredentialAssignmentModel, assignment_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_target_binding(
        self, *, source_target_binding_id: str
    ) -> ConnectorCredentialAssignmentRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorCredentialAssignmentModel).where(
                    ConnectorCredentialAssignmentModel.source_target_binding_id
                    == source_target_binding_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, assigned_by: str, idempotency_key: str
    ) -> ConnectorCredentialAssignmentRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorCredentialAssignmentModel).where(
                    ConnectorCredentialAssignmentModel.assigned_by == assigned_by,
                    ConnectorCredentialAssignmentModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorCredentialAssignmentRecord) -> bool:
        payload = ConnectorCredentialAssignmentService._normalize(asdict(record))
        assert isinstance(payload, dict)
        async with self._sessions() as session:
            try:
                session.add(
                    ConnectorCredentialAssignmentModel(
                        assignment_id=record.assignment_id,
                        source_target_binding_id=record.source_target_binding_id,
                        instance_id=record.instance_id,
                        credential_profile_id=record.credential_profile_id,
                        assigned_by=record.assigned_by,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorCredentialAssignmentRecord:
        payload = dict(raw)
        for field in ("next_rotation_at", "assigned_at"):
            payload[field] = datetime.fromisoformat(str(payload[field]))
        return ConnectorCredentialAssignmentRecord(**cast(Any, payload))
