from __future__ import annotations

from atlas.modules.itsm.domain.records import IncidentRecord


class InMemoryItsmIncidentRecordRepository:
    def __init__(self) -> None:
        self._records: dict[str, IncidentRecord] = {}

    async def get(self, integration_reference: str) -> IncidentRecord | None:
        return self._records.get(integration_reference)

    async def save(self, record: IncidentRecord) -> None:
        self._records[record.common.integration_reference] = record

    async def close(self) -> None:
        return None
