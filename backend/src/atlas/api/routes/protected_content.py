from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_content_schemas import (
    OperationalKnowledgeProtectedContentData,
    OperationalKnowledgeProtectedContentInput,
    OperationalKnowledgeProtectedContentResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_protected_content_create,
    authorize_operational_knowledge_protected_content_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.protected_content import (
    OperationalKnowledgeProtectedContentService,
)
from atlas.modules.knowledge.application.protected_content_ports import (
    OperationalKnowledgeProtectedContentError,
    OperationalKnowledgeProtectedContentUncertainError,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentGrant,
)

router = APIRouter(prefix="/knowledge/protected-inspections/leases", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeProtectedContentError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeProtectedContentUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "human_required")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith(("invalid", "integrity_failed")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Operational knowledge protected content unavailable",
        detail=(
            "No partial content, finding, decision, approval, workflow authority, or operational "
            "authority was returned. Claimed uncertain first presentations are not retried."
        ),
    ) from error


def _lease_secrets(request: Request) -> dict[str, str]:
    secrets: dict[str, str] = {}
    domain = request.cookies.get("atlas_knowledge_inspection_domain")
    security = request.cookies.get("atlas_knowledge_inspection_security")
    if domain:
        secrets["review-track.domain"] = domain
    if security:
        secrets["review-track.security"] = security
    return secrets


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


def _response_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"


def _response(
    grant: OperationalKnowledgeProtectedContentGrant,
    request: Request,
    response: Response,
) -> OperationalKnowledgeProtectedContentResponse:
    _response_headers(response)
    return OperationalKnowledgeProtectedContentResponse(
        data=OperationalKnowledgeProtectedContentData.from_grant(grant),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{lease_id}/presentations",
    response_model=OperationalKnowledgeProtectedContentResponse,
    status_code=201,
)
async def create_operational_knowledge_protected_content_presentation(
    lease_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeProtectedContentInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_protected_content_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeProtectedContentResponse:
    service: OperationalKnowledgeProtectedContentService = (
        request.app.state.operational_knowledge_protected_content_service
    )
    try:
        grant = await service.create(
            actor=subject,
            source_lease_id=lease_id,
            source_lease_digest=payload.source_lease_digest,
            presentation_policy_id=payload.presentation_policy_id,
            presentation_policy_digest=payload.presentation_policy_digest,
            purpose=payload.purpose,
            sensitive_read_only_acknowledged=(
                payload.acknowledged_sensitive_read_only_content_grants_no_review_authority
            ),
            browser_session_id=_browser_session_id(request),
            lease_secrets=_lease_secrets(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeProtectedContentError as error:
        _raise(error)
    return _response(grant, request, response)


@router.get(
    "/{lease_id}/presentations/{presentation_id}",
    response_model=OperationalKnowledgeProtectedContentResponse,
)
async def get_operational_knowledge_protected_content_presentation(
    lease_id: Annotated[str, SAFE_ID],
    presentation_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_protected_content_read),
    ],
) -> OperationalKnowledgeProtectedContentResponse:
    service: OperationalKnowledgeProtectedContentService = (
        request.app.state.operational_knowledge_protected_content_service
    )
    try:
        grant = await service.get(
            actor=subject,
            source_lease_id=lease_id,
            presentation_id=presentation_id,
            browser_session_id=_browser_session_id(request),
            lease_secrets=_lease_secrets(request),
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeProtectedContentError as error:
        _raise(error)
    return _response(grant, request, response)
