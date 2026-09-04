from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.explainability.application.audit import (
    record_approval_view_presentation,
    record_challenge_or_correction,
    record_explanation_generation,
    record_report_export,
    record_restricted_evidence_inspection,
)
from atlas.modules.explainability.domain.challenge_and_correction import (
    ChallengeOrCorrection,
    ChallengeOrCorrectionKind,
    ResultingArtifactKind,
)
from atlas.modules.explainability.domain.confidence import ConfidenceExplanation
from atlas.modules.explainability.domain.evidence_access import EvidenceInspectionLevel
from atlas.modules.explainability.domain.models import (
    AudienceProfile,
    EvidenceLink,
    Explanation,
    ExplanationChannel,
    ExplanationDetailLevel,
)
from atlas.modules.explainability.domain.report_explanation import ReportExplainabilityAddendum
from atlas.modules.explainability.domain.validation import ValidationOutcome, ValidationResult
from atlas.modules.guardrails.domain.reasoning_guardrails import ConfidenceLevel

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.recorded: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.recorded.append(event)


def evidence_link(**overrides: object) -> EvidenceLink:
    defaults: dict[str, object] = {
        "reference": "evidence.example",
        "source": "health-check.example",
        "version": "1",
        "target_id": "target.example",
        "observed_at": NOW,
        "authority": "vendor-documented",
        "applicability": "storage.health",
    }
    defaults.update(overrides)
    return EvidenceLink(**defaults)  # type: ignore[arg-type]


