from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageSigningReceiptModel
from atlas.modules.connectors.application.package_signing import PackageSigningService
from atlas.modules.connectors.domain.package_signing import (
    ConnectorPackageSignatureResult,
    ConnectorPackageSigningEnvelope,
    ConnectorPackageSigningReceipt,
)


class PostgreSQLPackageSigningRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageSigningRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, receipt_id: str) -> ConnectorPackageSigningReceipt | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageSigningReceiptModel, receipt_id)
            return self._to_domain(row.payload) if row else None

    async def get_by_attestation(
        self, *, source_attestation_report_id: str
    ) -> ConnectorPackageSigningReceipt | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageSigningReceiptModel).where(
                    ConnectorPackageSigningReceiptModel.source_attestation_report_id
                    == source_attestation_report_id
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorPackageSigningReceipt | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageSigningReceiptModel).where(
                    ConnectorPackageSigningReceiptModel.requested_by == requested_by,
                    ConnectorPackageSigningReceiptModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, receipt: ConnectorPackageSigningReceipt) -> bool:
        payload = PackageSigningService._normalize(asdict(receipt))
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPackageSigningReceiptModel(
                        receipt_id=receipt.receipt_id,
                        source_attestation_report_id=receipt.envelope.source_attestation_report_id,
                        requested_by=receipt.requested_by,
                        idempotency_key=receipt.idempotency_key,
                        organization_id=receipt.organization_id,
                        environment_id=receipt.environment_id,
                        canonical_digest=receipt.canonical_digest,
                        payload=payload,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, object]) -> ConnectorPackageSigningReceipt:
        payload = dict(raw)
        envelope_raw = cast(dict[str, object], payload["envelope"])
        envelope_payload = dict(envelope_raw)
        envelope_payload["created_at"] = datetime.fromisoformat(str(envelope_payload["created_at"]))
        signature_raw = cast(dict[str, object], payload["signature"])
        signature_payload = dict(signature_raw)
        signature_payload["issued_at"] = datetime.fromisoformat(str(signature_payload["issued_at"]))
        signature_payload["expires_at"] = datetime.fromisoformat(
            str(signature_payload["expires_at"])
        )
        payload["envelope"] = ConnectorPackageSigningEnvelope(**cast(Any, envelope_payload))
        payload["signature"] = ConnectorPackageSignatureResult(**cast(Any, signature_payload))
        payload["signed_at"] = datetime.fromisoformat(str(payload["signed_at"]))
        return ConnectorPackageSigningReceipt(**cast(Any, payload))
