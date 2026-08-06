from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.protected_inspection_schemas import (
    OperationalKnowledgeProtectedInspectionData,
    OperationalKnowledgeProtectedInspectionInput,
    OperationalKnowledgeProtectedInspectionResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_protected_inspection_create,
    authorize_operational_knowledge_protected_inspection_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.protected_inspection import (
    OperationalKnowledgeProtectedInspectionService,
)
from atlas.modules.knowledge.application.protected_inspection_ports import (
    OperationalKnowledgeProtectedInspectionError,
    OperationalKnowledgeProtectedInspectionUncertainError,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionRecord,
)

router = APIRouter(prefix="/knowledge/protected-inspections", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: OperationalKnowledgeProtectedInspectionError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeProtectedInspectionUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "mfa_required")):
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
        title="Operational knowledge protected inspection unavailable",
        detail=(
            "Lease issuance returned no content or bearer material in JSON, recorded no review "
            "decision, and granted no workflow or operational authority. Claimed uncertain "
            "attempts are not retried."
        ),
    ) from error


def _response(
    record: OperationalKnowledgeProtectedInspectionRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeProtectedInspectionResponse:
    response.headers["Cache-Control"] = "no-store"
    return OperationalKnowledgeProtectedInspectionResponse(
        data=OperationalKnowledgeProtectedInspectionData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/leases", response_model=OperationalKnowledgeProtectedInspectionResponse, status_code=201
)
async def create_operational_knowledge_protected_inspection_lease(
    payload: OperationalKnowledgeProtectedInspectionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_protected_inspection_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeProtectedInspectionResponse:
    browser_session_id = getattr(request.state, "authenticated_session_id", None)
    if not isinstance(browser_session_id, str):
        raise AtlasError(
            status=401,
            code="authentication_required",
            title="Authentication required",
            detail="A browser-bound authenticated identity is required.",
        )
    service: OperationalKnowledgeProtectedInspectionService = (
        request.app.state.operational_knowledge_protected_inspection_service
    )
    try:
        grant = await service.create(
            actor=subject,
            source_assignment_set_id=payload.source_assignment_set_id,
            source_assignment_set_digest=payload.source_assignment_set_digest,
            track_code=payload.track_code,
            inspection_policy_id=payload.inspection_policy_id,
            inspection_policy_digest=payload.inspection_policy_digest,
            purpose=payload.purpose,
            lease_only_acknowledged=(
                payload.acknowledged_lease_returns_no_content_and_records_no_decision
            ),
            browser_session_id=browser_session_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeProtectedInspectionError as error:
        _raise(error)
    if grant.lease_secret is not None:
        track = grant.record.track_code.removeprefix("review-track.")
        response.set_cookie(
            key=f"atlas_knowledge_inspection_{track}",
            value=grant.lease_secret,
            max_age=max(1, int((grant.record.expires_at - grant.record.issued_at).total_seconds())),
            httponly=True,
            secure=request.app.state.settings.environment == "production",
            samesite="strict",
            path="/api/v1/knowledge/protected-inspections",
        )
    return _response(grant.record, request, response)


@router.get("/leases/{lease_id}", response_model=OperationalKnowledgeProtectedInspectionResponse)
async def get_operational_knowledge_protected_inspection_lease(
    lease_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_protected_inspection_read),
    ],
) -> OperationalKnowledgeProtectedInspectionResponse:
    service: OperationalKnowledgeProtectedInspectionService = (
        request.app.state.operational_knowledge_protected_inspection_service
    )
    try:
        record = await service.get(
            actor=subject,
            lease_id=lease_id,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeProtectedInspectionError as error:
        _raise(error)
    return _response(record, request, response)
