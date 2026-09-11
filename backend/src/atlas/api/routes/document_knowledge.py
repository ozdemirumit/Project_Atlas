from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response

from atlas.api.document_knowledge_schemas import (
    DocumentKnowledgeApprovalData,
    DocumentKnowledgeApprovalInput,
    DocumentKnowledgeApprovalResponse,
    DocumentKnowledgeDraftData,
    DocumentKnowledgeDraftInput,
    DocumentKnowledgeDraftResponse,
    DocumentKnowledgePublicationPreparationData,
    DocumentKnowledgePublicationPreparationInput,
    DocumentKnowledgePublicationPreparationResponse,
    DocumentKnowledgeReviewData,
    DocumentKnowledgeReviewInput,
    DocumentKnowledgeReviewResponse,
)
from atlas.api.document_retrieval_schemas import (
    DocumentKnowledgeIndexData,
    DocumentKnowledgeIndexInput,
    DocumentKnowledgeIndexResponse,
    DocumentKnowledgeSearchInput,
    DocumentKnowledgeSearchResponse,
    DocumentKnowledgeSearchResultData,
)
from atlas.api.errors import AtlasError
from atlas.api.operation_schemas import OperationResourceData, OperationResourceResponse
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_document_knowledge_approval_create,
    authorize_document_knowledge_draft_create,
    authorize_document_knowledge_indexing_create,
    authorize_document_knowledge_publication_preparation_create,
    authorize_document_knowledge_retrieval_create,
    authorize_document_knowledge_review_create,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.document_knowledge import DocumentKnowledgeService
from atlas.modules.knowledge.application.document_knowledge_ports import DocumentKnowledgeError
from atlas.modules.knowledge.application.document_retrieval import (
    DocumentKnowledgeRetrievalService,
)
from atlas.modules.knowledge.application.document_retrieval_ports import (
    DocumentKnowledgeRetrievalError,
)
from atlas.modules.operations.application.ports import OperationResourceError
from atlas.modules.operations.application.service import OperationResourceService

router = APIRouter(prefix="/knowledge/documents", tags=["knowledge"])


def _raise(error: DocumentKnowledgeError) -> NoReturn:
    code = error.code
    if code.endswith(("required", "denied")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith(("invalid", "not_passed", "not_granted")):
        status = 422
    elif code.endswith("uncertain"):
        status = 503
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Document knowledge request unavailable",
        detail=(
            "Document draft curation, review, approval, and publication preparation grant no "
            "infrastructure, execution, or automatic-publication authority."
        ),
    ) from error


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


@router.post("/drafts", response_model=DocumentKnowledgeDraftResponse, status_code=201)
async def create_document_knowledge_draft(
    payload: DocumentKnowledgeDraftInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_document_knowledge_draft_create)],
) -> DocumentKnowledgeDraftResponse:
    service: DocumentKnowledgeService = request.app.state.document_knowledge_service
    try:
        draft = await service.curate_draft(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            content=payload.content_bytes(),
            title=payload.title,
            draft_domain=payload.draft_domain,
            content_type=payload.content_type,
            classification=payload.classification,
            access_policy_id=payload.access_policy_id,
            retention_policy_id=payload.retention_policy_id,
            purpose=payload.purpose,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeDraftResponse(
        data=DocumentKnowledgeDraftData.from_domain(draft), meta=_meta(request)
    )


@router.post("/reviews", response_model=DocumentKnowledgeReviewResponse, status_code=201)
async def submit_document_knowledge_review(
    payload: DocumentKnowledgeReviewInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_review_create)
    ],
) -> DocumentKnowledgeReviewResponse:
    service: DocumentKnowledgeService = request.app.state.document_knowledge_service
    try:
        review = await service.submit_review_decision(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            draft_id=payload.draft_id,
            decision=payload.decision,
            findings=tuple(payload.findings),
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeReviewResponse(
        data=DocumentKnowledgeReviewData.from_domain(review), meta=_meta(request)
    )


@router.post("/approvals", response_model=DocumentKnowledgeApprovalResponse, status_code=201)
async def record_document_knowledge_approval(
    payload: DocumentKnowledgeApprovalInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_approval_create)
    ],
) -> DocumentKnowledgeApprovalResponse:
    service: DocumentKnowledgeService = request.app.state.document_knowledge_service
    try:
        approval = await service.record_final_approval(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            review_id=payload.review_id,
            decision=payload.decision,
            rationale=payload.rationale,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeApprovalResponse(
        data=DocumentKnowledgeApprovalData.from_domain(approval), meta=_meta(request)
    )


@router.post(
    "/publication-preparations",
    response_model=DocumentKnowledgePublicationPreparationResponse,
    status_code=201,
)
async def prepare_document_knowledge_publication(
    payload: DocumentKnowledgePublicationPreparationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_document_knowledge_publication_preparation_create),
    ],
) -> DocumentKnowledgePublicationPreparationResponse:
    service: DocumentKnowledgeService = request.app.state.document_knowledge_service
    try:
        preparation = await service.prepare_publication(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            approval_id=payload.approval_id,
            chunking_profile_digest=payload.chunking_profile_digest,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgePublicationPreparationResponse(
        data=DocumentKnowledgePublicationPreparationData.from_domain(preparation),
        meta=_meta(request),
    )


def _raise_retrieval(error: DocumentKnowledgeRetrievalError) -> NoReturn:
    if error.code.endswith(("required", "denied")):
        status = 403
    elif error.code.endswith("not_found"):
        status = 404
    elif error.code.endswith(("invalid", "produced_no_chunks")):
        status = 422
    elif error.code.endswith("uncertain"):
        status = 503
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="Document retrieval request unavailable",
        detail="Indexing and retrieval operate only on already-approved document knowledge.",
    ) from error


@router.post("/index", response_model=DocumentKnowledgeIndexResponse, status_code=201)
async def index_document_knowledge(
    payload: DocumentKnowledgeIndexInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_indexing_create)
    ],
) -> DocumentKnowledgeIndexResponse:
    service: DocumentKnowledgeRetrievalService | None = (
        request.app.state.document_knowledge_retrieval_service
    )
    if service is None:
        _raise_retrieval(
            DocumentKnowledgeRetrievalError(
                "document_knowledge_retrieval_unavailable",
                "Document retrieval is not enabled in this environment.",
            )
        )
    try:
        chunk_count = await service.index_document(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            preparation_id=payload.preparation_id,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeRetrievalError as error:
        _raise_retrieval(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeIndexResponse(
        data=DocumentKnowledgeIndexData(
            preparation_id=payload.preparation_id, chunk_count=chunk_count
        ),
        meta=_meta(request),
    )


def _raise_operation(error: OperationResourceError) -> NoReturn:
    code = error.code
    if code.endswith(("required", "denied")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith(("invalid", "reason_required")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Operation resource request unavailable",
        detail="Document indexing operation resource creation failed.",
    ) from error


async def _run_index_document_operation(
    *,
    retrieval_service: DocumentKnowledgeRetrievalService,
    operation_service: OperationResourceService,
    actor: AuthenticatedSubject,
    organization_id: str,
    environment_id: str,
    preparation_id: str,
    operation_id: str,
    correlation_id: str,
) -> None:
    """Runs after the `202` response has been sent (FastAPI's `BackgroundTasks`), reporting the
    REAL outcome of the REAL `DocumentKnowledgeRetrievalService.index_document()` call back onto
    the SAME operation resource `index_document_knowledge_as_operation()` already created.
    """
    try:
        await operation_service.mark_running(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            operation_id=operation_id,
            current_step="indexing",
            progress_summary="Chunking, embedding, and indexing the approved document.",
            correlation_id=correlation_id,
        )
        chunk_count = await retrieval_service.index_document(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            preparation_id=preparation_id,
            correlation_id=correlation_id,
        )
    except DocumentKnowledgeRetrievalError as error:
        await operation_service.mark_failed(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            operation_id=operation_id,
            error_reference=f"error.{error.code}",
            correlation_id=correlation_id,
        )
        return
    except OperationResourceError:
        # The operation resource itself was concurrently cancelled or otherwise transitioned --
        # nothing further to report back onto it.
        return
    await operation_service.mark_succeeded(
        actor=actor,
        organization_id=organization_id,
        environment_id=environment_id,
        operation_id=operation_id,
        result_reference=f"chunks.{chunk_count}",
        correlation_id=correlation_id,
    )


@router.post(
    "/index-operations",
    response_model=OperationResourceResponse,
    status_code=202,
)
async def index_document_knowledge_as_operation(
    payload: DocumentKnowledgeIndexInput,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_indexing_create)
    ],
) -> OperationResourceResponse:
    """SS19's "requests expected to outlive the HTTP transaction return `202`", applied to the
    one genuinely slow real operation in this codebase: FastEmbed chunk embedding over a
    potentially large approved document. Additive to, and independent of, the existing
    synchronous `POST /index` route above -- that route is unmodified and keeps returning `201`
    once the real indexing has already finished inline.
    """
    retrieval_service: DocumentKnowledgeRetrievalService | None = (
        request.app.state.document_knowledge_retrieval_service
    )
    if retrieval_service is None:
        _raise_retrieval(
            DocumentKnowledgeRetrievalError(
                "document_knowledge_retrieval_unavailable",
                "Document retrieval is not enabled in this environment.",
            )
        )
    operation_service: OperationResourceService = request.app.state.operation_resource_service
    organization_id = subject.organization_id
    environment_id = f"environment.{request.app.state.settings.environment}"
    correlation_id = str(request.state.correlation_id)
    try:
        operation = await operation_service.create(
            actor=subject,
            organization_id=organization_id,
            environment_id=environment_id,
            operation_type="operation.knowledge-document-indexing",
            input_artifact_reference=payload.preparation_id,
            correlation_id=correlation_id,
        )
    except OperationResourceError as error:
        _raise_operation(error)
    background_tasks.add_task(
        _run_index_document_operation,
        retrieval_service=retrieval_service,
        operation_service=operation_service,
        actor=subject,
        organization_id=organization_id,
        environment_id=environment_id,
        preparation_id=payload.preparation_id,
        operation_id=operation.operation_id,
        correlation_id=correlation_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return OperationResourceResponse(
        data=OperationResourceData.from_domain(operation), meta=_meta(request)
    )


@router.post("/search", response_model=DocumentKnowledgeSearchResponse, status_code=200)
async def search_document_knowledge(
    payload: DocumentKnowledgeSearchInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_retrieval_create)
    ],
) -> DocumentKnowledgeSearchResponse:
    service: DocumentKnowledgeRetrievalService | None = (
        request.app.state.document_knowledge_retrieval_service
    )
    if service is None:
        _raise_retrieval(
            DocumentKnowledgeRetrievalError(
                "document_knowledge_retrieval_unavailable",
                "Document retrieval is not enabled in this environment.",
            )
        )
    try:
        results = await service.retrieve(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            query=payload.query,
            top_k=payload.top_k,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeRetrievalError as error:
        _raise_retrieval(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeSearchResponse(
        data=[DocumentKnowledgeSearchResultData.from_domain(result) for result in results],
        meta=_meta(request),
    )
