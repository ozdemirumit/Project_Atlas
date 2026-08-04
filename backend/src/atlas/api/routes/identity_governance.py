from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.identity_governance_schemas import (
    AdministrativeRevocationPayload,
    IdentityDisablementData,
    IdentityDisablementResponse,
    IdentityGovernanceApiCredential,
    IdentityGovernanceApiCredentialResponse,
    IdentityGovernanceInventoryData,
    IdentityGovernanceInventoryResponse,
    IdentityGovernanceSession,
    IdentityGovernanceSessionResponse,
    IdentityGovernanceSubject,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_api_credential_admin_revoke,
    authorize_identity_governance_read,
    authorize_identity_subject_admin_disable,
    authorize_session_admin_revoke,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.application.governance import (
    IdentityGovernanceError,
    IdentityGovernanceService,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/identity-governance", tags=["identity-governance"])


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id),
        generated_at=datetime.now(UTC),
    )


def _raise_governance_error(error: IdentityGovernanceError) -> NoReturn:
    if error.code == "governance_idempotency_conflict":
        raise AtlasError(
            status=409,
            code=error.code,
            title="Governance conflict",
            detail="The idempotency key is already bound to a different request.",
        ) from error
    if error.code == "current_admin_session_protected":
        raise AtlasError(
            status=409,
            code=error.code,
            title="Current session protected",
            detail="Use the sign-out flow to terminate the current administrator session.",
        ) from error
    if error.code == "current_admin_identity_protected":
        raise AtlasError(
            status=409,
            code=error.code,
            title="Current identity protected",
            detail="The current administrator identity cannot disable itself.",
        ) from error
    if error.code == "identity_disablement_unavailable":
        raise AtlasError(
            status=503,
            code=error.code,
            title="Identity disablement unavailable",
            detail="The identity state was not changed.",
        ) from error
    if error.code == "enterprise_human_required":
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Identity governance is not authorized.",
        ) from error
    raise AtlasError(
        status=404,
        code="governance_target_unavailable",
        title="Identity resource unavailable",
        detail="The requested identity resource is unavailable.",
    ) from error


@router.get("", response_model=IdentityGovernanceInventoryResponse)
async def get_identity_governance_inventory(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_identity_governance_read)],
    query: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> IdentityGovernanceInventoryResponse:
    service: IdentityGovernanceService = request.app.state.identity_governance_service
    try:
        inventory = await service.inventory(
            actor=subject,
            query=query,
            limit=limit,
            correlation_id=str(request.state.correlation_id),
        )
    except IdentityGovernanceError as exc:
        _raise_governance_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return IdentityGovernanceInventoryResponse(
        data=IdentityGovernanceInventoryData(
            subjects=[IdentityGovernanceSubject.from_domain(item) for item in inventory.subjects],
            sessions=[IdentityGovernanceSession.from_domain(item) for item in inventory.sessions],
            api_credentials=[
                IdentityGovernanceApiCredential.from_domain(item)
                for item in inventory.api_credentials
            ],
            truncated=inventory.truncated,
        ),
        meta=_meta(request),
    )


@router.post(
    "/subjects/{subject_id}/disablements",
    response_model=IdentityDisablementResponse,
)
async def administratively_disable_identity(
    subject_id: str,
    payload: AdministrativeRevocationPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_identity_subject_admin_disable),
    ],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
        ),
    ],
) -> IdentityDisablementResponse:
    service: IdentityGovernanceService = request.app.state.identity_governance_service
    try:
        result = await service.disable_identity(
            subject_id,
            actor=subject,
            expected_version=payload.expected_version,
            reason=payload.reason.strip(),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except IdentityGovernanceError as exc:
        _raise_governance_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return IdentityDisablementResponse(
        data=IdentityDisablementData.from_domain(result),
        meta=_meta(request),
    )


@router.post(
    "/sessions/{session_id}/revocations",
    response_model=IdentityGovernanceSessionResponse,
)
async def administratively_revoke_session(
    session_id: str,
    payload: AdministrativeRevocationPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_session_admin_revoke)],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
        ),
    ],
) -> IdentityGovernanceSessionResponse:
    current_session_id = getattr(request.state, "authenticated_session_id", None)
    if current_session_id is None:
        raise AtlasError(
            status=403,
            code="browser_session_required",
            title="Browser session required",
            detail="Use a CSRF-protected browser session for identity governance.",
        )
    service: IdentityGovernanceService = request.app.state.identity_governance_service
    try:
        record = await service.revoke_session(
            session_id,
            actor=subject,
            current_session_id=str(current_session_id),
            expected_version=payload.expected_version,
            reason=payload.reason.strip(),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except IdentityGovernanceError as exc:
        _raise_governance_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return IdentityGovernanceSessionResponse(
        data=IdentityGovernanceSession.from_domain(record),
        meta=_meta(request),
    )


@router.post(
    "/api-credentials/{credential_id}/revocations",
    response_model=IdentityGovernanceApiCredentialResponse,
)
async def administratively_revoke_api_credential(
    credential_id: str,
    payload: AdministrativeRevocationPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_api_credential_admin_revoke)],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
        ),
    ],
) -> IdentityGovernanceApiCredentialResponse:
    service: IdentityGovernanceService = request.app.state.identity_governance_service
    try:
        record = await service.revoke_api_credential(
            credential_id,
            actor=subject,
            expected_version=payload.expected_version,
            reason=payload.reason.strip(),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except IdentityGovernanceError as exc:
        _raise_governance_error(exc)
    response.headers["Cache-Control"] = "no-store"
    return IdentityGovernanceApiCredentialResponse(
        data=IdentityGovernanceApiCredential.from_domain(record),
        meta=_meta(request),
    )
