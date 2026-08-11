from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import InventoryDeviceRecordModel
from atlas.modules.inventory.application.service import InventoryDeviceService
from atlas.modules.inventory.domain.devices import (
    InventoryDeviceLifecycle,
    InventoryDeviceRecord,
    InventoryDeviceType,
)


class PostgreSQLInventoryDeviceRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLInventoryDeviceRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get(self, *, device_id: str) -> InventoryDeviceRecord | None:
        async with self._sessions() as session:
            row = await session.get(InventoryDeviceRecordModel, device_id)
            return self._to_domain(row.payload) if row else None

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        lifecycle: InventoryDeviceLifecycle | None,
        query: str | None,
        limit: int,
    ) -> tuple[InventoryDeviceRecord, ...]:
        statement = select(InventoryDeviceRecordModel).where(
            InventoryDeviceRecordModel.organization_id == organization_id,
            InventoryDeviceRecordModel.environment_id == environment_id,
        )
        if lifecycle is not None:
            statement = statement.where(InventoryDeviceRecordModel.lifecycle == lifecycle.value)
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(
                    InventoryDeviceRecordModel.device_key.ilike(pattern),
                    InventoryDeviceRecordModel.display_name.ilike(pattern),
                    InventoryDeviceRecordModel.vendor.ilike(pattern),
                    InventoryDeviceRecordModel.model.ilike(pattern),
                    InventoryDeviceRecordModel.serial_number.ilike(pattern),
                    InventoryDeviceRecordModel.management_address.ilike(pattern),
                )
            )
        statement = statement.order_by(
            InventoryDeviceRecordModel.updated_at.desc(),
            InventoryDeviceRecordModel.device_id.desc(),
        ).limit(limit)
        async with self._sessions() as session:
            rows = (await session.scalars(statement)).all()
            return tuple(self._to_domain(row.payload) for row in rows)

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, device_key: str
    ) -> InventoryDeviceRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(InventoryDeviceRecordModel).where(
                    InventoryDeviceRecordModel.organization_id == organization_id,
                    InventoryDeviceRecordModel.environment_id == environment_id,
                    InventoryDeviceRecordModel.device_key == device_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> InventoryDeviceRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(InventoryDeviceRecordModel).where(
                    InventoryDeviceRecordModel.created_by == created_by,
                    InventoryDeviceRecordModel.create_idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def get_by_retirement_key(
        self, *, retired_by: str, idempotency_key: str
    ) -> InventoryDeviceRecord | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(InventoryDeviceRecordModel).where(
                    InventoryDeviceRecordModel.retired_by == retired_by,
                    InventoryDeviceRecordModel.retirement_idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row else None

    async def add(self, record: InventoryDeviceRecord) -> bool:
        payload = InventoryDeviceService._normalize(asdict(record))
        assert isinstance(payload, dict)
        async with self._sessions() as session:
            try:
                session.add(self._model(record, cast(dict[str, Any], payload)))
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
        return True

    async def update(self, record: InventoryDeviceRecord, *, expected_version: int) -> bool:
        payload = InventoryDeviceService._normalize(asdict(record))
        assert isinstance(payload, dict)
        values = self._columns(record, cast(dict[str, Any], payload))
        async with self._sessions() as session:
            try:
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        update(InventoryDeviceRecordModel)
                        .where(
                            InventoryDeviceRecordModel.device_id == record.device_id,
                            InventoryDeviceRecordModel.version == expected_version,
                        )
                        .values(**values)
                    ),
                )
                if result.rowcount != 1:
                    await session.rollback()
                    return False
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _columns(record: InventoryDeviceRecord, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": record.version,
            "display_name": record.display_name,
            "vendor": record.vendor,
            "model": record.model,
            "serial_number": record.serial_number,
            "management_address": record.management_address,
            "lifecycle": record.lifecycle.value,
            "updated_at": record.updated_at,
            "retired_by": record.retired_by,
            "retirement_idempotency_key": record.retirement_idempotency_key,
            "canonical_digest": record.canonical_digest,
            "payload": payload,
        }

    @classmethod
    def _model(
        cls, record: InventoryDeviceRecord, payload: dict[str, Any]
    ) -> InventoryDeviceRecordModel:
        return InventoryDeviceRecordModel(
            device_id=record.device_id,
            device_key=record.device_key,
            version=record.version,
            display_name=record.display_name,
            device_type=record.device_type.value,
            vendor=record.vendor,
            model=record.model,
            serial_number=record.serial_number,
            management_address=record.management_address,
            lifecycle=record.lifecycle.value,
            created_by=record.created_by,
            create_idempotency_key=record.create_idempotency_key,
            updated_at=record.updated_at,
            retired_by=record.retired_by,
            retirement_idempotency_key=record.retirement_idempotency_key,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            site_id=record.site_id,
            canonical_digest=record.canonical_digest,
            payload=payload,
        )

    @staticmethod
    def _to_domain(raw: dict[str, Any]) -> InventoryDeviceRecord:
        payload = dict(raw)
        for field in ("created_at", "updated_at", "retired_at"):
            if payload.get(field) is not None:
                payload[field] = datetime.fromisoformat(str(payload[field]))
        payload["device_type"] = InventoryDeviceType(str(payload["device_type"]))
        payload["lifecycle"] = InventoryDeviceLifecycle(str(payload["lifecycle"]))
        return InventoryDeviceRecord(**cast(Any, payload))
