from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageRegistrationRecordModel
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
    ConnectorRegisteredCapability,
    ConnectorRegisteredManifestSnapshot,
)


class PostgreSQLPackageRegistrationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageRegistrationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, record_id: str) -> ConnectorPackageRegistrationRecord | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageRegistrationRecordModel, record_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_publication_receipt(
        self, *, source_publication_receipt_id: str
    ) -> ConnectorPackageRegistrationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageRegistrationRecordModel).where(
                    ConnectorPackageRegistrationRecordModel.source_publication_receipt_id
                    == source_publication_receipt_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_package_release(
        self, *, connector_id: str, release_version: str
    ) -> ConnectorPackageRegistrationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageRegistrationRecordModel).where(
                    ConnectorPackageRegistrationRecordModel.connector_id == connector_id,
                    ConnectorPackageRegistrationRecordModel.release_version == release_version,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, registered_by: str, idempotency_key: str
    ) -> ConnectorPackageRegistrationRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageRegistrationRecordModel).where(
                    ConnectorPackageRegistrationRecordModel.registered_by == registered_by,
                    ConnectorPackageRegistrationRecordModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: ConnectorPackageRegistrationRecord) -> bool:
        payload = PackageRegistrationService._normalize(asdict(record))
        assert isinstance(payload, dict)
        async with self._sessions() as session:
            try:
                session.add(
                    ConnectorPackageRegistrationRecordModel(
                        record_id=record.record_id,
                        source_publication_receipt_id=record.source_publication_receipt_id,
                        connector_id=record.connector_id,
                        release_version=record.release_version,
                        registered_by=record.registered_by,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorPackageRegistrationRecord:
        payload = dict(raw)
        manifest_payload = dict(cast(dict[str, object], payload["manifest"]))
        capabilities = tuple(
            ConnectorRegisteredCapability(**cast(Any, item))
            for item in cast(list[dict[str, object]], manifest_payload["capabilities"])
        )
        for field in ("target_products", "network_destinations"):
            manifest_payload[field] = tuple(cast(list[str], manifest_payload[field]))
        manifest_payload["capabilities"] = capabilities
        payload["manifest"] = ConnectorRegisteredManifestSnapshot(**cast(Any, manifest_payload))
        payload["registered_at"] = datetime.fromisoformat(str(payload["registered_at"]))
        return ConnectorPackageRegistrationRecord(**cast(Any, payload))
