from __future__ import annotations

from typing import Protocol

from atlas.modules.itsm.domain.records import IncidentRecord


class ItsmIncidentRecordRepository(Protocol):
    async def get(self, integration_reference: str) -> IncidentRecord | None: ...

    async def save(self, record: IncidentRecord) -> None: ...

    async def close(self) -> None: ...
