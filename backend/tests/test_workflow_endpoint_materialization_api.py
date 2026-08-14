from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_workflow_endpoint_resolution_authorization_lease_api import (
    ENDPOINT as LEASE_ENDPOINT,
)
from test_workflow_endpoint_resolution_authorization_lease_api import (
    RESOLVER_ID,
    _resolver_token,
    _seed_freshness_admission,
)
from test_workflow_endpoint_resolution_authorization_lease_api import (
    _payload as _lease_payload,
)
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

from atlas.api.app import create_app
from atlas.modules.identity.application.workload_identities import WorkloadIdentityService
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
    WorkflowPlanningService,
)
from atlas.modules.workflows.domain import (
    code_owned_workflow_event_physical_transport_endpoint_materialization_policy,
    code_owned_workflow_registry,
)

ENDPOINT = "/api/v1/workflows/physical-transport-endpoint-materializations"


class DurableDevelopmentWorkflowRepository(InMemoryWorkflowPlanRepository):
    @property
    def durable(self) -> bool:
        return True


def _app(
    *,
    workload_service: WorkloadIdentityService,
    audit_sink: _AuditSink,
) -> FastAPI:
    repository = DurableDevelopmentWorkflowRepository()
    planning_service = WorkflowPlanningService(
        registry=code_owned_workflow_registry(),
        repository=repository,
        audit_sink=audit_sink,
    )
    return create_app(
        _settings(),
        audit_sink=audit_sink,
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
        workflow_planning_service=planning_service,
    )


def _payload(lease: dict[str, object]) -> dict[str, object]:
    policy = code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
    return {
        "authorization_lease_id": lease["lease_id"],
        "authorization_lease_digest": lease["canonical_digest"],
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "endpoint-materialization-api-0001",
    }


def _assert_human_safe(data: dict[str, object]) -> None:
    assert set(data) == {
        "materialization_id",
        "lease_id",
        "freshness_admission_id",
        "selection_generation",
        "policy_id",
        "policy_version",
        "scope",
        "resolver_subject_id",
        "consumed_at",
        "recorded_at",
        "outcome",
        "lease_consumed",
        "protected_storage_verified",
        "raw_endpoint_disclosed",
        "authority",
        "integrity_reference",
    }
    assert data["resolver_subject_id"] == RESOLVER_ID
    assert data["outcome"] == "materialized_protected"
    assert data["lease_consumed"] is True
    assert data["protected_storage_verified"] is True
    assert data["raw_endpoint_disclosed"] is False
    authority = data["authority"]
    assert isinstance(authority, dict)
    assert len(authority) == 10
    assert not any(authority.values())
    normalized = str(data).casefold()
    for forbidden in (
        "artifact_id",
        "artifact_digest",
        "endpoint_count",
        "endpoint_set",
        "hostname",
        "url",
        "ip_address",
        "secret",
        "certificate",
        "fencing_token",
        "canonical_digest",
    ):
        assert forbidden not in normalized
    assert "port" not in data
    assert "credential" not in data


def test_resolver_consumes_once_and_browser_reads_minimized_outcome() -> None:
    workload_service, tokens = _workload_service()
    resolver_token = _resolver_token(workload_service)
    audit_sink = _AuditSink()
    app = _app(workload_service=workload_service, audit_sink=audit_sink)

    with TestClient(app) as client:
        csrf = _login(client)
        empty = client.get(ENDPOINT)
        admission, admission_digest = _seed_freshness_admission(
            client,
            csrf=csrf,
            tokens=tokens,
            workload_service=workload_service,
        )
        lease_response = client.post(
            LEASE_ENDPOINT,
            json=_lease_payload(admission, admission_digest),
            headers=_workload_headers(
                resolver_token,
                WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
            ),
        )
        assert lease_response.status_code == 201
        application = client.app
        assert isinstance(application, FastAPI)
        authorization_repository = (
            application.state.workflow_endpoint_resolution_authorization_lease_repository
        )
        stored_lease = asyncio.run(
            authorization_repository.get_endpoint_resolution_authorization_lease(
                freshness_admission_id=admission["freshness_admission_id"]
            )
        )
        assert stored_lease is not None
        lease = {
            **lease_response.json()["data"],
            "canonical_digest": stored_lease.canonical_digest,
        }
        payload = _payload(lease)
        headers = _workload_headers(
            resolver_token,
            WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
        )
        created = client.post(ENDPOINT, json=payload, headers=headers)
        replay = client.post(ENDPOINT, json=payload, headers=headers)
        inventory = client.get(ENDPOINT)
        leases = client.get(LEASE_ENDPOINT)

    assert empty.status_code == 200
    assert empty.json()["data"]["physical_transport_endpoint_materializations"] == []
    assert created.status_code == 201
    assert created.headers["Cache-Control"].startswith("no-store")
    outcome = dict(created.json()["data"])
    _assert_human_safe(outcome)
    assert replay.status_code == 201
    assert replay.json()["data"] == outcome
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert inventory.json()["data"]["physical_transport_endpoint_materializations"] == [outcome]
    assert inventory.json()["data"]["durable"] is True
    assert leases.status_code == 200
    assert (
        leases.json()["data"]["endpoint_resolution_authorization_leases"][0]["effective_state"]
        == "consumed"
    )
    _assert_no_step_up_language(inventory.text)
    assert resolver_token not in inventory.text


def test_creation_rejects_human_pat_wrong_workload_and_extra_authority() -> None:
    workload_service, tokens = _workload_service()
    resolver_token = _resolver_token(workload_service)
    audit_sink = _AuditSink()
    app = _app(workload_service=workload_service, audit_sink=audit_sink)
    policy = code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
    payload: dict[str, object] = {
        "authorization_lease_id": "workflow-endpoint-resolution-lease.missing",
        "authorization_lease_digest": "1" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "endpoint-materialization-api-denied-0001",
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
            json={**payload, "endpoint": "https://forbidden.invalid", "ttl_seconds": 15},
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
