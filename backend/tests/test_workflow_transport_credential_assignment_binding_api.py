from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    PUBLISHER_ID,
    _assert_no_step_up_language,
    _AuditSink,
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
    _workload_service,
)

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_BIND,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_READ,
)
from atlas.modules.identity.application.workload_identities import WorkloadIdentityService
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
)
from atlas.modules.workflows.domain import WorkflowScope

ENDPOINT = "/api/v1/workflows/physical-transport-credential-assignment-bindings"
BINDER_ID = "workload.atlas.workflow-physical-transport-credential-binder-01"
ROUTE_BINDING_ID = "physical-route-binding.test-0001"
ASSIGNMENT_SNAPSHOT_ID = "credential-assignment-snapshot.test-0001"


@dataclass(frozen=True, slots=True)
class _Binding:
    binding_id: str
    physical_transport_route_binding_id: str
    credential_assignment_snapshot_id: str
    scope: WorkflowScope
    bound_at: datetime


class _Repository:
    durable = False

    def __init__(self, bindings: tuple[_Binding, ...] = ()) -> None:
        self.bindings = bindings

    async def list_credential_assignment_bindings(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[_Binding, ...]:
        return tuple(binding for binding in self.bindings if binding.scope == scope)[:limit]


class _Service:
    durable = False

    def __init__(self, bindings: tuple[_Binding, ...] = ()) -> None:
        self.repository = _Repository(bindings)
        self.policy = SimpleNamespace(
            policy_id="policy.workflow-event-physical-transport-credential-assignment-binding",
            policy_version="1.0",
            canonical_digest="a" * 64,
        )
        self.bind_calls: list[dict[str, Any]] = []

    async def bind(self, **kwargs: Any) -> _Binding:
        self.bind_calls.append(kwargs)
        binding = _binding(scope=kwargs["context"].scope)
        self.repository.bindings = (binding,)
        return binding


def _binding(*, scope: WorkflowScope | None = None) -> _Binding:
    return _Binding(
        binding_id="credential-assignment-binding.test-0001",
        physical_transport_route_binding_id=ROUTE_BINDING_ID,
        credential_assignment_snapshot_id=ASSIGNMENT_SNAPSHOT_ID,
        scope=scope
        or WorkflowScope(
            organization_id="organization.development",
            environment_id="environment.development",
            site_id="site.local",
        ),
        bound_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
    )


def _payload(*, idempotency_key: str = "credential-assignment-binding-0001") -> dict[str, str]:
    return {
        "physical_transport_route_binding_id": ROUTE_BINDING_ID,
        "physical_transport_route_binding_digest": "1" * 64,
        "credential_assignment_snapshot_id": ASSIGNMENT_SNAPSHOT_ID,
        "credential_assignment_snapshot_digest": "2" * 64,
        "idempotency_key": idempotency_key,
    }


def _binder_token(service: WorkloadIdentityService) -> str:
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
    issued = asyncio.run(
        service.create(
            actor=actor,
            identity_id=BINDER_ID,
            display_name="Workflow physical transport credential-assignment binder",
            service_id="service.workflow-physical-transport-credential-binder",
            instance_id="instance.workflow-physical-transport-credential-binder.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Bind immutable credential-assignment evidence without access authority.",
            audiences=(WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE,),
            secret_reference_ids=("secret.workflow-physical-transport-credential-binder.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the dedicated credential-assignment binder API test identity.",
            idempotency_key="credential-assignment-binder-identity-0001",
            correlation_id="correlation.credential-assignment-binder-identity-0001",
        )
    )
    return issued.token


def _assert_minimized(binding: dict[str, Any]) -> None:
    assert set(binding) == {
        "binding_id",
        "physical_transport_route_binding_id",
        "credential_assignment_snapshot_id",
        "state",
        "bound_at",
        "integrity_reference",
    }
    assert binding["state"] == "bound"
    assert binding["integrity_reference"] == f"integrity.{binding['binding_id']}"
    normalized = str(binding).casefold()
    for forbidden in (
        "digest",
        "credential_profile",
        "credential_requirement",
        "target",
        "broker",
        "endpoint",
        "artifact",
        "secret",
        "authority",
        "policy",
    ):
        assert forbidden not in normalized


def test_default_app_wires_binding_service_to_shared_workflow_repository() -> None:
    app = create_app(_settings(), audit_sink=_AuditSink())

    with TestClient(app):
        service = app.state.workflow_event_physical_transport_credential_assignment_binding_service
        repository = (
            app.state.workflow_event_physical_transport_credential_assignment_binding_repository
        )

    assert service.repository is repository
    assert repository is app.state.workflow_planning_service.repository


def test_production_without_database_composes_fail_closed_shared_repository() -> None:
    app = create_app(
        Settings(environment="production", enable_api_docs=False, database_url=None),
        audit_sink=_AuditSink(),
    )

    with TestClient(app):
        service = app.state.workflow_event_physical_transport_credential_assignment_binding_service
        repository = (
            app.state.workflow_event_physical_transport_credential_assignment_binding_repository
        )

    assert isinstance(repository, UnavailableWorkflowPlanRepository)
    assert service.repository is repository
    assert repository is app.state.workflow_planning_service.repository
    assert repository.durable is False


def test_normal_browser_session_reads_minimized_binding_without_step_up() -> None:
    service = _Service((_binding(),))
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workflow_event_physical_transport_credential_assignment_binding_service=cast(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
            service,
        ),
    )

    with TestClient(app) as client:
        unauthenticated = client.get(ENDPOINT)
        _login(client)
        inventory = client.get(ENDPOINT)
        registered_permissions = app.state.authorization_service._permissions

    assert unauthenticated.status_code in {401, 403}
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_READ in (
        registered_permissions
    )
    assert WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_BINDING_BIND in (
        registered_permissions
    )
    bindings = inventory.json()["data"]["physical_transport_credential_assignment_bindings"]
    assert len(bindings) == 1
    _assert_minimized(bindings[0])
    _assert_no_step_up_language(inventory.text)


def test_only_dedicated_workload_binds_with_server_owned_policy() -> None:
    workload_service, tokens = _workload_service()
    binder_token = _binder_token(workload_service)
    service = _Service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_credential_assignment_binding_service=cast(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
            service,
        ),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        browser = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
        api_token = _issue_api_token(client, csrf)
        personal = client.post(
            ENDPOINT,
            json=_payload(),
            headers={"Authorization": f"Bearer {api_token}"},
        )
        wrong_workload = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                tokens[PUBLISHER_ID],
                WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
            ),
        )
        binder_headers = _workload_headers(
            binder_token,
            WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE,
        )
        created = client.post(ENDPOINT, json=_payload(), headers=binder_headers)
        forbidden = client.post(
            ENDPOINT,
            json=_payload(idempotency_key="credential-assignment-binding-extra-0001")
            | {"policy_digest": "f" * 64},
            headers=binder_headers,
        )

    for denied in (browser, personal, wrong_workload):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert forbidden.status_code == 422
    assert created.status_code == 201
    binding = created.json()["data"]
    _assert_minimized(binding)
    assert len(service.bind_calls) == 1
    call = service.bind_calls[0]
    assert call["policy_id"] == service.policy.policy_id
    assert call["policy_version"] == service.policy.policy_version
    assert call["policy_digest"] == service.policy.canonical_digest
    assert call["context"].credential_audience == (
        WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE
    )
    assert api_token not in personal.text
