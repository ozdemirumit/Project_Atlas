from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.guardrails.application.audit import (
    GuardrailAuditEventKind,
    guardrail_audit_data_stores_a_raw_secret_value_or_unsafe_payload,
    record_guardrail_event,
)
from atlas.modules.guardrails.domain.observability import GuardrailMetricCategory

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def test_absolute_rule_is_false() -> None:
    assert guardrail_audit_data_stores_a_raw_secret_value_or_unsafe_payload() is False


def test_metric_categories_cover_ss31() -> None:
    assert len(GuardrailMetricCategory) == 9


@pytest.mark.asyncio
async def test_record_guardrail_event_covers_every_named_kind() -> None:
    sink = CollectingAuditSink()
    for index, kind in enumerate(GuardrailAuditEventKind):
        await record_guardrail_event(
            sink,
            event_kind=kind,
            rule_or_incident_reference="rule.example",
            actor_identity="subject.operator.primary",
            is_automation=False,
            outcome="succeeded",
            detail_references=("detail.001",),
            occurred_at=NOW,
            correlation_id="correlation.test",
            event_id=f"evt_{index}",
            producer="project-atlas-api",
            producer_version="0.0.0",
        )
    assert len(sink.records) == len(GuardrailAuditEventKind) == 15
    assert all(record.event_type.startswith("atlas.guardrails.") for record in sink.records)
