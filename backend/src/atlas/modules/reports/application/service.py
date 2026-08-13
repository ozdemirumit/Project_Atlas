from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.recommendations.domain.models import RecommendationArtifact
from atlas.modules.reports.adapters.memory import InMemoryTechnicalReportRepository
from atlas.modules.reports.application.ports import (
    RecommendationProvider,
    ReportAssembler,
    TechnicalReportRepository,
)
from atlas.modules.reports.domain.models import ReportRequest, TechnicalReport

REPORT_RESOURCE_ID = "resource.report.storage.synthetic"


@dataclass(frozen=True, slots=True)
class ReportAccessContext:
    subject_id: str
    actor_type: str
    authentication_method: str
    assurance_level: str
    organization_id: str
    environment_id: str
    site_id: str
    resource_id: str
    correlation_id: str
    decision_id: str
    requested_at: datetime
    classification_ceiling: DataClassification = DataClassification.INTERNAL


class ReportOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ReportService:
    def __init__(
        self,
        *,
        source_provider: RecommendationProvider,
        assembler: ReportAssembler,
        audit_sink: AuditSink,
        repository: TechnicalReportRepository | None = None,
    ) -> None:
        self._source_provider = source_provider
        self._assembler = assembler
        self._audit_sink = audit_sink
        self._repository = repository or InMemoryTechnicalReportRepository()
        self._lock = asyncio.Lock()

    @property
    def repository(self) -> TechnicalReportRepository:
        return self._repository

    async def create(
        self,
        request: ReportRequest,
        *,
        context: ReportAccessContext,
    ) -> TechnicalReport:
        self._validate_scope(request, context)
        request_fingerprint = self._fingerprint(
            context.organization_id,
            context.environment_id,
            context.site_id,
            context.subject_id,
            request.source_recommendation_id,
            request.source_recommendation_version,
            request.target_id,
            request.report_type.value,
            request.audience.value,
            request.classification.value,
            request.include_itsm_handoff,
            request.incident_reference,
        )
        lineage_fingerprint = self._fingerprint(
            context.organization_id,
            context.environment_id,
            context.site_id,
            context.subject_id,
            request.target_id,
            request.report_type.value,
            request.audience.value,
            request.incident_reference,
        )
        async with self._lock:
            await self._record_audit(
                context,
                event_type="atlas.report.accepted",
                outcome="accepted",
                result_code="report_request_accepted",
            )
            existing = await self._repository.get_by_request_fingerprint(
                request_fingerprint=request_fingerprint
            )
            if existing is not None:
                self._validate_persisted_request(existing, request, context)
                await self._record_audit(
                    context,
                    event_type="atlas.report.completed",
                    outcome="succeeded",
                    result_code="report_artifact_reused",
                )
                return existing

            try:
                source = await self._source_provider.get_recommendation(
                    request.source_recommendation_id,
                    request.source_recommendation_version,
                    request.target_id,
                )
            except KeyError as exc:
                raise ReportOperationsError(
                    "report_source_unavailable",
                    "The requested report source is unavailable.",
                ) from exc
            self._validate_source(source, request, context)

            prior = await self._repository.get_latest(lineage_fingerprint=lineage_fingerprint)
            try:
                report = self._assembler.build(
                    request,
                    source,
                    requested_by=context.subject_id,
                    organization_id=context.organization_id,
                    environment_id=context.environment_id,
                    site_id=context.site_id,
                    created_at=context.requested_at,
                    version=1 if prior is None else prior.version + 1,
                    prior_version_id=None if prior is None else prior.report_id,
                )
            except ValueError as exc:
                raise ReportOperationsError(
                    "report_validation_failed",
                    "The request could not produce a valid governed report.",
                ) from exc
            self._validate_report(report, source, request, context)
            await self._record_audit(
                context,
                event_type="atlas.report.completed",
                outcome="succeeded",
                result_code="report_artifact_returned",
            )
            added = await self._repository.add(
                report,
                request_fingerprint=request_fingerprint,
                lineage_fingerprint=lineage_fingerprint,
            )
            if not added:
                raced = await self._repository.get_by_request_fingerprint(
                    request_fingerprint=request_fingerprint
                )
                if raced is not None:
                    self._validate_persisted_request(raced, request, context)
                    return raced
                raise ReportOperationsError(
                    "report_persistence_conflict",
                    "The governed report could not be persisted atomically.",
                )
            return report

    async def get(self, *, report_id: str) -> TechnicalReport | None:
        report = await self._repository.get(report_id=report_id)
        if report is not None:
            self._validate_integrity(report)
        return report

    async def read(self, *, report_id: str, context: ReportAccessContext) -> TechnicalReport:
        if context.resource_id != REPORT_RESOURCE_ID:
            raise ReportOperationsError(
                "report_scope_mismatch",
                "The report target is outside the authorized scope.",
            )
        report = await self.get(report_id=report_id)
        if report is None:
            raise ReportOperationsError("report_not_found", "The requested report was not found.")
        if (
            report.organization_id != context.organization_id
            or report.environment_id != context.environment_id
            or report.site_id != context.site_id
            or report.requested_by != context.subject_id
        ):
            raise ReportOperationsError(
                "report_scope_mismatch",
                "The report did not match the authorized scope.",
            )
        if report.expires_at <= context.requested_at:
            raise ReportOperationsError("report_expired", "The requested report has expired.")
        if not context.classification_ceiling.permits(report.classification):
            raise ReportOperationsError(
                "report_classification_denied",
                "The report classification exceeds the authorized boundary.",
            )
        await self._record_audit(
            context,
            event_type="atlas.report.read",
            outcome="succeeded",
            result_code="report_artifact_recovered",
            permission_id="report.read",
        )
        return report

    async def close(self) -> None:
        await self._repository.close()

    @staticmethod
    def _validate_scope(request: ReportRequest, context: ReportAccessContext) -> None:
        if context.resource_id != REPORT_RESOURCE_ID:
            raise ReportOperationsError(
                "report_scope_mismatch",
                "The report target is outside the authorized scope.",
            )
        if request.target_id not in {"asset.storage.lab.b28", "asset.storage.lab.g400"}:
            raise ReportOperationsError(
                "report_source_unavailable",
                "The requested report source is unavailable.",
            )
        if not context.classification_ceiling.permits(request.classification):
            raise ReportOperationsError(
                "report_classification_denied",
                "The report classification exceeds the authorized boundary.",
            )

    @staticmethod
    def _validate_source(
        source: RecommendationArtifact,
        request: ReportRequest,
        context: ReportAccessContext,
    ) -> None:
        if (
            source.recommendation_id != request.source_recommendation_id
            or source.version != request.source_recommendation_version
            or source.target_id != request.target_id
            or source.organization_id != context.organization_id
            or source.environment_id != context.environment_id
            or source.site_id != context.site_id
            or source.expires_at <= context.requested_at
        ):
            raise ReportOperationsError(
                "report_source_unavailable",
                "The requested report source is unavailable.",
            )
        expected_scope = "/".join(
            (
                context.organization_id,
                context.environment_id,
                context.site_id,
                request.target_id,
            )
        )
        if any(
            evidence.target_id != request.target_id
            or evidence.authorization_reference != expected_scope
            or not evidence.citation.strip()
            or not context.classification_ceiling.permits(evidence.classification)
            for evidence in source.source_evidence
        ):
            raise ReportOperationsError(
                "report_evidence_denied",
                "The report evidence did not satisfy the authorized data boundary.",
            )

    @staticmethod
    def _validate_report(
        report: TechnicalReport,
        source: RecommendationArtifact,
        request: ReportRequest,
        context: ReportAccessContext,
    ) -> None:
        if (
            report.target_id != request.target_id
            or report.source.recommendation_id != source.recommendation_id
            or report.source.recommendation_version != source.version
            or report.source.target_id != source.target_id
            or report.organization_id != context.organization_id
            or report.environment_id != context.environment_id
            or report.site_id != context.site_id
            or report.requested_by != context.subject_id
            or report.report_type is not request.report_type
            or report.audience is not request.audience
            or report.classification is not request.classification
            or report.expires_at > source.expires_at
        ):
            raise ReportOperationsError(
                "report_scope_mismatch",
                "The report did not match the authorized source and scope.",
            )
        digest = sha256(report.rendered_markdown.encode("utf-8")).hexdigest()
        if digest != report.content_digest:
            raise ReportOperationsError(
                "report_digest_mismatch",
                "The report content failed integrity validation.",
            )
        if report.execution_authorized or report.external_mutation_authorized:
            raise ReportOperationsError(
                "report_authority_denied",
                "A report cannot authorize execution or external mutation.",
            )
        handoff = report.itsm_handoff
        if request.include_itsm_handoff:
            if (
                handoff is None
                or handoff.incident_reference != request.incident_reference
                or handoff.dispatch_authorized
                or handoff.external_record_mutated
                or not handoff.human_review_required
            ):
                raise ReportOperationsError(
                    "report_handoff_denied",
                    "The ITSM handoff draft failed the governed boundary.",
                )
        elif handoff is not None:
            raise ReportOperationsError(
                "report_handoff_denied",
                "The report included an unrequested ITSM handoff draft.",
            )

    @classmethod
    def _validate_persisted_request(
        cls,
        report: TechnicalReport,
        request: ReportRequest,
        context: ReportAccessContext,
    ) -> None:
        if (
            report.source.recommendation_id != request.source_recommendation_id
            or report.source.recommendation_version != request.source_recommendation_version
            or report.target_id != request.target_id
            or report.organization_id != context.organization_id
            or report.environment_id != context.environment_id
            or report.site_id != context.site_id
            or report.requested_by != context.subject_id
            or report.report_type is not request.report_type
            or report.audience is not request.audience
            or report.classification is not request.classification
            or (report.itsm_handoff is not None) is not request.include_itsm_handoff
            or (
                report.itsm_handoff is not None
                and report.itsm_handoff.incident_reference != request.incident_reference
            )
            or report.expires_at <= context.requested_at
        ):
            raise ReportOperationsError(
                "report_scope_mismatch",
                "The persisted report did not match the authorized request and scope.",
            )
        cls._validate_integrity(report)

    @staticmethod
    def _validate_integrity(report: TechnicalReport) -> None:
        digest = sha256(report.rendered_markdown.encode("utf-8")).hexdigest()
        handoff = report.itsm_handoff
        if digest != report.content_digest:
            raise ReportOperationsError(
                "report_digest_mismatch",
                "The report content failed integrity validation.",
            )
        if report.execution_authorized or report.external_mutation_authorized:
            raise ReportOperationsError(
                "report_authority_denied",
                "A report cannot authorize execution or external mutation.",
            )
        if handoff is not None and (
            handoff.report_id != report.report_id
            or handoff.report_version != report.version
            or handoff.dispatch_authorized
            or handoff.external_record_mutated
            or not handoff.human_review_required
        ):
            raise ReportOperationsError(
                "report_handoff_denied",
                "The ITSM handoff draft failed the governed boundary.",
            )

    @staticmethod
    def _fingerprint(*values: object) -> str:
        canonical = json.dumps(values, separators=(",", ":"), ensure_ascii=True)
        return sha256(canonical.encode("utf-8")).hexdigest()

    async def _record_audit(
        self,
        context: ReportAccessContext,
        *,
        event_type: str,
        outcome: str,
        result_code: str,
        permission_id: str = "report.create",
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id=permission_id,
                resource_type="resource.report",
                scope_reference="/".join(
                    (
                        context.organization_id,
                        context.environment_id,
                        context.site_id,
                        context.resource_id,
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
            )
        )
