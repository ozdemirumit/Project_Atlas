from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from atlas.api.deployment_configuration_schemas import (
    DeploymentConfigurationPreviewData,
    DeploymentConfigurationPreviewInput,
    DeploymentConfigurationPreviewResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_deployment_configuration_preview,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.deployment_configuration import (
    DeploymentConfigurationScopeError,
    DeploymentConfigurationService,
)

router = APIRouter(prefix="/platform/deployment-configuration", tags=["deployment-configuration"])


@router.post("/preview", response_model=DeploymentConfigurationPreviewResponse)
async def preview_deployment_configuration(
    payload: DeploymentConfigurationPreviewInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_deployment_configuration_preview)
    ],
) -> DeploymentConfigurationPreviewResponse:
    service: DeploymentConfigurationService = request.app.state.deployment_configuration_service
    try:
        domain_request = payload.to_domain()
        preview = await service.preview(
            actor=subject,
            request=domain_request,
            correlation_id=str(request.state.correlation_id),
        )
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="request_validation_failed",
            title="Request validation failed",
            detail="The deployment configuration request is malformed.",
        ) from error
    except DeploymentConfigurationScopeError as error:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        ) from error
    response.headers["Cache-Control"] = "no-store"
    return DeploymentConfigurationPreviewResponse(
        data=DeploymentConfigurationPreviewData.from_domain(preview),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
