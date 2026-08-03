from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.investigations.application.ports import InvestigationAssembler
from atlas.modules.investigations.domain.models import InvestigationRequest, ReasoningArtifact

INVESTIGATION_RESOURCE_ID = "resource.investigation.storage.synthetic"
ALLOWED_CHECK_CAPABILITIES = frozenset(
    {
        "hitachi.opscenter.storage.path-events.read",
        "atlas.telemetry.service-health.read",
    }
)


@dataclass(frozen=True, slots=True)
class InvestigationAccessContext:
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


class InvestigationOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class InvestigationService:
    def __init__(self, *, assembler: InvestigationAssembler, audit_sink: AuditSink) -> None:
        self._assembler = assembler
        self._audit_sink = audit_sink
        self._latest: dict[str, ReasoningArtifact] = {}
        self._lock = asyncio.Lock()

    async def create(
        self, request: InvestigationRequest, *, context: InvestigationAccessContext
    ) -> ReasoningArtifact:
        self._validate_scope(request, context)
        async with self._lock:
            prior = self._latest.get(request.target_id)
            await self._record_audit(
                context,
                event_type="atlas.investigation.accepted",
                outcome="accepted",
                result_code="investigation_accepted",
            )
            try:
                artifact = self._assembler.build(
                    request,
                    requested_by=context.subject_id,
                    organization_id=context.organization_id,
                    environment_id=context.environment_id,
                    site_id=context.site_id,
                    created_at=context.requested_at,
                    version=1 if prior is None else prior.version + 1,
                    prior_version_id=None if prior is None else prior.artifact_id,
                )
            except KeyError as exc:
                raise InvestigationOperationsError(
                    "investigation_target_unavailable",
                    "The requested investigation target is unavailable.",
                ) from exc
            except ValueError as exc:
                raise InvestigationOperationsError(
                    "investigation_validation_failed",
                    "The investigation could not produce a valid governed artifact.",
                ) from exc

            self._validate_artifact(artifact, request, context)
            await self._record_audit(
                context,
                event_type="atlas.investigation.completed",
                outcome="succeeded",
                result_code="investigation_artifact_returned",
            )
            self._latest[request.target_id] = artifact
            return artifact

    @staticmethod
    def _validate_scope(request: InvestigationRequest, context: InvestigationAccessContext) -> None:
        if context.resource_id != INVESTIGATION_RESOURCE_ID:
            raise InvestigationOperationsError(
                "investigation_scope_mismatch",
                "The investigation target is outside the authorized scope.",
            )
        if not request.target_id.startswith("asset.storage.lab."):
            raise InvestigationOperationsError(
                "investigation_target_unavailable",
                "The requested investigation target is unavailable.",
            )

    @staticmethod
    def _validate_artifact(
        artifact: ReasoningArtifact,
        request: InvestigationRequest,
        context: InvestigationAccessContext,
    ) -> None:
        if len(artifact.evidence) > request.max_evidence_records:
            raise InvestigationOperationsError(
                "investigation_evidence_budget_exceeded",
                "The governed evidence budget is too small for this investigation.",
            )
        expected_scope = "/".join(
            (
                context.organization_id,
                context.environment_id,
                context.site_id,
                request.target_id,
            )
        )
        if (
            artifact.target_id != request.target_id
            or artifact.organization_id != context.organization_id
            or artifact.environment_id != context.environment_id
            or artifact.site_id != context.site_id
            or artifact.requested_by != context.subject_id
        ):
            raise InvestigationOperationsError(
                "investigation_scope_mismatch",
                "The investigation artifact did not match the authorized scope.",
            )
        if any(
            item.target_id != request.target_id
            or item.authorization_reference != expected_scope
            or not context.classification_ceiling.permits(item.classification)
            for item in artifact.evidence
        ):
            raise InvestigationOperationsError(
                "investigation_evidence_denied",
                "The investigation evidence did not satisfy the authorized data boundary.",
            )
        checks = (
            check
            for hypothesis in artifact.hypotheses
            for check in hypothesis.discriminating_checks
        )
        if any(
            check.capability_class != "C1"
            or check.capability_id not in ALLOWED_CHECK_CAPABILITIES
            or check.target_id != request.target_id
            for check in checks
        ):
            raise InvestigationOperationsError(
                "investigation_check_denied",
                "The investigation proposed a check outside the governed read-only boundary.",
            )
        if artifact.root_cause_confirmed or artifact.outage_confirmed:
            raise InvestigationOperationsError(
                "investigation_unsupported_confirmation",
                "This investigation slice cannot confirm root cause or outage.",
            )

    async def _record_audit(
        self,
        context: InvestigationAccessContext,
        *,
        event_type: str,
        outcome: str,
        result_code: str,
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
                permission_id="investigation.create",
                resource_type="resource.investigation",
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
