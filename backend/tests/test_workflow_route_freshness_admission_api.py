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
from test_workflow_physical_transport_route_binding_api import (
    ENDPOINT as BINDING_ENDPOINT,
)
from test_workflow_physical_transport_route_binding_api import (
    _binder_token,
    _seed_binding_evidence,
)
from test_workflow_physical_transport_route_binding_api import (
    _payload as _binding_payload,
)
from test_workflow_transport_compatibility_admission_api import _admitter_token
from test_workflow_transport_profile_snapshot_api import _registry_token as _profile_registry_token
from test_workflow_transport_route_snapshot_api import _registry_token as _route_registry_token

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
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
)
from atlas.modules.workflows.domain import (
    code_owned_workflow_event_physical_transport_route_freshness_policy,
)

ADMITTER_ID = "workload.atlas.workflow-physical-route-freshness-admitter-01"
ENDPOINT = "/api/v1/workflows/physical-transport-route-freshness-admissions"


def _freshness_admitter_token(service: WorkloadIdentityService) -> str:
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
            identity_id=ADMITTER_ID,
            display_name="Workflow physical route freshness admitter",
            service_id="service.workflow-physical-route-freshness-admitter",
            instance_id="instance.workflow-physical-route-freshness-admitter.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Admit bounded route freshness without endpoint resolution authority.",
            audiences=(WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,),
            secret_reference_ids=("secret.workflow-physical-route-freshness-admitter.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the dedicated route freshness API test identity.",
            idempotency_key="physical-route-freshness-admitter-identity-0001",
            correlation_id="correlation.physical-route-freshness-admitter-identity-0001",
        )
    )
    return issued.token


def _seed_binding(
    client: TestClient,
    *,
    csrf: str,
    tokens: dict[str, str],
    workload_service: WorkloadIdentityService,
) -> tuple[dict[str, Any], str]:
    logical, compatibility, profile, route = _seed_binding_evidence(
        client,
        csrf=csrf,
        worker_token=tokens[WORKER_ID],
        publisher_token=tokens[PUBLISHER_ID],
        profile_registry_token=_profile_registry_token(workload_service),
        route_registry_token=_route_registry_token(workload_service),
        admitter_token=_admitter_token(workload_service),
    )
    binder_token = _binder_token(workload_service)
    binding = client.post(
        BINDING_ENDPOINT,
        json=_binding_payload(logical, compatibility, profile, route),
        headers=_workload_headers(
            binder_token,
            WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
        ),
    )
    assert binding.status_code == 201
    domain_binding = asyncio.run(
        client.app.state.workflow_event_physical_transport_route_binding_repository.get_physical_transport_route_binding(
            logical_channel_binding_id=logical["logical_channel_binding_id"]
        )
    )
    assert domain_binding is not None
    return dict(binding.json()["data"]), domain_binding.canonical_digest


def _payload(binding: dict[str, Any], binding_digest: str) -> dict[str, object]:
    policy = code_owned_workflow_event_physical_transport_route_freshness_policy()
    return {
        "physical_transport_route_binding_id": binding["binding_id"],
        "physical_transport_route_binding_digest": binding_digest,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "physical-route-freshness-admission-0001",
    }


def _assert_human_safe(admission: dict[str, Any]) -> None:
    assert set(admission) == {
        "freshness_admission_id",
        "physical_transport_route_binding_id",
        "transport_route_snapshot_id",
        "selection_head_id",
        "selection_generation",
        "policy_id",
        "policy_version",
        "scope",
        "admitter_subject_id",
        "evaluated_at",
        "valid_until",
        "state",
        "authority",
        "integrity_reference",
    }
    assert admission["state"] == "admitted_current"
    assert admission["selection_generation"] == 1
    assert admission["admitter_subject_id"] == ADMITTER_ID
    assert len(admission["authority"]) == 10
    assert not any(admission["authority"].values())
    evaluated_at = datetime.fromisoformat(admission["evaluated_at"])
    valid_until = datetime.fromisoformat(admission["valid_until"])
    assert valid_until - evaluated_at == timedelta(seconds=60)
    normalized = str(admission).casefold()
    for forbidden in (
        "digest",
        "fencing_token",
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


def test_freshness_admitter_creates_and_one_browser_login_reads_minimized_evidence() -> None:
    workload_service, tokens = _workload_service()
    freshness_token = _freshness_admitter_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        binding, binding_digest = _seed_binding(
            client,
            csrf=csrf,
            tokens=tokens,
            workload_service=workload_service,
        )
        payload = _payload(binding, binding_digest)
        empty = client.get(ENDPOINT)
        headers = _workload_headers(
            freshness_token,
            WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
        )
        created = client.post(ENDPOINT, json=payload, headers=headers)
        replay = client.post(ENDPOINT, json=payload, headers=headers)
        inventory = client.get(ENDPOINT)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"] == {
        "physical_transport_route_freshness_admissions": [],
        "durable": False,
    }
    assert created.status_code == 201
    assert created.headers["Cache-Control"].startswith("no-store")
    admission = dict(created.json()["data"])
    _assert_human_safe(admission)
    assert replay.status_code == 201
    assert replay.json()["data"] == admission
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert inventory.json()["data"]["physical_transport_route_freshness_admissions"] == [admission]
    _assert_no_step_up_language(inventory.text)
    assert freshness_token not in inventory.text


def test_creation_rejects_browser_api_token_and_wrong_workload_audience() -> None:
    workload_service, tokens = _workload_service()
    freshness_token = _freshness_admitter_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )
    policy = code_owned_workflow_event_physical_transport_route_freshness_policy()
    payload = {
        "physical_transport_route_binding_id": "physical-route-binding.missing",
        "physical_transport_route_binding_digest": "1" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "physical-route-freshness-admission-denied-0001",
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
        admitter = client.post(
            ENDPOINT,
            json=payload,
            headers=_workload_headers(
                freshness_token,
                WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
            ),
        )

    for denied in (browser, pat, wrong_workload):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert admitter.status_code == 409
    assert admitter.json()["code"].endswith("_evidence_conflict")
    assert api_token not in pat.text
