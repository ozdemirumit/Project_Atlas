from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Request

from atlas import __version__
from atlas.api.errors import AtlasError
from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.modules.authorization.application.bootstrap import (
    AI_GROUNDED_QUERY_CREATE,
    API_CREDENTIAL_ADMIN_REVOKE,
    API_CREDENTIAL_SELF_CREATE,
    API_CREDENTIAL_SELF_READ,
    API_CREDENTIAL_SELF_REVOKE,
    APPROVAL_REQUEST_CREATE,
    APPROVAL_REQUEST_DECIDE,
    APPROVAL_REQUEST_READ,
    AUDIT_EXPORT,
    AUDIT_READ,
    BACKUP_LOGICAL_CREATE,
    BACKUP_LOGICAL_PREVIEW,
    BACKUP_LOGICAL_RESTORE_VALIDATE,
    BOOTSTRAP_INVALIDATION_PREVIEW,
    BOOTSTRAP_PLAN_READ,
    BOOTSTRAP_STATE_MANAGE,
    BOOTSTRAP_STATE_READ,
    CONNECTOR_PACKAGE_ACQUIRE,
    CONNECTOR_PACKAGE_ACQUISITION_READ,
    CONNECTOR_PACKAGE_VALIDATION_CREATE,
    CONNECTOR_PACKAGE_VALIDATION_READ,
    DEPLOYMENT_CONFIGURATION_PREVIEW,
    GRAPH_STORAGE_IMPACT_READ,
    HEALTH_CHECK_OVERVIEW_READ,
    HEALTH_CHECK_RUN_CREATE,
    IDENTITY_GOVERNANCE_READ,
    IDENTITY_SELF_READ,
    IDENTITY_SUBJECT_ADMIN_DISABLE,
    INVESTIGATION_CREATE,
    MCP_BUILDER_CANDIDATE_HANDOFF_CREATE,
    MCP_BUILDER_CANDIDATE_HANDOFF_DOWNLOAD,
    MCP_BUILDER_CANDIDATE_HANDOFF_READ,
    MCP_BUILDER_DESIGN_CREATE,
    MCP_BUILDER_DESIGN_READ,
    MCP_BUILDER_DOMAIN_REVIEW_CREATE,
    MCP_BUILDER_DOMAIN_REVIEW_READ,
    MCP_BUILDER_GENERATION_CREATE,
    MCP_BUILDER_GENERATION_READ,
    MCP_BUILDER_LAB_VALIDATION_CREATE,
    MCP_BUILDER_LAB_VALIDATION_READ,
    MCP_BUILDER_PROJECT_CREATE,
    MCP_BUILDER_PROJECT_READ,
    MCP_BUILDER_SECURITY_REVIEW_CREATE,
    MCP_BUILDER_SECURITY_REVIEW_READ,
    MCP_BUILDER_VALIDATION_CREATE,
    MCP_BUILDER_VALIDATION_READ,
    RCA_CREATE,
    RECOMMENDATION_CREATE,
    RELEASE_PREFLIGHT_READ,
    REPORT_CREATE,
    SECURITY_EXPORT_OVERVIEW_READ,
    SECURITY_EXPORT_TEST_CREATE,
    SESSION_ADMIN_REVOKE,
    SESSION_SELF_READ,
    SESSION_SELF_REVOKE,
    STORAGE_OVERVIEW_READ,
    SUPPORT_BUNDLE_EXPORT,
    SUPPORT_BUNDLE_PREVIEW,
    UPGRADE_CHANGE_REVIEW_CREATE,
    UPGRADE_CHANGE_REVIEW_PREVIEW,
    UPGRADE_COMPLETION_RECEIPT_CREATE,
    UPGRADE_COMPLETION_RECEIPT_READ,
    UPGRADE_HUMAN_REVIEW_CREATE,
    UPGRADE_HUMAN_REVIEW_DECIDE,
    UPGRADE_HUMAN_REVIEW_READ,
    UPGRADE_READINESS_PREVIEW,
    UPGRADE_ROLLBACK_SIMULATE,
    WORKLOAD_IDENTITY_ADMIN_CREATE,
    WORKLOAD_IDENTITY_ADMIN_REVOKE,
    WORKLOAD_IDENTITY_ADMIN_ROTATE,
    WORKLOAD_IDENTITY_GOVERNANCE_READ,
    ai_grounded_query_scope,
    api_credential_self_scope,
    approval_scope,
    audit_export_scope,
    bootstrap_invalidation_scope,
    bootstrap_plan_scope,
    bootstrap_state_scope,
    connector_package_acquisition_scope,
    connector_package_validation_scope,
    current_identity_scope,
    deployment_configuration_scope,
    graph_storage_impact_scope,
    health_check_scope,
    identity_governance_scope,
    investigation_scope,
    logical_backup_scope,
    mcp_builder_scope,
    rca_scope,
    recommendation_scope,
    release_preflight_scope,
    report_scope,
    security_export_scope,
    session_self_scope,
    storage_overview_scope,
    support_bundle_scope,
    upgrade_change_review_scope,
    upgrade_completion_receipt_scope,
    upgrade_human_review_scope,
    upgrade_simulation_scope,
    workload_identity_governance_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import AuthorizationDecision, AuthorizationRequest
from atlas.modules.identity.application.api_credentials import (
    ApiCredentialOperationsError,
    ApiCredentialService,
)
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.application.sessions import SessionOperationsError, SessionService
from atlas.modules.identity.domain.models import (
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.identity.domain.sessions import CredentialKind


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
    settings = request.app.state.settings
    session_token = request.cookies.get(settings.session_cookie_name)
    if session_token is not None and scheme is not None:
        raise AtlasError(
            status=400,
            code="ambiguous_authentication",
            title="Ambiguous authentication",
            detail="Use exactly one supported authentication mechanism.",
        )
    if session_token is not None:
        session_service: SessionService = request.app.state.session_service
        try:
            context = await session_service.authenticate(
                session_token,
                csrf_token=request.headers.get(settings.csrf_header_name),
                unsafe_request=request.method not in {"GET", "HEAD", "OPTIONS"},
                correlation_id=str(request.state.correlation_id),
            )
        except SessionOperationsError as exc:
            raise AtlasError(
                status=403,
                code=exc.code,
                title="Session validation failed",
                detail="The browser session could not authorize this request.",
            ) from exc
        if context is None:
            raise AtlasError(
                status=401,
                code="authentication_required",
                title="Authentication required",
                detail="A valid authenticated identity is required for this operation.",
            )
        request.state.authenticated_subject = context.subject
        request.state.authenticated_session_id = context.session_id
        request.state.authenticated_credential_kind = CredentialKind.BROWSER_SESSION
        return context.subject
    if scheme == "bearer" and credential is not None:
        api_credential_service: ApiCredentialService = request.app.state.api_credential_service
        try:
            api_context = await api_credential_service.authenticate(
                credential,
                unsafe_request=request.method not in {"GET", "HEAD", "OPTIONS"},
                correlation_id=str(request.state.correlation_id),
            )
        except ApiCredentialOperationsError as exc:
            raise AtlasError(
                status=403,
                code=exc.code,
                title="API credential denied",
                detail="The API credential cannot authorize this request.",
            ) from exc
        if api_context is None:
            raise AtlasError(
                status=401,
                code="authentication_required",
                title="Authentication required",
                detail="A valid authenticated identity is required for this operation.",
            )
        request.state.authenticated_subject = api_context.subject
        request.state.authenticated_api_credential_id = api_context.credential_id
        request.state.authenticated_credential_kind = CredentialKind.API_TOKEN
        return api_context.subject
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


async def browser_session_subject(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthenticatedSubject:
    if (
        getattr(request.state, "authenticated_credential_kind", None)
        is not CredentialKind.BROWSER_SESSION
    ):
        raise AtlasError(
            status=403,
            code="browser_session_required",
            title="Browser session required",
            detail="Use a CSRF-protected browser session for credential management.",
        )
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


async def _authorize_session_self(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.identity.session",
            scope=session_self_scope(
                subject.organization_id, settings.environment, capability_class
            ),
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


async def authorize_session_self_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_session_self(
        request,
        subject,
        permission_id=SESSION_SELF_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_session_self_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_session_self(
        request,
        subject,
        permission_id=SESSION_SELF_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_api_credential_self(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.identity.api-credential",
            scope=api_credential_self_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="API credential management is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_api_credential_self_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_api_credential_self(
        request,
        subject,
        permission_id=API_CREDENTIAL_SELF_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_api_credential_self_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_api_credential_self(
        request,
        subject,
        permission_id=API_CREDENTIAL_SELF_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_api_credential_self_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_api_credential_self(
        request,
        subject,
        permission_id=API_CREDENTIAL_SELF_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_identity_governance(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
    target_subject_id: str | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
    target_metadata: tuple[tuple[str, str], ...] = (),
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.identity.governance",
            scope=identity_governance_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
            target_subject_id=target_subject_id,
            reason=reason,
            idempotency_key=idempotency_key,
            target_metadata=target_metadata,
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Identity governance is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_identity_governance_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_identity_governance(
        request,
        subject,
        permission_id=IDENTITY_GOVERNANCE_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_session_admin_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    session_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.identity_governance_service.target_audit_fields(
        "browser_session", session_id
    )
    reason, idempotency_key = await _governance_mutation_audit_fields(request)
    return await _authorize_identity_governance(
        request,
        subject,
        permission_id=SESSION_ADMIN_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        reason=reason,
        idempotency_key=idempotency_key,
        target_metadata=target_metadata,
    )


async def authorize_api_credential_admin_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    credential_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.identity_governance_service.target_audit_fields(
        "personal_api_credential", credential_id
    )
    reason, idempotency_key = await _governance_mutation_audit_fields(request)
    return await _authorize_identity_governance(
        request,
        subject,
        permission_id=API_CREDENTIAL_ADMIN_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        reason=reason,
        idempotency_key=idempotency_key,
        target_metadata=target_metadata,
    )


async def authorize_identity_subject_admin_disable(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    subject_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.identity_governance_service.target_audit_fields(
        "identity_subject", subject_id
    )
    reason, idempotency_key = await _governance_mutation_audit_fields(request)
    return await _authorize_identity_governance(
        request,
        subject,
        permission_id=IDENTITY_SUBJECT_ADMIN_DISABLE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        reason=reason,
        idempotency_key=idempotency_key,
        target_metadata=target_metadata,
    )


async def _governance_mutation_audit_fields(request: Request) -> tuple[str | None, str | None]:
    try:
        body = await request.json()
    except ValueError:
        body = None
    raw_reason = body.get("reason") if isinstance(body, dict) else None
    reason = raw_reason.strip() if isinstance(raw_reason, str) else None
    if reason is not None and (
        not reason or len(reason) > 240 or any(ord(character) < 32 for character in reason)
    ):
        reason = None
    raw_idempotency_key = request.headers.get("Idempotency-Key")
    idempotency_key = (
        raw_idempotency_key
        if raw_idempotency_key is not None and len(raw_idempotency_key) <= 128
        else None
    )
    return reason, idempotency_key


async def _authorize_workload_identity(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
    target_subject_id: str | None = None,
    target_metadata: tuple[tuple[str, str], ...] = (),
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    reason, idempotency_key = await _governance_mutation_audit_fields(request)
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.identity.workload",
            scope=workload_identity_governance_scope(
                subject.organization_id,
                settings.environment,
                capability_class,
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
            target_subject_id=target_subject_id,
            reason=reason,
            idempotency_key=idempotency_key,
            target_metadata=target_metadata,
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Workload identity governance is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_workload_identity_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_workload_identity(
        request,
        subject,
        permission_id=WORKLOAD_IDENTITY_GOVERNANCE_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_workload_identity_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_workload_identity(
        request,
        subject,
        permission_id=WORKLOAD_IDENTITY_ADMIN_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_workload_identity_rotate(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    identity_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.workload_identity_service.target_audit_fields(
        "workload_identity", identity_id
    )
    return await _authorize_workload_identity(
        request,
        subject,
        permission_id=WORKLOAD_IDENTITY_ADMIN_ROTATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        target_metadata=target_metadata,
    )


async def authorize_workload_identity_revoke(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    credential_id: str,
) -> AuthorizationDecision:
    (
        target_subject_id,
        target_metadata,
    ) = await request.app.state.workload_identity_service.target_audit_fields(
        "workload_credential", credential_id
    )
    return await _authorize_workload_identity(
        request,
        subject,
        permission_id=WORKLOAD_IDENTITY_ADMIN_REVOKE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
        target_subject_id=target_subject_id,
        target_metadata=target_metadata,
    )


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


async def authorize_release_preflight_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=RELEASE_PREFLIGHT_READ,
            resource_type="resource.platform.release-preflight",
            scope=release_preflight_scope(subject.organization_id, settings.environment),
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


async def authorize_deployment_configuration_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=DEPLOYMENT_CONFIGURATION_PREVIEW,
            resource_type="resource.platform.deployment-configuration",
            scope=deployment_configuration_scope(subject.organization_id, settings.environment),
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


async def authorize_bootstrap_plan_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=BOOTSTRAP_PLAN_READ,
            resource_type="resource.platform.bootstrap-plan",
            scope=bootstrap_plan_scope(subject.organization_id, settings.environment),
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


async def authorize_bootstrap_invalidation_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=BOOTSTRAP_INVALIDATION_PREVIEW,
            resource_type="resource.platform.bootstrap-invalidation",
            scope=bootstrap_invalidation_scope(subject.organization_id, settings.environment),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Bootstrap invalidation preview is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_support_bundle_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_support_bundle(
        request,
        subject,
        permission_id=SUPPORT_BUNDLE_PREVIEW,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_support_bundle_export(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_support_bundle(
        request,
        subject,
        permission_id=SUPPORT_BUNDLE_EXPORT,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_support_bundle(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.support.bundle",
            scope=support_bundle_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Support bundle access is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_backup_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_logical_backup(
        request,
        subject,
        permission_id=BACKUP_LOGICAL_PREVIEW,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_backup_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_logical_backup(
        request,
        subject,
        permission_id=BACKUP_LOGICAL_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_restore_validation(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_logical_backup(
        request,
        subject,
        permission_id=BACKUP_LOGICAL_RESTORE_VALIDATE,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_logical_backup(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.backup.logical",
            scope=logical_backup_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Logical backup or restore validation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_upgrade_readiness(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_simulation(
        request,
        subject,
        permission_id=UPGRADE_READINESS_PREVIEW,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_upgrade_simulation(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_simulation(
        request,
        subject,
        permission_id=UPGRADE_ROLLBACK_SIMULATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_upgrade_simulation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.upgrade-simulation",
            scope=upgrade_simulation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Upgrade readiness or isolated rollback simulation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_upgrade_change_review_preview(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_change_review(
        request,
        subject,
        permission_id=UPGRADE_CHANGE_REVIEW_PREVIEW,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_upgrade_change_review_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_change_review(
        request,
        subject,
        permission_id=UPGRADE_CHANGE_REVIEW_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_upgrade_change_review(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.upgrade-change-review",
            scope=upgrade_change_review_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Upgrade change review is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_upgrade_human_review_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_human_review(
        request,
        subject,
        permission_id=UPGRADE_HUMAN_REVIEW_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_upgrade_human_review_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_human_review(
        request,
        subject,
        permission_id=UPGRADE_HUMAN_REVIEW_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_upgrade_human_review_decide(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_human_review(
        request,
        subject,
        permission_id=UPGRADE_HUMAN_REVIEW_DECIDE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_upgrade_completion_receipt_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_completion_receipt(
        request,
        subject,
        permission_id=UPGRADE_COMPLETION_RECEIPT_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_upgrade_completion_receipt_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_upgrade_completion_receipt(
        request,
        subject,
        permission_id=UPGRADE_COMPLETION_RECEIPT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_upgrade_completion_receipt(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.upgrade-human-review-receipt",
            scope=upgrade_completion_receipt_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Human review completion receipt is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_upgrade_human_review(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.upgrade-change-human-review",
            scope=upgrade_human_review_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Upgrade human review is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def _authorize_bootstrap_state(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.platform.bootstrap-state",
            scope=bootstrap_state_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="Bootstrap coordination is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_bootstrap_state_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_bootstrap_state(
        request,
        subject,
        permission_id=BOOTSTRAP_STATE_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_bootstrap_state_manage(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_bootstrap_state(
        request,
        subject,
        permission_id=BOOTSTRAP_STATE_MANAGE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


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


async def _authorize_health_check(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.health-check",
            scope=health_check_scope(subject.organization_id, settings.environment),
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


async def authorize_health_check_overview_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_health_check(request, subject, permission_id=HEALTH_CHECK_OVERVIEW_READ)


async def authorize_health_check_run_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_health_check(request, subject, permission_id=HEALTH_CHECK_RUN_CREATE)


async def authorize_investigation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=INVESTIGATION_CREATE,
            resource_type="resource.investigation",
            scope=investigation_scope(subject.organization_id, settings.environment),
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


async def authorize_rca_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=RCA_CREATE,
            resource_type="resource.rca",
            scope=rca_scope(subject.organization_id, settings.environment),
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


async def authorize_recommendation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=RECOMMENDATION_CREATE,
            resource_type="resource.recommendation",
            scope=recommendation_scope(subject.organization_id, settings.environment),
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


async def _authorize_approval(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.approval",
            scope=approval_scope(subject.organization_id, settings.environment, capability_class),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The approval operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_approval_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_approval(
        request,
        subject,
        permission_id=APPROVAL_REQUEST_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_approval_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_approval(
        request,
        subject,
        permission_id=APPROVAL_REQUEST_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_approval_decide(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_approval(
        request,
        subject,
        permission_id=APPROVAL_REQUEST_DECIDE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_report_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=REPORT_CREATE,
            resource_type="resource.report",
            scope=report_scope(subject.organization_id, settings.environment),
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


async def _authorize_security_export(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
) -> AuthorizationDecision:
    service: AuthorizationService = request.app.state.authorization_service
    settings = request.app.state.settings
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.security-export",
            scope=security_export_scope(subject.organization_id, settings.environment),
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


async def authorize_security_export_overview_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_security_export(
        request, subject, permission_id=SECURITY_EXPORT_OVERVIEW_READ
    )


async def authorize_security_export_test_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
) -> AuthorizationDecision:
    return await _authorize_security_export(
        request, subject, permission_id=SECURITY_EXPORT_TEST_CREATE
    )


async def _authorize_audit_export(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    scope = audit_export_scope(
        subject.organization_id,
        settings.environment,
        capability_class,
    )
    requested_at = datetime.now(UTC)
    if (
        subject.kind is not SubjectKind.HUMAN
        or subject.authentication_method is AuthenticationMethod.DEVELOPMENT
    ):
        await request.app.state.audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.audit.access.denied",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=requested_at,
                correlation_id=str(request.state.correlation_id),
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                assurance_level=subject.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.audit.events",
                scope_reference=scope.reference,
                decision_id=None,
                outcome="denied",
                result_code="enterprise_human_browser_required",
            )
        )
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity is not authorized for this operation.",
        )
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.audit.events",
            scope=scope,
            correlation_id=str(request.state.correlation_id),
            requested_at=requested_at,
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


async def authorize_audit_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_audit_export(
        request,
        subject,
        permission_id=AUDIT_READ,
        capability_class=CapabilityClass.C0_INFORMATIONAL,
    )


async def authorize_audit_export(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_audit_export(
        request,
        subject,
        permission_id=AUDIT_EXPORT,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def _authorize_mcp_builder(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.mcp-builder.project",
            scope=mcp_builder_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The MCP Builder operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_mcp_builder_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_PROJECT_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_PROJECT_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_design_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_DESIGN_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_design_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_DESIGN_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_generation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_GENERATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_generation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_GENERATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_domain_review_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_DOMAIN_REVIEW_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_domain_review_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_DOMAIN_REVIEW_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_security_review_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_SECURITY_REVIEW_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_security_review_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_SECURITY_REVIEW_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_lab_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_LAB_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_lab_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_LAB_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_candidate_handoff_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_CANDIDATE_HANDOFF_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_mcp_builder_candidate_handoff_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_CANDIDATE_HANDOFF_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def authorize_mcp_builder_candidate_handoff_download(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_mcp_builder(
        request,
        subject,
        permission_id=MCP_BUILDER_CANDIDATE_HANDOFF_DOWNLOAD,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_acquisition(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-acquisition",
            scope=connector_package_acquisition_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The connector package acquisition operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_acquire(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_acquisition(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_ACQUIRE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_acquisition_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_acquisition(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_ACQUISITION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )


async def _authorize_connector_package_validation(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    permission_id: str,
    capability_class: CapabilityClass,
) -> AuthorizationDecision:
    settings = request.app.state.settings
    service: AuthorizationService = request.app.state.authorization_service
    decision = await service.evaluate(
        AuthorizationRequest(
            subject=subject,
            permission_id=permission_id,
            resource_type="resource.connector.package-validation",
            scope=connector_package_validation_scope(
                subject.organization_id, settings.environment, capability_class
            ),
            correlation_id=str(request.state.correlation_id),
            requested_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        raise AtlasError(
            status=403,
            code="authorization_denied",
            title="Request denied",
            detail="The connector package validation operation is not authorized.",
        )
    request.state.authorization_decision = decision
    return decision


async def authorize_connector_package_validation_create(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_VALIDATION_CREATE,
        capability_class=CapabilityClass.C2_DIAGNOSTIC,
    )


async def authorize_connector_package_validation_read(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
) -> AuthorizationDecision:
    return await _authorize_connector_package_validation(
        request,
        subject,
        permission_id=CONNECTOR_PACKAGE_VALIDATION_READ,
        capability_class=CapabilityClass.C1_READ_ONLY,
    )
