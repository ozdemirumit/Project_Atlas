from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition


class InMemoryPackageAcquisitionRepository:
    durable = False

    def __init__(self) -> None:
        self._records: dict[str, ConnectorPackageAcquisition] = {}
        self._lock = asyncio.Lock()

    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None:
        return self._records.get(acquisition_id)

    async def get_by_handoff(self, *, source_handoff_id: str) -> ConnectorPackageAcquisition | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.source_handoff_id == source_handoff_id
            ),
            None,
        )

    async def get_by_create_key(
        self, *, acquired_by: str, idempotency_key: str
    ) -> ConnectorPackageAcquisition | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.acquired_by == acquired_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, acquisition: ConnectorPackageAcquisition) -> bool:
        async with self._lock:
            if acquisition.acquisition_id in self._records:
                return False
            if any(
                item.source_handoff_id == acquisition.source_handoff_id
                or item.package_digest == acquisition.package_digest
                or (
                    item.acquired_by == acquisition.acquired_by
                    and item.idempotency_key == acquisition.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[acquisition.acquisition_id] = acquisition
            return True

    async def close(self) -> None:
        return None
