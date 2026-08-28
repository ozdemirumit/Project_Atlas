from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import (
    CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID as _HITACHI_CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import (
    HARDWARE_HEALTH_CAPABILITY_ID as _HITACHI_HARDWARE_HEALTH_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import (
    PATH_EVENTS_CAPABILITY_ID as _HITACHI_PATH_EVENTS_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import (
    PATH_REMEDIATION_PLAN_CAPABILITY_ID as _HITACHI_PATH_REMEDIATION_PLAN_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID as _HUAWEI_CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    CONTROLLER_HEALTH_CAPABILITY_ID as _HUAWEI_CONTROLLER_HEALTH_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    PATH_EVENTS_CAPABILITY_ID as _HUAWEI_PATH_EVENTS_CAPABILITY_ID,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    PATH_REMEDIATION_PLAN_CAPABILITY_ID as _HUAWEI_PATH_REMEDIATION_PLAN_CAPABILITY_ID,
)
from atlas.modules.recommendations.application.ports import (
    RcaCaseProvider,
    RecommendationAssembler,
)
from atlas.modules.recommendations.domain.models import (
    OptionState,
    RecommendationArtifact,
    RecommendationRequest,
)

RECOMMENDATION_RESOURCE_ID = "resource.recommendation.storage.synthetic"
# Each vendor contributes its own named capability-id constants (see health_checks/application/
# service.py for the same pattern); "atlas.*" entries are Atlas-internal capabilities, not
# vendor-provided, so they stay literals here.
ALLOWED_CAPABILITIES = frozenset(
    {
        _HITACHI_PATH_EVENTS_CAPABILITY_ID,
        _HITACHI_HARDWARE_HEALTH_CAPABILITY_ID,
        "atlas.telemetry.service-health.read",
        "atlas.vendor.support.package.prepare",
        "atlas.graph.storage-impact.read",
        _HITACHI_CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID,
        _HITACHI_PATH_REMEDIATION_PLAN_CAPABILITY_ID,
        _HUAWEI_PATH_EVENTS_CAPABILITY_ID,
        _HUAWEI_CONTROLLER_HEALTH_CAPABILITY_ID,
        _HUAWEI_CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID,
        _HUAWEI_PATH_REMEDIATION_PLAN_CAPABILITY_ID,
    }
)
CAPABILITY_ORDER = {f"C{index}": index for index in range(6)}


@dataclass(frozen=True, slots=True)
class RecommendationAccessContext:
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


class RecommendationOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class RecommendationService:
    def __init__(
        self,
        *,
        source_provider: RcaCaseProvider,
        assembler: RecommendationAssembler,
        audit_sink: AuditSink,
    ) -> None:
        self._source_provider = source_provider
        self._assembler = assembler
        self._audit_sink = audit_sink
        self._latest: dict[tuple[str, str], RecommendationArtifact] = {}
        self._artifacts: dict[str, RecommendationArtifact] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        request: RecommendationRequest,
        *,
        context: RecommendationAccessContext,
    ) -> RecommendationArtifact:
        self._validate_scope(request, context)
        key = (request.source_case_id, request.decision_question)
        async with self._lock:
            prior = self._latest.get(key)
            await self._record_audit(
                context,
                event_type="atlas.recommendation.accepted",
                outcome="accepted",
                result_code="recommendation_request_accepted",
            )
            try:
                source_case = await self._source_provider.get_case(
                    request.source_case_id,
                    request.source_case_version,
                    request.target_id,
                )
            except KeyError as exc:
                raise RecommendationOperationsError(
                    "recommendation_source_unavailable",
                    "The requested recommendation source is unavailable.",
                ) from exc
            self._validate_source(source_case, request, context)
            try:
                artifact = self._assembler.build(
                    request,
                    source_case,
                    requested_by=context.subject_id,
                    organization_id=context.organization_id,
                    environment_id=context.environment_id,
                    site_id=context.site_id,
                    created_at=context.requested_at,
                    version=1 if prior is None else prior.version + 1,
                    prior_version_id=None if prior is None else prior.recommendation_id,
                )
            except ValueError as exc:
                raise RecommendationOperationsError(
                    "recommendation_validation_failed",
                    "The request could not produce a valid governed recommendation.",
                ) from exc

            self._validate_artifact(artifact, request, context)
            await self._record_audit(
                context,
                event_type="atlas.recommendation.completed",
                outcome="succeeded",
                result_code="recommendation_artifact_returned",
            )
            self._latest[key] = artifact
            self._artifacts[artifact.recommendation_id] = artifact
            return artifact

    async def get_recommendation(
        self,
        recommendation_id: str,
        version: int,
        target_id: str,
    ) -> RecommendationArtifact:
        artifact = self._artifacts.get(recommendation_id)
        if artifact is None or artifact.version != version or artifact.target_id != target_id:
            raise KeyError(recommendation_id)
        return artifact

    @staticmethod
    def _validate_scope(
        request: RecommendationRequest,
        context: RecommendationAccessContext,
    ) -> None:
        del request
        if context.resource_id != RECOMMENDATION_RESOURCE_ID:
            raise RecommendationOperationsError(
                "recommendation_scope_mismatch",
                "The recommendation target is outside the authorized scope.",
            )

    @staticmethod
    def _validate_source(
        source_case: object, request: RecommendationRequest, context: RecommendationAccessContext
    ) -> None:
        from atlas.modules.rca.domain.models import RcaCase

        if not isinstance(source_case, RcaCase):
            raise RecommendationOperationsError(
                "recommendation_source_unavailable",
                "The requested recommendation source is unavailable.",
            )
        if (
            source_case.case_id != request.source_case_id
            or source_case.version != request.source_case_version
            or source_case.target_id != request.target_id
            or source_case.organization_id != context.organization_id
            or source_case.environment_id != context.environment_id
            or source_case.site_id != context.site_id
        ):
            raise RecommendationOperationsError(
                "recommendation_source_unavailable",
                "The requested recommendation source is unavailable.",
            )

    @staticmethod
    def _validate_artifact(
        artifact: RecommendationArtifact,
        request: RecommendationRequest,
        context: RecommendationAccessContext,
    ) -> None:
        if len(artifact.options) > request.max_options:
            raise RecommendationOperationsError(
                "recommendation_option_budget_exceeded",
                "The governed option budget is too small for this recommendation.",
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
            or artifact.source_case_id != request.source_case_id
            or artifact.source_case_version != request.source_case_version
            or artifact.organization_id != context.organization_id
            or artifact.environment_id != context.environment_id
            or artifact.site_id != context.site_id
            or artifact.requested_by != context.subject_id
        ):
            raise RecommendationOperationsError(
                "recommendation_scope_mismatch",
                "The recommendation did not match the authorized scope.",
            )
        if any(
            evidence.target_id != request.target_id
            or evidence.authorization_reference != expected_scope
            or not evidence.citation.strip()
            or not context.classification_ceiling.permits(evidence.classification)
            for evidence in artifact.source_evidence
        ):
            raise RecommendationOperationsError(
                "recommendation_evidence_denied",
                "The recommendation evidence did not satisfy the authorized data boundary.",
            )
        maximum = CAPABILITY_ORDER[request.maximum_capability_class]
        for option in artifact.options:
            for step in option.plan_steps:
                if step.executable_by_atlas or (
                    step.capability_id is not None
                    and step.capability_id not in ALLOWED_CAPABILITIES
                ):
                    raise RecommendationOperationsError(
                        "recommendation_capability_denied",
                        "The recommendation contains a capability outside the governed boundary.",
                    )
                if (
                    option.state is OptionState.VIABLE
                    and CAPABILITY_ORDER[step.capability_class] > maximum
                ):
                    raise RecommendationOperationsError(
                        "recommendation_capability_denied",
                        "A viable recommendation exceeded the requested capability boundary.",
                    )
        if artifact.execution_authorized:
            raise RecommendationOperationsError(
                "recommendation_execution_denied",
                "A recommendation cannot authorize infrastructure execution.",
            )

    async def _record_audit(
        self,
        context: RecommendationAccessContext,
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
                permission_id="recommendation.create",
                resource_type="resource.recommendation",
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
