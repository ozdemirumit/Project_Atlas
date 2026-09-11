"""ATLAS-032 SS12/S22: the on-demand half of "integrity verification runs on schedule and on
demand" -- see `atlas.core.audit_ledger`'s module docstring for the full wiring status, including
why scheduled verification is a distinct, infrastructure-blocked deferral.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response

from atlas import __version__
from atlas.api.audit_ledger_integrity_schemas import (
    AuditIntegrityReportData,
    AuditLedgerIntegrityVerificationResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authorize_audit_ledger_integrity_verify, browser_session_subject
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.audit_ledger import AuditIntegrityReport, DurableAuditLedger
from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    AUDIT_LEDGER_INTEGRITY_VERIFY,
    audit_ledger_integrity_scope,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/platform/audit-ledger", tags=["audit-ledger-integrity"])


async def _record_verification_event(
    request: Request,
    subject: AuthenticatedSubject,
    decision: AuthorizationDecision,
    report: AuditIntegrityReport,
) -> None:
    scope = audit_ledger_integrity_scope(
        subject.organization_id,
        request.app.state.settings.environment,
        CapabilityClass.C2_DIAGNOSTIC,
    )
    audit_sink: AuditSink = request.app.state.audit_sink
    await audit_sink.record(
        AuditRecord(
            event_id=f"evt_{uuid4().hex}",
            event_type="audit.ledger-integrity-verification",
            schema_version="1.0",
            producer="project-atlas-api",
            producer_version=__version__,
            occurred_at=report.verified_at,
            correlation_id=str(request.state.correlation_id),
            subject_id=subject.subject_id,
            actor_type=subject.kind.value,
            authentication_method=subject.authentication_method.value,
            assurance_level=subject.assurance_level.value,
            permission_id=AUDIT_LEDGER_INTEGRITY_VERIFY,
            resource_type="resource.audit.ledger-integrity",
            scope_reference=scope.reference,
            decision_id=decision.decision_id,
            outcome="succeeded" if report.is_intact else "failed",
            result_code="ledger_intact" if report.is_intact else "ledger_findings_detected",
            target_metadata=(
                ("first_sequence", str(report.first_sequence)),
                ("last_sequence", str(report.last_sequence)),
                ("records_checked", str(report.records_checked)),
                ("findings_count", str(len(report.findings))),
            ),
        )
    )


@router.post("/integrity-verifications", response_model=AuditLedgerIntegrityVerificationResponse)
async def verify_audit_ledger_integrity(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_audit_ledger_integrity_verify)],
) -> AuditLedgerIntegrityVerificationResponse:
    now = datetime.now(UTC)
    response.headers["Cache-Control"] = "no-store"
    ledger: DurableAuditLedger = request.app.state.audit_ledger
    report = await ledger.verify_integrity(at=now)
    await _record_verification_event(request, subject, decision, report)
    return AuditLedgerIntegrityVerificationResponse(
        data=AuditIntegrityReportData.from_domain(report),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
