"""ATLAS-045 SS29: audit, completing Runbook Engine.

Maps this subsystem's already-built domain objects onto the platform's own
`atlas.core.audit.AuditRecord`/`AuditSink` -- the same primitive `authorization`'s service,
`policy_engine.application.audit.record_policy_decision`, and
`explainability.application.audit` already record through -- rather than a fourth audit path.

SS29 lists eighteen audited concerns; several collapse onto one already-built object rather than
needing a separate function: plan derivation, target binding, and policy/approval state are all
carried by `DerivedPlan` (`record_plan_derivation`); outcome and feedback are both on
`RunbookOutcomeRecord` (`record_outcome`); approval, publication, suspension, and supersession are
all `RunbookLifecycleState` transitions (`record_lifecycle_transition`).
"""

from __future__ import annotations

from datetime import datetime

from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.runbook_engine.domain.authoring import AiProposedField
from atlas.modules.runbook_engine.domain.deviation import DeviationRecord
from atlas.modules.runbook_engine.domain.dry_run import DryRunReport
from atlas.modules.runbook_engine.domain.handoff import OperatorRecordedResult
from atlas.modules.runbook_engine.domain.ingestion_and_security import (
    ExportedArtifact,
    ParseLineage,
    SourceRegistration,
)
from atlas.modules.runbook_engine.domain.models import RunbookLifecycleState
from atlas.modules.runbook_engine.domain.outcome import RunbookOutcomeRecord
from atlas.modules.runbook_engine.domain.plan_generation import DerivedPlan
from atlas.modules.runbook_engine.domain.retrieval import RunbookCandidate
from atlas.modules.runbook_engine.domain.review import RunbookReview
from atlas.modules.runbook_engine.domain.validation import RunbookValidationFinding


async def record_source_registration(
    sink: AuditSink,
    registration: SourceRegistration,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.runbook_engine.source_registration.{registration.state.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=registration.registered_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.source",
            scope_reference=registration.source_id,
            decision_id=None,
            outcome=registration.state.value,
            result_code=f"source_registration.{registration.state.value}",
            target_metadata=(("classification", registration.classification.value),),
        )
    )


async def record_parsing(
    sink: AuditSink,
    lineage: ParseLineage,
    *,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.runbook_engine.parsing.completed",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.source",
            scope_reference=lineage.source_id,
            decision_id=None,
            outcome="parsed",
            result_code="parsing.completed",
            target_metadata=(("parser_version", lineage.parser_version),),
        )
    )


async def record_ai_generation(
    sink: AuditSink,
    field: AiProposedField,
    *,
    version_id: str,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.runbook_engine.ai_generation",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.version",
            scope_reference=version_id,
            decision_id=None,
            outcome="proposed",
            result_code=f"ai_generation.{field.confidence.value}",
            target_metadata=(("field_name", field.field_name),),
        )
    )


async def record_validation_finding(
    sink: AuditSink,
    finding: RunbookValidationFinding,
    *,
    version_id: str,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.runbook_engine.validation.{finding.category.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=finding.owner,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.version",
            scope_reference=version_id,
            decision_id=None,
            outcome=finding.resolution_state.value,
            result_code=f"validation.{finding.severity.value}",
            reason=finding.description,
        )
    )


async def record_review(
    sink: AuditSink,
    review: RunbookReview,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.runbook_engine.review.{review.decision.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=review.reviewed_at,
            correlation_id=correlation_id,
            subject_id=review.reviewer_id,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.version",
            scope_reference=review.version_id,
            decision_id=None,
            outcome=review.decision.value,
            result_code=f"review.{review.reviewer_role.value}",
            reason=review.rationale,
        )
    )


