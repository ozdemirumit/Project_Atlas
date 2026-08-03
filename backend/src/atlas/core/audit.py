from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AuditRecord:
    event_type: str
    occurred_at: datetime
    correlation_id: str
    actor_reference: str
    outcome: str


class AuditSink(Protocol):
    async def record(self, event: AuditRecord) -> None: ...
