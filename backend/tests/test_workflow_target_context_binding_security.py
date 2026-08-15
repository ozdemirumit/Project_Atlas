from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from atlas.api.errors import AtlasError
from atlas.api.security import (
    authorize_workflow_physical_transport_target_context_binding_read,
    workflow_physical_transport_target_context_binder_subject,
)
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    DEVELOPMENT_ROLE_ID,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_READ,
    build_development_authorization_service,
    workflow_physical_transport_target_context_binding_scope,
)
from atlas.modules.identity.adapters.workload_identities import (
    InMemoryWorkloadIdentityRepository,
)
from atlas.modules.identity.application.workload_identities import WorkloadIdentityService
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
)


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


def _request(settings: Settings, **state: object) -> Request:
    app = SimpleNamespace(state=SimpleNamespace(settings=settings, **state))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "app": app,
            "state": {"correlation_id": "cor_target_context_binding_security"},
        }
    )


def _human(
    settings: Settings,
    *,
    subject_id: str | None = None,
    role_ids: tuple[str, ...] | None = None,
) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id or settings.development_subject_id,
        display_name="Target Context Reader",
        kind=SubjectKind.HUMAN,
        provider_id="provider.development.local",
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
        authenticated_at=datetime.now(UTC),
        organization_id=settings.development_organization_id,
        role_ids=role_ids or (DEVELOPMENT_ROLE_ID,),
    )


async def _workload_service() -> tuple[WorkloadIdentityService, str, str]:
    service = WorkloadIdentityService(
        repository=InMemoryWorkloadIdentityRepository(),
        audit_sink=_AuditSink(),
        environment_id="environment.development",
        signing_keys={1: b"target-context-binding-security-key" * 2},
    )
    actor = AuthenticatedSubject(
        subject_id="subject.enterprise.security-admin",
        display_name="Security Administrator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=datetime.now(UTC),
        organization_id="organization.development",
        role_ids=("role.security-administrator",),
    )

    async def issue(identity_id: str, suffix: str) -> str:
        issued = await service.create(
            actor=actor,
            identity_id=identity_id,
            display_name=f"Target context binder {suffix}",
            service_id=identity_id,
            instance_id=f"instance.target-context-binder.{suffix}",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Bind immutable endpoint and credential materialization evidence.",
            audiences=(WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,),
            secret_reference_ids=(f"secret.target-context-binder.{suffix}",),
            lifetime=timedelta(minutes=10),
            reason="Verify exact IMP-208 workload authentication.",
            idempotency_key=f"target-context-binding-security-{suffix}",
            correlation_id=f"cor_target_context_binding_security_{suffix}",
        )
        return issued.token

    exact_token = await issue(WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT, "exact")
    wrong_token = await issue("service.workflow-physical-transport-wrong-binder", "wrong")
    return service, exact_token, wrong_token


@pytest.mark.asyncio
async def test_target_context_binding_read_is_c1_scope_bound_and_default_deny() -> None:
    settings = Settings(environment="development", development_identity_enabled=True)
    authorization = build_development_authorization_service(settings, _AuditSink())
    scope = workflow_physical_transport_target_context_binding_scope(
        settings.development_organization_id,
        settings.environment,
    )
    request = _request(settings, authorization_service=authorization)

    decision = await authorize_workflow_physical_transport_target_context_binding_read(
        request,
        _human(settings),
    )

    assert decision.allowed is True
    assert decision.permission_id == WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDING_READ
    assert decision.scope_reference == scope.reference
    assert scope.capability_class.value == "C1"

    denied_request = _request(settings, authorization_service=authorization)
    with pytest.raises(AtlasError) as denied:
        await authorize_workflow_physical_transport_target_context_binding_read(
            denied_request,
            _human(
                settings,
                subject_id="subject.development.unassigned",
                role_ids=("role.unassigned",),
            ),
        )
    assert denied.value.status == 403
    assert denied.value.code == "authorization_denied"


@pytest.mark.asyncio
async def test_target_context_binder_requires_exact_workload_subject_audience_and_environment() -> (
    None
):
    settings = Settings(environment="development")
    workload_service, exact_token, wrong_token = await _workload_service()

    exact_request = _request(settings, workload_identity_service=workload_service)
    subject = await workflow_physical_transport_target_context_binder_subject(
        exact_request,
        authorization=f"Workload {exact_token}",
        audience=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
        environment_id="environment.development",
    )
    assert subject.subject_id == WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT
    assert subject.kind is SubjectKind.SERVICE
    assert subject.authentication_method is AuthenticationMethod.WORKLOAD_TOKEN

    failures = (
        (exact_token, "audience.workflow-physical-transport-wrong", "environment.development"),
        (
            exact_token,
            WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
            "environment.test",
        ),
        (
            wrong_token,
            WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
            "environment.development",
        ),
    )
    for token, audience, environment_id in failures:
        denied_request = _request(settings, workload_identity_service=workload_service)
        with pytest.raises(AtlasError) as denied:
            await workflow_physical_transport_target_context_binder_subject(
                denied_request,
                authorization=f"Workload {token}",
                audience=audience,
                environment_id=environment_id,
            )
        assert denied.value.status == 401
        assert denied.value.code == "workload_authentication_failed"
