from __future__ import annotations

from typing import Protocol

from atlas.modules.inventory.domain.devices import (
    InventoryDeviceLifecycle,
    InventoryDeviceRecord,
)


class InventoryDeviceRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, device_id: str) -> InventoryDeviceRecord | None: ...

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        lifecycle: InventoryDeviceLifecycle | None,
        query: str | None,
        limit: int,
    ) -> tuple[InventoryDeviceRecord, ...]: ...

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, device_key: str
    ) -> InventoryDeviceRecord | None: ...

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> InventoryDeviceRecord | None: ...

    async def get_by_retirement_key(
        self, *, retired_by: str, idempotency_key: str
    ) -> InventoryDeviceRecord | None: ...

    async def add(self, record: InventoryDeviceRecord) -> bool: ...

    async def update(self, record: InventoryDeviceRecord, *, expected_version: int) -> bool: ...

    async def close(self) -> None: ...
