from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.mcp_builder_schemas import (
    McpBuilderProjectData,
    McpBuilderProjectInput,
    McpBuilderProjectResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_mcp_builder_create,
    authorize_mcp_builder_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.mcp_builder.application.ports import McpBuilderError
from atlas.modules.mcp_builder.application.service import McpBuilderService
from atlas.modules.mcp_builder.domain.models import McpBuilderProject

router = APIRouter(prefix="/mcp-builder/projects", tags=["mcp-builder"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key",
    min_length=8,
    max_length=128,
    pattern=r"^[A-Za-z0-9._:-]+$",
)


def _raise(error: McpBuilderError) -> NoReturn:
    if error.code in {"builder_enterprise_human_mfa_required"}:
        status = 403
    elif error.code == "builder_project_not_found":
        status = 404
    elif error.code.endswith(("invalid", "missing", "unsupported", "exceeded", "detected")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="MCP Builder analysis unavailable",
        detail="The governed source analysis could not proceed within its safety boundary.",
    ) from error


def _response(
    project: McpBuilderProject, request: Request, response: Response
) -> McpBuilderProjectResponse:
    response.headers["Cache-Control"] = "no-store"
    return McpBuilderProjectResponse(
        data=McpBuilderProjectData.from_domain(project),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=McpBuilderProjectResponse, status_code=201)
async def create_mcp_builder_project(
    payload: McpBuilderProjectInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> McpBuilderProjectResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        project = await service.create_project(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            intended_product_versions=tuple(payload.intended_product_versions),
            **payload.model_dump(exclude={"schema_version", "intended_product_versions"}),
        )
    except McpBuilderError as error:
        _raise(error)
    return _response(project, request, response)


@router.get("/{project_id}", response_model=McpBuilderProjectResponse)
async def get_mcp_builder_project(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_read)],
) -> McpBuilderProjectResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        project = await service.get_project(
            actor=subject,
            project_id=project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    return _response(project, request, response)
