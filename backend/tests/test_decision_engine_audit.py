from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.decision_engine.application.audit import (
    record_decision,
    record_sensitive_export,
)
from atlas.modules.decision_engine.domain.hypotheses import DecisionConfidenceCategory
from atlas.modules.decision_engine.domain.models import DecisionRequest
from atlas.modules.decision_engine.domain.record import (
    DecisionComponentVersions,
    DecisionRecord,
    DecisionReviewState,
    DecisionSupersessionState,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.recorded: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.recorded.append(event)


def request(**overrides: object) -> DecisionRequest:
    defaults: dict[str, object] = {
        "request_id": "decision-request.example",
        "workflow_id": "workflow.example",
        "requesting_identity": "subject.requester",
        "authorized_scope_reference": "authorization.example",
        "decision_type": "root_cause_diagnosis",
        "question": "Why did controller B degrade?",
        "target_ids": ("target.example",),
        "service_ids": ("service.file-shares",),
        "environment_id": "environment.production",
        "time_window_start": NOW - timedelta(hours=2),
        "time_window_end": NOW,
        "required_evidence_domains": ("health_check",),
        "required_output_schema": "decision-record.v1",
        "deadline": None,
        "required_freshness_seconds": 300,
        "applicable_domain": "storage",
        "applicable_product_versions": ("6.1.x",),
    }
    defaults.update(overrides)
    return DecisionRequest(**defaults)  # type: ignore[arg-type]


def record(**overrides: object) -> DecisionRecord:
    defaults: dict[str, object] = {
        "decision_id": "decision-record.example",
        "version": 1,
        "prior_version_id": None,
        "request": request(),
        "workflow_id": "workflow.example",
        "created_at": NOW,
        "valid_until": NOW + timedelta(hours=4),
        "target_ids": ("target.example",),
        "scope": "Single storage controller within organization.example.",
        "evidence_package_version": "decision-evidence-package.example:v1",
        "findings": (),
        "hypotheses": (),
        "confidence_category": DecisionConfidenceCategory.MEDIUM,
        "confidence_uncertainty_note": (
            "One independent evidence unit supports the leading hypothesis."
        ),
        "impact_assessment": None,
        "graph_freshness_statement": "Graph snapshot generated within the last five minutes.",
        "recommendation_candidates": (),
        "alternatives": (),
        "policy_handoffs": (),
        "required_approvals": (),
        "component_versions": DecisionComponentVersions(
            model_version="model.v3",
            rule_version="rule.v1",
            agent_version="decision-agent.v1",
            prompt_version=None,
            schema_version="decision-record.v1",
        ),
        "review_state": DecisionReviewState.UNREVIEWED,
        "supersession_state": DecisionSupersessionState.CURRENT,
        "superseded_by_decision_id": None,
    }
    defaults.update(overrides)
    return DecisionRecord(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_decision() -> None:
    sink = RecordingAuditSink()
    await record_decision(
        sink,
        record(),
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.decision_engine.decision.current"
    assert event.result_code == "decision.version_1"
    assert event.subject_id == "subject.requester"
    assert ("decision_request_id", "decision-request.example") in event.target_metadata
    assert ("model_version", "model.v3") in event.target_metadata


@pytest.mark.asyncio
async def test_record_decision_reflects_supersession_state() -> None:
    sink = RecordingAuditSink()
    await record_decision(
        sink,
        record(
            supersession_state=DecisionSupersessionState.SUPERSEDED,
            superseded_by_decision_id="decision-record.next",
        ),
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.decision_engine.decision.superseded"


@pytest.mark.asyncio
async def test_record_sensitive_export() -> None:
    sink = RecordingAuditSink()
    await record_sensitive_export(
        sink,
        decision_id="decision-record.example",
        exported_by="subject.reviewer",
        export_reference="export.decision-record.example",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.decision_engine.sensitive_export"
    assert event.subject_id == "subject.reviewer"
    assert ("export_reference", "export.decision-record.example") in event.target_metadata
