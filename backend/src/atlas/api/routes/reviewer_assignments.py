from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.reviewer_assignment_schemas import (
    OperationalKnowledgeReviewerAssignmentData,
    OperationalKnowledgeReviewerAssignmentInput,
    OperationalKnowledgeReviewerAssignmentResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_knowledge_reviewer_assignment_create,
    authorize_operational_knowledge_reviewer_assignment_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentService,
)
from atlas.modules.knowledge.application.reviewer_assignment_ports import (
    OperationalKnowledgeReviewerAssignmentError,
    OperationalKnowledgeReviewerAssignmentUncertainError,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)

router = APIRouter(prefix="/knowledge/operational-reviewer-assignments", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: OperationalKnowledgeReviewerAssignmentError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalKnowledgeReviewerAssignmentUncertainError):
        status = 503
    elif code.endswith(("required", "denied", "mfa_required", "separation_required")):
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
        title="Operational knowledge reviewer assignment unavailable",
        detail=(
            "Assignment did not expose identity attributes or content, record a decision, approve "
            "or publish knowledge, or grant operational authority. Claimed uncertain attempts are "
            "not retried."
        ),
    ) from error


def _response(
    record: OperationalKnowledgeReviewerAssignmentRecord,
    request: Request,
    response: Response,
) -> OperationalKnowledgeReviewerAssignmentResponse:
    response.headers["Cache-Control"] = "no-store"
    return OperationalKnowledgeReviewerAssignmentResponse(
        data=OperationalKnowledgeReviewerAssignmentData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=OperationalKnowledgeReviewerAssignmentResponse, status_code=201)
async def create_operational_knowledge_reviewer_assignment(
    payload: OperationalKnowledgeReviewerAssignmentInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_reviewer_assignment_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalKnowledgeReviewerAssignmentResponse:
    service: OperationalKnowledgeReviewerAssignmentService = (
        request.app.state.operational_knowledge_reviewer_assignment_service
    )
    try:
        record = await service.create(
            actor=subject,
            source_review_request_id=payload.source_review_request_id,
            source_review_request_digest=payload.source_review_request_digest,
            assignment_policy_id=payload.assignment_policy_id,
            assignment_policy_digest=payload.assignment_policy_digest,
            purpose=payload.purpose,
            assignment_only_acknowledged=(
                payload.acknowledged_assignment_opens_no_content_and_records_no_decision
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeReviewerAssignmentError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{assignment_set_id}", response_model=OperationalKnowledgeReviewerAssignmentResponse)
async def get_operational_knowledge_reviewer_assignment(
    assignment_set_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_knowledge_reviewer_assignment_read),
    ],
) -> OperationalKnowledgeReviewerAssignmentResponse:
    service: OperationalKnowledgeReviewerAssignmentService = (
        request.app.state.operational_knowledge_reviewer_assignment_service
    )
    try:
        record = await service.get(
            actor=subject,
            assignment_set_id=assignment_set_id,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalKnowledgeReviewerAssignmentError as error:
        _raise(error)
    return _response(record, request, response)