async def record_lifecycle_transition(
    sink: AuditSink,
    *,
    runbook_id: str,
    version_id: str,
    from_state: RunbookLifecycleState,
    to_state: RunbookLifecycleState,
    changed_by: str,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    """Covers SS29's approval, publication, suspension, and supersession -- each is a
    `RunbookLifecycleState` transition (slice 1), not a separate concept."""
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.runbook_engine.lifecycle.{to_state.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=changed_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.version",
            scope_reference=version_id,
            decision_id=None,
            outcome=to_state.value,
            result_code=f"lifecycle.{from_state.value}_to_{to_state.value}",
            target_metadata=(("runbook_id", runbook_id),),
        )
    )


async def record_sensitive_retrieval(
    sink: AuditSink,
    candidate: RunbookCandidate,
    *,
    retrieved_by: str,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.runbook_engine.retrieval.sensitive_use",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=retrieved_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.version",
            scope_reference=candidate.version_id,
            decision_id=None,
            outcome="retrieved",
            result_code=f"retrieval.{candidate.applicability.overall_result.value}",
            target_metadata=(("runbook_id", candidate.runbook_id),),
        )
    )


async def record_plan_derivation(
    sink: AuditSink,
    plan: DerivedPlan,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    """Covers SS29's plan derivation, target binding, and policy/approval state -- all carried by
    `DerivedPlan` (slice 11)."""
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.runbook_engine.plan_derivation.{plan.kind.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=plan.created_at,
            correlation_id=correlation_id,
            subject_id=plan.created_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.plan",
            scope_reference=plan.target_id,
            decision_id=plan.bound_policy_decision_id,
            outcome="derived",
            result_code=f"plan_derivation.{plan.kind.value}",
            target_metadata=(
                ("source_runbook_id", plan.source_runbook_id),
                ("source_version_id", plan.source_version_id),
            ),
        )
    )


async def record_dry_run(
    sink: AuditSink,
    report: DryRunReport,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    outcome = "passed" if report.all_checks_passed else "failed"
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.runbook_engine.dry_run.{outcome}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=report.performed_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.plan",
            scope_reference=report.plan_id,
            decision_id=None,
            outcome=outcome,
            result_code=f"dry_run.{report.maturity_level.value}",
        )
    )


async def record_operator_step_result(
    sink: AuditSink,
    record: OperatorRecordedResult,
    *,
    plan_id: str,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.runbook_engine.step_result.{record.kind.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=record.recorded_at,
            correlation_id=correlation_id,
            subject_id=record.recorded_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.step",
            scope_reference=record.step_id,
            decision_id=None,
            outcome=record.kind.value,
            result_code=f"step_result.{record.kind.value}",
            target_metadata=(("plan_id", plan_id),),
        )
    )


async def record_deviation(
    sink: AuditSink,
    deviation: DeviationRecord,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.runbook_engine.deviation.{deviation.kind.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=deviation.recorded_at,
            correlation_id=correlation_id,
            subject_id=deviation.recorded_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.plan",
            scope_reference=deviation.plan_id,
            decision_id=None,
            outcome=deviation.decision.value,
            result_code=f"deviation.{deviation.kind.value}",
            reason=deviation.reason,
        )
    )


async def record_outcome(
    sink: AuditSink,
    outcome: RunbookOutcomeRecord,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    """Covers SS29's outcome and feedback -- both carried by `RunbookOutcomeRecord`
    (slice 15)."""
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.runbook_engine.outcome.{outcome.final_outcome.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=outcome.recorded_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.plan",
            scope_reference=outcome.plan_id,
            decision_id=None,
            outcome=outcome.final_outcome.value,
            result_code=f"outcome.{outcome.final_outcome.value}",
            reason=outcome.operator_feedback,
            target_metadata=(
                ("runbook_id", outcome.runbook_id),
                ("version_id", outcome.version_id),
            ),
        )
    )


async def record_export(
    sink: AuditSink,
    artifact: ExportedArtifact,
    *,
    exported_by: str,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.runbook_engine.export",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=exported_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="runbook_engine.export",
            scope_reference=artifact.artifact_id,
            decision_id=None,
            outcome="exported",
            result_code=f"export.{artifact.classification.value}",
        )
    )
