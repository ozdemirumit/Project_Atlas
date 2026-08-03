from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request

from atlas.api.errors import AtlasError
from atlas.modules.authorization.application.bootstrap import (
    IDENTITY_SELF_READ,
    current_identity_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationDecision, AuthorizationRequest
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.domain.models import AuthenticatedSubject, AuthenticationInput


def _presented_authorization(request: Request) -> tuple[str | None, str | None]:
    value = request.headers.get("Authorization")
    if value is None:
        return None, None
    parts = value.split(" ", maxsplit=1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return "invalid", None
    return parts[0].lower(), parts[1]


async def authenticated_subject(request: Request) -> AuthenticatedSubject:
    scheme, credential = _presented_authorization(request)
    service: IdentityService = request.app.state.identity_service
    subject = await service.authenticate(
        AuthenticationInput(
            correlation_id=str(request.state.correlation_id),
            authorization_scheme=scheme,
            credential=credential,
        )
    )
    if subject is None:
        raise AtlasError(
            status=401,
            code="authentication_required",
            title="Authentication required",
            detail="A valid authenticated identity is required for this operation.",
        )
    request.state.authenticated_subject = subject
    return subject


async def authorize_identity_self_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=IDENTITY_SELF_READ,
            resource_type="resource.identity.context",
            scope=current_identity_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    request.state.authorization_decision = decision
    return decision
