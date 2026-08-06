from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.evidence_draft_schemas import (
    OperationalEvidenceKnowledgeDraftData,
    OperationalEvidenceKnowledgeDraftInput,
    OperationalEvidenceKnowledgeDraftResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_operational_evidence_knowledge_draft_create,
    authorize_operational_evidence_knowledge_draft_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.evidence_draft import (
    OperationalEvidenceKnowledgeDraftService,
)
from atlas.modules.knowledge.application.evidence_draft_ports import (
    OperationalEvidenceKnowledgeDraftError,
    OperationalEvidenceKnowledgeDraftUncertainError,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    OperationalEvidenceKnowledgeDraftRecord,
)

router = APIRouter(prefix="/knowledge/operational-evidence-drafts", tags=["knowledge"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: OperationalEvidenceKnowledgeDraftError) -> NoReturn:
    code = str(error)
    if isinstance(error, OperationalEvidenceKnowledgeDraftUncertainError):
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
        title="Operational evidence knowledge draft unavailable",
        detail=(
            "Draft curation did not approve or publish knowledge, create model context, "
            "or grant operational authority. Claimed uncertain attempts are not retried."
        ),
    ) from error


def _response(
    record: OperationalEvidenceKnowledgeDraftRecord,
    request: Request,
    response: Response,
) -> OperationalEvidenceKnowledgeDraftResponse:
    response.headers["Cache-Control"] = "no-store"
    return OperationalEvidenceKnowledgeDraftResponse(
        data=OperationalEvidenceKnowledgeDraftData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=OperationalEvidenceKnowledgeDraftResponse, status_code=201)
async def create_operational_evidence_knowledge_draft(
    payload: OperationalEvidenceKnowledgeDraftInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_evidence_knowledge_draft_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> OperationalEvidenceKnowledgeDraftResponse:
    service: OperationalEvidenceKnowledgeDraftService = (
        request.app.state.operational_evidence_knowledge_draft_service
    )
    try:
        record = await service.create(
            actor=subject,
            source_ingestion_id=payload.source_ingestion_id,
            source_ingestion_digest=payload.source_ingestion_digest,
            curation_policy_id=payload.curation_policy_id,
            curation_policy_digest=payload.curation_policy_digest,
            purpose=payload.purpose,
            unapproved_non_retrievable_draft_acknowledged=(
                payload.acknowledged_result_is_an_unapproved_non_retrievable_draft
            ),
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalEvidenceKnowledgeDraftError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{draft_id}", response_model=OperationalEvidenceKnowledgeDraftResponse)
async def get_operational_evidence_knowledge_draft(
    draft_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_operational_evidence_knowledge_draft_read),
    ],
) -> OperationalEvidenceKnowledgeDraftResponse:
    service: OperationalEvidenceKnowledgeDraftService = (
        request.app.state.operational_evidence_knowledge_draft_service
    )
    try:
        record = await service.get(
            actor=subject,
            draft_id=draft_id,
            correlation_id=str(request.state.correlation_id),
        )
    except OperationalEvidenceKnowledgeDraftError as error:
        _raise(error)
    return _response(record, request, response)
