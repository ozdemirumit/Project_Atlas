from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_model_invocation_schemas import (
    ProtectedModelInvocationInput,
    ProtectedModelInvocationResponse,
    ProtectedModelInvocationResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_protected_model_invocation_create,
    authorize_protected_model_invocation_read,
    browser_session_subject,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_model_invocation_ports import (
    ProtectedModelInvocationError,
    ProtectedModelInvocationUncertainError,
)
from atlas.modules.ai.domain.protected_model_invocation import ProtectedModelInvocationResult
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/ai/model-contexts", tags=["ai"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ProtectedModelInvocationError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, ProtectedModelInvocationUncertainError)
        else 403
        if code.endswith(("required", "denied"))
        else 404
        if code.endswith(("not_found", "unavailable"))
        else 422
        if code.endswith(("invalid", "integrity_failed", "validation_failed"))
        else 409
    )
    raise AtlasError(
        status=status,
        code=code,
        title="Protected model invocation unavailable",
        detail=(
            "No prompt, protected draft, secret, tool, workflow, answer authority, or "
            "operational authority was returned."
        ),
    ) from error


def _browser_session_id(request: Request) -> str:
    value = getattr(request.state, "authenticated_session_id", None)
    if not isinstance(value, str):
        raise AtlasError(
            status=401,
            code="authentication_required",
            title="Authentication required",
            detail="A browser-bound authenticated identity is required.",
        )
    return value


def _response(
    result: ProtectedModelInvocationResult, request: Request, response: Response
) -> ProtectedModelInvocationResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return ProtectedModelInvocationResponse(
        data=ProtectedModelInvocationResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{context_id}/invocations", response_model=ProtectedModelInvocationResponse, status_code=201
)
async def create_protected_model_invocation(
    context_id: Annotated[str, SAFE_ID],
    payload: ProtectedModelInvocationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_protected_model_invocation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ProtectedModelInvocationResponse:
    service: GovernedProtectedModelInvocationService = (
        request.app.state.protected_model_invocation_service
    )
    try:
        result = await service.create(
            actor=subject,
            context_id=context_id,
            context_digest=payload.context_digest,
            invocation_policy_id=payload.invocation_policy_id,
            invocation_policy_digest=payload.invocation_policy_digest,
            purpose=payload.purpose,
            draft_untrusted_acknowledged=payload.acknowledged_draft_is_untrusted,
            citations_and_unknowns_acknowledged=payload.acknowledged_citations_and_unknowns_require_validation,
            no_answer_or_operational_authority_acknowledged=payload.acknowledged_no_answer_or_operational_authority,
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ProtectedModelInvocationError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{context_id}/invocations/{invocation_id}", response_model=ProtectedModelInvocationResponse
)
async def get_protected_model_invocation(
    context_id: Annotated[str, SAFE_ID],
    invocation_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_protected_model_invocation_read)],
) -> ProtectedModelInvocationResponse:
    service: GovernedProtectedModelInvocationService = (
        request.app.state.protected_model_invocation_service
    )
    try:
        result = await service.get(
            actor=subject,
            invocation_id=invocation_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.context_id != context_id:
            raise ProtectedModelInvocationError("protected_model_invocation_not_found")
    except ProtectedModelInvocationError as error:
        _raise(error)
    return _response(result, request, response)
