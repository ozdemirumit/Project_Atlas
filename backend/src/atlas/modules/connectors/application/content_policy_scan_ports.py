from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.content_policy_scan import ConnectorPackageContentPolicyScan
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)


class PackageContentPolicyScanError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PackageContentPolicyScanRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, scan_id: str) -> ConnectorPackageContentPolicyScan | None: ...

    async def get_by_inventory(
        self, *, source_inventory_id: str
    ) -> ConnectorPackageContentPolicyScan | None: ...

    async def get_by_create_key(
        self, *, scanned_by: str, idempotency_key: str
    ) -> ConnectorPackageContentPolicyScan | None: ...

    async def add(self, scan: ConnectorPackageContentPolicyScan) -> bool: ...

    async def close(self) -> None: ...


class ContentPolicyInventorySource(Protocol):
    async def get_by_id(
        self, *, inventory_id: str
    ) -> ConnectorPackageSupplyChainInventory | None: ...


class ContentPolicyAcquisitionSource(Protocol):
    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...


class ContentPolicyArchiveSource(Protocol):
    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...
