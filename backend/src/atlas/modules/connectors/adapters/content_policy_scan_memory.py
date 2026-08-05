from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.content_policy_scan import ConnectorPackageContentPolicyScan


class InMemoryPackageContentPolicyScanRepository:
    durable = False

    def __init__(self) -> None:
        self._records: dict[str, ConnectorPackageContentPolicyScan] = {}
        self._lock = asyncio.Lock()

    async def get_by_id(self, *, scan_id: str) -> ConnectorPackageContentPolicyScan | None:
        return self._records.get(scan_id)

    async def get_by_inventory(
        self, *, source_inventory_id: str
    ) -> ConnectorPackageContentPolicyScan | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.source_inventory_id == source_inventory_id
            ),
            None,
        )

    async def get_by_create_key(
        self, *, scanned_by: str, idempotency_key: str
    ) -> ConnectorPackageContentPolicyScan | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.scanned_by == scanned_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, scan: ConnectorPackageContentPolicyScan) -> bool:
        async with self._lock:
            if scan.scan_id in self._records:
                return False
            if any(
                item.source_inventory_id == scan.source_inventory_id
                or (
                    item.scanned_by == scan.scanned_by
                    and item.idempotency_key == scan.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[scan.scan_id] = scan
            return True

    async def close(self) -> None:
        return None
