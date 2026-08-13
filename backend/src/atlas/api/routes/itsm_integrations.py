from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.itsm_integration_schemas import (
    CreateItsmIntegrationProfileInput,
    CreateItsmSandboxConformanceInput,
    ItsmIntegrationProfileData,
    ItsmIntegrationProfileInventoryData,
    ItsmIntegrationProfileInventoryResponse,
    ItsmIntegrationProfileResponse,
    ItsmSandboxConformanceData,
    ItsmSandboxConformanceResponse,
    ItsmSandboxOnboardingReadinessData,
    ItsmSandboxOnboardingReadinessResponse,
    RetireItsmIntegrationProfileInput,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_itsm_integration_create,
    authorize_itsm_integration_read,
    authorize_itsm_integration_retire,
    authorize_itsm_sandbox_conformance_create,
    authorize_itsm_sandbox_conformance_read,
    authorize_itsm_sandbox_onboarding_read,
    itsm_integration_mutation_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.application.service import ItsmIntegrationError, ItsmIntegrationService
from atlas.modules.itsm.domain.models import (
    ItsmFieldMapping,
    ItsmIntegrationProfile,
    ItsmProfileLifecycle,
)

router = APIRouter(prefix="/itsm/integrations", tags=["itsm"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _raise(error: ItsmIntegrationError) -> NoReturn:
    code = str(error)
    if code.endswith("not_found"):
        status = 404
    elif code.endswith(("required", "request_invalid")):
        status = 422
    elif code.endswith("human_required"):
        status = 403
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="ITSM integration profile operation unavailable",
        detail="The governed ITSM configuration operation could not be completed.",
    ) from error


def _response(
    record: ItsmIntegrationProfile, request: Request, response: Response
) -> ItsmIntegrationProfileResponse:
    response.headers["Cache-Control"] = "no-store"
    return ItsmIntegrationProfileResponse(
        data=ItsmIntegrationProfileData.from_domain(record), meta=_meta(request)
    )


@router.get("", response_model=ItsmIntegrationProfileInventoryResponse)
async def list_itsm_integration_profiles(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_integration_read)],
    lifecycle: Annotated[ItsmProfileLifecycle | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ItsmIntegrationProfileInventoryResponse:
    service: ItsmIntegrationService = request.app.state.itsm_integration_service
    try:
        profiles = await service.list_profiles(
            actor=subject,
            lifecycle=lifecycle,
            limit=limit,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmIntegrationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmIntegrationProfileInventoryResponse(
        data=ItsmIntegrationProfileInventoryData(
            profiles=[ItsmIntegrationProfileData.from_domain(item) for item in profiles],
            durable=service.repository.durable,
            truncated=len(profiles) == limit,
        ),
        meta=_meta(request),
    )


@router.post("", response_model=ItsmIntegrationProfileResponse, status_code=201)
async def create_itsm_integration_profile(
    payload: CreateItsmIntegrationProfileInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(itsm_integration_mutation_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_integration_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ItsmIntegrationProfileResponse:
    service: ItsmIntegrationService = request.app.state.itsm_integration_service
    data = payload.model_dump(exclude={"schema_version"})
    data["allowed_operations"] = tuple(data["allowed_operations"])
    data["field_mappings"] = tuple(ItsmFieldMapping(**item) for item in data["field_mappings"])
    try:
        record = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **data,
        )
    except (ItsmIntegrationError, ValueError) as error:
        if isinstance(error, ValueError):
            error = ItsmIntegrationError("itsm_integration_request_invalid")
        _raise(error)
    return _response(record, request, response)


@router.get("/{profile_id}", response_model=ItsmIntegrationProfileResponse)
async def get_itsm_integration_profile(
    profile_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_integration_read)],
) -> ItsmIntegrationProfileResponse:
    service: ItsmIntegrationService = request.app.state.itsm_integration_service
    try:
        record = await service.get(
            actor=subject,
            profile_id=profile_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmIntegrationError as error:
        _raise(error)
    return _response(record, request, response)


@router.post("/{profile_id}/retirements", response_model=ItsmIntegrationProfileResponse)
async def retire_itsm_integration_profile(
    profile_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: RetireItsmIntegrationProfileInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(itsm_integration_mutation_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_integration_retire)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ItsmIntegrationProfileResponse:
    service: ItsmIntegrationService = request.app.state.itsm_integration_service
    try:
        record = await service.retire(
            actor=subject,
            profile_id=profile_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ItsmIntegrationError as error:
        _raise(error)
    return _response(record, request, response)


@router.post(
    "/{profile_id}/sandbox-conformance-assessments",
    response_model=ItsmSandboxConformanceResponse,
    status_code=201,
)
async def assess_itsm_sandbox_conformance(
    profile_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: CreateItsmSandboxConformanceInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(itsm_integration_mutation_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_sandbox_conformance_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ItsmSandboxConformanceResponse:
    service: ItsmIntegrationService = request.app.state.itsm_integration_service
    try:
        assessment = await service.assess_sandbox_conformance(
            actor=subject,
            profile_id=profile_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ItsmIntegrationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmSandboxConformanceResponse(
        data=ItsmSandboxConformanceData.from_domain(assessment), meta=_meta(request)
    )


@router.get(
    "/{profile_id}/sandbox-conformance-assessments/latest",
    response_model=ItsmSandboxConformanceResponse,
)
async def latest_itsm_sandbox_conformance(
    profile_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_sandbox_conformance_read)],
) -> ItsmSandboxConformanceResponse:
    service: ItsmIntegrationService = request.app.state.itsm_integration_service
    try:
        assessment = await service.latest_sandbox_conformance(
            actor=subject,
            profile_id=profile_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmIntegrationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmSandboxConformanceResponse(
        data=ItsmSandboxConformanceData.from_domain(assessment), meta=_meta(request)
    )


@router.get(
    "/{profile_id}/sandbox-onboarding-readiness",
    response_model=ItsmSandboxOnboardingReadinessResponse,
)
async def get_itsm_sandbox_onboarding_readiness(
    profile_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_sandbox_onboarding_read)],
) -> ItsmSandboxOnboardingReadinessResponse:
    service: ItsmIntegrationService = request.app.state.itsm_integration_service
    try:
        readiness = await service.sandbox_onboarding_readiness(
            actor=subject,
            profile_id=profile_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmIntegrationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmSandboxOnboardingReadinessResponse(
        data=ItsmSandboxOnboardingReadinessData.from_domain(readiness),
        meta=_meta(request),
    )
