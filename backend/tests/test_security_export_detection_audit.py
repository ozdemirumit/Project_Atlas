from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.security_export.application.detection_audit import (
    SiemDetectionAuditEventKind,
    record_siem_detection_lifecycle_event,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.recorded: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.recorded.append(event)


@pytest.mark.asyncio
async def test_record_siem_detection_lifecycle_event_for_activation() -> None:
    sink = RecordingAuditSink()
    await record_siem_detection_lifecycle_event(
        sink,
        event_kind=SiemDetectionAuditEventKind.DETECTION_ACTIVATED_PRODUCTION,
        detection_reference="SIEM-UC-001",
        actor_identity="subject.security-owner",
        is_automation=False,
        outcome="activated",
        detail_references=("detection-content.SIEM-UC-001.v1.0.0",),
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.siem_detection.detection_activated_production"
    assert event.result_code == "siem_detection.detection_activated_production.activated"
    assert event.actor_type == "human"
    assert ("detail_reference", "detection-content.SIEM-UC-001.v1.0.0") in event.target_metadata


@pytest.mark.asyncio
async def test_record_siem_detection_lifecycle_event_for_automation_actor() -> None:
    sink = RecordingAuditSink()
    await record_siem_detection_lifecycle_event(
        sink,
        event_kind=SiemDetectionAuditEventKind.INCIDENT_HANDOFF,
        detection_reference="SIEM-UC-002",
        actor_identity="service.security-export",
        is_automation=True,
        outcome="dispatched",
        detail_references=(),
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.actor_type == "automation"
    assert event.event_type == "atlas.siem_detection.incident_handoff"
