from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.knowledge_source_registration_schemas import (
    KnowledgeSourceRegistrationData,
    KnowledgeSourceRegistrationInput,
    KnowledgeSourceRegistrationResponse,
    KnowledgeSourceTransitionInput,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_knowledge_source_registration_administer,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.application.source_registration import (
    KnowledgeSourceRegistrationError,
    KnowledgeSourceRegistrationService,
)

router = APIRouter(prefix="/knowledge/sources", tags=["knowledge"])
SOURCE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _raise(exc: KnowledgeSourceRegistrationError) -> NoReturn:
    status_by_code = {
        "knowledge_source_registration_invalid": 422,
        "knowledge_source_already_registered": 409,
        "knowledge_source_unavailable": 404,
        "knowledge_source_transition_invalid": 409,
    }
    raise AtlasError(
        status=status_by_code.get(exc.code, 400),
        code=exc.code,
        title="Knowledge source registration unavailable",
        detail="The requested knowledge source registration operation could not be completed.",
    ) from exc


@router.post("/{source_id}", response_model=KnowledgeSourceRegistrationResponse, status_code=201)
async def register_knowledge_source(
    source_id: Annotated[str, SOURCE_ID],
    payload: KnowledgeSourceRegistrationInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_knowledge_source_registration_administer)
    ],
) -> KnowledgeSourceRegistrationResponse:
    service: KnowledgeSourceRegistrationService = (
        request.app.state.knowledge_source_registration_service
    )
    try:
        registration = await service.register(
            source_id=source_id,
            display_name=payload.display_name,
            source_type=payload.source_type,
            source_class=payload.source_class,
            owner=payload.owner,
            technical_contact=payload.technical_contact,
            acquisition_method=payload.acquisition_method,
            acquisition_endpoint=payload.acquisition_endpoint,
            secret_reference_id=payload.secret_reference_id,
            organization_id=payload.organization_id,
            tenant_id=payload.tenant_id,
            environment_id=payload.environment_id,
            vendor=payload.vendor,
            product=payload.product,
            default_classification=payload.default_classification,
            access_mapping_method=payload.access_mapping_method,
            expected_version_behavior=payload.expected_version_behavior,
            authority_trust_rationale=payload.authority_trust_rationale,
            retention_policy=payload.retention_policy,
            deletion_policy=payload.deletion_policy,
            license_or_usage_restrictions=payload.license_or_usage_restrictions,
            ingestion_schedule=payload.ingestion_schedule,
            failure_policy=payload.failure_policy,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeSourceRegistrationError as exc:
        _raise(exc)
    return KnowledgeSourceRegistrationResponse(
        data=KnowledgeSourceRegistrationData.from_domain(registration), meta=_meta(request)
    )


@router.post("/{source_id}/transitions", response_model=KnowledgeSourceRegistrationResponse)
async def transition_knowledge_source(
    source_id: Annotated[str, SOURCE_ID],
    payload: KnowledgeSourceTransitionInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_knowledge_source_registration_administer)
    ],
) -> KnowledgeSourceRegistrationResponse:
    service: KnowledgeSourceRegistrationService = (
        request.app.state.knowledge_source_registration_service
    )
    try:
        registration = await service.transition(
            source_id=source_id,
            target=payload.target,
            correlation_id=str(request.state.correlation_id),
        )
    except KnowledgeSourceRegistrationError as exc:
        _raise(exc)
    return KnowledgeSourceRegistrationResponse(
        data=KnowledgeSourceRegistrationData.from_domain(registration), meta=_meta(request)
    )
