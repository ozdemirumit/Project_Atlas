from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.draft_review_request_schemas import (
    OperationalKnowledgeReviewRequestInput,
    OperationalKnowledgeReviewRequestInventoryData,
    OperationalKnowledgeReviewRequestInventoryItemResponse,
    OperationalKnowledgeReviewRequestInventoryResponse,
    OperationalKnowledgeReviewRequestOptionData,
    OperationalKnowledgeReviewRequestOptionsResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_review_request_create,
    authorize_operational_knowledge_review_request_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.draft_review_request import (
    OperationalKnowledgeReviewRequestService,
)
from atlas.modules.knowledge.application.draft_review_request_ports import (
    OperationalKnowledgeReviewRequestError,
    OperationalKnowledgeReviewRequestUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)

router = APIRouter(prefix="/knowledge/operational-review-requests", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


def _raise(error: OperationalKnowledgeReviewRequestError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeReviewRequestUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "separation_required")):
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
        title="Operational knowledge review request unavailable",
        detail=(
            "Review orchestration did not expose content, assign a reviewer, record a decision, "
            "approve or publish knowledge, or grant operational authority. Claimed uncertain "
            "attempts are not retried."
        ),
    ) from error


def _response(
    record: OperationalKnowledgeReviewRequestRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeReviewRequestInventoryItemResponse:
    response.headers["Cache-Control"] = "no-store"
    return OperationalKnowledgeReviewRequestInventoryItemResponse(
        data=OperationalKnowledgeReviewRequestInventoryData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("", response_model=OperationalKnowledgeReviewRequestInventoryResponse)
async def list_operational_knowledge_review_requests(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_review_request_read),
    ],
    source_draft_id: Annotated[str | None, Query(pattern=STABLE_ID)] = None,
) -> OperationalKnowledgeReviewRequestInventoryResponse:
    service: OperationalKnowledgeReviewRequestService = (
        request.app.state.operational_knowledge_review_request_service
    )
    try:
        records = await service.list_requests(
            actor=subject,
            source_draft_id=source_draft_id,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeReviewRequestError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return OperationalKnowledgeReviewRequestInventoryResponse(
        data=tuple(
            OperationalKnowledgeReviewRequestInventoryData.from_domain(record) for record in records
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/options", response_model=OperationalKnowledgeReviewRequestOptionsResponse)
async def list_operational_knowledge_review_request_options(
    source_draft_id: Annotated[str, Query(pattern=STABLE_ID)],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_review_request_read),
    ],
) -> OperationalKnowledgeReviewRequestOptionsResponse:
    service: OperationalKnowledgeReviewRequestService = (
        request.app.state.operational_knowledge_review_request_service
    )
    try:
        options = await service.list_options(
            actor=subject,
            source_draft_id=source_draft_id,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeReviewRequestError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return OperationalKnowledgeReviewRequestOptionsResponse(
        data=tuple(
            OperationalKnowledgeReviewRequestOptionData.from_application(option)
            for option in options
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "",
    response_model=OperationalKnowledgeReviewRequestInventoryItemResponse,
    status_code=201,
)
async def create_operational_knowledge_review_request(
    payload: OperationalKnowledgeReviewRequestInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_review_request_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeReviewRequestInventoryItemResponse:
    service: OperationalKnowledgeReviewRequestService = (
        request.app.state.operational_knowledge_review_request_service
    )
    try:
        record = await service.create(
            actor=subject,
            source_draft_id=payload.source_draft_id,
            review_request_option_id=payload.review_request_option_id,
            purpose=payload.purpose,
            review_request_only_acknowledged=(
                payload.acknowledged_result_is_only_an_unassigned_review_request
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeReviewRequestError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{review_request_id}",
    response_model=OperationalKnowledgeReviewRequestInventoryItemResponse,
)
async def get_operational_knowledge_review_request(
    review_request_id: Annotated[str, Path(pattern=STABLE_ID)],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_review_request_read),
    ],
) -> OperationalKnowledgeReviewRequestInventoryItemResponse:
    service: OperationalKnowledgeReviewRequestService = (
        request.app.state.operational_knowledge_review_request_service
    )
    try:
        record = await service.get(
            actor=subject,
            review_request_id=review_request_id,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeReviewRequestError as error:
        _raise(error)
    return _response(record, request, response)
