from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from atlas.api.bootstrap_invalidation_schemas import (
    BootstrapInvalidationData,
    BootstrapInvalidationInput,
    BootstrapInvalidationResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_bootstrap_invalidation_preview
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_invalidation import (
    BootstrapInvalidationScopeError,
    BootstrapInvalidationService,
)

router = APIRouter(prefix="/platform/bootstrap-invalidation-preview", tags=["bootstrap"])


@router.post("", response_model=BootstrapInvalidationResponse)
async def preview_bootstrap_invalidation(
    payload: BootstrapInvalidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_bootstrap_invalidation_preview)],
) -> BootstrapInvalidationResponse:
    service: BootstrapInvalidationService = request.app.state.bootstrap_invalidation_service
    try:
        preview = await service.preview(
            actor=subject,
            candidate=payload.to_domain(),
            correlation_id=str(request.state.correlation_id),
        )
    except BootstrapInvalidationScopeError as error:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The bootstrap invalidation preview is unavailable.",
        ) from error
    response.headers["Cache-Control"] = "no-store"
    return BootstrapInvalidationResponse(
        data=BootstrapInvalidationData.from_domain(preview),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
