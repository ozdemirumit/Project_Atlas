from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageInstallationReceiptModel
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationReceipt,
    ConnectorPackageInstallationResult,
)


class PostgreSQLPackageInstallationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageInstallationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, receipt_id: str) -> ConnectorPackageInstallationReceipt | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageInstallationReceiptModel, receipt_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_registration_record(
        self, *, source_registration_record_id: str
    ) -> ConnectorPackageInstallationReceipt | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageInstallationReceiptModel).where(
                    ConnectorPackageInstallationReceiptModel.source_registration_record_id
                    == source_registration_record_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_package_release(
        self, *, connector_id: str, release_version: str
    ) -> ConnectorPackageInstallationReceipt | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageInstallationReceiptModel).where(
                    ConnectorPackageInstallationReceiptModel.connector_id == connector_id,
                    ConnectorPackageInstallationReceiptModel.release_version == release_version,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, installed_by: str, idempotency_key: str
    ) -> ConnectorPackageInstallationReceipt | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageInstallationReceiptModel).where(
                    ConnectorPackageInstallationReceiptModel.installed_by == installed_by,
                    ConnectorPackageInstallationReceiptModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorPackageInstallationReceipt, ...]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(ConnectorPackageInstallationReceiptModel)
                .where(
                    ConnectorPackageInstallationReceiptModel.organization_id == organization_id,
                    ConnectorPackageInstallationReceiptModel.environment_id == environment_id,
                )
                .order_by(
                    ConnectorPackageInstallationReceiptModel.connector_id,
                    ConnectorPackageInstallationReceiptModel.release_version,
                    ConnectorPackageInstallationReceiptModel.receipt_id,
                )
            )
            return tuple(self._to_domain(row.payload) for row in rows)

    async def add(self, receipt: ConnectorPackageInstallationReceipt) -> bool:
        payload = PackageInstallationService._normalize(asdict(receipt))
        assert isinstance(payload, dict)
        async with self._sessions() as session:
            try:
                session.add(
                    ConnectorPackageInstallationReceiptModel(
                        receipt_id=receipt.receipt_id,
                        source_registration_record_id=receipt.source_registration_record_id,
                        connector_id=receipt.connector_id,
                        release_version=receipt.release_version,
                        installation_store_profile_id=(
                            receipt.installation.installation_store_profile_id
                        ),
                        installed_by=receipt.installed_by,
                        idempotency_key=receipt.idempotency_key,
                        organization_id=receipt.organization_id,
                        environment_id=receipt.environment_id,
                        canonical_digest=receipt.canonical_digest,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorPackageInstallationReceipt:
        payload = dict(raw)
        installation_payload = dict(cast(dict[str, object], payload["installation"]))
        installation_payload["stored_at"] = datetime.fromisoformat(
            str(installation_payload["stored_at"])
        )
        payload["installation"] = ConnectorPackageInstallationResult(
            **cast(Any, installation_payload)
        )
        payload["installed_at"] = datetime.fromisoformat(str(payload["installed_at"]))
        return ConnectorPackageInstallationReceipt(**cast(Any, payload))
