from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.model_context_assembly_schemas import (
    ProtectedModelContextInput,
    ProtectedModelContextResponse,
    ProtectedModelContextResultData,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_protected_model_context_create,
    authorize_protected_model_context_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.model_context_assembly import (
    GovernedProtectedModelContextService,
)
from atlas.modules.knowledge.application.model_context_assembly_ports import (
    ProtectedModelContextError,
    ProtectedModelContextUncertainError,
)
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextResult

router = APIRouter(prefix="/ai/retrievals", tags=["ai"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ProtectedModelContextError) -> NoReturn:
    code = str(error)
    if isinstance(error, ProtectedModelContextUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "mfa_required")):
        status = 403
    elif code.endswith(("not_found", "unavailable")):
        status = 404
    elif code.endswith(("invalid", "integrity_failed", "validation_failed")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Protected model-context assembly unavailable",
        detail=(
            "No protected context body, prompt layer, model invocation, tool, workflow, or "
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
    result: ProtectedModelContextResult,
    request: Request,
    response: Response,
) -> ProtectedModelContextResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return ProtectedModelContextResponse(
        data=ProtectedModelContextResultData.from_domain(result),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{retrieval_id}/model-contexts",
    response_model=ProtectedModelContextResponse,
    status_code=201,
)
async def create_protected_model_context(
    retrieval_id: Annotated[str, SAFE_ID],
    payload: ProtectedModelContextInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_protected_model_context_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ProtectedModelContextResponse:
    service: GovernedProtectedModelContextService = (
        request.app.state.protected_model_context_service
    )
    try:
        result = await service.create(
            actor=subject,
            retrieval_id=retrieval_id,
            retrieval_digest=payload.retrieval_digest,
            context_policy_id=payload.context_policy_id,
            context_policy_digest=payload.context_policy_digest,
            objective=payload.objective,
            purpose=payload.purpose,
            untrusted_intent_acknowledged=payload.acknowledged_untrusted_intent,
            citation_boundaries_acknowledged=payload.acknowledged_citation_boundaries,
            no_model_or_operational_authority_acknowledged=(
                payload.acknowledged_no_model_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except ProtectedModelContextError as error:
        _raise(error)
    return _response(result, request, response)


@router.get(
    "/{retrieval_id}/model-contexts/{context_id}",
    response_model=ProtectedModelContextResponse,
)
async def get_protected_model_context(
    retrieval_id: Annotated[str, SAFE_ID],
    context_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_protected_model_context_read),
    ],
) -> ProtectedModelContextResponse:
    service: GovernedProtectedModelContextService = (
        request.app.state.protected_model_context_service
    )
    try:
        result = await service.get(
            actor=subject,
            context_id=context_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if result.record.retrieval_id != retrieval_id:
            raise ProtectedModelContextError("protected_model_context_not_found")
    except ProtectedModelContextError as error:
        _raise(error)
    return _response(result, request, response)
