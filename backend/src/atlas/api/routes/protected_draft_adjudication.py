from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_draft_adjudication_schemas import (
    ProtectedDraftAdjudicationInput,
    ProtectedDraftAdjudicationResponse,
    ProtectedDraftAdjudicationResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_protected_draft_adjudication_create,
    authorize_protected_draft_adjudication_read,
    browser_session_subject,
)
from atlas.modules.ai.application.protected_draft_adjudication import (
    GovernedProtectedDraftAdjudicationService,
)
from atlas.modules.ai.application.protected_draft_adjudication_ports import (
    ProtectedDraftAdjudicationError,
    ProtectedDraftAdjudicationUncertainError,
)
from atlas.modules.ai.domain.protected_draft_adjudication import ProtectedDraftAdjudicationResult
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/ai/model-invocations", tags=["ai"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ProtectedDraftAdjudicationError) -> NoReturn:
    code = str(error)
    status = (
        503
        if isinstance(error, ProtectedDraftAdjudicationUncertainError)
        else 403
        if code.endswith(("required", "denied", "mfa_required"))
        else 404
        if code.endswith(("not_found", "unavailable"))
        else 422
        if code.endswith(("invalid", "integrity_failed", "validation_failed"))
        else 409
    )
    raise AtlasError(
        status=status,
        code=code,
        title="Protected draft adjudication unavailable",
        detail=(
            "No draft, evidence, protected report, answer, tool, workflow, or operational "
            "authority was returned."
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
    result: ProtectedDraftAdjudicationResult, request: Request, response: Response
) -> ProtectedDraftAdjudicationResponse:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        }
    )
    return ProtectedDraftAdjudicationResponse(
        data=ProtectedDraftAdjudicationResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{invocation_id}/adjudications",
    response_model=ProtectedDraftAdjudicationResponse,
    status_code=201,
)
async def create_protected_draft_adjudication(
    invocation_id: Annotated[str, SAFE_ID],
    payload: ProtectedDraftAdjudicationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_protected_draft_adjudication_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ProtectedDraftAdjudicationResponse:
    service: GovernedProtectedDraftAdjudicationService = (
        request.app.state.protected_draft_adjudication_service
    )
    try:
        result = await service.create(
            actor=subject,
            invocation_id=invocation_id,
            invocation_digest=payload.invocation_digest,
            adjudication_policy_id=payload.adjudication_policy_id,
            adjudication_policy_digest=payload.adjudication_policy_digest,
            purpose=payload.purpose,
            draft_untrusted_acknowledged=payload.acknowledged_draft_is_untrusted,
            no_content_presentation_acknowledged=payload.acknowledged_no_content_presentation,
            no_answer_or_operational_authority_acknowledged=payload.acknowledged_no_answer_or_operational_authority,
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ProtectedDraftAdjudicationError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{invocation_id}/adjudications/{adjudication_id}",
    response_model=ProtectedDraftAdjudicationResponse,
)
async def get_protected_draft_adjudication(
    invocation_id: Annotated[str, SAFE_ID],
    adjudication_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_protected_draft_adjudication_read)
    ],
) -> ProtectedDraftAdjudicationResponse:
    service: GovernedProtectedDraftAdjudicationService = (
        request.app.state.protected_draft_adjudication_service
    )
    try:
        result = await service.get(
            actor=subject,
            adjudication_id=adjudication_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.invocation_id != invocation_id:
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_not_found")
    except ProtectedDraftAdjudicationError as error:
        _raise(error)
    return _response(result, request, response)
