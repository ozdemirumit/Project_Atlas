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

from atlas.api.app import _deployment_event_transport_routes, create_app
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
    WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
)
from atlas.modules.workflows.domain import DeploymentEventTransportRoute

REGISTRY_ID = "workload.atlas.workflow-transport-route-registry-01"
ENDPOINT = "/api/v1/workflows/transport-route-snapshots"


def test_non_development_environments_do_not_fabricate_transport_routes() -> None:
    assert (
        _deployment_event_transport_routes(
            Settings(environment="test", development_identity_enabled=True)
        )
        == ()
    )


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
            display_name="Workflow transport route registry",
            service_id="service.workflow-transport-route-registry",
            instance_id="instance.workflow-transport-route-registry.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Capture server-owned immutable route metadata without operation authority.",
            audiences=(WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,),
            secret_reference_ids=("secret.workflow-transport-route-registry.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the dedicated transport route registry API test identity.",
            idempotency_key="transport-route-registry-identity-0001",
            correlation_id="correlation.transport-route-registry-identity-0001",
        )
    )
    return issued.token


def _source_route(app: Any) -> DeploymentEventTransportRoute:
    routes = app.state.workflow_transport_route_source_routes
    assert isinstance(routes, tuple)
    assert len(routes) == 1
    route = routes[0]
    assert isinstance(route, DeploymentEventTransportRoute)
    return route


def _payload(
    source: DeploymentEventTransportRoute,
    *,
    idempotency_key: str = "transport-route-snapshot-0001",
) -> dict[str, object]:
    return {
        "source_route_id": source.route_id,
        "source_route_revision": source.route_revision,
        "source_route_digest": source.canonical_digest,
        "idempotency_key": idempotency_key,
    }


def _assert_minimized_snapshot(snapshot: dict[str, Any]) -> None:
    assert set(snapshot) == {
        "snapshot_id",
        "route_id",
        "route_revision",
        "route_set_id",
        "route_set_revision",
        "selection_epoch_id",
        "selection_epoch_revision",
        "source_route_digest",
        "deployment_release_id",
        "deployment_profile",
        "scope",
        "transport_profile_id",
        "transport_profile_revision",
        "transport_resource_id",
        "transport_implementation_id",
        "transport_implementation_version",
        "adapter_contract_id",
        "adapter_contract_version",
        "route_kind",
        "endpoint_set_id",
        "endpoint_set_revision",
        "destination_id",
        "destination_revision",
        "routing_contract_id",
        "routing_contract_revision",
        "transport_security_policy_id",
        "transport_security_policy_version",
        "minimum_tls_version",
        "server_authentication_required",
        "client_authentication_required",
        "plaintext_fallback_prohibited",
        "network_policy_id",
        "network_policy_version",
        "source_zone_class",
        "destination_zone_class",
        "restricted_network_enforced",
        "public_egress_prohibited",
        "proxy_mode",
        "credential_requirement_profile_id",
        "credential_requirement_profile_version",
        "authentication_mechanism_class",
        "principal_class",
        "snapshotter_subject_id",
        "captured_at",
        "state",
        "authority",
        "canonical_digest",
    }
    assert snapshot["state"] == "snapshotted"
    assert not any(snapshot["authority"].values())
    for forbidden in (
        "transport_resource_digest",
        "adapter_contract_digest",
        "endpoint_set_digest",
        "destination_digest",
        "routing_contract_digest",
        "transport_security_policy_digest",
        "network_policy_digest",
        "credential_requirement_profile_digest",
        "private_route_descriptor_commitment",
        "hostname",
        "url",
        "ip_address",
        "namespace",
        "topic_name",
        "stream_name",
        "queue_name",
        "partition",
        "routing_key",
        "credential_reference",
        "secret_reference",
        "vault_path",
        "certificate_reference",
    ):
        assert forbidden not in snapshot


def test_registry_workload_snapshots_and_one_browser_login_reads_minimized_inventory() -> None:
    workload_service, _ = _workload_service()
    registry_token = _registry_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )

    with TestClient(app) as client:
        _login(client)
        source = _source_route(app)
        empty = client.get(ENDPOINT)
        headers = _workload_headers(
            registry_token,
            WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
        )
        created = client.post(ENDPOINT, json=_payload(source), headers=headers)
        replay = client.post(ENDPOINT, json=_payload(source), headers=headers)
        inventory = client.get(ENDPOINT)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"] == {"transport_route_snapshots": [], "durable": False}
    assert created.status_code == 201
    assert created.headers["Cache-Control"].startswith("no-store")
    snapshot = created.json()["data"]
    _assert_minimized_snapshot(snapshot)
    assert snapshot["route_id"] == source.route_id
    assert snapshot["route_revision"] == source.route_revision
    assert snapshot["source_route_digest"] == source.canonical_digest
    assert snapshot["snapshotter_subject_id"] == REGISTRY_ID
    assert replay.status_code == 201
    assert replay.json()["data"] == snapshot
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert inventory.json()["data"]["transport_route_snapshots"] == [snapshot]
    _assert_no_step_up_language(inventory.text)
    assert registry_token not in inventory.text
    assert "http://" not in inventory.text
    assert "https://" not in inventory.text


def test_snapshot_creation_rejects_browser_pat_and_wrong_workload_audience() -> None:
    workload_service, tokens = _workload_service()
    registry_token = _registry_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )

    with TestClient(app) as client:
        csrf = _login(client)
        source = _source_route(app)
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
        admitted = client.post(
            ENDPOINT,
            json=payload,
            headers=_workload_headers(
                registry_token,
                WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
            ),
        )

    for denied in (browser, pat, wrong_workload):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert admitted.status_code == 201
    assert api_token not in pat.text


def test_snapshot_creation_rejects_caller_controlled_route_and_operational_fields() -> None:
    workload_service, _ = _workload_service()
    registry_token = _registry_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )

    with TestClient(app) as client:
        source = _source_route(app)
        headers = _workload_headers(
            registry_token,
            WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
        )
        for index, (field, value) in enumerate(
            (
                ("endpoint", "https://example.invalid"),
                ("topic", "caller-selected"),
                ("destination_id", "destination.caller-selected"),
                ("routing_key", "caller-selected"),
                ("credential_reference", "secret.caller-selected"),
                ("health_probe", True),
                ("ready", True),
                ("publish", True),
                ("route_binding", True),
            ),
            start=1,
        ):
            response = client.post(
                ENDPOINT,
                json=_payload(
                    source,
                    idempotency_key=f"transport-route-extra-denied-{index:04d}",
                )
                | {field: value},
                headers=headers,
            )
            assert response.status_code == 422


def test_transport_route_inventory_is_default_deny_without_explicit_assignment() -> None:
    app = create_app(
        Settings(
            environment="development",
            development_identity_enabled=True,
            development_role_ids=("role.unassigned",),
        ),
        audit_sink=_AuditSink(),
    )

    with TestClient(app) as client:
        _login(client)
        denied = client.get(ENDPOINT)

    assert denied.status_code == 403
    assert denied.json()["code"] == "authorization_denied"
    _assert_no_step_up_language(denied.text)
