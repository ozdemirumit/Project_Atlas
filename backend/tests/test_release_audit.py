from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.release.application.audit import (
    ReleaseAuditEventKind,
    record_release_lifecycle_event,
    release_evidence_preserves_secret_material,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.recorded: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.recorded.append(event)


def test_release_evidence_never_preserves_secret_material() -> None:
    assert release_evidence_preserves_secret_material() is False


@pytest.mark.asyncio
async def test_record_release_lifecycle_event_for_approval() -> None:
    sink = RecordingAuditSink()
    await record_release_lifecycle_event(
        sink,
        event_kind=ReleaseAuditEventKind.APPROVAL,
        release_reference="release.1.5.0",
        actor_identity="subject.product-owner",
        is_automation=False,
        outcome="approved",
        detail_references=("release-candidate.1.5.0-rc.3",),
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.release.approval"
    assert event.result_code == "release.approval.approved"
    assert event.actor_type == "human"
    assert ("detail_reference", "release-candidate.1.5.0-rc.3") in event.target_metadata


@pytest.mark.asyncio
async def test_record_release_lifecycle_event_for_automation_actor() -> None:
    sink = RecordingAuditSink()
    await record_release_lifecycle_event(
        sink,
        event_kind=ReleaseAuditEventKind.CANDIDATE_CREATION,
        release_reference="release.1.5.0",
        actor_identity="service.ci-pipeline",
        is_automation=True,
        outcome="created",
        detail_references=(),
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.actor_type == "automation"
    assert event.event_type == "atlas.release.candidate_creation"
