from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from atlas.api.api_credential_schemas import (
    ApiCredentialCreatePayload,
    ApiCredentialCreateResponse,
    ApiCredentialData,
    ApiCredentialGrantData,
    ApiCredentialInventoryData,
    ApiCredentialInventoryResponse,
    IssuedApiCredentialData,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_api_credential_self_create,
    authorize_api_credential_self_read,
    authorize_api_credential_self_revoke,
    browser_session_subject,
)
from atlas.modules.authorization.application.bootstrap import (
    personal_api_grant_catalog,
    personal_api_grant_scopes,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationDecision, AuthorizationRequest
from atlas.modules.identity.application.api_credentials import (
    ApiCredentialOperationsError,
    ApiCredentialService,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/authentication/api-credentials", tags=["authentication"])


def _response_meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id),
        generated_at=datetime.now(UTC),
    )


async def _evaluate_grant(
    request: Request,
    subject: AuthenticatedSubject,
    permission_id: str,
) -> bool:
    settings = request.app.state.settings
    scopes = personal_api_grant_scopes(subject.organization_id, settings.environment)
    authorization_service: AuthorizationService = request.app.state.authorization_service
    decision = await authorization_service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.identity.api-credential.grant",
            scope=scopes[permission_id],
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    return decision.allowed


@router.post("", response_model=ApiCredentialCreateResponse, status_code=201)
async def create_api_credential(
    payload: ApiCredentialCreatePayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_api_credential_self_create),
    ],
) -> ApiCredentialCreateResponse:
    if len(set(payload.permission_ids)) != len(payload.permission_ids):
        raise AtlasError(
            status=422,
            code="credential_grants_invalid",
            title="Credential request invalid",
            detail="Select unique supported read-only permissions.",
        )
    settings = request.app.state.settings
    catalog = personal_api_grant_catalog(subject.organization_id, settings.environment)
    if any(permission_id not in catalog for permission_id in payload.permission_ids):
        raise AtlasError(
            status=422,
            code="credential_grants_invalid",
            title="Credential request invalid",
            detail="Select unique supported read-only permissions.",
        )
    for permission_id in sorted(payload.permission_ids):
        if not await _evaluate_grant(request, subject, permission_id):
            raise AtlasError(
                status=403,
                code="credential_grant_denied",
                title="Credential request denied",
                detail="One or more requested read-only grants are unavailable.",
            )
    service: ApiCredentialService = request.app.state.api_credential_service
    try:
        issued = await service.issue(
            subject=subject,
            display_name=payload.display_name,
            purpose=payload.purpose,
            lifetime=timedelta(minutes=payload.expires_in_minutes),
            grants=tuple(catalog[item] for item in payload.permission_ids),
            correlation_id=str(request.state.correlation_id),
        )
    except ApiCredentialOperationsError as exc:
        status = 429 if exc.code == "credential_limit_exceeded" else 422
        raise AtlasError(
            status=status,
            code=exc.code,
            title="Credential unavailable",
            detail="The API credential could not be issued.",
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    data = ApiCredentialData.from_domain(issued.record).model_dump()
    return ApiCredentialCreateResponse(
        data=IssuedApiCredentialData(**data, token=issued.token),
        meta=_response_meta(request),
    )


@router.get("", response_model=ApiCredentialInventoryResponse)
async def list_api_credentials(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_api_credential_self_read),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiCredentialInventoryResponse:
    service: ApiCredentialService = request.app.state.api_credential_service
    inventory = await service.inventory(
        subject.subject_id,
        correlation_id=str(request.state.correlation_id),
        limit=limit,
    )
    settings = request.app.state.settings
    catalog = personal_api_grant_catalog(subject.organization_id, settings.environment)
    available_grants = [
        catalog[permission_id]
        for permission_id in sorted(catalog)
        if await _evaluate_grant(request, subject, permission_id)
    ]
    response.headers["Cache-Control"] = "no-store"
    return ApiCredentialInventoryResponse(
        data=ApiCredentialInventoryData(
            credentials=[ApiCredentialData.from_domain(item) for item in inventory.records],
            available_grants=[
                ApiCredentialGrantData(
                    permission_id=item.permission_id,
                    scope_reference=item.scope_reference,
                )
                for item in available_grants
            ],
            truncated=inventory.truncated,
        ),
        meta=_response_meta(request),
    )


@router.delete("/{credential_id}", status_code=204)
async def revoke_api_credential(
    credential_id: str,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_api_credential_self_revoke),
    ],
) -> None:
    service: ApiCredentialService = request.app.state.api_credential_service
    try:
        await service.revoke(
            credential_id,
            subject_id=subject.subject_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ApiCredentialOperationsError as exc:
        raise AtlasError(
            status=404,
            code="credential_not_found",
            title="Credential unavailable",
            detail="The requested API credential is unavailable.",
        ) from exc
    response.headers["Cache-Control"] = "no-store"
