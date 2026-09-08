"""ATLAS-035 SS19: the application service that makes the detection content contract, the
nine-stage lifecycle, and the SIEM-originated incident handoff summary reachable. The detection
content itself is never re-typed by a caller -- SS13's own framing is that Atlas ships a fixed
catalog of reviewed baseline specifications (`baseline_detections.BASELINE_DETECTION_CATALOG`),
so registering a deployment only ever references one of those by id."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.security_export.application.detection_audit import (
    SiemDetectionAuditEventKind,
    record_siem_detection_lifecycle_event,
)
from atlas.modules.security_export.application.detection_lifecycle_ports import (
    SiemDetectionDeploymentRepository,
)
from atlas.modules.security_export.domain.baseline_detections import detection_by_id
from atlas.modules.security_export.domain.detection_content import DetectionUseCaseId
from atlas.modules.security_export.domain.detection_deployment import SiemDetectionDeployment
from atlas.modules.security_export.domain.detection_lifecycle import (
    DetectionLifecycleStage,
    is_valid_transition,
)
from atlas.modules.security_export.domain.handoff_metrics import (
    SiemIncidentHandoffSummary,
    TriageStatus,
)

_STAGE_AUDIT_EVENT: dict[DetectionLifecycleStage, SiemDetectionAuditEventKind] = {
    DetectionLifecycleStage.REGISTERED: SiemDetectionAuditEventKind.DESTINATION_REGISTERED,
    DetectionLifecycleStage.CONFIGURED_INACTIVE: SiemDetectionAuditEventKind.DESTINATION_CONFIGURED,
    DetectionLifecycleStage.VALIDATED: SiemDetectionAuditEventKind.DESTINATION_VALIDATED,
    DetectionLifecycleStage.FIXTURES_REPLAYED: SiemDetectionAuditEventKind.FIXTURES_REPLAYED,
    DetectionLifecycleStage.VERIFIED: SiemDetectionAuditEventKind.DETECTION_VERIFIED,
    DetectionLifecycleStage.DEPLOYED_TEST_MODE: (
        SiemDetectionAuditEventKind.DETECTION_DEPLOYED_TEST_MODE
    ),
    DetectionLifecycleStage.PRODUCTION_ACTIVE: (
        SiemDetectionAuditEventKind.DETECTION_ACTIVATED_PRODUCTION
    ),
    DetectionLifecycleStage.MONITORED: SiemDetectionAuditEventKind.DETECTION_TUNED,
    DetectionLifecycleStage.RETIRED: SiemDetectionAuditEventKind.DETECTION_RETIRED,
}

_HANDOFF_ELIGIBLE_STAGES = frozenset(
    {DetectionLifecycleStage.PRODUCTION_ACTIVE, DetectionLifecycleStage.MONITORED}
)


class SiemDetectionLifecycleError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SiemDetectionLifecycleService:
    def __init__(
        self,
        *,
        repository: SiemDetectionDeploymentRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def register(
        self,
        *,
        deployment_id: str,
        detection_id: DetectionUseCaseId,
        destination_id: str,
        owner: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> SiemDetectionDeployment:
        if await self._repository.get(deployment_id) is not None:
            raise SiemDetectionLifecycleError("siem_detection_deployment_already_registered")
        try:
            contract = detection_by_id(detection_id)
        except KeyError as error:
            raise SiemDetectionLifecycleError("siem_detection_id_unrecognized") from error
        now = self._clock()
        try:
            deployment = SiemDetectionDeployment(
                deployment_id=deployment_id,
                detection_id=detection_id,
                detection_version=contract.version,
                destination_id=destination_id,
                stage=DetectionLifecycleStage.REGISTERED,
                owner=owner,
                registered_by=actor.subject_id,
                registered_at=now,
                updated_at=now,
            )
        except ValueError as error:
            raise SiemDetectionLifecycleError("siem_detection_deployment_invalid") from error
        await self._repository.save(deployment)
        await self._audit(
            deployment,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=SiemDetectionAuditEventKind.DESTINATION_REGISTERED,
            outcome="registered",
        )
        return deployment

    async def transition(
        self,
        *,
        deployment_id: str,
        target_stage: DetectionLifecycleStage,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> SiemDetectionDeployment:
        deployment = await self._repository.get(deployment_id)
        if deployment is None:
            raise SiemDetectionLifecycleError("siem_detection_deployment_not_found")
        if not is_valid_transition(deployment.stage, target_stage):
            raise SiemDetectionLifecycleError("siem_detection_lifecycle_transition_invalid")
        updated = replace(deployment, stage=target_stage, updated_at=self._clock())
        await self._repository.save(updated)
        await self._audit(
            updated,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=_STAGE_AUDIT_EVENT[target_stage],
            outcome="transitioned",
        )
        return updated

    async def record_incident_handoff(
        self,
        *,
        deployment_id: str,
        alert_reference: str,
        event_references: tuple[str, ...],
        confidence: str,
        triage_status: TriageStatus,
        affected_deployment: str,
        affected_services: tuple[str, ...],
        affected_targets: tuple[str, ...],
        investigation_summary: str,
        evidence_link_kinds: tuple[str, ...],
        ownership: str,
        synchronization_state: str,
        ai_generated_summary: bool,
        summary_labeled_as_ai_generated: bool,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> SiemIncidentHandoffSummary:
        deployment = await self._repository.get(deployment_id)
        if deployment is None:
            raise SiemDetectionLifecycleError("siem_detection_deployment_not_found")
        if deployment.stage not in _HANDOFF_ELIGIBLE_STAGES:
            raise SiemDetectionLifecycleError("siem_detection_not_live")
        contract = detection_by_id(deployment.detection_id)
        try:
            handoff = SiemIncidentHandoffSummary(
                detection_id=deployment.detection_id,
                detection_version=deployment.detection_version,
                alert_reference=alert_reference,
                event_references=event_references,
                severity=contract.severity,
                confidence=confidence,
                triage_status=triage_status,
                affected_deployment=affected_deployment,
                affected_services=affected_services,
                affected_targets=affected_targets,
                investigation_summary=investigation_summary,
                evidence_link_kinds=evidence_link_kinds,
                ownership=ownership,
                synchronization_state=synchronization_state,
                ai_generated_summary=ai_generated_summary,
                summary_labeled_as_ai_generated=summary_labeled_as_ai_generated,
            )
        except ValueError as error:
            raise SiemDetectionLifecycleError("siem_incident_handoff_invalid") from error
        await self._repository.add_handoff(deployment_id, handoff)
        await self._audit(
            deployment,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=SiemDetectionAuditEventKind.INCIDENT_HANDOFF,
            outcome="handed_off",
            detail_references=(alert_reference,),
        )
        return handoff

    async def close(self) -> None:
        await self._repository.close()

    async def _audit(
        self,
        deployment: SiemDetectionDeployment,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        event_kind: SiemDetectionAuditEventKind,
        outcome: str,
        detail_references: tuple[str, ...] = (),
    ) -> None:
        await record_siem_detection_lifecycle_event(
            self._audit_sink,
            event_kind=event_kind,
            detection_reference=deployment.deployment_id,
            actor_identity=actor.subject_id,
            is_automation=False,
            outcome=outcome,
            detail_references=detail_references or (deployment.detection_id.value,),
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )
