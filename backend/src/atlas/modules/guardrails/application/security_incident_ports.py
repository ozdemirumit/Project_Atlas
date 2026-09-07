from __future__ import annotations

from typing import Protocol

from atlas.modules.guardrails.domain.security_incident import SecurityIncidentRecord


class SecurityIncidentRepository(Protocol):
    async def save(self, incident: SecurityIncidentRecord) -> None: ...

    async def get(self, incident_id: str) -> SecurityIncidentRecord | None: ...
