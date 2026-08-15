from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from test_workflow_credential_materializations import fixture
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
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
)
from atlas.modules.workflows.domain import (
    code_owned_workflow_event_physical_transport_credential_materialization_policy,
)

ENDPOINT = "/api/v1/workflows/physical-transport-credential-materializations"


def _credential_accessor_workload() -> tuple[WorkloadIdentityService, str]:
    service = WorkloadIdentityService(
        repository=InMemoryWorkloadIdentityRepository(),
        audit_sink=_AuditSink(),
        environment_id="environment.development",
        signing_keys={7: b"credential-materialization-api-test-key" * 2},
    )
    actor = AuthenticatedSubject(
        subject_id="subject.enterprise.security-admin",
        display_name="Security Administrator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=datetime.now(UTC),
        organization_id="organization.atlas",
        role_ids=("role.security-administrator",),
    )
    issued = asyncio.run(
        service.create(
            actor=actor,
            identity_id=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
            display_name="Workflow physical transport credential accessor",
            service_id="service.workflow-physical-transport-credential-accessor",
            instance_id="instance.workflow-physical-transport-credential-accessor.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Materialize one protected credential from one authorization lease.",
            audiences=(WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,),
            secret_reference_ids=("secret.workflow-credential-accessor.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the exact IMP-207 API test workload.",
            idempotency_key="credential-materialization-accessor-api-0001",
            correlation_id="correlation.credential-materialization-api-identity",
        )
    )
    return service, issued.token


def _payload(lease: Any) -> dict[str, object]:
    policy = code_owned_workflow_event_physical_transport_credential_materialization_policy()
    return {
        "authorization_lease_id": lease.authorization_lease_id,
        "authorization_lease_digest": lease.canonical_digest,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "credential-materialization-api-0001",
    }


def _assert_human_safe(data: dict[str, object]) -> None:
    assert set(data) == {
        "materialization_id",
        "lease_id",
        "freshness_admission_id",
        "assignment_revision",
        "credential_generation",
        "rotation_epoch",
        "policy_id",
        "policy_version",
        "scope",
        "accessor_subject_id",
        "consumed_at",
        "recorded_at",
        "outcome",
        "lease_consumed",
        "protected_storage_verified",
        "raw_credential_disclosed",
        "authority",
        "integrity_reference",
    }
    assert data["outcome"] == "materialized_protected"
    assert data["lease_consumed"] is True
    assert data["protected_storage_verified"] is True
    assert data["raw_credential_disclosed"] is False
    authority = data["authority"]
    assert isinstance(authority, dict)
    assert len(authority) == 17
    assert all(value is False for value in authority.values())
    normalized = str(data).casefold()
    for forbidden in (
        "artifact_id",
        "artifact_digest",
        "canonical_digest",
        "authorization_lease_digest",
        "policy_digest",
        "secret",
        "password",
        "vault",
        "locator",
        "provider_payload",
        "broker_policy",
        "target_scope_commitment",
    ):
        assert forbidden not in normalized


def test_exact_accessor_materializes_once_and_password_session_reads_minimized_result() -> None:
    service, _, materializer, audit_sink, lease = asyncio.run(fixture())
    workload_service, token = _credential_accessor_workload()
    app = create_app(
        _settings().model_copy(update={"development_organization_id": "organization.atlas"}),
        audit_sink=audit_sink,
        workload_identity_service=workload_service,
        workflow_event_physical_transport_credential_materialization_service=service,
    )
    payload = _payload(lease)
    headers = _workload_headers(
        token,
        WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
    )

    with TestClient(app) as client:
        unauthenticated = client.get(ENDPOINT)
        _login(client)
        empty = client.get(ENDPOINT)
        created = client.post(ENDPOINT, json=payload, headers=headers)
        replay = client.post(ENDPOINT, json=payload, headers=headers)
        inventory = client.get(ENDPOINT)

    assert unauthenticated.status_code == 403
    assert empty.status_code == 200
    assert empty.json()["data"]["physical_transport_credential_materializations"] == []
    assert created.status_code == 201
    outcome = dict(created.json()["data"])
    _assert_human_safe(outcome)
    assert replay.status_code == 201
    assert replay.json()["data"] == outcome
    assert len(materializer.calls) == 1
    assert inventory.status_code == 200
    assert inventory.json()["data"]["physical_transport_credential_materializations"] == [outcome]
    assert inventory.json()["data"]["durable"] is True
    for response in (unauthenticated, empty, created, replay, inventory):
        assert response.headers["Cache-Control"] == "no-store, max-age=0"
        assert response.headers["Referrer-Policy"] == "no-referrer"
    _assert_no_step_up_language(inventory.text)
    assert "authorized browser session" not in inventory.text.casefold()
    assert token not in inventory.text


def test_post_rejects_browser_pat_wrong_workload_and_extra_fields() -> None:
    service, _, _, audit_sink, lease = asyncio.run(fixture())
    workload_service, exact_token = _credential_accessor_workload()
    wrong_workload_service, tokens = _workload_service()
    app = create_app(
        _settings().model_copy(update={"development_organization_id": "organization.atlas"}),
        audit_sink=audit_sink,
        workload_identity_service=workload_service,
        workflow_event_physical_transport_credential_materialization_service=service,
    )
    wrong_app = create_app(
        _settings(),
        audit_sink=audit_sink,
        workload_identity_service=wrong_workload_service,
        workflow_event_physical_transport_credential_materialization_service=service,
    )
    payload = _payload(lease)

    with TestClient(app) as client:
        csrf = _login(client)
        browser = client.post(ENDPOINT, json=payload, headers={"X-CSRF-Token": csrf})
        api_token = _issue_api_token(client, csrf)
        pat = client.post(
            ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {api_token}"},
        )
        extra = client.post(
            ENDPOINT,
            json={**payload, "secret_reference": "private-reference-value"},
            headers=_workload_headers(
                exact_token,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
            ),
        )
    with TestClient(wrong_app) as client:
        wrong = client.post(
            ENDPOINT,
            json=payload,
            headers=_workload_headers(
                tokens[PUBLISHER_ID],
                WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
            ),
        )

    for denied in (browser, pat, wrong):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert extra.status_code == 422
    assert "private-reference-value" not in extra.text.casefold()
    assert api_token not in pat.text
