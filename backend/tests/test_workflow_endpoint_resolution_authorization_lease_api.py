from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    PUBLISHER_ID,
    _assert_no_step_up_language,
    _AuditSink,
    _ExplicitTargetAccessSource,
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
    _workload_service,
)
from test_workflow_route_freshness_admission_api import (
    ENDPOINT as FRESHNESS_ENDPOINT,
)
from test_workflow_route_freshness_admission_api import (
    _freshness_admitter_token,
    _seed_binding,
)
from test_workflow_route_freshness_admission_api import (
    _payload as _freshness_payload,
)

from atlas.api.app import create_app
from atlas.modules.identity.application.workload_identities import WorkloadIdentityService
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
)
from atlas.modules.workflows.domain import (
    code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy,
)

RESOLVER_ID = "workload.atlas.workflow-physical-transport-endpoint-resolver-01"
ENDPOINT = "/api/v1/workflows/physical-transport-endpoint-resolution-authorization-leases"


def _resolver_token(service: WorkloadIdentityService) -> str:
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
            identity_id=RESOLVER_ID,
            display_name="Workflow physical transport endpoint resolver",
            service_id="service.workflow-physical-transport-endpoint-resolver",
            instance_id="instance.workflow-physical-transport-endpoint-resolver.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Resolve one route endpoint under a bounded authorization lease.",
            audiences=(WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,),
            secret_reference_ids=("secret.workflow-physical-transport-endpoint-resolver.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the dedicated endpoint resolver API test identity.",
            idempotency_key="physical-transport-endpoint-resolver-identity-0001",
            correlation_id="correlation.physical-transport-endpoint-resolver-identity-0001",
        )
    )
    return issued.token


def _seed_freshness_admission(
    client: TestClient,
    *,
    csrf: str,
    tokens: dict[str, str],
    workload_service: WorkloadIdentityService,
) -> tuple[dict[str, Any], str]:
    binding, binding_digest = _seed_binding(
        client,
        csrf=csrf,
        tokens=tokens,
        workload_service=workload_service,
    )
    created = client.post(
        FRESHNESS_ENDPOINT,
        json=_freshness_payload(binding, binding_digest),
        headers=_workload_headers(
            _freshness_admitter_token(workload_service),
            "audience.workflow-physical-transport-route-freshness-admitter",
        ),
    )
    assert created.status_code == 201
    admission_data = dict(created.json()["data"])
    application = cast(FastAPI, client.app)
    admission = asyncio.run(
        application.state.workflow_event_physical_transport_route_freshness_admission_repository.get_route_freshness_admission_by_id(
            freshness_admission_id=admission_data["freshness_admission_id"]
        )
    )
    assert admission is not None
    return admission_data, admission.canonical_digest


def _payload(admission: dict[str, Any], admission_digest: str) -> dict[str, object]:
    policy = code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy()
    return {
        "freshness_admission_id": admission["freshness_admission_id"],
        "freshness_admission_digest": admission_digest,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "endpoint-resolution-authorization-lease-0001",
    }


def _assert_human_safe(lease: dict[str, Any]) -> None:
    assert set(lease) == {
        "lease_id",
        "freshness_admission_id",
        "selection_generation",
        "policy_id",
        "policy_version",
        "scope",
        "resolver_subject_id",
        "authorized_at",
        "expires_at",
        "state",
        "effective_state",
        "single_use",
        "renewable",
        "authority",
        "integrity_reference",
    }
    assert lease["state"] == "authorized_unconsumed"
    assert lease["effective_state"] == "active"
    assert lease["single_use"] is True
    assert lease["renewable"] is False
    assert lease["resolver_subject_id"] == RESOLVER_ID
    assert lease["selection_generation"] == 1
    assert len(lease["authority"]) == 10
    assert lease["authority"]["endpoint_resolution_authorized"] is True
    assert sum(bool(value) for value in lease["authority"].values()) == 1
    authorized_at = datetime.fromisoformat(lease["authorized_at"])
    expires_at = datetime.fromisoformat(lease["expires_at"])
    assert expires_at - authorized_at == timedelta(seconds=15)
    normalized = str(lease).casefold()
    for forbidden in (
        "digest",
        "fencing_token",
        "endpoint_set",
        "destination_id",
        "routing_contract",
        "private_route_descriptor",
        "hostname",
        "locator",
        "credential_reference",
        "secret_reference",
        "certificate",
        "provider_message",
    ):
        assert forbidden not in normalized


def test_resolver_authorizes_once_and_browser_reads_minimized_lease() -> None:
    workload_service, tokens = _workload_service()
    resolver_token = _resolver_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        empty = client.get(ENDPOINT)
        admission, admission_digest = _seed_freshness_admission(
            client,
            csrf=csrf,
            tokens=tokens,
            workload_service=workload_service,
        )
        payload = _payload(admission, admission_digest)
        headers = _workload_headers(
            resolver_token,
            WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
        )
        created = client.post(ENDPOINT, json=payload, headers=headers)
        replay = client.post(ENDPOINT, json=payload, headers=headers)
        inventory = client.get(ENDPOINT)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"]["endpoint_resolution_authorization_leases"] == []
    assert created.status_code == 201
    assert created.headers["Cache-Control"].startswith("no-store")
    lease = dict(created.json()["data"])
    _assert_human_safe(lease)
    assert replay.status_code == 201
    assert replay.json()["data"] == lease
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert inventory.json()["data"]["endpoint_resolution_authorization_leases"] == [lease]
    assert datetime.fromisoformat(inventory.json()["data"]["server_time"]).tzinfo is not None
    _assert_no_step_up_language(inventory.text)
    assert resolver_token not in inventory.text


def test_creation_rejects_browser_api_token_wrong_audience_and_extra_authority() -> None:
    workload_service, tokens = _workload_service()
    resolver_token = _resolver_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )
    policy = code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy()
    payload: dict[str, object] = {
        "freshness_admission_id": "freshness-admission.missing",
        "freshness_admission_digest": "1" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "endpoint-resolution-authorization-denied-0001",
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
        extra = client.post(
            ENDPOINT,
            json={**payload, "resolver_subject_id": RESOLVER_ID, "ttl_seconds": 15},
            headers=_workload_headers(
                resolver_token,
                WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
            ),
        )

    for denied in (browser, pat, wrong_workload):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert extra.status_code == 422
    assert api_token not in pat.text