def explanation(**overrides: object) -> Explanation:
    defaults: dict[str, object] = {
        "explanation_id": "explanation.example",
        "version": 1,
        "created_at": NOW,
        "freshness_boundary": NOW + timedelta(hours=1),
        "source_artifact_ids": ("rca-finding.example",),
        "source_artifact_versions": ("1",),
        "audience": AudienceProfile.INFRASTRUCTURE_ENGINEER,
        "channel": ExplanationChannel.CHAT,
        "detail_level": ExplanationDetailLevel.L1_SUMMARY,
        "summary": "Controller B reports a degraded status.",
        "claims": (),
        "evidence_links": (evidence_link(),),
        "unknowns": (),
        "alternatives": (),
        "recommended_next_step": "Review controller B diagnostics.",
        "redacted": False,
    }
    defaults.update(overrides)
    return Explanation(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_explanation_generation_carries_audience_purpose_and_redaction() -> None:
    sink = RecordingAuditSink()
    await record_explanation_generation(
        sink,
        explanation(),
        validation=ValidationResult(outcome=ValidationOutcome.VALID, violations=()),
        purpose="Summarize the controller B remediation for the on-call engineer.",
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert len(sink.recorded) == 1
    event = sink.recorded[0]
    assert event.event_type == "atlas.explainability.explanation.valid"
    assert event.result_code == "explanation.valid"
    assert event.scope_reference == "explanation.example"
    assert ("audience", "infrastructure_engineer") in event.target_metadata
    assert ("purpose", "Summarize the controller B remediation for the on-call engineer.") in (
        event.target_metadata
    )
    assert ("redacted", "False") in event.target_metadata


@pytest.mark.asyncio
async def test_record_explanation_generation_uses_the_route_to_review_result_code() -> None:
    sink = RecordingAuditSink()
    await record_explanation_generation(
        sink,
        explanation(),
        validation=ValidationResult(outcome=ValidationOutcome.ROUTE_TO_REVIEW, violations=("x",)),
        purpose="Summarize the controller B remediation for the on-call engineer.",
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    assert sink.recorded[0].result_code == "explanation.route_to_review"


@pytest.mark.asyncio
async def test_record_restricted_evidence_inspection_permitted() -> None:
    sink = RecordingAuditSink()
    await record_restricted_evidence_inspection(
        sink,
        explanation_id="explanation.example",
        evidence_reference="evidence.example",
        requested_level=EvidenceInspectionLevel.EXCERPT,
        permitted=True,
        inspector_id="subject.reviewer",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.explainability.evidence_inspection.permitted"
    assert event.outcome == "permitted"
    assert event.result_code == "evidence_inspection.excerpt"
    assert event.subject_id == "subject.reviewer"
    assert ("explanation_id", "explanation.example") in event.target_metadata


@pytest.mark.asyncio
async def test_record_restricted_evidence_inspection_denied() -> None:
    sink = RecordingAuditSink()
    await record_restricted_evidence_inspection(
        sink,
        explanation_id="explanation.example",
        evidence_reference="evidence.example",
        requested_level=EvidenceInspectionLevel.ORIGINAL_ARTIFACT,
        permitted=False,
        inspector_id="subject.reviewer",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.explainability.evidence_inspection.denied"
    assert event.outcome == "denied"


def confidence(**overrides: object) -> ConfidenceExplanation:
    defaults: dict[str, object] = {
        "category": ConfidenceLevel.HIGH,
        "category_definition": "High confidence: multiple independent, current signals agree.",
        "supporting_factors": ("Matches a known, resolved fault pattern.",),
        "limiting_factors": (),
        "remaining_alternatives": (),
        "missing_or_conflicting_evidence": (),
        "what_would_change_the_category": "A repeat occurrence after the fix would lower it.",
        "is_confirmed": False,
        "domain_criteria_met": False,
    }
    defaults.update(overrides)
    return ConfidenceExplanation(**defaults)  # type: ignore[arg-type]


def addendum(**overrides: object) -> ReportExplainabilityAddendum:
    defaults: dict[str, object] = {
        "report_id": "report.example",
        "report_version": 1,
        "purpose": "Summarize the storage remediation decision for the change board.",
        "data_freshness_boundary": NOW,
        "ai_generated_section_ids": (),
        "excluded_evidence": (),
        "access_boundary": "Visible to the requesting organization's technical operations role.",
        "confidence": confidence(),
        "assumptions": (),
        "unknowns": (),
    }
    defaults.update(overrides)
    return ReportExplainabilityAddendum(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_report_export() -> None:
    sink = RecordingAuditSink()
    await record_report_export(
        sink,
        addendum(),
        exported_by="subject.requester",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.explainability.report_export"
    assert event.scope_reference == "report.example"
    assert event.subject_id == "subject.requester"
    assert ("report_version", "1") in event.target_metadata


def challenge(**overrides: object) -> ChallengeOrCorrection:
    defaults: dict[str, object] = {
        "challenge_id": "challenge.example",
        "kind": ChallengeOrCorrectionKind.HUMAN_REVIEW_REQUESTED,
        "target_explanation_id": "explanation.example",
        "target_claim_id": None,
        "field_correction": None,
        "note": "Please have a human review this explanation before I act on it.",
        "submitted_by": "subject.requester",
        "submitted_at": NOW,
        "resulting_artifact_kind": ResultingArtifactKind.REVIEW_ITEM,
    }
    defaults.update(overrides)
    return ChallengeOrCorrection(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_challenge_or_correction() -> None:
    sink = RecordingAuditSink()
    await record_challenge_or_correction(
        sink,
        challenge(),
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.explainability.challenge.human_review_requested"
    assert event.result_code == "challenge.review_item"
    assert event.subject_id == "subject.requester"
    assert ("challenge_id", "challenge.example") in event.target_metadata


@pytest.mark.asyncio
async def test_record_challenge_or_correction_includes_target_claim_id_when_present() -> None:
    sink = RecordingAuditSink()
    await record_challenge_or_correction(
        sink,
        challenge(
            kind=ChallengeOrCorrectionKind.CLAIM_MARKED_INCORRECT,
            target_claim_id="explanation-claim.example",
        ),
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert ("target_claim_id", "explanation-claim.example") in event.target_metadata


@pytest.mark.asyncio
async def test_record_approval_view_presentation() -> None:
    sink = RecordingAuditSink()
    await record_approval_view_presentation(
        sink,
        target_id="target.example",
        requested_by="subject.requester",
        presented_to="subject.reviewer",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.explainability.approval_view_presented"
    assert event.scope_reference == "target.example"
    assert event.subject_id == "subject.reviewer"
    assert ("requested_by", "subject.requester") in event.target_metadata
