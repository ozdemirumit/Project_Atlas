from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.mcp_builder_draft_schemas import (
    BuilderDraftAnalyzeInput,
    BuilderDraftCreateInput,
    BuilderDraftData,
    BuilderDraftResponse,
    BuilderSupersessionCreateInput,
    BuilderSupersessionData,
    BuilderSupersessionResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_mcp_builder_draft_analyze,
    authorize_mcp_builder_draft_create,
    authorize_mcp_builder_supersession_create,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.mcp_builder.application.draft_and_supersession import (
    BuilderDraftError,
    BuilderDraftService,
)

router = APIRouter(prefix="/mcp-builder", tags=["mcp-builder"])
DRAFT_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
SUPERSESSION_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: BuilderDraftError) -> NoReturn:
    status_by_code = {
        "builder_draft_invalid": 422,
        "builder_draft_unavailable": 404,
        "builder_draft_already_analyzed": 409,
        "builder_project_already_superseded": 409,
        "builder_project_supersession_invalid": 422,
    }
    raise AtlasError(
        status=status_by_code.get(error.code, 409),
        code=error.code,
        title="MCP Builder draft unavailable",
        detail="The requested Builder draft operation could not be completed.",
    ) from error


@router.post("/drafts/{draft_id}", response_model=BuilderDraftResponse, status_code=201)
async def create_builder_draft(
    draft_id: Annotated[str, DRAFT_ID],
    payload: BuilderDraftCreateInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_draft_create)],
) -> BuilderDraftResponse:
    now = datetime.now(UTC)
    settings = request.app.state.settings
    service: BuilderDraftService = request.app.state.builder_draft_service
    try:
        draft = await service.create_draft(
            draft_id=draft_id,
            organization_id=subject.organization_id,
            environment_id=f"environment.{settings.environment}",
            owner_id=subject.subject_id,
            vendor=payload.vendor,
            product=payload.product,
            target_environment=payload.target_environment,
            notes=payload.notes,
            correlation_id=str(request.state.correlation_id),
        )
    except BuilderDraftError as error:
        _raise(error)
    return BuilderDraftResponse(
        data=BuilderDraftData.from_domain(draft),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post("/drafts/{draft_id}/analysis", response_model=BuilderDraftResponse, status_code=200)
async def mark_builder_draft_analyzed(
    draft_id: Annotated[str, DRAFT_ID],
    payload: BuilderDraftAnalyzeInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_draft_analyze)],
) -> BuilderDraftResponse:
    now = datetime.now(UTC)
    service: BuilderDraftService = request.app.state.builder_draft_service
    try:
        draft = await service.mark_analyzed(
            draft_id=draft_id,
            analyzed_project_id=payload.analyzed_project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except BuilderDraftError as error:
        _raise(error)
    return BuilderDraftResponse(
        data=BuilderDraftData.from_domain(draft),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post(
    "/supersessions/{supersession_id}",
    response_model=BuilderSupersessionResponse,
    status_code=201,
)
async def record_builder_supersession(
    supersession_id: Annotated[str, SUPERSESSION_ID],
    payload: BuilderSupersessionCreateInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_supersession_create)],
) -> BuilderSupersessionResponse:
    now = datetime.now(UTC)
    service: BuilderDraftService = request.app.state.builder_draft_service
    try:
        supersession = await service.record_supersession(
            supersession_id=supersession_id,
            superseded_project_id=payload.superseded_project_id,
            superseding_project_id=payload.superseding_project_id,
            reason=payload.reason,
            recorded_by=subject.subject_id,
            correlation_id=str(request.state.correlation_id),
        )
    except BuilderDraftError as error:
        _raise(error)
    return BuilderSupersessionResponse(
        data=BuilderSupersessionData.from_domain(supersession),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
