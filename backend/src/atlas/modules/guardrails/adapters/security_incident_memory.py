from __future__ import annotations

import asyncio

from atlas.modules.guardrails.domain.security_incident import SecurityIncidentRecord


class InMemorySecurityIncidentRepository:
    def __init__(self) -> None:
        self._records: dict[str, SecurityIncidentRecord] = {}
        self._lock = asyncio.Lock()

    async def save(self, incident: SecurityIncidentRecord) -> None:
        async with self._lock:
            self._records[incident.incident_id] = incident

    async def get(self, incident_id: str) -> SecurityIncidentRecord | None:
        async with self._lock:
            return self._records.get(incident_id)
