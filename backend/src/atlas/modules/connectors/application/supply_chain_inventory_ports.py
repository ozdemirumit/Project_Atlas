from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)
from atlas.modules.connectors.domain.validation_intake import ConnectorPackageValidation


class PackageSupplyChainInventoryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PackageSupplyChainInventoryRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(
        self, *, inventory_id: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...

    async def get_by_validation(
        self, *, source_validation_id: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...

    async def get_by_create_key(
        self, *, inventoried_by: str, idempotency_key: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...

    async def add(self, inventory: ConnectorPackageSupplyChainInventory) -> bool: ...

    async def close(self) -> None: ...


class PackageValidationSource(Protocol):
    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageValidation | None: ...


class InventoryAcquisitionSource(Protocol):
    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...


class InventoryArchiveSource(Protocol):
    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...
