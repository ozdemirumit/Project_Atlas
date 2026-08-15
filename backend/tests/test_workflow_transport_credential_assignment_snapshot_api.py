from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

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
from test_workflow_transport_credential_assignment_snapshots import (
    assignment_fixture,
    route_fixture,
)
from test_workflow_transport_route_snapshot_api import (
    ENDPOINT as ROUTE_ENDPOINT,
)
from test_workflow_transport_route_snapshot_api import (
    _payload as _route_payload,
)
from test_workflow_transport_route_snapshot_api import (
    _registry_token as _route_registry_token,
)
from test_workflow_transport_route_snapshot_api import (
    _source_route,
)

from atlas.api.app import _deployment_physical_transport_credential_assignments, create_app
from atlas.core.config import Settings
from atlas.modules.identity.application.workload_identities import WorkloadIdentityService
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.workflows.application import (
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT,
    WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
)
from atlas.modules.workflows.domain import (
    DeploymentPhysicalTransportCredentialAssignment,
    WorkflowScope,
    canonical_digest,
)

ENDPOINT = "/api/v1/workflows/transport-credential-assignment-snapshots"
REGISTRY_ID = WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_SUBJECT


def test_non_development_environments_do_not_fabricate_credential_assignments() -> None:
    settings = Settings(environment="test", development_identity_enabled=True)
    assert _deployment_physical_transport_credential_assignments(settings, ()) == ()


def test_non_development_registry_reads_the_workflow_repository() -> None:
    app = create_app(
        Settings(environment="test", development_identity_enabled=True),
        audit_sink=_AuditSink(),
    )
    with TestClient(app):
        service = app.state.workflow_transport_credential_assignment_snapshot_service
        assert service._registry is service.repository


def test_non_development_assignment_configuration_is_validated_and_loaded() -> None:
    source = assignment_fixture(
        route=route_fixture(),
        scope=WorkflowScope("org.atlas", "environment.test", "site.istanbul"),
    )
    configured = source.digest_payload()
    scope = configured.pop("scope")
    assert isinstance(scope, dict)
    settings = Settings(
        environment="test",
        development_identity_enabled=True,
        workflow_transport_credential_assignments=(configured | scope,),
    )
    assert _deployment_physical_transport_credential_assignments(settings, ()) == (source,)


def _registry_token(service: WorkloadIdentityService) -> str:
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
            identity_id=REGISTRY_ID,
            display_name="Workflow transport credential assignment registry",
            service_id=REGISTRY_ID,
            instance_id="instance.workflow-transport-credential-assignment-registry.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Capture immutable credential assignment metadata without secret access.",
            audiences=(WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,),
            secret_reference_ids=(
                "secret.workflow-transport-credential-assignment-registry.local-01",
            ),
            lifetime=timedelta(minutes=10),
            reason="Create the dedicated credential assignment registry API test identity.",
            idempotency_key="transport-credential-assignment-registry-identity-0001",
            correlation_id="correlation.transport-credential-assignment-registry-identity-0001",
        )
    )
    return issued.token


def _source_assignment(app: Any) -> DeploymentPhysicalTransportCredentialAssignment:
    assignments = app.state.workflow_transport_credential_assignment_source_assignments
    assert isinstance(assignments, tuple)
    assert len(assignments) == 1
    assignment = assignments[0]
    assert isinstance(assignment, DeploymentPhysicalTransportCredentialAssignment)
    return assignment


def _payload(
    source: DeploymentPhysicalTransportCredentialAssignment,
    *,
    idempotency_key: str = "transport-credential-assignment-snapshot-0001",
) -> dict[str, object]:
    return {
        "assignment_id": source.assignment_id,
        "assignment_revision": source.assignment_revision,
        "source_assignment_digest": source.canonical_digest,
        "idempotency_key": idempotency_key,
    }


def _assert_minimized_snapshot(snapshot: dict[str, Any]) -> None:
    assert set(snapshot) == {
        "snapshot_id",
        "assignment_id",
        "assignment_revision",
        "state",
        "credential_generation",
        "rotation_epoch",
        "activated_at",
        "expires_at",
        "captured_at",
        "authority",
    }
    assert snapshot["state"] == "snapshotted"
    assert not any(snapshot["authority"].values())
    serialized = str(snapshot).lower()
    for forbidden in (
        "credential_profile",
        "credential_requirement",
        "target_scope",
        "broker_policy",
        "source_assignment_digest",
        "source_route_digest",
        "canonical_digest",
        "secret_reference",
        "vault_path",
        "username",
        "password",
        "certificate",
        "hostname",
        "http://",
        "https://",
    ):
        assert forbidden not in serialized


