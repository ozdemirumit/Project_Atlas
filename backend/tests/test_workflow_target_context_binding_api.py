from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

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
from test_workflow_target_context_binding_service import (
    CREDENTIAL_DIGEST,
    CREDENTIAL_ID,
    ENDPOINT_DIGEST,
    ENDPOINT_ID,
    service_fixture,
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
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
    WorkflowEventPhysicalTransportTargetContextBindingError,
)

ENDPOINT = "/api/v1/workflows/physical-transport-target-context-bindings"


def _target_context_binder_workload() -> tuple[WorkloadIdentityService, str]:
    service = WorkloadIdentityService(
        repository=InMemoryWorkloadIdentityRepository(),
        audit_sink=_AuditSink(),
        environment_id="environment.development",
        signing_keys={11: b"target-context-binding-api-test-key" * 2},
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
    issued = asyncio.run(
        service.create(
            actor=actor,
            identity_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
            display_name="Workflow physical transport target-context binder",
            service_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
            instance_id="instance.workflow-physical-transport-target-context-binder.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Bind immutable endpoint and credential lineage without artifact access.",
            audiences=(WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,),
            secret_reference_ids=("secret.workflow-target-context-binder.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the exact IMP-208 API test workload.",
            idempotency_key="target-context-binder-api-identity-0001",
            correlation_id="correlation.target-context-binder-api-identity",
        )
    )
    return service, issued.token


def _payload() -> dict[str, object]:
    return {
        "endpoint_materialization_id": ENDPOINT_ID,
        "endpoint_materialization_digest": ENDPOINT_DIGEST,
        "credential_materialization_id": CREDENTIAL_ID,
        "credential_materialization_digest": CREDENTIAL_DIGEST,
        "policy_id": "policy.workflow-event-physical-transport-target-context-binding",
        "policy_version": "1.0",
        "idempotency_key": "target-context-binding-api-0001",
    }


def _assert_human_safe(binding: dict[str, object]) -> None:
    assert set(binding) == {
        "binding_id",
        "endpoint_materialization_id",
        "credential_materialization_id",
        "state",
        "effective_state",
        "scope",
        "binder_subject_id",
        "bound_at",
        "joint_usable_until",
        "policy_reference",
        "target_context_schema_reference",
        "authority",
    }
    assert binding["state"] == "bound"
    assert binding["effective_state"] == "active"
    authority = binding["authority"]
    assert isinstance(authority, dict)
    assert len(authority) == 17
    assert all(value is False for value in authority.values())
    normalized = str(binding).casefold()
    for forbidden in (
        "artifact_id",
        "artifact_digest",
        "canonical_digest",
        "materialization_digest",
        "target_context_commitment",
        "policy_digest",
        "endpoint_set",
        "destination_id",
        "credential_assignment_snapshot",
        "secret",
        "password",
        "provider_payload",
        "broker_policy",
    ):
        assert forbidden not in normalized


def test_exact_binder_creates_once_and_password_session_reads_safe_inventory() -> None:
    service, repository, audit_sink = service_fixture()
    workload_service, token = _target_context_binder_workload()
    app = create_app(
        _settings(),
        audit_sink=audit_sink,
        workload_identity_service=workload_service,
        workflow_event_physical_transport_target_context_binding_service=service,
    )
    headers = _workload_headers(
        token,
        WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
    )

    with TestClient(app) as client:
        unauthenticated = client.get(ENDPOINT)
        _login(client)
        empty = client.get(ENDPOINT)
        created = client.post(ENDPOINT, json=_payload(), headers=headers)
        replay = client.post(ENDPOINT, json=_payload(), headers=headers)
        inventory = client.get(ENDPOINT)

    assert unauthenticated.status_code == 403
    assert empty.status_code == 200
    assert empty.json()["data"]["physical_transport_target_context_bindings"] == []
    assert created.status_code == 201
    outcome = dict(created.json()["data"])
    _assert_human_safe(outcome)
    assert replay.status_code == 201
    assert replay.json()["data"] == outcome
    assert len(repository.bindings) == 1
    assert inventory.status_code == 200
    assert inventory.json()["data"]["physical_transport_target_context_bindings"] == [outcome]
    assert inventory.json()["data"]["durable"] is True
    for result in (unauthenticated, empty, created, replay, inventory):
        assert result.headers["Cache-Control"] == "no-store, max-age=0"
        assert result.headers["Referrer-Policy"] == "no-referrer"
        _assert_no_step_up_language(result.text)
    assert token not in inventory.text


def test_post_rejects_browser_pat_wrong_workload_and_extra_fields() -> None:
    service, _, audit_sink = service_fixture()
    workload_service, exact_token = _target_context_binder_workload()
    wrong_workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=audit_sink,
        workload_identity_service=workload_service,
        workflow_event_physical_transport_target_context_binding_service=service,
    )
    wrong_app = create_app(
        _settings(),
        audit_sink=audit_sink,
        workload_identity_service=wrong_workload_service,
        workflow_event_physical_transport_target_context_binding_service=service,
    )

    with TestClient(app) as client:
        csrf = _login(client)
        browser = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
        api_token = _issue_api_token(client, csrf)
        pat = client.post(
            ENDPOINT,
            json=_payload(),
            headers={"Authorization": f"Bearer {api_token}"},
        )
        extra = client.post(
            ENDPOINT,
            json={**_payload(), "secret_reference": "private-reference-value"},
            headers=_workload_headers(
                exact_token,
                WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
            ),
        )
    with TestClient(wrong_app) as client:
        wrong = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(tokens[PUBLISHER_ID], "audience.workflow-outbox-publisher"),
        )

    for denied in (browser, pat, wrong):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert extra.status_code == 422
    assert "private-reference-value" not in extra.text.casefold()
    assert api_token not in pat.text


def test_internal_evidence_failures_share_one_non_oracle_conflict() -> None:
    service, _, audit_sink = service_fixture()
    workload_service, token = _target_context_binder_workload()
    bind = AsyncMock(
        side_effect=[
            WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_endpoint_materialization_not_found",
                "not found",
            ),
            WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_lineage_mismatch",
                "lineage mismatch",
            ),
            WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_already_bound",
                "already bound",
            ),
        ]
    )
    app = create_app(
        _settings(),
        audit_sink=audit_sink,
        workload_identity_service=workload_service,
        workflow_event_physical_transport_target_context_binding_service=service,
    )
    headers = _workload_headers(
        token,
        WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
    )

    with patch.object(service, "bind", bind), TestClient(app) as client:
        responses = [client.post(ENDPOINT, json=_payload(), headers=headers) for _ in range(3)]

    for response in responses:
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "workflow_physical_transport_target_context_binding_unavailable"
        assert body["retryable"] is False
        assert "not_found" not in response.text
        assert "lineage" not in response.text.casefold()
        assert "already_bound" not in response.text
        assert response.headers["Cache-Control"] == "no-store, max-age=0"
        _assert_no_step_up_language(response.text)
