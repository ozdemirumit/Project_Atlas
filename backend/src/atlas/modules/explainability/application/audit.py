"""ATLAS-046 SS28: audit.

Maps this subsystem's already-built domain objects onto the platform's own
`atlas.core.audit.AuditRecord`/`AuditSink` -- the same primitive `authorization`'s service and
`policy_engine.application.audit.record_policy_decision` already record through -- rather than
building a second, Explainability-specific audit path.

SS28 lists ten things to audit: explanation generation, source artifacts, audience and purpose,
access and redaction decisions, model and template versions, validation state, restricted
evidence inspection, export, user challenge/correction, and approval-view presentation. This
module covers everything this subsystem's earlier slices can actually produce a record for --
`record_explanation_generation` alone covers generation, source artifacts, audience, purpose,
redaction, and validation state via `AuditRecord.target_metadata`. Model and template versions
are not recorded: no rendering pipeline exists yet to version them, the same gap `Explanation`'s
own docstring (slice 1) and the API contract (slice 12) already state plainly rather than
fabricate a value for.
"""

from __future__ import annotations

from datetime import datetime

from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.explainability.domain.challenge_and_correction import ChallengeOrCorrection
from atlas.modules.explainability.domain.evidence_access import EvidenceInspectionLevel
from atlas.modules.explainability.domain.models import Explanation
from atlas.modules.explainability.domain.report_explanation import ReportExplainabilityAddendum
from atlas.modules.explainability.domain.validation import ValidationOutcome, ValidationResult

_RESULT_CODE_FOR_VALIDATION_OUTCOME: dict[ValidationOutcome, str] = {
    ValidationOutcome.VALID: "explanation.valid",
    ValidationOutcome.SAFE_INCOMPLETE: "explanation.safe_incomplete",
    ValidationOutcome.ROUTE_TO_REVIEW: "explanation.route_to_review",
}


async def record_explanation_generation(
    sink: AuditSink,
    explanation: Explanation,
    *,
    validation: ValidationResult,
    purpose: str,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.explainability.explanation.{validation.outcome.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=explanation.created_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="explainability.explanation",
            scope_reference=explanation.explanation_id,
            decision_id=None,
            outcome=validation.outcome.value,
            result_code=_RESULT_CODE_FOR_VALIDATION_OUTCOME[validation.outcome],
            target_metadata=(
                ("audience", explanation.audience.value),
                ("channel", explanation.channel.value),
                ("purpose", purpose),
                ("redacted", str(explanation.redacted)),
                ("source_artifact_ids", ",".join(explanation.source_artifact_ids)),
            ),
        )
    )


async def record_restricted_evidence_inspection(
    sink: AuditSink,
    *,
    explanation_id: str,
    evidence_reference: str,
    requested_level: EvidenceInspectionLevel,
    permitted: bool,
    inspector_id: str,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    outcome = "permitted" if permitted else "denied"
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.explainability.evidence_inspection.{outcome}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=inspector_id,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="explainability.evidence",
            scope_reference=evidence_reference,
            decision_id=None,
            outcome=outcome,
            result_code=f"evidence_inspection.{requested_level.value}",
            target_metadata=(("explanation_id", explanation_id),),
        )
    )


async def record_report_export(
    sink: AuditSink,
    addendum: ReportExplainabilityAddendum,
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
            event_type="atlas.explainability.report_export",
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
            resource_type="explainability.report",
            scope_reference=addendum.report_id,
            decision_id=None,
            outcome="exported",
            result_code="report_export.completed",
            target_metadata=(
                ("report_version", str(addendum.report_version)),
                ("purpose", addendum.purpose),
            ),
        )
    )


async def record_challenge_or_correction(
    sink: AuditSink,
    challenge: ChallengeOrCorrection,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    target_metadata: tuple[tuple[str, str], ...] = (("challenge_id", challenge.challenge_id),)
    if challenge.target_claim_id is not None:
        target_metadata = (*target_metadata, ("target_claim_id", challenge.target_claim_id))
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.explainability.challenge.{challenge.kind.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=challenge.submitted_at,
            correlation_id=correlation_id,
            subject_id=challenge.submitted_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="explainability.explanation",
            scope_reference=challenge.target_explanation_id,
            decision_id=None,
            outcome=challenge.kind.value,
            result_code=f"challenge.{challenge.resulting_artifact_kind.value}",
            target_metadata=target_metadata,
        )
    )


async def record_approval_view_presentation(
    sink: AuditSink,
    *,
    target_id: str,
    requested_by: str,
    presented_to: str,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.explainability.approval_view_presented",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=presented_to,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="explainability.approval_view",
            scope_reference=target_id,
            decision_id=None,
            outcome="presented",
            result_code="approval_view.presented",
            target_metadata=(("requested_by", requested_by),),
        )
    )
