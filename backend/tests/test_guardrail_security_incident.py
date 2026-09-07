from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.guardrails.adapters.security_incident_memory import (
    InMemorySecurityIncidentRepository,
)
from atlas.modules.guardrails.application.security_incident import (
    SecurityIncidentError,
    SecurityIncidentService,
)
from atlas.modules.guardrails.domain.security_incident import (
    IncidentTrigger,
    SecurityIncidentRecord,
    an_ai_agent_closes_a_security_incident,
)
from atlas.modules.identity.domain.models import SubjectKind

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[SecurityIncidentService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = SecurityIncidentService(
        repository=InMemorySecurityIncidentRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def test_absolute_rule_is_false() -> None:
    assert an_ai_agent_closes_a_security_incident() is False


def test_closure_by_a_non_human_kind_is_unconstructable() -> None:
    with pytest.raises(ValueError, match="only be closed by a human"):
        SecurityIncidentRecord(
            incident_id="incident.primary",
            trigger=IncidentTrigger.SUSPECTED_EXFILTRATION,
            detected_at=NOW,
            affected_references=("agent.primary",),
            contained_at=NOW,
            evidence_preserved=True,
            recovery_validated_at=NOW,
            closed_at=NOW,
            closed_by="agent.ai.primary",
            closer_kind=SubjectKind.SERVICE,
        )


@pytest.mark.asyncio
async def test_full_incident_lifecycle() -> None:
    service, audit_sink = _service()
    incident = await service.open_incident(
        incident_id="incident.primary",
        trigger=IncidentTrigger.REPEATED_TOOL_BYPASS,
        affected_references=("connector.hitachi.primary",),
        correlation_id="correlation.test",
    )
    assert incident.contained_at is None
    contained = await service.contain_and_preserve(
        incident_id=incident.incident_id,
        alert_reference="alert.secops.001",
        correlation_id="correlation.test",
    )
    assert contained.evidence_preserved is True
    recovered = await service.record_recovery(
        incident_id=incident.incident_id,
        credentials_revoked=True,
        scope_assessment="Limited to one connector instance; no lateral movement found.",
        improvement_reference="rule.tool-use.bypass-detection.v2",
        correlation_id="correlation.test",
    )
    assert recovered.recovery_validated_at == NOW
    closed = await service.close(
        incident_id=incident.incident_id,
        closed_by="subject.security-lead.primary",
        closer_kind=SubjectKind.HUMAN,
        correlation_id="correlation.test",
    )
    assert closed.closed_by == "subject.security-lead.primary"
    assert any(item.outcome == "closed" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_close_before_recovery_is_refused() -> None:
    service, _audit = _service()
    incident = await service.open_incident(
        incident_id="incident.primary",
        trigger=IncidentTrigger.MODEL_COMPROMISE,
        affected_references=("model.endpoint.primary",),
        correlation_id="correlation.test",
    )
    await service.contain_and_preserve(
        incident_id=incident.incident_id,
        alert_reference="alert.secops.002",
        correlation_id="correlation.test",
    )
    with pytest.raises(SecurityIncidentError, match="security_incident_close_invalid"):
        await service.close(
            incident_id=incident.incident_id,
            closed_by="subject.security-lead.primary",
            closer_kind=SubjectKind.HUMAN,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_operations_require_an_existing_incident() -> None:
    service, _audit = _service()
    with pytest.raises(SecurityIncidentError, match="security_incident_unavailable"):
        await service.contain_and_preserve(
            incident_id="incident.no-such-one",
            alert_reference="alert.secops.003",
            correlation_id="correlation.test",
        )
