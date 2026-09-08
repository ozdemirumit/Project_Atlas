from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_security_export_detection_handoff_record,
    authorize_security_export_detection_register,
    authorize_security_export_detection_transition,
)
from atlas.api.security_export_detection_schemas import (
    RecordSiemIncidentHandoffPayload,
    RegisterSiemDetectionDeploymentPayload,
    SiemDetectionDeploymentData,
    SiemDetectionDeploymentResponse,
    SiemIncidentHandoffData,
    SiemIncidentHandoffResponse,
    TransitionSiemDetectionDeploymentPayload,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.security_export.application.detection_lifecycle_service import (
    SiemDetectionLifecycleError,
    SiemDetectionLifecycleService,
)
from atlas.modules.security_export.domain.detection_content import DetectionUseCaseId
from atlas.modules.security_export.domain.detection_deployment import SiemDetectionDeployment
from atlas.modules.security_export.domain.detection_lifecycle import DetectionLifecycleStage
from atlas.modules.security_export.domain.handoff_metrics import (
    SiemIncidentHandoffSummary,
    TriageStatus,
)

router = APIRouter(prefix="/security-export/detections", tags=["security-export"])
DEPLOYMENT_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: SiemDetectionLifecycleError) -> NoReturn:
    if error.code.endswith("not_found"):
        status = 404
    elif error.code.endswith(("invalid", "unrecognized", "not_live")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="SIEM detection lifecycle operation unavailable",
        detail="The requested detection lifecycle operation could not be completed.",
    ) from error


def _deployment_data(deployment: SiemDetectionDeployment) -> SiemDetectionDeploymentData:
    return SiemDetectionDeploymentData(
        deployment_id=deployment.deployment_id,
        detection_id=deployment.detection_id.value,
        detection_version=deployment.detection_version,
        destination_id=deployment.destination_id,
        stage=deployment.stage.value,
        owner=deployment.owner,
        registered_by=deployment.registered_by,
        registered_at=deployment.registered_at.isoformat(),
        updated_at=deployment.updated_at.isoformat(),
    )


def _handoff_data(handoff: SiemIncidentHandoffSummary) -> SiemIncidentHandoffData:
    return SiemIncidentHandoffData(
        detection_id=handoff.detection_id.value,
        detection_version=handoff.detection_version,
        alert_reference=handoff.alert_reference,
        event_references=list(handoff.event_references),
        severity=handoff.severity.value,
        confidence=handoff.confidence,
        triage_status=handoff.triage_status.value,
        affected_deployment=handoff.affected_deployment,
        affected_services=list(handoff.affected_services),
        affected_targets=list(handoff.affected_targets),
        investigation_summary=handoff.investigation_summary,
        evidence_link_kinds=list(handoff.evidence_link_kinds),
        ownership=handoff.ownership,
        synchronization_state=handoff.synchronization_state,
        ai_generated_summary=handoff.ai_generated_summary,
        summary_labeled_as_ai_generated=handoff.summary_labeled_as_ai_generated,
    )


@router.post("/{deployment_id}", response_model=SiemDetectionDeploymentResponse, status_code=201)
async def register_detection_deployment(
    deployment_id: Annotated[str, DEPLOYMENT_ID],
    payload: RegisterSiemDetectionDeploymentPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_security_export_detection_register)
    ],
) -> SiemDetectionDeploymentResponse:
    now = datetime.now(UTC)
    try:
        detection_id = DetectionUseCaseId(payload.detection_id)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="siem_detection_id_unrecognized",
            title="SIEM detection lifecycle operation unavailable",
            detail="The detection id is not one of the baseline detection catalog entries.",
        ) from error
    service: SiemDetectionLifecycleService = request.app.state.siem_detection_lifecycle_service
    try:
        deployment = await service.register(
            deployment_id=deployment_id,
            detection_id=detection_id,
            destination_id=payload.destination_id,
            owner=payload.owner,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except SiemDetectionLifecycleError as error:
        _raise(error)
    return SiemDetectionDeploymentResponse(
        data=_deployment_data(deployment),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/{deployment_id}/transitions", response_model=SiemDetectionDeploymentResponse)
async def transition_detection_deployment(
    deployment_id: Annotated[str, DEPLOYMENT_ID],
    payload: TransitionSiemDetectionDeploymentPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_security_export_detection_transition)
    ],
) -> SiemDetectionDeploymentResponse:
    now = datetime.now(UTC)
    try:
        target_stage = DetectionLifecycleStage(payload.target_stage)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="siem_detection_lifecycle_stage_unrecognized",
            title="SIEM detection lifecycle operation unavailable",
            detail="The target lifecycle stage is not recognized.",
        ) from error
    service: SiemDetectionLifecycleService = request.app.state.siem_detection_lifecycle_service
    try:
        deployment = await service.transition(
            deployment_id=deployment_id,
            target_stage=target_stage,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except SiemDetectionLifecycleError as error:
        _raise(error)
    return SiemDetectionDeploymentResponse(
        data=_deployment_data(deployment),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post(
    "/{deployment_id}/incident-handoffs",
    response_model=SiemIncidentHandoffResponse,
    status_code=201,
)
async def record_incident_handoff(
    deployment_id: Annotated[str, DEPLOYMENT_ID],
    payload: RecordSiemIncidentHandoffPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_security_export_detection_handoff_record)
    ],
) -> SiemIncidentHandoffResponse:
    now = datetime.now(UTC)
    try:
        triage_status = TriageStatus(payload.triage_status)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="siem_incident_handoff_triage_status_unrecognized",
            title="SIEM detection lifecycle operation unavailable",
            detail="The triage status is not recognized.",
        ) from error
    service: SiemDetectionLifecycleService = request.app.state.siem_detection_lifecycle_service
    try:
        handoff = await service.record_incident_handoff(
            deployment_id=deployment_id,
            alert_reference=payload.alert_reference,
            event_references=tuple(payload.event_references),
            confidence=payload.confidence,
            triage_status=triage_status,
            affected_deployment=payload.affected_deployment,
            affected_services=tuple(payload.affected_services),
            affected_targets=tuple(payload.affected_targets),
            investigation_summary=payload.investigation_summary,
            evidence_link_kinds=tuple(payload.evidence_link_kinds),
            ownership=payload.ownership,
            synchronization_state=payload.synchronization_state,
            ai_generated_summary=payload.ai_generated_summary,
            summary_labeled_as_ai_generated=payload.summary_labeled_as_ai_generated,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except SiemDetectionLifecycleError as error:
        _raise(error)
    return SiemIncidentHandoffResponse(
        data=_handoff_data(handoff),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
