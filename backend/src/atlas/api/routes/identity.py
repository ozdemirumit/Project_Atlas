from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from atlas.api.schemas import CurrentIdentityData, CurrentIdentityResponse, ResponseMeta
from atlas.api.security import authenticated_subject, authorize_identity_self_read
from atlas.modules.authorization.application.bootstrap import current_identity_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/me", response_model=CurrentIdentityResponse)
async def current_identity(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_identity_self_read)],
) -> CurrentIdentityResponse:
    scope = current_identity_scope(subject.organization_id, request.app.state.settings.environment)
    return CurrentIdentityResponse(
        data=CurrentIdentityData.from_domain(
            subject,
            scope,
            decision,
            credential_kind=getattr(
                request.state,
                "authenticated_credential_kind",
                "identity_provider",
            ),
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )
