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

from atlas.api.app import _deployment_event_transport_profiles, create_app
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
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
)
from atlas.modules.workflows.domain import DeploymentEventTransportProfile

REGISTRY_ID = "workload.atlas.workflow-transport-profile-registry-01"
ENDPOINT = "/api/v1/workflows/transport-profile-snapshots"


def test_non_development_environments_do_not_fabricate_transport_profiles() -> None:
    assert (
        _deployment_event_transport_profiles(
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
            display_name="Workflow transport profile registry",
            service_id="service.workflow-transport-profile-registry",
            instance_id="instance.workflow-transport-profile-registry.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Capture server-owned transport capability evidence without route authority.",
            audiences=(WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,),
            secret_reference_ids=("secret.workflow-transport-profile-registry.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the dedicated transport profile registry API test identity.",
            idempotency_key="transport-profile-registry-identity-0001",
            correlation_id="correlation.transport-profile-registry-identity-0001",
        )
    )
    return issued.token


def _source_profile(app: Any) -> DeploymentEventTransportProfile:
    profiles = app.state.workflow_transport_profile_source_profiles
    assert len(profiles) == 1
    return profiles[0]


def _payload(
    source: DeploymentEventTransportProfile,
    *,
    idempotency_key: str = "transport-profile-snapshot-0001",
) -> dict[str, object]:
    return {
        "source_profile_id": source.transport_profile_id,
        "source_profile_revision": source.transport_profile_revision,
        "source_profile_digest": source.canonical_digest,
        "idempotency_key": idempotency_key,
    }


def _assert_minimized_snapshot(snapshot: dict[str, Any]) -> None:
    assert set(snapshot) == {
        "snapshot_id",
        "transport_profile_id",
        "transport_profile_revision",
        "source_profile_digest",
        "deployment_release_id",
        "deployment_profile",
        "scope",
        "transport_resource_id",
        "transport_resource_digest",
        "transport_implementation_id",
        "transport_implementation_version",
        "adapter_contract_id",
        "adapter_contract_version",
        "adapter_contract_digest",
        "supported_event_contracts",
        "supported_classifications",
        "supported_representations",
        "supported_encodings",
        "supported_delivery_semantics",
        "durable_delivery_supported",
        "supported_ordering_key_kinds",
        "supported_retention_classes",
        "maximum_message_byte_count",
        "transport_encryption_required",
        "restricted_network_supported",
        "snapshotter_subject_id",
        "captured_at",
        "state",
        "authority",
        "canonical_digest",
    }
    assert snapshot["supported_event_contracts"] == [
        {
            "event_type": "WorkflowStepDispatchRequested",
            "event_version": "1.0",
            "schema_uri": "urn:project-atlas:event:workflow-step-dispatch-requested:1.0",
        }
    ]
    assert snapshot["state"] == "snapshotted"
    assert not any(snapshot["authority"].values())


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
        source = _source_profile(app)
        empty = client.get(ENDPOINT)
        created = client.post(
            ENDPOINT,
            json=_payload(source),
            headers=_workload_headers(registry_token, WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE),
        )
        replay = client.post(
            ENDPOINT,
            json=_payload(source),
            headers=_workload_headers(registry_token, WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE),
        )
        inventory = client.get(ENDPOINT)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"] == {
        "transport_profile_snapshots": [],
        "durable": False,
    }
    assert created.status_code == 201
    assert created.headers["Cache-Control"].startswith("no-store")
    snapshot = created.json()["data"]
    _assert_minimized_snapshot(snapshot)
    assert snapshot["transport_profile_id"] == source.transport_profile_id
    assert snapshot["transport_profile_revision"] == source.transport_profile_revision
    assert snapshot["source_profile_digest"] == source.canonical_digest
    assert snapshot["snapshotter_subject_id"] == REGISTRY_ID
    assert replay.status_code == 201
    assert replay.json()["data"] == snapshot
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert inventory.json()["data"]["transport_profile_snapshots"] == [snapshot]
    _assert_no_step_up_language(inventory.text)

    normalized = inventory.text.casefold()
    for forbidden in (
        "event_id",
        "workflow_id",
        "lease_id",
        "route_binding",
        "endpoint",
        "namespace",
        "topic",
        "queue",
        "partition",
        "routing_key",
        "credential",
        "secret_reference",
        "health_result",
        "compatible",
        "publication_attempt",
        "provider_message",
    ):
        assert f'"{forbidden}"' not in normalized
    assert registry_token not in inventory.text


def test_snapshot_creation_rejects_browser_pat_and_wrong_workload_audience() -> None:
    workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )

    with TestClient(app) as client:
        csrf = _login(client)
        source = _source_profile(app)
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
            headers=_workload_headers(tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
        )

    for denied in (browser, pat, wrong_workload):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert api_token not in pat.text


def test_snapshot_creation_rejects_caller_controlled_capability_and_route_fields() -> None:
    workload_service, _ = _workload_service()
    registry_token = _registry_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )

    with TestClient(app) as client:
        source = _source_profile(app)
        headers = _workload_headers(registry_token, WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE)
        for index, (field, value) in enumerate(
            (
                ("supported_delivery_semantics", ["at-most-once"]),
                ("maximum_message_byte_count", 1),
                ("route", "caller-selected"),
                ("endpoint", "https://example.invalid"),
                ("topic", "caller-selected"),
                ("credential_reference", "secret.caller-selected"),
                ("health_probe", True),
                ("compatible", True),
            ),
            start=1,
        ):
            response = client.post(
                ENDPOINT,
                json=_payload(
                    source,
                    idempotency_key=f"transport-profile-extra-denied-{index:04d}",
                )
                | {field: value},
                headers=headers,
            )
            assert response.status_code == 422


def test_transport_profile_inventory_is_default_deny_without_explicit_assignment() -> None:
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