def _snapshot_route(client: TestClient, app: Any, token: str) -> None:
    source = _source_route(app)
    response = client.post(
        ROUTE_ENDPOINT,
        json=_route_payload(source),
        headers=_workload_headers(token, WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE),
    )
    assert response.status_code == 201


def test_registry_workload_snapshots_and_normal_browser_login_reads_inventory() -> None:
    workload_service, _ = _workload_service()
    route_token = _route_registry_token(workload_service)
    registry_token = _registry_token(workload_service)
    registry_subject = asyncio.run(
        workload_service.authenticate(
            registry_token,
            audience=WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,
            environment_id="environment.development",
            correlation_id="correlation.credential-assignment-registry-authentication",
        )
    )
    assert registry_subject.subject_id == REGISTRY_ID
    assert registry_subject.organization_id == "organization.development"
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )

    with TestClient(app) as client:
        _login(client)
        empty = client.get(ENDPOINT)
        _snapshot_route(client, app, route_token)
        source = _source_assignment(app)
        requested_at = datetime.now(UTC)
        assert source.scope == WorkflowScope(
            organization_id=registry_subject.organization_id,
            environment_id="environment.development",
            site_id="site.local",
        )
        assert source.canonical_digest == canonical_digest(source.digest_payload())
        assert source.active and not source.revoked
        assert source.activated_at <= requested_at < source.expires_at
        assert source.privilege_class == "read-only"
        assert source.credential_generation >= 1 and source.rotation_epoch >= 1
        headers = _workload_headers(
            registry_token,
            WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,
        )
        created = client.post(ENDPOINT, json=_payload(source), headers=headers)
        replay = client.post(ENDPOINT, json=_payload(source), headers=headers)
        app.state.workflow_transport_credential_assignment_source_assignments = ()
        inventory = client.get(ENDPOINT)

    assert empty.status_code == 200
    assert empty.json()["data"] == {
        "transport_credential_assignment_snapshots": [],
        "durable": False,
    }
    assert created.status_code == 201, created.text
    snapshot = created.json()["data"]
    _assert_minimized_snapshot(snapshot)
    assert snapshot["assignment_id"] == source.assignment_id
    assert snapshot["assignment_revision"] == source.assignment_revision
    assert replay.status_code == 201
    assert replay.json()["data"] == snapshot
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert inventory.json()["data"]["transport_credential_assignment_snapshots"] == [snapshot]
    _assert_no_step_up_language(inventory.text)
    assert registry_token not in inventory.text


def test_snapshot_creation_rejects_humans_pat_wrong_audience_and_operational_fields() -> None:
    workload_service, tokens = _workload_service()
    route_token = _route_registry_token(workload_service)
    registry_token = _registry_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )

    with TestClient(app) as client:
        csrf = _login(client)
        _snapshot_route(client, app, route_token)
        source = _source_assignment(app)
        payload = _payload(source)
        browser = client.post(ENDPOINT, json=payload, headers={"X-CSRF-Token": csrf})
        api_token = _issue_api_token(client, csrf)
        pat = client.post(
            ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {api_token}"},
        )
        wrong_workload = client.post(
            ENDPOINT,
            json=payload,
            headers=_workload_headers(
                tokens[PUBLISHER_ID],
                WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
            ),
        )
        headers = _workload_headers(
            registry_token,
            WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,
        )
        for index, (field, value) in enumerate(
            (
                ("credential_profile_id", "credential-profile.caller"),
                ("secret_reference", "secret.caller"),
                ("vault_path", "/caller/secret"),
                ("endpoint", "https://example.invalid"),
                ("network_access_authorized", True),
                ("credential_access_authorized", True),
                ("publish", True),
            ),
            start=1,
        ):
            denied_field = client.post(
                ENDPOINT,
                json=_payload(
                    source,
                    idempotency_key=f"credential-assignment-extra-denied-{index:04d}",
                )
                | {field: value},
                headers=headers,
            )
            assert denied_field.status_code == 422

    for denied in (browser, pat, wrong_workload):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert api_token not in pat.text
