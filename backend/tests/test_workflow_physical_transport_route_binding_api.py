from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    PUBLISHER_ID,
    WORKER_ID,
    _assert_no_step_up_language,
    _AuditSink,
    _ExplicitTargetAccessSource,
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
    _workload_service,
)
from test_workflow_transport_compatibility_admission_api import (
    ENDPOINT as COMPATIBILITY_ENDPOINT,
)
from test_workflow_transport_compatibility_admission_api import (
    _admitter_token,
    _seed_sources,
)
from test_workflow_transport_compatibility_admission_api import (
    _payload as _compatibility_payload,
)
from test_workflow_transport_profile_snapshot_api import _registry_token as _profile_registry_token
from test_workflow_transport_route_snapshot_api import ENDPOINT as ROUTE_ENDPOINT
from test_workflow_transport_route_snapshot_api import _payload as _route_payload
from test_workflow_transport_route_snapshot_api import _registry_token as _route_registry_token
from test_workflow_transport_route_snapshot_api import _source_route

from atlas.api.app import create_app
from atlas.modules.identity.application.workload_identities import WorkloadIdentityService
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
    WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
    WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
)
from atlas.modules.workflows.domain import (
    code_owned_workflow_event_physical_transport_route_binding_policy,
)

BINDER_ID = "workload.atlas.workflow-physical-transport-route-binder-01"
ENDPOINT = "/api/v1/workflows/physical-transport-route-bindings"


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
            display_name="Workflow physical transport route binder",
            service_id="service.workflow-physical-transport-route-binder",
            instance_id="instance.workflow-physical-transport-route-binder.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Bind exact immutable workflow transport evidence without runtime authority.",
            audiences=(WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,),
            secret_reference_ids=("secret.workflow-physical-transport-route-binder.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the dedicated physical transport route binder API test identity.",
            idempotency_key="physical-transport-route-binder-identity-0001",
            correlation_id="correlation.physical-transport-route-binder-identity-0001",
        )
    )
    return issued.token


def _seed_binding_evidence(
    client: TestClient,
    *,
    csrf: str,
    worker_token: str,
    publisher_token: str,
    profile_registry_token: str,
    route_registry_token: str,
    admitter_token: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    logical, profile = _seed_sources(
        client,
        csrf=csrf,
        worker_token=worker_token,
        publisher_token=publisher_token,
        registry_token=profile_registry_token,
    )
    compatibility = client.post(
        COMPATIBILITY_ENDPOINT,
        json=_compatibility_payload(logical, profile),
        headers=_workload_headers(
            admitter_token,
            WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
        ),
    )
    assert compatibility.status_code == 201
    route_source = _source_route(client.app)
    route = client.post(
        ROUTE_ENDPOINT,
        json=_route_payload(route_source),
        headers=_workload_headers(
            route_registry_token,
            WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
        ),
    )
    assert route.status_code == 201
    return logical, dict(compatibility.json()["data"]), profile, dict(route.json()["data"])


def _payload(
    logical: dict[str, Any],
    compatibility: dict[str, Any],
    profile: dict[str, Any],
    route: dict[str, Any],
) -> dict[str, object]:
    policy = code_owned_workflow_event_physical_transport_route_binding_policy()
    return {
        "logical_channel_binding_id": logical["logical_channel_binding_id"],
        "logical_channel_binding_digest": logical["canonical_digest"],
        "compatibility_admission_id": compatibility["compatibility_admission_id"],
        "compatibility_admission_digest": compatibility["canonical_digest"],
        "transport_profile_snapshot_id": profile["snapshot_id"],
        "transport_profile_snapshot_digest": profile["canonical_digest"],
        "transport_route_snapshot_id": route["snapshot_id"],
        "transport_route_snapshot_digest": route["canonical_digest"],
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "idempotency_key": "physical-transport-route-binding-0001",
    }


def _assert_human_safe(binding: dict[str, Any]) -> None:
    assert set(binding) == {
        "binding_id",
        "logical_channel_binding_id",
        "compatibility_admission_id",
        "transport_profile_snapshot_id",
        "transport_route_snapshot_id",
        "policy_id",
        "policy_version",
        "scope",
        "binder_subject_id",
        "bound_at",
        "state",
        "authority",
        "integrity_reference",
    }
    assert binding["state"] == "bound"
    assert binding["binder_subject_id"] == BINDER_ID
    assert binding["integrity_reference"] == f"integrity.{binding['binding_id']}"
    assert len(binding["authority"]) == 10
    assert not any(binding["authority"].values())
    normalized = str(binding).casefold()
    for forbidden in (
        "digest",
        "route_set",
        "selection_epoch",
        "endpoint_set",
        "destination_id",
        "routing_contract",
        "private_route_descriptor",
        "locator",
        "credential_reference",
        "secret_reference",
        "provider_message",
    ):
        assert forbidden not in normalized


def test_binder_workload_creates_and_one_browser_login_reads_minimized_binding() -> None:
    workload_service, tokens = _workload_service()
    profile_token = _profile_registry_token(workload_service)
    route_token = _route_registry_token(workload_service)
    admitter_token = _admitter_token(workload_service)
    binder_token = _binder_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        logical, compatibility, profile, route = _seed_binding_evidence(
            client,
            csrf=csrf,
            worker_token=tokens[WORKER_ID],
            publisher_token=tokens[PUBLISHER_ID],
            profile_registry_token=profile_token,
            route_registry_token=route_token,
            admitter_token=admitter_token,
        )
        payload = _payload(logical, compatibility, profile, route)
        empty = client.get(ENDPOINT)
        headers = _workload_headers(
            binder_token,
            WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
        )
        created = client.post(ENDPOINT, json=payload, headers=headers)
        replay = client.post(ENDPOINT, json=payload, headers=headers)
        inventory = client.get(ENDPOINT)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"] == {
        "physical_transport_route_bindings": [],
        "durable": False,
    }
    assert created.status_code == 201
    assert created.headers["Cache-Control"].startswith("no-store")
    binding = dict(created.json()["data"])
    _assert_human_safe(binding)
    assert replay.status_code == 201
    assert replay.json()["data"] == binding
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert inventory.json()["data"]["physical_transport_route_bindings"] == [binding]
    _assert_no_step_up_language(inventory.text)
    assert binder_token not in inventory.text


def test_creation_rejects_browser_api_token_and_wrong_workload_audience() -> None:
    workload_service, tokens = _workload_service()
    binder_token = _binder_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )
    policy = code_owned_workflow_event_physical_transport_route_binding_policy()
    payload = {
        "logical_channel_binding_id": "logical-binding.missing",
        "logical_channel_binding_digest": "1" * 64,
        "compatibility_admission_id": "compatibility-admission.missing",
        "compatibility_admission_digest": "2" * 64,
        "transport_profile_snapshot_id": "transport-profile-snapshot.missing",
        "transport_profile_snapshot_digest": "3" * 64,
        "transport_route_snapshot_id": "transport-route-snapshot.missing",
        "transport_route_snapshot_digest": "4" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "idempotency_key": "physical-transport-route-binding-denied-0001",
    }

    with TestClient(app) as client:
        csrf = _login(client)
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
                WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
            ),
        )
        binder = client.post(
            ENDPOINT,
            json=payload,
            headers=_workload_headers(
                binder_token,
                WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
            ),
        )

    for denied in (browser, pat, wrong_workload):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert binder.status_code == 409
    assert binder.json()["code"] == "workflow_physical_transport_route_binding_evidence_conflict"
    assert api_token not in pat.text
