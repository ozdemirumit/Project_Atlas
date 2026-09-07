"""ATLAS-047 SS29: Security Incident Handling application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditSink
from atlas.modules.guardrails.application.audit import (
    GuardrailAuditEventKind,
    record_guardrail_event,
)
from atlas.modules.guardrails.application.security_incident_ports import (
    SecurityIncidentRepository,
)
from atlas.modules.guardrails.domain.security_incident import (
    IncidentTrigger,
    SecurityIncidentRecord,
)
from atlas.modules.identity.domain.models import SubjectKind


class SecurityIncidentError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SecurityIncidentService:
    """Steps 1-7 of SS29 are represented as progressive updates to one `SecurityIncidentRecord`
    rather than seven separate methods -- the record's own `__post_init__` is what actually
    enforces the ordering (closure requires containment, evidence preservation, and validated
    recovery to already be present; closure requires a human closer)."""

    def __init__(
        self,
        *,
        repository: SecurityIncidentRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def open_incident(
        self,
        *,
        incident_id: str,
        trigger: IncidentTrigger,
        affected_references: tuple[str, ...],
        correlation_id: str,
    ) -> SecurityIncidentRecord:
        try:
            incident = SecurityIncidentRecord(
                incident_id=incident_id,
                trigger=trigger,
                detected_at=self._clock(),
                affected_references=affected_references,
            )
        except ValueError as error:
            raise SecurityIncidentError("security_incident_invalid") from error
        await self._repository.save(incident)
        await self._audit(correlation_id=correlation_id, incident_id=incident_id, outcome="opened")
        return incident

    async def contain_and_preserve(
        self, *, incident_id: str, alert_reference: str, correlation_id: str
    ) -> SecurityIncidentRecord:
        incident = await self._require(incident_id)
        try:
            updated = replace(
                incident,
                contained_at=self._clock(),
                evidence_preserved=True,
                alert_reference=alert_reference,
            )
        except ValueError as error:
            raise SecurityIncidentError("security_incident_invalid") from error
        await self._repository.save(updated)
        await self._audit(
            correlation_id=correlation_id, incident_id=incident_id, outcome="contained"
        )
        return updated

    async def record_recovery(
        self,
        *,
        incident_id: str,
        credentials_revoked: bool,
        scope_assessment: str,
        improvement_reference: str,
        correlation_id: str,
    ) -> SecurityIncidentRecord:
        incident = await self._require(incident_id)
        try:
            updated = replace(
                incident,
                credentials_revoked=credentials_revoked,
                scope_assessment=scope_assessment,
                recovery_validated_at=self._clock(),
                improvement_reference=improvement_reference,
            )
        except ValueError as error:
            raise SecurityIncidentError("security_incident_invalid") from error
        await self._repository.save(updated)
        await self._audit(
            correlation_id=correlation_id, incident_id=incident_id, outcome="recovery_validated"
        )
        return updated

    async def close(
        self, *, incident_id: str, closed_by: str, closer_kind: SubjectKind, correlation_id: str
    ) -> SecurityIncidentRecord:
        incident = await self._require(incident_id)
        try:
            updated = replace(
                incident,
                closed_at=self._clock(),
                closed_by=closed_by,
                closer_kind=closer_kind,
            )
        except ValueError as error:
            raise SecurityIncidentError("security_incident_close_invalid") from error
        await self._repository.save(updated)
        await self._audit(
            correlation_id=correlation_id,
            incident_id=incident_id,
            outcome="closed",
            actor_identity=closed_by,
        )
        return updated

    async def _require(self, incident_id: str) -> SecurityIncidentRecord:
        incident = await self._repository.get(incident_id)
        if incident is None:
            raise SecurityIncidentError("security_incident_unavailable")
        return incident

    async def _audit(
        self,
        *,
        correlation_id: str,
        incident_id: str,
        outcome: str,
        actor_identity: str | None = None,
    ) -> None:
        await record_guardrail_event(
            self._audit_sink,
            event_kind=GuardrailAuditEventKind.INCIDENT,
            rule_or_incident_reference=incident_id,
            actor_identity=actor_identity,
            is_automation=actor_identity is None,
            outcome=outcome,
            detail_references=(incident_id,),
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )
