from __future__ import annotations

import pytest

from atlas.modules.security_export.domain.detection_content import DetectionUseCaseId
from atlas.modules.security_export.domain.handoff_metrics import (
    SiemIncidentHandoffSummary,
    SiemServiceMetric,
    TriageStatus,
    ticket_creation_authorizes_operational_action,
)
from atlas.modules.security_export.domain.models import SecuritySeverity


def _build(**overrides: object) -> SiemIncidentHandoffSummary:
    defaults: dict[str, object] = {
        "detection_id": DetectionUseCaseId.SIEM_UC_002,
        "detection_version": "1.0.0",
        "alert_reference": "alert.example-001",
        "event_references": ("evt_1",),
        "severity": SecuritySeverity.HIGH,
        "confidence": "high",
        "triage_status": TriageStatus.NEW,
        "affected_deployment": "deployment.primary",
        "affected_services": ("service.authorization",),
        "affected_targets": ("target.example",),
        "investigation_summary": "Wildcard scope grant outside a change window.",
        "evidence_link_kinds": ("audit_ledger_reference",),
        "ownership": "security-operations",
        "synchronization_state": "pending",
        "ai_generated_summary": False,
        "summary_labeled_as_ai_generated": False,
    }
    defaults.update(overrides)
    return SiemIncidentHandoffSummary(**defaults)  # type: ignore[arg-type]


def test_ticket_creation_never_authorizes_operational_action() -> None:
    assert ticket_creation_authorizes_operational_action() is False


def test_metric_has_eight_members() -> None:
    assert len(SiemServiceMetric) == 8


def test_valid_summary_builds() -> None:
    summary = _build()
    assert summary.detection_id is DetectionUseCaseId.SIEM_UC_002


def test_ai_generated_summary_must_be_labeled() -> None:
    with pytest.raises(ValueError, match="must be labeled as AI-generated"):
        _build(ai_generated_summary=True, summary_labeled_as_ai_generated=False)


def test_ai_generated_and_labeled_summary_is_valid() -> None:
    summary = _build(ai_generated_summary=True, summary_labeled_as_ai_generated=True)
    assert summary.ai_generated_summary is True


def test_requires_event_and_evidence_references() -> None:
    with pytest.raises(ValueError, match="event and evidence links"):
        _build(event_references=())
    with pytest.raises(ValueError, match="event and evidence links"):
        _build(evidence_link_kinds=())


@pytest.mark.parametrize(
    "field",
    [
        "detection_version",
        "alert_reference",
        "confidence",
        "affected_deployment",
        "investigation_summary",
        "ownership",
        "synchronization_state",
    ],
)
def test_requires_every_narrative_field(field: str) -> None:
    with pytest.raises(ValueError, match="every narrative field"):
        _build(**{field: "  "})
