from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_workload_identity_create,
    authorize_workload_identity_read,
    authorize_workload_identity_revoke,
    authorize_workload_identity_rotate,
    browser_session_subject,
)
from atlas.api.workload_identity_schemas import (
    STABLE_ID_PATTERN,
    CreateWorkloadIdentityPayload,
    CurrentWorkloadIdentityData,
    CurrentWorkloadIdentityResponse,
    IssuedWorkloadCredentialData,
    IssuedWorkloadCredentialResponse,
    RevokeWorkloadCredentialPayload,
    RotateWorkloadCredentialPayload,
    WorkloadCredentialData,
    WorkloadCredentialResponse,
    WorkloadIdentityData,
    WorkloadIdentityInventoryData,
    WorkloadIdentityInventoryResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.application.workload_identities import (
    WorkloadIdentityError,
    WorkloadIdentityService,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/workload-identities", tags=["workload-identities"])
IDEMPOTENCY_HEADER = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _raise_workload_error(error: WorkloadIdentityError) -> NoReturn:
    if error.code == "workload_idempotency_conflict":
        raise AtlasError(
            status=409,
            code=error.code,
            title="Workload identity conflict",
            detail="The idempotency key is already bound to a different request.",
        ) from error
    if error.code in {"workload_rotation_unavailable", "workload_identity_unavailable"}:
        raise AtlasError(
            status=409,
            code="workload_identity_unavailable",
            title="Workload identity unavailable",
            detail="The requested workload identity state is unavailable.",
        ) from error
    if error.code == "workload_authentication_failed":
        raise AtlasError(
            status=401,
            code=error.code,
            title="Workload authentication failed",
            detail="The workload credential is invalid or no longer active.",
        ) from error
    if error.code == "enterprise_human_required":
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Workload identity governance is not authorized.",
        ) from error
    raise AtlasError(
        status=404,
        code="workload_credential_unavailable",
        title="Workload credential unavailable",
        detail="The requested workload credential is unavailable.",
    ) from error


@router.get("", response_model=WorkloadIdentityInventoryResponse)
async def get_workload_identities(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_workload_identity_read)],
    query: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> WorkloadIdentityInventoryResponse:
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        inventory = await service.inventory(
            actor=subject,
            query=query,
            limit=limit,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        _raise_workload_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return WorkloadIdentityInventoryResponse(
        data=WorkloadIdentityInventoryData(
            identities=[WorkloadIdentityData.from_domain(item) for item in inventory.identities],
            credentials=[
                WorkloadCredentialData.from_domain(item) for item in inventory.credentials
            ],
            truncated=inventory.truncated,
        ),
        meta=_meta(request),
    )


@router.post("", response_model=IssuedWorkloadCredentialResponse, status_code=201)
async def create_workload_identity(
    payload: CreateWorkloadIdentityPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_workload_identity_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> IssuedWorkloadCredentialResponse:
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        issued = await service.create(
            actor=subject,
            identity_id=payload.identity_id,
            display_name=payload.display_name,
            service_id=payload.service_id,
            instance_id=payload.instance_id,
            owner_subject_id=payload.owner_subject_id,
            purpose=payload.purpose,
            audiences=tuple(payload.audiences),
            secret_reference_ids=tuple(payload.secret_reference_ids),
            lifetime=timedelta(minutes=payload.lifetime_minutes),
            reason=payload.reason,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        _raise_workload_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return IssuedWorkloadCredentialResponse(
        data=IssuedWorkloadCredentialData.from_domain(issued), meta=_meta(request)
    )


@router.post(
    "/{identity_id}/rotations",
    response_model=IssuedWorkloadCredentialResponse,
    status_code=201,
)
async def rotate_workload_credential(
    identity_id: str,
    payload: RotateWorkloadCredentialPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_workload_identity_rotate)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> IssuedWorkloadCredentialResponse:
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        issued = await service.rotate(
            identity_id,
            actor=subject,
            expected_version=payload.expected_version,
            lifetime=timedelta(minutes=payload.lifetime_minutes),
            overlap=timedelta(minutes=payload.overlap_minutes),
            reason=payload.reason,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        _raise_workload_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return IssuedWorkloadCredentialResponse(
        data=IssuedWorkloadCredentialData.from_domain(issued), meta=_meta(request)
    )


@router.post(
    "/credentials/{credential_id}/revocations",
    response_model=WorkloadCredentialResponse,
)
async def revoke_workload_credential(
    credential_id: str,
    payload: RevokeWorkloadCredentialPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_workload_identity_revoke)],
    idempotency_key: Annotated[str, IDEMPOTENCY_HEADER],
) -> WorkloadCredentialResponse:
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        record = await service.revoke(
            credential_id,
            actor=subject,
            expected_version=payload.expected_version,
            reason=payload.reason,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        _raise_workload_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return WorkloadCredentialResponse(
        data=WorkloadCredentialData.from_domain(record), meta=_meta(request)
    )


@router.get("/current", response_model=CurrentWorkloadIdentityResponse)
async def get_current_workload_identity(
    request: Request,
    response: Response,
    authorization: Annotated[str, Header(alias="Authorization")],
    audience: Annotated[str, Header(alias="X-Atlas-Audience", pattern=STABLE_ID_PATTERN)],
    environment_id: Annotated[str, Header(alias="X-Atlas-Environment", pattern=STABLE_ID_PATTERN)],
) -> CurrentWorkloadIdentityResponse:
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "workload":
        token = ""
    service: WorkloadIdentityService = request.app.state.workload_identity_service
    try:
        subject = await service.authenticate(
            token,
            audience=audience,
            environment_id=environment_id,
            correlation_id=str(request.state.correlation_id),
        )
    except WorkloadIdentityError as exc:
        _raise_workload_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return CurrentWorkloadIdentityResponse(
        data=CurrentWorkloadIdentityData.from_domain(
            subject, audience=audience, environment_id=environment_id
        ),
        meta=_meta(request),
    )
