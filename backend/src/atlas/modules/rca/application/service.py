from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import (
    HARDWARE_HEALTH_CAPABILITY_ID as _HITACHI_HARDWARE_HEALTH_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import (
    PATH_EVENTS_CAPABILITY_ID as _HITACHI_PATH_EVENTS_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    CONTROLLER_HEALTH_CAPABILITY_ID as _HUAWEI_CONTROLLER_HEALTH_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    PATH_EVENTS_CAPABILITY_ID as _HUAWEI_PATH_EVENTS_CAPABILITY_ID,
)
from atlas.modules.rca.application.ports import RcaAssembler
from atlas.modules.rca.domain.models import ConfirmationLevel, RcaCase, RcaCreateRequest

RCA_RESOURCE_ID = "resource.rca.storage.synthetic"
# Each vendor contributes its own named capability-id constants (see health_checks/application/
# service.py for the same pattern); "atlas.telemetry.service-health.read" is an Atlas-internal
# capability, not vendor-provided, so it stays a literal here.
ALLOWED_DIAGNOSTIC_CAPABILITIES = frozenset(
    {
        _HITACHI_PATH_EVENTS_CAPABILITY_ID,
        "atlas.telemetry.service-health.read",
        _HITACHI_HARDWARE_HEALTH_CAPABILITY_ID,
        _HUAWEI_PATH_EVENTS_CAPABILITY_ID,
        _HUAWEI_CONTROLLER_HEALTH_CAPABILITY_ID,
    }
)


@dataclass(frozen=True, slots=True)
class RcaAccessContext:
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


class RcaOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class RcaService:
    def __init__(self, *, assembler: RcaAssembler, audit_sink: AuditSink) -> None:
        self._assembler = assembler
        self._audit_sink = audit_sink
        self._latest: dict[tuple[str, str], RcaCase] = {}
        self._cases: dict[str, RcaCase] = {}
        self._lock = asyncio.Lock()

    async def create(self, request: RcaCreateRequest, *, context: RcaAccessContext) -> RcaCase:
        self._validate_scope(request, context)
        key = (request.incident_id, request.target_id)
        async with self._lock:
            prior = self._latest.get(key)
            await self._record_audit(
                context,
                event_type="atlas.rca.accepted",
                outcome="accepted",
                result_code="rca_request_accepted",
            )
            try:
                case = await self._assembler.build(
                    request,
                    requested_by=context.subject_id,
                    organization_id=context.organization_id,
                    environment_id=context.environment_id,
                    site_id=context.site_id,
                    created_at=context.requested_at,
                    version=1 if prior is None else prior.version + 1,
                    prior_version_id=None if prior is None else prior.case_id,
                )
            except KeyError as exc:
                raise RcaOperationsError(
                    "rca_target_unavailable",
                    "The requested RCA target is unavailable.",
                ) from exc
            except ValueError as exc:
                raise RcaOperationsError(
                    "rca_validation_failed",
                    "The RCA request could not produce a valid governed case.",
                ) from exc

            self._validate_case(case, request, context)
            await self._record_audit(
                context,
                event_type="atlas.rca.completed",
                outcome="succeeded",
                result_code="rca_case_returned",
            )
            self._latest[key] = case
            self._cases[case.case_id] = case
            return case

    async def get_case(self, case_id: str, version: int, target_id: str) -> RcaCase:
        async with self._lock:
            case = self._cases.get(case_id)
            if case is None or case.version != version or case.target_id != target_id:
                raise KeyError(case_id)
            return case

    @staticmethod
    def _validate_scope(request: RcaCreateRequest, context: RcaAccessContext) -> None:
        del request
        if context.resource_id != RCA_RESOURCE_ID:
            raise RcaOperationsError(
                "rca_scope_mismatch",
                "The RCA target is outside the authorized scope.",
            )

    @staticmethod
    def _validate_case(
        case: RcaCase,
        request: RcaCreateRequest,
        context: RcaAccessContext,
    ) -> None:
        if len(case.evidence) > request.max_evidence_records:
            raise RcaOperationsError(
                "rca_evidence_budget_exceeded",
                "The governed evidence budget is too small for this RCA case.",
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
            case.target_id != request.target_id
            or case.organization_id != context.organization_id
            or case.environment_id != context.environment_id
            or case.site_id != context.site_id
            or case.requested_by != context.subject_id
        ):
            raise RcaOperationsError(
                "rca_scope_mismatch",
                "The RCA case did not match the authorized scope.",
            )
        if any(
            evidence.target_id != request.target_id
            or evidence.authorization_reference != expected_scope
            or not evidence.citation.strip()
            or not context.classification_ceiling.permits(evidence.classification)
            for evidence in case.evidence
        ):
            raise RcaOperationsError(
                "rca_evidence_denied",
                "The RCA evidence did not satisfy the authorized data boundary.",
            )
        diagnostics = (
            step for hypothesis in case.hypotheses for step in hypothesis.diagnostic_steps
        )
        if any(
            step.capability_class not in {"C0", "C1"}
            or step.capability_id not in ALLOWED_DIAGNOSTIC_CAPABILITIES
            or step.target_id != request.target_id
            or step.approval_required
            for step in diagnostics
        ):
            raise RcaOperationsError(
                "rca_diagnostic_denied",
                "The RCA case proposed a diagnostic outside the governed read-only boundary.",
            )
        if case.root_cause_confirmed or any(
            hypothesis.confirmation_level is ConfirmationLevel.CONFIRMED
            for hypothesis in case.hypotheses
        ):
            raise RcaOperationsError(
                "rca_unsupported_confirmation",
                "This RCA slice cannot confirm root cause.",
            )

    async def _record_audit(
        self,
        context: RcaAccessContext,
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
                permission_id="rca.create",
                resource_type="resource.rca",
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
