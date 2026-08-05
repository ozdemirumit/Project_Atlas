from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)


class InMemoryPackageSupplyChainInventoryRepository:
    durable = False

    def __init__(self) -> None:
        self._records: dict[str, ConnectorPackageSupplyChainInventory] = {}
        self._lock = asyncio.Lock()

    async def get_by_id(self, *, inventory_id: str) -> ConnectorPackageSupplyChainInventory | None:
        return self._records.get(inventory_id)

    async def get_by_validation(
        self, *, source_validation_id: str
    ) -> ConnectorPackageSupplyChainInventory | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.source_validation_id == source_validation_id
            ),
            None,
        )

    async def get_by_create_key(
        self, *, inventoried_by: str, idempotency_key: str
    ) -> ConnectorPackageSupplyChainInventory | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.inventoried_by == inventoried_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, inventory: ConnectorPackageSupplyChainInventory) -> bool:
        async with self._lock:
            if inventory.inventory_id in self._records:
                return False
            if any(
                item.source_validation_id == inventory.source_validation_id
                or (
                    item.inventoried_by == inventory.inventoried_by
                    and item.idempotency_key == inventory.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[inventory.inventory_id] = inventory
            return True

    async def close(self) -> None:
        return None
