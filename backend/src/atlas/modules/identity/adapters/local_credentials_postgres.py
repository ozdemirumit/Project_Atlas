from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import LocalCredentialModel, LocalRecoveryActivationModel
from atlas.modules.identity.domain.local_credentials import (
    LocalCredentialRecord,
    LocalRecoveryActivation,
)


def _normalize(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


class PostgreSQLLocalCredentialRepository:
    """Durable `LocalCredentialRepository` implementation, closing the sole real gap in the
    otherwise-complete ATLAS-030 local bootstrap/recovery credential subsystem: the admin account
    previously lived only in process memory and did not survive a restart."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLLocalCredentialRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    async def get(self, subject_id: str) -> LocalCredentialRecord | None:
        async with self._sessions() as session:
            row = await session.get(LocalCredentialModel, subject_id)
            return self._record_to_domain(row.payload) if row is not None else None

    async def create(self, record: LocalCredentialRecord) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    LocalCredentialModel(
                        subject_id=record.subject_id,
                        organization_id=record.organization_id,
                        version=record.version,
                        payload=cast(dict[str, Any], _normalize(asdict(record))),
                    )
                )
        except IntegrityError:
            return False
        return True

    async def update(self, record: LocalCredentialRecord, *, expected_version: int) -> bool:
        async with self._sessions.begin() as session:
            row = await session.get(LocalCredentialModel, record.subject_id)
            if row is None or row.version != expected_version:
                return False
            row.version = record.version
            row.payload = cast(dict[str, Any], _normalize(asdict(record)))
        return True

    async def get_recovery_activation(self, subject_id: str) -> LocalRecoveryActivation | None:
        async with self._sessions() as session:
            row = await session.get(LocalRecoveryActivationModel, subject_id)
            return self._activation_to_domain(row.payload) if row is not None else None

    async def save_recovery_activation(self, activation: LocalRecoveryActivation) -> None:
        payload = cast(dict[str, Any], _normalize(asdict(activation)))
        async with self._sessions.begin() as session:
            row = await session.get(LocalRecoveryActivationModel, activation.subject_id)
            if row is None:
                session.add(
                    LocalRecoveryActivationModel(subject_id=activation.subject_id, payload=payload)
                )
            else:
                row.payload = payload

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _record_to_domain(raw: dict[str, object]) -> LocalCredentialRecord:
        payload = dict(raw)
        payload["role_ids"] = tuple(cast(list[str], payload["role_ids"]))
        for field in ("created_at", "updated_at", "locked_until", "last_used_at"):
            if payload.get(field) is not None:
                payload[field] = datetime.fromisoformat(str(payload[field]))
        return LocalCredentialRecord(**cast(Any, payload))

    @staticmethod
    def _activation_to_domain(raw: dict[str, object]) -> LocalRecoveryActivation:
        payload = dict(raw)
        for field in ("activated_at", "expires_at", "used_at", "reviewed_at"):
            if payload.get(field) is not None:
                payload[field] = datetime.fromisoformat(str(payload[field]))
        return LocalRecoveryActivation(**cast(Any, payload))
