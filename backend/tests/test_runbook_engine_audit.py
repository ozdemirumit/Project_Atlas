from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.classification import DataClassification
from atlas.modules.guardrails.domain.reasoning_guardrails import ConfidenceLevel
from atlas.modules.runbook_engine.application.audit import (
    record_ai_generation,
    record_deviation,
    record_dry_run,
    record_export,
    record_lifecycle_transition,
    record_operator_step_result,
    record_outcome,
    record_parsing,
    record_plan_derivation,
    record_review,
    record_sensitive_retrieval,
    record_source_registration,
    record_validation_finding,
)
from atlas.modules.runbook_engine.domain.applicability import (
    ApplicabilityFactor,
    ApplicabilityFactorKind,
    ApplicabilityFactorResult,
    ApplicabilityMatch,
)
from atlas.modules.runbook_engine.domain.authoring import AiProposedField
from atlas.modules.runbook_engine.domain.deviation import (
    DeviationDecision,
    DeviationKind,
    DeviationRecord,
)
from atlas.modules.runbook_engine.domain.dry_run import (
    DryRunCheck,
    DryRunCheckKind,
    DryRunCheckResult,
    DryRunReport,
    SimulationMaturityLevel,
)
from atlas.modules.runbook_engine.domain.handoff import OperatorRecordedResult, OperatorRecordKind
from atlas.modules.runbook_engine.domain.ingestion_and_security import (
    ExportedArtifact,
    ParseLineage,
    SourceRegistration,
    SourceRegistrationState,
)
from atlas.modules.runbook_engine.domain.models import RunbookLifecycleState
from atlas.modules.runbook_engine.domain.outcome import FinalOutcome, RunbookOutcomeRecord
from atlas.modules.runbook_engine.domain.plan_generation import DerivedPlan, PlanOutputKind
from atlas.modules.runbook_engine.domain.retrieval import RunbookCandidate
from atlas.modules.runbook_engine.domain.review import ReviewDecision, ReviewerRole, RunbookReview
from atlas.modules.runbook_engine.domain.validation import (
    RunbookValidationFinding,
    ValidationCategory,
    ValidationResolutionState,
    ValidationSeverity,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


class RecordingAuditSink:
    def __init__(self) -> None:
        self.recorded: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.recorded.append(event)


@pytest.mark.asyncio
async def test_record_source_registration() -> None:
    sink = RecordingAuditSink()
    registration = SourceRegistration(
        source_id="runbook-source.example",
        classification=DataClassification.INTERNAL,
        state=SourceRegistrationState.CLASSIFIED,
        registered_at=NOW,
    )
    await record_source_registration(
        sink,
        registration,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.runbook_engine.source_registration.classified"
    assert event.scope_reference == "runbook-source.example"


@pytest.mark.asyncio
async def test_record_parsing() -> None:
    sink = RecordingAuditSink()
    lineage = ParseLineage(
        source_id="runbook-source.example",
        original_artifact_digest=DIGEST,
        extracted_text_digest=DIGEST,
        parser_version="runbook-parser.v1",
    )
    await record_parsing(
        sink,
        lineage,
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.runbook_engine.parsing.completed"


@pytest.mark.asyncio
async def test_record_ai_generation() -> None:
    sink = RecordingAuditSink()
    field = AiProposedField(
        field_name="vendor",
        proposed_value="Hitachi",
        source_span="Section 2, paragraph 1.",
        confidence=ConfidenceLevel.HIGH,
    )
    await record_ai_generation(
        sink,
        field,
        version_id="runbook-version.example",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.result_code == "ai_generation.high"


@pytest.mark.asyncio
async def test_record_validation_finding() -> None:
    sink = RecordingAuditSink()
    finding = RunbookValidationFinding(
        finding_id="runbook-validation-finding.example",
        category=ValidationCategory.SCHEMA_AND_SECTION_COMPLETENESS,
        severity=ValidationSeverity.BLOCKING,
        description="Mandatory section is missing.",
        evidence="No section found.",
        owner="subject.domain-reviewer",
        resolution_state=ValidationResolutionState.OPEN,
        resolution_rationale=None,
    )
    await record_validation_finding(
        sink,
        finding,
        version_id="runbook-version.example",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.runbook_engine.validation.schema_and_section_completeness"


@pytest.mark.asyncio
async def test_record_review() -> None:
    sink = RecordingAuditSink()
    review = RunbookReview(
        review_id="runbook-review.example",
        runbook_id="runbook.example",
        version_id="runbook-version.example",
        reviewer_role=ReviewerRole.DOMAIN_REVIEWER,
        reviewer_id="subject.domain-reviewer",
        decision=ReviewDecision.APPROVE,
        rationale="Matches vendor documentation.",
        reviewed_at=NOW,
    )
    await record_review(
        sink,
        review,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.runbook_engine.review.approve"


@pytest.mark.asyncio
async def test_record_lifecycle_transition() -> None:
    sink = RecordingAuditSink()
    await record_lifecycle_transition(
        sink,
        runbook_id="runbook.example",
        version_id="runbook-version.example",
        from_state=RunbookLifecycleState.APPROVED,
        to_state=RunbookLifecycleState.PUBLISHED,
        changed_by="subject.governance-approver",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.result_code == "lifecycle.approved_to_published"


def applicability() -> ApplicabilityMatch:
    return ApplicabilityMatch(
        runbook_id="runbook.example",
        version_id="runbook-version.example",
        target_id="target.example",
        factors=(
            ApplicabilityFactor(
                kind=ApplicabilityFactorKind.VENDOR_AND_VERSION_COMPATIBILITY,
                result=ApplicabilityFactorResult.EXACT,
                explanation="The target's firmware matches the runbook's tested version.",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_record_sensitive_retrieval() -> None:
    sink = RecordingAuditSink()
    candidate = RunbookCandidate(
        runbook_id="runbook.example",
        version_id="runbook-version.example",
        state=RunbookLifecycleState.PUBLISHED,
        applicability=applicability(),
        is_tested=True,
        ai_generated=False,
        is_exact_product_and_version_match=True,
        authority="source-authority.vendor",
    )
    await record_sensitive_retrieval(
        sink,
        candidate,
        retrieved_by="subject.reviewer",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.result_code == "retrieval.exact"


def plan(**overrides: object) -> DerivedPlan:
    defaults: dict[str, object] = {
        "plan_id": "runbook-plan.example",
        "kind": PlanOutputKind.HUMAN_CHECKLIST,
        "source_runbook_id": "runbook.example",
        "source_version_id": "runbook-version.example",
        "target_id": "target.example",
        "bound_parameters": (("controller_id", "controller-b"),),
        "bound_evidence_references": ("evidence.example",),
        "bound_policy_decision_id": None,
        "bound_impact_analysis_reference": None,
        "created_at": NOW,
        "created_by": "subject.requester",
    }
    defaults.update(overrides)
    return DerivedPlan(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_record_plan_derivation() -> None:
    sink = RecordingAuditSink()
    await record_plan_derivation(
        sink,
        plan(),
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.runbook_engine.plan_derivation.human_checklist"
    assert event.subject_id == "subject.requester"


@pytest.mark.asyncio
async def test_record_dry_run() -> None:
    sink = RecordingAuditSink()
    report = DryRunReport(
        report_id="runbook-dry-run.example",
        plan_id="runbook-plan.example",
        checks=(
            DryRunCheck(
                kind=DryRunCheckKind.TARGET_RESOLUTION_AND_SCOPE,
                result=DryRunCheckResult.PASSED,
                detail="Target resolved.",
            ),
        ),
        maturity_level=SimulationMaturityLevel.STRUCTURAL_ONLY,
        performed_at=NOW,
    )
    await record_dry_run(
        sink,
        report,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.runbook_engine.dry_run.passed"


@pytest.mark.asyncio
async def test_record_operator_step_result() -> None:
    sink = RecordingAuditSink()
    record = OperatorRecordedResult(
        record_id="operator-record.example",
        step_id="runbook-step.example",
        kind=OperatorRecordKind.ACTUAL_RESULT,
        recorded_by="subject.operator",
        recorded_at=NOW,
        actual_result="Controller B reported healthy.",
        deviation_note=None,
    )
    await record_operator_step_result(
        sink,
        record,
        plan_id="runbook-plan.example",
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.runbook_engine.step_result.actual_result"


@pytest.mark.asyncio
async def test_record_deviation() -> None:
    sink = RecordingAuditSink()
    deviation = DeviationRecord(
        deviation_id="runbook-deviation.example",
        plan_id="runbook-plan.example",
        step_id="runbook-step.example",
        kind=DeviationKind.UNPLANNED,
        reason="Controller B did not respond.",
        actual_state="Controller B remains degraded.",
        impact="Extended redundancy loss.",
        decision=DeviationDecision.PAUSE,
        recorded_by="subject.operator",
        recorded_at=NOW,
        new_plan_version_id=None,
    )
    await record_deviation(
        sink,
        deviation,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.runbook_engine.deviation.unplanned"


@pytest.mark.asyncio
async def test_record_outcome() -> None:
    sink = RecordingAuditSink()
    outcome = RunbookOutcomeRecord(
        outcome_id="runbook-outcome.example",
        runbook_id="runbook.example",
        version_id="runbook-version.example",
        plan_id="runbook-plan.example",
        target_id="target.example",
        starting_context="Controller B was reported degraded.",
        step_outcomes=(),
        actual_duration_minutes=4,
        actual_interruption="None observed.",
        actual_impact="Momentary redundancy loss.",
        resource_use="One operator for four minutes.",
        validation_passed=True,
        rollback_used=False,
        recovery_used=False,
        final_outcome=FinalOutcome.SUCCESS,
        operator_feedback=None,
        missing_or_ambiguous_instructions=(),
        related_incident_reference=None,
        related_problem_reference=None,
        related_change_reference=None,
        recorded_at=NOW,
    )
    await record_outcome(
        sink,
        outcome,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.event_type == "atlas.runbook_engine.outcome.success"


@pytest.mark.asyncio
async def test_record_export() -> None:
    sink = RecordingAuditSink()
    artifact = ExportedArtifact(
        artifact_id="runbook-export.example",
        classification=DataClassification.CONFIDENTIAL,
        redacted=True,
    )
    await record_export(
        sink,
        artifact,
        exported_by="subject.requester",
        occurred_at=NOW,
        correlation_id="correlation.example",
        event_id="audit-event.example",
        producer="test-producer",
        producer_version="0.0.0",
    )
    event = sink.recorded[0]
    assert event.result_code == "export.confidential"
