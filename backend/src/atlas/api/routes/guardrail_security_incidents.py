from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.guardrail_security_incident_schemas import (
    SecurityIncidentContainInput,
    SecurityIncidentData,
    SecurityIncidentOpenInput,
    SecurityIncidentRecoveryInput,
    SecurityIncidentResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_guardrail_security_incident_close,
    authorize_guardrail_security_incident_contain,
    authorize_guardrail_security_incident_open,
    authorize_guardrail_security_incident_recover,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.guardrails.application.security_incident import (
    SecurityIncidentError,
    SecurityIncidentService,
)
from atlas.modules.guardrails.domain.security_incident import (
    IncidentTrigger,
    SecurityIncidentRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind

router = APIRouter(prefix="/guardrails/security-incidents", tags=["guardrails"])
INCIDENT_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(exc: SecurityIncidentError) -> NoReturn:
    status_by_code = {
        "security_incident_invalid": 422,
        "security_incident_unavailable": 404,
        "security_incident_close_invalid": 422,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 409),
        code=exc.code,
        title="Security incident unavailable",
        detail="The requested security incident operation could not be completed.",
    ) from exc


def _response(
    incident: SecurityIncidentRecord, correlation_id: str, generated_at: datetime
) -> SecurityIncidentResponse:
    return SecurityIncidentResponse(
        data=SecurityIncidentData.from_domain(incident),
        meta=ResponseMeta(correlation_id=correlation_id, generated_at=generated_at),
    )


@router.post("/{incident_id}", response_model=SecurityIncidentResponse, status_code=201)
async def open_security_incident(
    incident_id: Annotated[str, INCIDENT_ID],
    payload: SecurityIncidentOpenInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_guardrail_security_incident_open)
    ],
) -> SecurityIncidentResponse:
    now = datetime.now(UTC)
    service: SecurityIncidentService = request.app.state.security_incident_service
    try:
        trigger = IncidentTrigger(payload.trigger)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="security_incident_trigger_invalid",
            title="Security incident unavailable",
            detail="The incident trigger is not recognized.",
        ) from error
    try:
        incident = await service.open_incident(
            incident_id=incident_id,
            trigger=trigger,
            affected_references=tuple(payload.affected_references),
            correlation_id=str(request.state.correlation_id),
        )
    except SecurityIncidentError as error:
        _raise(error)
    return _response(incident, str(request.state.correlation_id), now)


@router.post("/{incident_id}/containment", response_model=SecurityIncidentResponse, status_code=200)
async def contain_security_incident(
    incident_id: Annotated[str, INCIDENT_ID],
    payload: SecurityIncidentContainInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_guardrail_security_incident_contain)
    ],
) -> SecurityIncidentResponse:
    now = datetime.now(UTC)
    service: SecurityIncidentService = request.app.state.security_incident_service
    try:
        incident = await service.contain_and_preserve(
            incident_id=incident_id,
            alert_reference=payload.alert_reference,
            correlation_id=str(request.state.correlation_id),
        )
    except SecurityIncidentError as error:
        _raise(error)
    return _response(incident, str(request.state.correlation_id), now)


@router.post("/{incident_id}/recovery", response_model=SecurityIncidentResponse, status_code=200)
async def record_security_incident_recovery(
    incident_id: Annotated[str, INCIDENT_ID],
    payload: SecurityIncidentRecoveryInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_guardrail_security_incident_recover)
    ],
) -> SecurityIncidentResponse:
    now = datetime.now(UTC)
    service: SecurityIncidentService = request.app.state.security_incident_service
    try:
        incident = await service.record_recovery(
            incident_id=incident_id,
            credentials_revoked=payload.credentials_revoked,
            scope_assessment=payload.scope_assessment,
            improvement_reference=payload.improvement_reference,
            correlation_id=str(request.state.correlation_id),
        )
    except SecurityIncidentError as error:
        _raise(error)
    return _response(incident, str(request.state.correlation_id), now)


@router.post("/{incident_id}/closure", response_model=SecurityIncidentResponse, status_code=200)
async def close_security_incident(
    incident_id: Annotated[str, INCIDENT_ID],
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_guardrail_security_incident_close)
    ],
) -> SecurityIncidentResponse:
    now = datetime.now(UTC)
    service: SecurityIncidentService = request.app.state.security_incident_service
    if subject.kind is not SubjectKind.HUMAN:
        raise AtlasError(
            status=403,
            code="security_incident_close_requires_human",
            title="Security incident unavailable",
            detail="Only a human subject may decide security incident closure.",
        )
    try:
        incident = await service.close(
            incident_id=incident_id,
            closed_by=subject.subject_id,
            closer_kind=subject.kind,
            correlation_id=str(request.state.correlation_id),
        )
    except SecurityIncidentError as error:
        _raise(error)
    return _response(incident, str(request.state.correlation_id), now)
