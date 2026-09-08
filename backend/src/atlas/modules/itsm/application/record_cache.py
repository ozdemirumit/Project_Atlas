"""ATLAS-036 SS5/SS6: the application service that makes the normalized ITSM object model
reachable. `IncidentRecord` is the first of the six SS6 record types wired -- the most
operationally central, and the one this session's own RCA/investigation work already produces
evidence for. `ProblemRecord`/`ChangeRecord`/`TaskRecord`/`ApprovalRecord`/
`ConfigurationItemRecord` share the identical `ItsmRecordCommonFields` shape and the identical
cache-and-retrieve pattern; they are a deliberately scoped follow-on, not silently dropped (see
IMPLEMENTATION_TRACKER.md).

Per SS5, ITSM remains authoritative for these records -- this service is a bounded, versioned
cache fed by a governed adapter (or, until a real ITSM sync adapter exists, by a caller with the
same authorization this endpoint requires), not an originator of ticket lifecycle state."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.application.dispatch_audit import (
    ItsmAuditEventKind,
    record_itsm_integration_event,
)
from atlas.modules.itsm.application.record_cache_ports import ItsmIncidentRecordRepository
from atlas.modules.itsm.domain.records import IncidentRecord


class ItsmRecordCacheError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ItsmIncidentRecordCacheService:
    def __init__(
        self,
        *,
        repository: ItsmIncidentRecordRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def upsert(
        self, record: IncidentRecord, *, actor: AuthenticatedSubject, correlation_id: str
    ) -> IncidentRecord:
        existing = await self._repository.get(record.common.integration_reference)
        await self._repository.save(record)
        await self._audit(
            record.common.integration_reference,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.SYNCHRONIZATION,
            outcome="updated" if existing is not None else "created",
        )
        return record

    async def get(
        self, integration_reference: str, *, actor: AuthenticatedSubject, correlation_id: str
    ) -> IncidentRecord:
        record = await self._repository.get(integration_reference)
        if record is None:
            raise ItsmRecordCacheError("itsm_incident_record_not_found")
        await self._audit(
            integration_reference,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.RECORD_RETRIEVAL_OF_SENSITIVE_CONTENT,
            outcome="read",
        )
        return record

    async def close(self) -> None:
        await self._repository.close()

    async def _audit(
        self,
        reference: str,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        event_kind: ItsmAuditEventKind,
        outcome: str,
    ) -> None:
        await record_itsm_integration_event(
            self._audit_sink,
            event_kind=event_kind,
            profile_reference=reference,
            actor_identity=actor.subject_id,
            is_automation=False,
            outcome=outcome,
            external_record_id=None,
            external_source_version=None,
            idempotency_key=None,
            detail_references=(reference,),
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )
