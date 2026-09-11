"""docs/027_Knowledge_Engine.md SS8 (lifecycle transitions) and SS21 (Conflict and Supersession)
made reachable over HTTP for the real document-sourced knowledge pipeline. See
atlas.modules.knowledge.application.document_knowledge_lifecycle for the service and
atlas.modules.knowledge.domain.document_knowledge_lifecycle for why this targets that pipeline and
not the older, still-synthetic Operational-chain ``KnowledgeLifecycle`` enum.

Every mutation here uses ``browser_session_subject`` (CSRF-protected) -- these are real human
commands (suspend/resume/supersede/retire an item, record/resolve a conflict), matching this
module's established convention for ``document_knowledge.py``'s own mutating routes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Query, Request, Response

from atlas.api.document_knowledge_lifecycle_schemas import (
    DocumentKnowledgeConflictData,
    DocumentKnowledgeConflictInput,
    DocumentKnowledgeConflictListResponse,
    DocumentKnowledgeConflictResolutionInput,
    DocumentKnowledgeConflictResponse,
    DocumentKnowledgeItemLifecycleData,
    DocumentKnowledgeItemLifecycleResponse,
    DocumentKnowledgeItemLifecycleViewData,
    DocumentKnowledgeItemLifecycleViewResponse,
    DocumentKnowledgeLifecycleTransitionInput,
    DocumentKnowledgeSupersessionInput,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_document_knowledge_conflict_create,
    authorize_document_knowledge_conflict_read,
    authorize_document_knowledge_lifecycle_create,
    authorize_document_knowledge_lifecycle_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.document_knowledge_lifecycle import (
    DocumentKnowledgeLifecycleService,
)
from atlas.modules.knowledge.application.document_knowledge_lifecycle_ports import (
    DocumentKnowledgeError,
)
from atlas.modules.knowledge.domain.document_knowledge_lifecycle import (
    DocumentKnowledgeConflictType,
)

router = APIRouter(prefix="/knowledge/documents", tags=["knowledge"])

_STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


def _raise(error: DocumentKnowledgeError) -> NoReturn:
    code = error.code
    if code.endswith(("required", "denied")):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith("invalid"):
        status = 422
    elif code.endswith("uncertain"):
        status = 503
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Document knowledge lifecycle request unavailable",
        detail=(
            "Lifecycle and conflict records reflect only real, already-recorded document-"
            "sourced knowledge state transitions."
        ),
    ) from error


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _service(request: Request) -> DocumentKnowledgeLifecycleService:
    service: DocumentKnowledgeLifecycleService | None = (
        request.app.state.document_knowledge_lifecycle_service
    )
    if service is None:
        _raise(
            DocumentKnowledgeError(
                "document_knowledge_lifecycle_unavailable",
                "Document knowledge lifecycle tracking is not enabled in this environment.",
            )
        )
    return service


# ---------------------------------------------------------------------------
# Conflicts -- registered ahead of the dynamic {knowledge_item_id} routes below.
# ---------------------------------------------------------------------------


@router.post("/conflicts", response_model=DocumentKnowledgeConflictResponse, status_code=201)
async def record_document_knowledge_conflict(
    payload: DocumentKnowledgeConflictInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_conflict_create)
    ],
) -> DocumentKnowledgeConflictResponse:
    service = _service(request)
    try:
        conflict_type = DocumentKnowledgeConflictType(payload.conflict_type)
    except ValueError:
        _raise(
            DocumentKnowledgeError(
                "document_knowledge_conflict_type_invalid",
                "conflict_type must be one of the recognized conflict types.",
            )
        )
    try:
        conflict = await service.record_conflict(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            knowledge_item_id_a=payload.knowledge_item_id_a,
            knowledge_item_id_b=payload.knowledge_item_id_b,
            conflict_type=conflict_type,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeConflictResponse(
        data=DocumentKnowledgeConflictData.from_domain(conflict), meta=_meta(request)
    )


@router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=DocumentKnowledgeConflictResponse,
    status_code=200,
)
async def resolve_document_knowledge_conflict(
    conflict_id: str,
    payload: DocumentKnowledgeConflictResolutionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_conflict_create)
    ],
) -> DocumentKnowledgeConflictResponse:
    service = _service(request)
    try:
        conflict = await service.resolve_conflict(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            conflict_id=conflict_id,
            resolution=payload.resolution,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeConflictResponse(
        data=DocumentKnowledgeConflictData.from_domain(conflict), meta=_meta(request)
    )


@router.get("/conflicts", response_model=DocumentKnowledgeConflictListResponse, status_code=200)
async def list_document_knowledge_conflicts(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_conflict_read)
    ],
    knowledge_item_id: Annotated[str, Query(pattern=_STABLE_ID)],
) -> DocumentKnowledgeConflictListResponse:
    service = _service(request)
    try:
        conflicts = await service.list_conflicts(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            knowledge_item_id=knowledge_item_id,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeConflictListResponse(
        data=[DocumentKnowledgeConflictData.from_domain(conflict) for conflict in conflicts],
        meta=_meta(request),
    )


# ---------------------------------------------------------------------------
# Per-item lifecycle.
# ---------------------------------------------------------------------------


@router.get(
    "/{knowledge_item_id}/lifecycle",
    response_model=DocumentKnowledgeItemLifecycleViewResponse,
    status_code=200,
)
async def get_document_knowledge_item_lifecycle(
    knowledge_item_id: str,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_lifecycle_read)
    ],
) -> DocumentKnowledgeItemLifecycleViewResponse:
    service = _service(request)
    try:
        view = await service.get_lifecycle(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            knowledge_item_id=knowledge_item_id,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeItemLifecycleViewResponse(
        data=DocumentKnowledgeItemLifecycleViewData.from_domain(view), meta=_meta(request)
    )


@router.post(
    "/{knowledge_item_id}/lifecycle/suspend",
    response_model=DocumentKnowledgeItemLifecycleResponse,
    status_code=200,
)
async def suspend_document_knowledge_item(
    knowledge_item_id: str,
    payload: DocumentKnowledgeLifecycleTransitionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_lifecycle_create)
    ],
) -> DocumentKnowledgeItemLifecycleResponse:
    service = _service(request)
    try:
        record = await service.suspend(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            knowledge_item_id=knowledge_item_id,
            reason=payload.reason,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeItemLifecycleResponse(
        data=DocumentKnowledgeItemLifecycleData.from_domain(record), meta=_meta(request)
    )


@router.post(
    "/{knowledge_item_id}/lifecycle/resume",
    response_model=DocumentKnowledgeItemLifecycleResponse,
    status_code=200,
)
async def resume_document_knowledge_item(
    knowledge_item_id: str,
    payload: DocumentKnowledgeLifecycleTransitionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_lifecycle_create)
    ],
) -> DocumentKnowledgeItemLifecycleResponse:
    service = _service(request)
    try:
        record = await service.resume(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            knowledge_item_id=knowledge_item_id,
            reason=payload.reason,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeItemLifecycleResponse(
        data=DocumentKnowledgeItemLifecycleData.from_domain(record), meta=_meta(request)
    )


@router.post(
    "/{knowledge_item_id}/lifecycle/supersede",
    response_model=DocumentKnowledgeItemLifecycleResponse,
    status_code=200,
)
async def supersede_document_knowledge_item(
    knowledge_item_id: str,
    payload: DocumentKnowledgeSupersessionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_lifecycle_create)
    ],
) -> DocumentKnowledgeItemLifecycleResponse:
    service = _service(request)
    try:
        record = await service.supersede(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            knowledge_item_id=knowledge_item_id,
            superseded_by_item_id=payload.superseded_by_item_id,
            reason=payload.reason,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeItemLifecycleResponse(
        data=DocumentKnowledgeItemLifecycleData.from_domain(record), meta=_meta(request)
    )


@router.post(
    "/{knowledge_item_id}/lifecycle/retire",
    response_model=DocumentKnowledgeItemLifecycleResponse,
    status_code=200,
)
async def retire_document_knowledge_item(
    knowledge_item_id: str,
    payload: DocumentKnowledgeLifecycleTransitionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_document_knowledge_lifecycle_create)
    ],
) -> DocumentKnowledgeItemLifecycleResponse:
    service = _service(request)
    try:
        record = await service.retire(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            knowledge_item_id=knowledge_item_id,
            reason=payload.reason,
            correlation_id=str(request.state.correlation_id),
        )
    except DocumentKnowledgeError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentKnowledgeItemLifecycleResponse(
        data=DocumentKnowledgeItemLifecycleData.from_domain(record), meta=_meta(request)
    )
