from __future__ import annotations

import asyncio

from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorConnectionTestResultRepository,
)
from atlas.modules.connectors.domain.connection_test import ConnectorConnectionTestResult


class InMemoryConnectorConnectionTestResultRepository(
    ConnectorConnectionTestResultRepository
):
    def __init__(self) -> None:
        self._records: dict[
            tuple[str, str, str], list[ConnectorConnectionTestResult]
        ] = {}
        self._lock = asyncio.Lock()

    async def put(
        self,
        *,
        organization_id: str,
        environment_id: str,
        result: ConnectorConnectionTestResult,
    ) -> None:
        async with self._lock:
            key = (organization_id, environment_id, result.instance_id)
            self._records.setdefault(key, []).append(result)

    async def get_latest(
        self,
        *,
        organization_id: str,
        environment_id: str,
        instance_id: str,
    ) -> ConnectorConnectionTestResult | None:
        records = self._records.get((organization_id, environment_id, instance_id), [])
        return records[-1] if records else None
