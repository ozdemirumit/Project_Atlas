from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.mcp_builder_schemas import (
    BuilderGeneratedFileData,
    McpBuilderCandidateHandoffData,
    McpBuilderCandidateHandoffInput,
    McpBuilderCandidateHandoffResponse,
    McpBuilderDesignCheckpointData,
    McpBuilderDesignCheckpointInput,
    McpBuilderDesignCheckpointResponse,
    McpBuilderDomainReviewData,
    McpBuilderDomainReviewInput,
    McpBuilderDomainReviewResponse,
    McpBuilderGeneratedFileData,
    McpBuilderGeneratedFileResponse,
    McpBuilderGenerationData,
    McpBuilderGenerationInput,
    McpBuilderGenerationResponse,
    McpBuilderLabValidationData,
    McpBuilderLabValidationInput,
    McpBuilderLabValidationResponse,
    McpBuilderProjectData,
    McpBuilderProjectInput,
    McpBuilderProjectResponse,
    McpBuilderSecurityReviewData,
    McpBuilderSecurityReviewInput,
    McpBuilderSecurityReviewResponse,
    McpBuilderValidationData,
    McpBuilderValidationInput,
    McpBuilderValidationResponse,
    design_capability_decision,
    design_entity_mapping,
    domain_capability_decision,
    security_control_assessment,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_mcp_builder_candidate_handoff_create,
    authorize_mcp_builder_candidate_handoff_download,
    authorize_mcp_builder_candidate_handoff_read,
    authorize_mcp_builder_create,
    authorize_mcp_builder_design_create,
    authorize_mcp_builder_design_read,
    authorize_mcp_builder_domain_review_create,
    authorize_mcp_builder_domain_review_read,
    authorize_mcp_builder_generation_create,
    authorize_mcp_builder_generation_read,
    authorize_mcp_builder_lab_validation_create,
    authorize_mcp_builder_lab_validation_read,
    authorize_mcp_builder_read,
    authorize_mcp_builder_security_review_create,
    authorize_mcp_builder_security_review_read,
    authorize_mcp_builder_validation_create,
    authorize_mcp_builder_validation_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.mcp_builder.application.ports import McpBuilderError
from atlas.modules.mcp_builder.application.service import McpBuilderService
from atlas.modules.mcp_builder.domain.candidate_handoff import McpBuilderCandidateHandoff
from atlas.modules.mcp_builder.domain.design_review import McpBuilderDesignCheckpoint
from atlas.modules.mcp_builder.domain.domain_review import McpBuilderDomainReview
from atlas.modules.mcp_builder.domain.generation import McpBuilderGeneration
from atlas.modules.mcp_builder.domain.lab_validation import McpBuilderLabValidation
from atlas.modules.mcp_builder.domain.models import McpBuilderProject
from atlas.modules.mcp_builder.domain.security_review import McpBuilderSecurityReview
from atlas.modules.mcp_builder.domain.validation import McpBuilderValidation

router = APIRouter(prefix="/mcp-builder/projects", tags=["mcp-builder"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key",
    min_length=8,
    max_length=128,
    pattern=r"^[A-Za-z0-9._:-]+$",
)


def _raise(error: McpBuilderError) -> NoReturn:
    if error.code == "builder_human_required":
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


def _validation_response(
    validation: McpBuilderValidation, request: Request, response: Response
) -> McpBuilderValidationResponse:
    response.headers["Cache-Control"] = "no-store"
    return McpBuilderValidationResponse(
        data=McpBuilderValidationData.from_domain(validation),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


def _domain_review_response(
    review: McpBuilderDomainReview, request: Request, response: Response
) -> McpBuilderDomainReviewResponse:
    response.headers["Cache-Control"] = "no-store"
    return McpBuilderDomainReviewResponse(
        data=McpBuilderDomainReviewData.from_domain(review),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


def _security_review_response(
    review: McpBuilderSecurityReview, request: Request, response: Response
) -> McpBuilderSecurityReviewResponse:
    response.headers["Cache-Control"] = "no-store"
    return McpBuilderSecurityReviewResponse(
        data=McpBuilderSecurityReviewData.from_domain(review),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


def _lab_validation_response(
    validation: McpBuilderLabValidation, request: Request, response: Response
) -> McpBuilderLabValidationResponse:
    response.headers["Cache-Control"] = "no-store"
    return McpBuilderLabValidationResponse(
        data=McpBuilderLabValidationData.from_domain(validation),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


def _candidate_handoff_response(
    handoff: McpBuilderCandidateHandoff, request: Request, response: Response
) -> McpBuilderCandidateHandoffResponse:
    response.headers["Cache-Control"] = "no-store"
    return McpBuilderCandidateHandoffResponse(
        data=McpBuilderCandidateHandoffData.from_domain(handoff),
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


@router.post(
    "/{project_id}/validations", response_model=McpBuilderValidationResponse, status_code=201
)
async def create_mcp_builder_validation(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: McpBuilderValidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_validation_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> McpBuilderValidationResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        validation = await service.create_validation(
            actor=subject,
            project_id=project_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except McpBuilderError as error:
        _raise(error)
    return _validation_response(validation, request, response)


@router.get("/{project_id}/validation", response_model=McpBuilderValidationResponse)
async def get_mcp_builder_validation(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_validation_read)],
) -> McpBuilderValidationResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        validation = await service.get_validation(
            actor=subject,
            project_id=project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    return _validation_response(validation, request, response)


@router.post(
    "/{project_id}/domain-reviews",
    response_model=McpBuilderDomainReviewResponse,
    status_code=201,
)
async def create_mcp_builder_domain_review(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: McpBuilderDomainReviewInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_mcp_builder_domain_review_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> McpBuilderDomainReviewResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        review = await service.create_domain_review(
            actor=subject,
            project_id=project_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            capability_decisions=tuple(
                domain_capability_decision(item) for item in payload.capability_decisions
            ),
            **payload.model_dump(exclude={"schema_version", "capability_decisions"}),
        )
    except McpBuilderError as error:
        _raise(error)
    return _domain_review_response(review, request, response)


@router.get("/{project_id}/domain-review", response_model=McpBuilderDomainReviewResponse)
async def get_mcp_builder_domain_review(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_domain_review_read)],
) -> McpBuilderDomainReviewResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        review = await service.get_domain_review(
            actor=subject,
            project_id=project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    return _domain_review_response(review, request, response)


@router.post(
    "/{project_id}/security-reviews",
    response_model=McpBuilderSecurityReviewResponse,
    status_code=201,
)
async def create_mcp_builder_security_review(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: McpBuilderSecurityReviewInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_mcp_builder_security_review_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> McpBuilderSecurityReviewResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        review = await service.create_security_review(
            actor=subject,
            project_id=project_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            control_assessments=tuple(
                security_control_assessment(item) for item in payload.control_assessments
            ),
            **payload.model_dump(exclude={"schema_version", "control_assessments"}),
        )
    except McpBuilderError as error:
        _raise(error)
    return _security_review_response(review, request, response)


@router.get("/{project_id}/security-review", response_model=McpBuilderSecurityReviewResponse)
async def get_mcp_builder_security_review(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_mcp_builder_security_review_read)
    ],
) -> McpBuilderSecurityReviewResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        review = await service.get_security_review(
            actor=subject,
            project_id=project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    return _security_review_response(review, request, response)


@router.post(
    "/{project_id}/lab-validations",
    response_model=McpBuilderLabValidationResponse,
    status_code=201,
)
async def create_mcp_builder_lab_validation(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: McpBuilderLabValidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_mcp_builder_lab_validation_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> McpBuilderLabValidationResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        validation = await service.create_lab_validation(
            actor=subject,
            project_id=project_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except McpBuilderError as error:
        _raise(error)
    return _lab_validation_response(validation, request, response)


@router.get("/{project_id}/lab-validation", response_model=McpBuilderLabValidationResponse)
async def get_mcp_builder_lab_validation(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_mcp_builder_lab_validation_read)],
) -> McpBuilderLabValidationResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        validation = await service.get_lab_validation(
            actor=subject,
            project_id=project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    return _lab_validation_response(validation, request, response)


@router.post(
    "/{project_id}/candidate-handoffs",
    response_model=McpBuilderCandidateHandoffResponse,
    status_code=201,
)
async def create_mcp_builder_candidate_handoff(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: McpBuilderCandidateHandoffInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_mcp_builder_candidate_handoff_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> McpBuilderCandidateHandoffResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        handoff = await service.create_candidate_handoff(
            actor=subject,
            project_id=project_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except McpBuilderError as error:
        _raise(error)
    return _candidate_handoff_response(handoff, request, response)


@router.get("/{project_id}/candidate-handoff", response_model=McpBuilderCandidateHandoffResponse)
async def get_mcp_builder_candidate_handoff(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_mcp_builder_candidate_handoff_read)
    ],
) -> McpBuilderCandidateHandoffResponse:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        handoff = await service.get_candidate_handoff(
            actor=subject,
            project_id=project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    return _candidate_handoff_response(handoff, request, response)


@router.get("/{project_id}/candidate-handoff/archive")
async def download_mcp_builder_candidate_archive(
    project_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_mcp_builder_candidate_handoff_download)
    ],
) -> Response:
    service: McpBuilderService = request.app.state.mcp_builder_service
    try:
        handoff, content = await service.download_candidate_archive(
            actor=subject,
            project_id=project_id,
            correlation_id=str(request.state.correlation_id),
        )
    except McpBuilderError as error:
        _raise(error)
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{handoff.package_filename}"',
            "X-Content-Type-Options": "nosniff",
            "X-Atlas-Package-Digest": handoff.package_digest,
        },
    )
