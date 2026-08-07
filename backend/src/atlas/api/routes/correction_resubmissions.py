from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.correction_resubmission_schemas import (
    OperationalKnowledgeCorrectionData,
    OperationalKnowledgeCorrectionInput,
    OperationalKnowledgeCorrectionResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_correction_create,
    authorize_operational_knowledge_correction_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.correction_resubmission import (
    OperationalKnowledgeCorrectionService,
)
from atlas.modules.knowledge.application.correction_resubmission_ports import (
    OperationalKnowledgeCorrectionError,
    OperationalKnowledgeCorrectionUncertainError,
)
from atlas.modules.knowledge.domain.correction_resubmission import (
    OperationalKnowledgeCorrectionRecord,
)

router = APIRouter(prefix="/knowledge/review-requests", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: OperationalKnowledgeCorrectionError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeCorrectionUncertainError):
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
        title="Operational knowledge correction unavailable",
        detail=(
            "No corrected content, artifact location, approval, publication, workflow authority, "
            "or operational authority was returned. Claimed uncertain corrections are not retried."
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
    record: OperationalKnowledgeCorrectionRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeCorrectionResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return OperationalKnowledgeCorrectionResponse(
        data=OperationalKnowledgeCorrectionData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{review_request_id}/corrections",
    response_model=OperationalKnowledgeCorrectionResponse,
    status_code=201,
)
async def create_operational_knowledge_correction(
    review_request_id: Annotated[str, SAFE_ID],
    payload: OperationalKnowledgeCorrectionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_correction_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeCorrectionResponse:
    service: OperationalKnowledgeCorrectionService = (
        request.app.state.operational_knowledge_correction_service
    )
    try:
        record = await service.create(
            actor=subject,
            source_review_request_id=review_request_id,
            source_review_request_digest=payload.source_review_request_digest,
            source_decision_ids=payload.source_decision_ids,
            source_decision_digests=payload.source_decision_digests,
            correction_submission_id=payload.correction_submission_id,
            correction_submission_digest=payload.correction_submission_digest,
            correction_policy_id=payload.correction_policy_id,
            correction_policy_digest=payload.correction_policy_digest,
            purpose=payload.purpose,
            exact_change_requirements_addressed_acknowledged=(
                payload.acknowledged_exact_change_requirements_addressed
            ),
            new_immutable_generation_acknowledged=(
                payload.acknowledged_new_immutable_review_generation
            ),
            no_later_authority_acknowledged=(
                payload.acknowledged_no_approval_or_operational_authority
            ),
            browser_session_id=_browser_session_id(request),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeCorrectionError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{review_request_id}/corrections/{correction_id}",
    response_model=OperationalKnowledgeCorrectionResponse,
)
async def get_operational_knowledge_correction(
    review_request_id: Annotated[str, SAFE_ID],
    correction_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_correction_read),
    ],
) -> OperationalKnowledgeCorrectionResponse:
    service: OperationalKnowledgeCorrectionService = (
        request.app.state.operational_knowledge_correction_service
    )
    try:
        record = await service.get(
            actor=subject,
            correction_id=correction_id,
            browser_session_id=_browser_session_id(request),
            correlation_id=str(request.state.correlation_id),
        )
        if record.source_review_request_id != review_request_id:
            raise OperationalKnowledgeCorrectionError("operational_knowledge_correction_not_found")
    except OperationalKnowledgeCorrectionError as error:
        _raise(error)
    return _response(record, request, response)
