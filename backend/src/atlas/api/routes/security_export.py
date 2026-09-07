from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_security_export_destination_administer,
    authorize_security_export_overview_read,
    authorize_security_export_test_create,
)
from atlas.api.security_export_schemas import (
    DeliveryRecordData,
    SecurityExportOverviewData,
    SecurityExportOverviewResponse,
    SecurityExportTestResponse,
    SyslogDestinationDisablementPayload,
    SyslogDestinationProfileData,
    SyslogDestinationProfilePayload,
    SyslogDestinationProfileResponse,
    SyslogDestinationValidationData,
    SyslogDestinationValidationResponse,
    SyslogDestinationValidationStepPayload,
)
from atlas.modules.authorization.application.bootstrap import security_export_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.security_export.application.destination_administration import (
    SyslogDestinationAdministrationError,
    SyslogDestinationAdministrationService,
)
from atlas.modules.security_export.application.service import (
    SecurityExportAccessContext,
    SecurityExportOperationsError,
    SecurityExportService,
)
from atlas.modules.security_export.domain.destination_administration import (
    DestinationValidationStep,
)

router = APIRouter(prefix="/security-export", tags=["security-export"])


def _context(
    request: Request,
    subject: AuthenticatedSubject,
    decision: AuthorizationDecision,
    requested_at: datetime,
) -> SecurityExportAccessContext:
    scope = security_export_scope(subject.organization_id, request.app.state.settings.environment)
    return SecurityExportAccessContext(
        subject_id=subject.subject_id,
        actor_type=subject.kind.value,
        authentication_method=subject.authentication_method.value,
        assurance_level=subject.assurance_level.value,
        organization_id=scope.organization_id,
        environment_id=scope.environment_id,
        site_id=scope.site_id,
        resource_id=scope.resource_id,
        correlation_id=str(request.state.correlation_id),
        decision_id=decision.decision_id,
        requested_at=requested_at,
    )


@router.get("/overview", response_model=SecurityExportOverviewResponse)
async def get_security_export_overview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_security_export_overview_read)],
) -> SecurityExportOverviewResponse:
    now = datetime.now(UTC)
    service: SecurityExportService = request.app.state.security_export_service
    try:
        overview = await service.get_overview(context=_context(request, subject, decision, now))
    except SecurityExportOperationsError as exc:
        raise AtlasError(
            status=409,
            code=exc.code,
            title="Security export unavailable",
            detail=exc.detail,
        ) from exc
    return SecurityExportOverviewResponse(
        data=SecurityExportOverviewData.from_domain(overview),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/test-event", response_model=SecurityExportTestResponse)
async def create_security_export_test_event(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_security_export_test_create)],
) -> SecurityExportTestResponse:
    now = datetime.now(UTC)
    service: SecurityExportService = request.app.state.security_export_service
    try:
        delivery = await service.emit_test_event(context=_context(request, subject, decision, now))
    except SecurityExportOperationsError as exc:
        raise AtlasError(
            status=409,
            code=exc.code,
            title="Security export test unavailable",
            detail=exc.detail,
        ) from exc
    return SecurityExportTestResponse(
        data=DeliveryRecordData.from_domain(delivery),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


def _raise_destination_administration_error(
    exc: SyslogDestinationAdministrationError,
) -> NoReturn:
    status_by_code = {
        "syslog_destination_unavailable": 404,
        "syslog_destination_already_registered": 409,
        "syslog_destination_profile_invalid": 422,
        "syslog_destination_validation_out_of_order": 422,
        "syslog_destination_validation_incomplete": 409,
        "syslog_destination_disablement_denied": 403,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 409),
        code=exc.code,
        title="Syslog destination administration unavailable",
        detail="The requested destination administration operation could not be completed.",
    ) from exc


@router.post("/destinations", response_model=SyslogDestinationProfileResponse, status_code=201)
async def register_syslog_destination(
    payload: SyslogDestinationProfilePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_security_export_destination_administer)
    ],
) -> SyslogDestinationProfileResponse:
    now = datetime.now(UTC)
    service: SyslogDestinationAdministrationService = (
        request.app.state.syslog_destination_administration_service
    )
    try:
        profile = await service.register_profile(
            destination_id=payload.destination_id,
            owner=payload.owner,
            purpose=payload.purpose,
            environment_id=payload.environment_id,
            maintenance_windows=payload.maintenance_windows,
            health_alert_recipients=payload.health_alert_recipients,
            mandatory=payload.mandatory,
            correlation_id=str(request.state.correlation_id),
        )
    except SyslogDestinationAdministrationError as exc:
        _raise_destination_administration_error(exc)
    return SyslogDestinationProfileResponse(
        data=SyslogDestinationProfileData.from_domain(profile),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post(
    "/destinations/{destination_id}/validation-steps",
    response_model=SyslogDestinationValidationResponse,
)
async def record_syslog_destination_validation_step(
    destination_id: str,
    payload: SyslogDestinationValidationStepPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_security_export_destination_administer)
    ],
) -> SyslogDestinationValidationResponse:
    now = datetime.now(UTC)
    service: SyslogDestinationAdministrationService = (
        request.app.state.syslog_destination_administration_service
    )
    try:
        step = DestinationValidationStep(payload.step)
    except ValueError as exc:
        raise AtlasError(
            status=422,
            code="syslog_destination_validation_step_invalid",
            title="Syslog destination administration unavailable",
            detail="The validation step is not recognized.",
        ) from exc
    try:
        record = await service.record_validation_step(
            destination_id=destination_id,
            step=step,
            correlation_id=str(request.state.correlation_id),
        )
    except SyslogDestinationAdministrationError as exc:
        _raise_destination_administration_error(exc)
    return SyslogDestinationValidationResponse(
        data=SyslogDestinationValidationData.from_domain(record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post(
    "/destinations/{destination_id}/activate", response_model=SyslogDestinationProfileResponse
)
async def activate_syslog_destination(
    destination_id: str,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_security_export_destination_administer)
    ],
) -> SyslogDestinationProfileResponse:
    now = datetime.now(UTC)
    service: SyslogDestinationAdministrationService = (
        request.app.state.syslog_destination_administration_service
    )
    try:
        profile = await service.activate(
            destination_id=destination_id,
            activated_by=subject.subject_id,
            correlation_id=str(request.state.correlation_id),
        )
    except SyslogDestinationAdministrationError as exc:
        _raise_destination_administration_error(exc)
    return SyslogDestinationProfileResponse(
        data=SyslogDestinationProfileData.from_domain(profile),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/destinations/{destination_id}/disable", status_code=204)
async def disable_syslog_destination(
    destination_id: str,
    payload: SyslogDestinationDisablementPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_security_export_destination_administer)
    ],
) -> None:
    service: SyslogDestinationAdministrationService = (
        request.app.state.syslog_destination_administration_service
    )
    try:
        await service.disable(
            destination_id=destination_id,
            disabled_by=subject.subject_id,
            reason=payload.reason,
            elevated_authorization=payload.elevated_authorization,
            warning_acknowledged=payload.warning_acknowledged,
            correlation_id=str(request.state.correlation_id),
        )
    except SyslogDestinationAdministrationError as exc:
        _raise_destination_administration_error(exc)
