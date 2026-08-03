from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request

from atlas.api.errors import AtlasError
from atlas.modules.authorization.application.bootstrap import (
    AI_GROUNDED_QUERY_CREATE,
    GRAPH_STORAGE_IMPACT_READ,
    IDENTITY_SELF_READ,
    STORAGE_OVERVIEW_READ,
    ai_grounded_query_scope,
    current_identity_scope,
    graph_storage_impact_scope,
    storage_overview_scope,
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


async def authorize_storage_overview_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=STORAGE_OVERVIEW_READ,
            resource_type="resource.storage.overview",
            scope=storage_overview_scope(subject.organization_id, settings.environment),
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


async def authorize_ai_grounded_query(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=AI_GROUNDED_QUERY_CREATE,
            resource_type="resource.ai.grounded-query",
            scope=ai_grounded_query_scope(subject.organization_id, settings.environment),
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


async def authorize_graph_storage_impact_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=GRAPH_STORAGE_IMPACT_READ,
            resource_type="resource.graph.storage-impact",
            scope=graph_storage_impact_scope(subject.organization_id, settings.environment),
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
