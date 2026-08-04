from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AuditRecord:
    event_id: str
    event_type: str
    schema_version: str
    producer: str
    producer_version: str
    occurred_at: datetime
    correlation_id: str
    subject_id: str | None
    actor_type: str | None
    authentication_method: str | None
    assurance_level: str | None
    permission_id: str | None
    resource_type: str | None
    scope_reference: str | None
    decision_id: str | None
    outcome: str
    result_code: str
    target_subject_id: str | None = None
    reason: str | None = None
    idempotency_key: str | None = None
    target_metadata: tuple[tuple[str, str], ...] = ()


class AuditSink(Protocol):
    async def record(self, event: AuditRecord) -> None: ...


class LoggingAuditSink:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    async def record(self, event: AuditRecord) -> None:
        self._logger.info("atlas_audit_event", extra={"audit": asdict(event)})
