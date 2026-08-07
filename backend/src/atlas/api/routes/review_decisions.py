from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.review_decision_schemas import (
    OperationalKnowledgeTrackReviewDecisionData,
    OperationalKnowledgeTrackReviewDecisionInput,
    OperationalKnowledgeTrackReviewDecisionResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_track_review_decision_create,
    authorize_operational_knowledge_track_review_decision_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.review_decision import (
    OperationalKnowledgeTrackReviewDecisionService,
)
from atlas.modules.knowledge.application.review_decision_ports import (
    OperationalKnowledgeTrackReviewDecisionError,
    OperationalKnowledgeTrackReviewDecisionUncertainError,
)
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionGrant,
)

router = APIRouter(prefix="/knowledge/protected-inspections/leases", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeTrackReviewDecisionError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeTrackReviewDecisionUncertainError):
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
        title="Operational knowledge track review decision unavailable",
        detail=(
            "No finding content, correction, approval, publication, workflow authority, or "
            "operational authority was returned. Claimed uncertain decisions are not retried."
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


def _response(
    grant: OperationalKnowledgeTrackReviewDecisionGrant,
    request: Request,
    response: Response,
) -> OperationalKnowledgeTrackReviewDecisionResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgeTrackReviewDecisionResponse(
        data=OperationalKnowledgeTrackReviewDecisionData.from_grant(grant),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{lease_id}/presentations/{content_presentation_id}/findings/{finding_packet_id}"
    "/presentations/{finding_presentation_id}/decisions",
    response_model=OperationalKnowledgeTrackReviewDecisionResponse,
    status_code=201,
)
async def create_operational_knowledge_track_review_decision(
    lease_id: Annotated[str, SAFE_ID],
    content_presentation_id: Annotated[str, SAFE_ID],
    finding_packet_id: Annotated[str, SAFE_ID],
    finding_presentation_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeTrackReviewDecisionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_track_review_decision_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeTrackReviewDecisionResponse:
    service: OperationalKnowledgeTrackReviewDecisionService = (
        request.app.state.operational_knowledge_track_review_decision_service
    )
    try:
        grant = await service.create(
            actor=subject,
            source_lease_id=lease_id,
            source_content_presentation_id=content_presentation_id,
            source_finding_packet_id=finding_packet_id,
            source_finding_presentation_id=finding_presentation_id,
            source_finding_presentation_digest=payload.source_finding_presentation_digest,
            decision_policy_id=payload.decision_policy_id,
            decision_policy_digest=payload.decision_policy_digest,
            disposition_code=payload.disposition_code,
            basis_codes=payload.basis_codes,
            purpose=payload.purpose,
            exact_findings_reviewed_acknowledged=(payload.acknowledged_exact_findings_reviewed),
            human_track_decision_acknowledged=payload.acknowledged_human_track_decision,
            no_approval_or_operational_authority_acknowledged=(
                payload.acknowledged_no_approval_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            lease_secrets=_lease_secrets(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeTrackReviewDecisionError as error:
        _raise(error)
    return _response(grant, request, response)


@router.get(
    "/{lease_id}/presentations/{content_presentation_id}/findings/{finding_packet_id}"
    "/presentations/{finding_presentation_id}/decisions/{decision_id}",
    response_model=OperationalKnowledgeTrackReviewDecisionResponse,
)
async def get_operational_knowledge_track_review_decision(
    lease_id: Annotated[str, SAFE_ID],
    content_presentation_id: Annotated[str, SAFE_ID],
    finding_packet_id: Annotated[str, SAFE_ID],
    finding_presentation_id: Annotated[str, SAFE_ID],
    decision_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_track_review_decision_read),
    ],
) -> OperationalKnowledgeTrackReviewDecisionResponse:
    service: OperationalKnowledgeTrackReviewDecisionService = (
        request.app.state.operational_knowledge_track_review_decision_service
    )
    try:
        grant = await service.get(
            actor=subject,
            source_lease_id=lease_id,
            source_content_presentation_id=content_presentation_id,
            source_finding_packet_id=finding_packet_id,
            source_finding_presentation_id=finding_presentation_id,
            decision_id=decision_id,
            browser_session_id=_browser_session_id(request),
            lease_secrets=_lease_secrets(request),
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeTrackReviewDecisionError as error:
        _raise(error)
    return _response(grant, request, response)
