from __future__ import annotations

import asyncio

from atlas.modules.connectors.application.bundled_runtime_state_ports import (
    BundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.domain.bundled_runtime_state import (
    BundledConnectorRuntimeState,
)


class InMemoryBundledConnectorRuntimeStateRepository(BundledConnectorRuntimeStateRepository):
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], BundledConnectorRuntimeState] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, *, organization_id: str, environment_id: str, instance_id: str
    ) -> BundledConnectorRuntimeState | None:
        return self._records.get((organization_id, environment_id, instance_id))

    async def put(self, record: BundledConnectorRuntimeState, *, expected_version: int) -> bool:
        key = (record.organization_id, record.environment_id, record.instance_id)
        async with self._lock:
            current = self._records.get(key)
            actual_version = current.version if current is not None else 0
            if actual_version != expected_version:
                return False
            self._records[key] = record
            return True

    async def clear(self, *, organization_id: str, environment_id: str, instance_id: str) -> None:
        async with self._lock:
            self._records.pop((organization_id, environment_id, instance_id), None)
