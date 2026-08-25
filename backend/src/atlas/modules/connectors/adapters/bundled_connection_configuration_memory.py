from __future__ import annotations

import asyncio

from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)


class InMemoryBundledConnectionConfigurationRepository(
    BundledConnectionConfigurationRepository
):
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], BundledConnectionConfiguration] = {}
        self._lock = asyncio.Lock()

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[BundledConnectionConfiguration, ...]:
        return tuple(
            record
            for (record_organization, record_environment, _), record in self._records.items()
            if record_organization == organization_id and record_environment == environment_id
        )

    async def get(
        self, *, organization_id: str, environment_id: str, instance_id: str
    ) -> BundledConnectionConfiguration | None:
        return self._records.get((organization_id, environment_id, instance_id))

    async def put(self, record: BundledConnectionConfiguration) -> None:
        async with self._lock:
            self._records[(record.organization_id, record.environment_id, record.instance_id)] = (
                record
            )
