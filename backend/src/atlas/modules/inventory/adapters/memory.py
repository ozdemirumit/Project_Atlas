from __future__ import annotations

import asyncio

from atlas.modules.inventory.domain.devices import (
    InventoryDeviceLifecycle,
    InventoryDeviceRecord,
)


class InMemoryInventoryDeviceRepository:
    def __init__(self) -> None:
        self._records: dict[str, InventoryDeviceRecord] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, device_id: str) -> InventoryDeviceRecord | None:
        return self._records.get(device_id)

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        lifecycle: InventoryDeviceLifecycle | None,
        query: str | None,
        limit: int,
    ) -> tuple[InventoryDeviceRecord, ...]:
        needle = query.casefold() if query else None
        records = [
            record
            for record in self._records.values()
            if record.organization_id == organization_id
            and record.environment_id == environment_id
            and (lifecycle is None or record.lifecycle is lifecycle)
            and (
                needle is None
                or needle
                in " ".join(
                    filter(
                        None,
                        (
                            record.device_key,
                            record.display_name,
                            record.vendor,
                            record.model,
                            record.serial_number,
                            record.management_address,
                        ),
                    )
                ).casefold()
            )
        ]
        records.sort(key=lambda record: (record.updated_at, record.device_id), reverse=True)
        return tuple(records[:limit])

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, device_key: str
    ) -> InventoryDeviceRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.organization_id == organization_id
                and record.environment_id == environment_id
                and record.device_key == device_key
            ),
            None,
        )

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> InventoryDeviceRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.created_by == created_by
                and record.create_idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_by_retirement_key(
        self, *, retired_by: str, idempotency_key: str
    ) -> InventoryDeviceRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.retired_by == retired_by
                and record.retirement_idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, record: InventoryDeviceRecord) -> bool:
        async with self._lock:
            if record.device_id in self._records or any(
                (
                    existing.organization_id == record.organization_id
                    and existing.environment_id == record.environment_id
                    and existing.device_key == record.device_key
                )
                or (
                    existing.created_by == record.created_by
                    and existing.create_idempotency_key == record.create_idempotency_key
                )
                for existing in self._records.values()
            ):
                return False
            self._records[record.device_id] = record
            return True

    async def update(self, record: InventoryDeviceRecord, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._records.get(record.device_id)
            if current is None or current.version != expected_version:
                return False
            if record.retirement_idempotency_key and any(
                existing.device_id != record.device_id
                and existing.retired_by == record.retired_by
                and existing.retirement_idempotency_key == record.retirement_idempotency_key
                for existing in self._records.values()
            ):
                return False
            self._records[record.device_id] = record
            return True

    async def close(self) -> None:
        return None
