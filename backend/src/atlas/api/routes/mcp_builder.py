from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.mcp_builder_schemas import (
    BuilderGeneratedFileData,
    McpBuilderDesignCheckpointData,
    McpBuilderDesignCheckpointInput,
    McpBuilderDesignCheckpointResponse,
    McpBuilderGeneratedFileData,
    McpBuilderGeneratedFileResponse,
    McpBuilderGenerationData,
    McpBuilderGenerationInput,
    McpBuilderGenerationResponse,
    McpBuilderProjectData,
    McpBuilderProjectInput,
    McpBuilderProjectResponse,
    design_capability_decision,
    design_entity_mapping,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_mcp_builder_create,
    authorize_mcp_builder_design_create,
    authorize_mcp_builder_design_read,
    authorize_mcp_builder_generation_create,
    authorize_mcp_builder_generation_read,
    authorize_mcp_builder_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.mcp_builder.application.ports import McpBuilderError
from atlas.modules.mcp_builder.application.service import McpBuilderService
from atlas.modules.mcp_builder.domain.design_review import McpBuilderDesignCheckpoint
from atlas.modules.mcp_builder.domain.generation import McpBuilderGeneration
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
    elif error.code.endswith("not_found"):
        status = 404
    elif error.code.endswith(("invalid", "missing", "unsupported", "exceeded", "detected")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="MCP Builder operation unavailable",
        detail="The governed Builder operation could not proceed within its safety boundary.",
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


def _design_response(
    checkpoint: McpBuilderDesignCheckpoint, request: Request, response: Response
) -> McpBuilderDesignCheckpointResponse:
    response.headers["Cache-Control"] = "no-store"
    return McpBuilderDesignCheckpointResponse(
        data=McpBuilderDesignCheckpointData.from_domain(checkpoint),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


def _generation_response(
    generation: McpBuilderGeneration, request: Request, response: Response
) -> McpBuilderGenerationResponse:
    response.headers["Cache-Control"] = "no-store"
    return McpBuilderGenerationResponse(
        data=McpBuilderGenerationData.from_domain(generation),
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


@router.post(
    "/{project_id}/design-checkpoints",
    response_model=McpBuilderDesignCheckpointResponse,
    status_code=201,
)
async def create_mcp_builder_design_checkpoint(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: McpBuilderDesignCheckpointInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_design_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> McpBuilderDesignCheckpointResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        checkpoint = await service.create_design_checkpoint(
            actor=subject,
            project_id=project_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            target_products=tuple(payload.target_products),
            network_destinations=tuple(payload.network_destinations),
            configuration_keys=tuple(payload.configuration_keys),
            secret_reference_ids=tuple(payload.secret_reference_ids),
            entity_mappings=tuple(design_entity_mapping(item) for item in payload.entity_mappings),
            capability_decisions=tuple(
                design_capability_decision(item) for item in payload.capability_decisions
            ),
            **payload.model_dump(
                exclude={
                    "schema_version",
                    "target_products",
                    "network_destinations",
                    "configuration_keys",
                    "secret_reference_ids",
                    "entity_mappings",
                    "capability_decisions",
                }
            ),
        )
    except McpBuilderError as error:
        _raise(error)
    return _design_response(checkpoint, request, response)


@router.get("/{project_id}/design-checkpoint", response_model=McpBuilderDesignCheckpointResponse)
async def get_mcp_builder_design_checkpoint(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_design_read)],
) -> McpBuilderDesignCheckpointResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        checkpoint = await service.get_design_checkpoint(
            actor=subject,
            project_id=project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    return _design_response(checkpoint, request, response)


@router.post(
    "/{project_id}/generations", response_model=McpBuilderGenerationResponse, status_code=201
)
async def create_mcp_builder_generation(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: McpBuilderGenerationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_generation_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> McpBuilderGenerationResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        generation = await service.create_generation(
            actor=subject,
            project_id=project_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except McpBuilderError as error:
        _raise(error)
    return _generation_response(generation, request, response)


@router.get("/{project_id}/generation", response_model=McpBuilderGenerationResponse)
async def get_mcp_builder_generation(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_generation_read)],
) -> McpBuilderGenerationResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        generation = await service.get_generation(
            actor=subject,
            project_id=project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    return _generation_response(generation, request, response)


@router.get(
    "/{project_id}/generation/files/{relative_path:path}",
    response_model=McpBuilderGeneratedFileResponse,
)
async def get_mcp_builder_generated_file(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    relative_path: Annotated[str, Path(min_length=1, max_length=240)],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_generation_read)],
) -> McpBuilderGeneratedFileResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        generation, metadata, content = await service.get_generated_file(
            actor=subject,
            project_id=project_id,
            relative_path=relative_path,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return McpBuilderGeneratedFileResponse(
        data=McpBuilderGeneratedFileData(
            generation_id=generation.generation_id,
            state=generation.state.value,
            artifact_digest=generation.artifact_digest,
            file=BuilderGeneratedFileData.from_domain(metadata),
            content=content,
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
