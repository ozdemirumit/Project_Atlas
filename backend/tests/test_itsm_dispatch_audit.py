from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.itsm.application.dispatch_audit import (
    ItsmAuditEventKind,
    record_itsm_integration_event,
    ticket_content_is_copied_unconditionally_into_the_audit_ledger,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.recorded: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.recorded.append(event)


def test_ticket_content_is_never_copied_unconditionally_into_the_audit_ledger() -> None:
    assert ticket_content_is_copied_unconditionally_into_the_audit_ledger() is False


def test_event_kind_has_fifteen_members() -> None:
    assert len(ItsmAuditEventKind) == 15


@pytest.mark.asyncio
async def test_record_itsm_integration_event_for_create() -> None:
    sink = RecordingAuditSink()
    await record_itsm_integration_event(
        sink,
        event_kind=ItsmAuditEventKind.CREATE,
        profile_reference="profile.example-001",
        actor_identity="subject.owner",
        is_automation=False,
        outcome="created",
        external_record_id="external.rec-001",
        external_source_version="version.1",
        idempotency_key="idempotency.example-001",
        detail_references=("draft.example-001",),
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.itsm_integration.create"
    assert event.result_code == "itsm_integration.create.created"
    assert event.actor_type == "human"
    assert event.idempotency_key == "idempotency.example-001"
    assert ("external_record_id", "external.rec-001") in event.target_metadata
    assert ("external_source_version", "version.1") in event.target_metadata
    assert ("detail_reference", "draft.example-001") in event.target_metadata


@pytest.mark.asyncio
async def test_record_itsm_integration_event_for_automation_actor_without_external_fields() -> None:
    sink = RecordingAuditSink()
    await record_itsm_integration_event(
        sink,
        event_kind=ItsmAuditEventKind.SYNCHRONIZATION,
        profile_reference="profile.example-001",
        actor_identity="service.itsm-integration",
        is_automation=True,
        outcome="synchronized",
        external_record_id=None,
        external_source_version=None,
        idempotency_key=None,
        detail_references=(),
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.actor_type == "automation"
    assert event.target_metadata == ()
