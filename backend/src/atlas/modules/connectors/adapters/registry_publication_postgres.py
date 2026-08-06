from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorRegistryPublicationReceiptModel
from atlas.modules.connectors.application.registry_publication import RegistryPublicationService
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
    ConnectorInternalRegistryPublicationResult,
    ConnectorPackageSignatureVerification,
)


class PostgreSQLRegistryPublicationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRegistryPublicationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, receipt_id: str) -> ConnectorInternalRegistryPublicationReceipt | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorRegistryPublicationReceiptModel, receipt_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_signing_receipt(
        self, *, source_signing_receipt_id: str
    ) -> ConnectorInternalRegistryPublicationReceipt | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRegistryPublicationReceiptModel).where(
                    ConnectorRegistryPublicationReceiptModel.source_signing_receipt_id
                    == source_signing_receipt_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorInternalRegistryPublicationReceipt | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorRegistryPublicationReceiptModel).where(
                    ConnectorRegistryPublicationReceiptModel.requested_by == requested_by,
                    ConnectorRegistryPublicationReceiptModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, receipt: ConnectorInternalRegistryPublicationReceipt) -> bool:
        payload = RegistryPublicationService._normalize(asdict(receipt))
        assert isinstance(payload, dict)
        async with self._sessions() as session:
            try:
                session.add(
                    ConnectorRegistryPublicationReceiptModel(
                        receipt_id=receipt.receipt_id,
                        source_signing_receipt_id=receipt.source_signing_receipt_id,
                        requested_by=receipt.requested_by,
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
    def _to_domain(raw: dict[str, Any]) -> ConnectorInternalRegistryPublicationReceipt:
        payload = dict(raw)
        verification = dict(cast(dict[str, object], payload["verification"]))
        publication = dict(cast(dict[str, object], payload["publication"]))
        if not isinstance(verification, dict) or not isinstance(publication, dict):
            raise ValueError("Registry publication persistence payload is invalid")
        verification["verified_at"] = datetime.fromisoformat(str(verification["verified_at"]))
        publication["published_at"] = datetime.fromisoformat(str(publication["published_at"]))
        payload["verification"] = ConnectorPackageSignatureVerification(**cast(Any, verification))
        payload["publication"] = ConnectorInternalRegistryPublicationResult(
            **cast(Any, publication)
        )
        payload["published_at"] = datetime.fromisoformat(str(payload["published_at"]))
        return ConnectorInternalRegistryPublicationReceipt(**cast(Any, payload))
