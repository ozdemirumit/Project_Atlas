from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    _assert_no_step_up_language,
    _AuditSink,
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
)

from atlas.api.app import create_app
from atlas.core.config import Settings
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
    WorkflowTransportCredentialAccessAuthorizationLeaseError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_access_authorization_policy,
)

ENDPOINT = "/api/v1/workflows/physical-transport-credential-access-authorization-leases"
SCOPE = WorkflowScope(
    "organization.development",
    "environment.development",
    "site.local",
)
NOW = datetime(2026, 8, 15, 16, 0, tzinfo=UTC)


def _lease(
    *,
    lease_id: str = "credential-access-authorization-lease.api-0001",
    scope: WorkflowScope = SCOPE,
    policy_id: str | None = None,
    policy_version: str | None = None,
) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease:
    policy = code_owned_workflow_event_physical_transport_credential_access_authorization_policy()
    authority = WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority()
    values: dict[str, Any] = {
        "authorization_lease_id": lease_id,
        "freshness_admission_id": "credential-assignment-freshness-admission.api-0001",
        "freshness_admission_digest": "1" * 64,
        "physical_transport_credential_assignment_binding_id": (
            "credential-assignment-binding.api-0001"
        ),
        "physical_transport_credential_assignment_binding_digest": "2" * 64,
        "credential_assignment_snapshot_id": "credential-assignment-snapshot.api-0001",
        "credential_assignment_snapshot_digest": "3" * 64,
        "assignment_id": "credential-assignment.api-0001",
        "assignment_revision": "13",
        "source_assignment_digest": "4" * 64,
        "credential_generation": 23,
        "rotation_epoch": 8,
        "assignment_activated_at": NOW - timedelta(days=1),
        "assignment_expires_at": NOW + timedelta(days=1),
        "assignment_active": True,
        "assignment_non_revoked": True,
        "policy_id": policy_id or policy.policy_id,
        "policy_version": policy_version or policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "scope": scope,
        "accessor_subject_id": WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
        "issued_at": NOW,
        "valid_until": NOW + timedelta(seconds=15),
        "state": (
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "authority": authority,
    }
    payload = {
        "accessor_subject_id": values["accessor_subject_id"],
        "assignment_activated_at": values["assignment_activated_at"].isoformat(),
        "assignment_active": True,
        "assignment_expires_at": values["assignment_expires_at"].isoformat(),
        "assignment_id": values["assignment_id"],
        "assignment_non_revoked": True,
        "assignment_revision": values["assignment_revision"],
        "authority": authority.canonical_value(),
        "authorization_lease_id": values["authorization_lease_id"],
        "credential_assignment_snapshot_digest": values["credential_assignment_snapshot_digest"],
        "credential_assignment_snapshot_id": values["credential_assignment_snapshot_id"],
        "credential_generation": values["credential_generation"],
        "freshness_admission_digest": values["freshness_admission_digest"],
        "freshness_admission_id": values["freshness_admission_id"],
        "issued_at": values["issued_at"].isoformat(),
        "physical_transport_credential_assignment_binding_digest": values[
            "physical_transport_credential_assignment_binding_digest"
        ],
        "physical_transport_credential_assignment_binding_id": values[
            "physical_transport_credential_assignment_binding_id"
        ],
        "policy_digest": values["policy_digest"],
        "policy_id": values["policy_id"],
        "policy_version": values["policy_version"],
        "rotation_epoch": values["rotation_epoch"],
        "scope": scope.canonical_value(),
        "source_assignment_digest": values["source_assignment_digest"],
        "state": "authorized_unconsumed",
        "valid_until": values["valid_until"].isoformat(),
    }
    return WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease(
        **values,
        canonical_digest=canonical_digest(payload),
    )


class _Service:
    durable = False

    def __init__(
        self,
        leases: tuple[WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease, ...] = (),
        *,
        failure: WorkflowTransportCredentialAccessAuthorizationLeaseError | None = None,
        unavailable: bool = False,
        ignore_scope: bool = False,
    ) -> None:
        self.repository = self
        self.leases = list(leases)
        self.failure = failure
        self.unavailable = unavailable
        self.ignore_scope = ignore_scope
        self.authorize_calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        if self.unavailable:
            raise RuntimeError("repository unavailable")
        return NOW + timedelta(seconds=1)

    async def list_leases(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease, ...]:
        if self.unavailable:
            raise RuntimeError("repository unavailable")
        if self.ignore_scope:
            return tuple(self.leases)[:limit]
        return tuple(item for item in self.leases if item.scope == scope)[:limit]

    async def authorize(
        self, **kwargs: Any
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease:
        self.authorize_calls.append(kwargs)
        if self.failure is not None:
            raise self.failure
        lease = _lease()
        if not self.leases:
            self.leases.append(lease)
        return self.leases[0]


def _workload_service_and_token(
    *,
    identity_id: str = WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
    audience: str = WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
) -> tuple[WorkloadIdentityService, str]:
    service = WorkloadIdentityService(
        repository=InMemoryWorkloadIdentityRepository(),
        audit_sink=_AuditSink(),
        environment_id="environment.development",
        signing_keys={7: b"credential-access-authorization-api-test-key" * 2},
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
            identity_id=identity_id,
            display_name="Workflow physical transport credential accessor",
            service_id="service.workflow-physical-transport-credential-accessor",
            instance_id="instance.workflow-physical-transport-credential-accessor.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Request one bounded credential-access authorization lease.",
            audiences=(audience,),
            secret_reference_ids=(
                "secret.workflow-physical-transport-credential-accessor.local-01",
            ),
            lifetime=timedelta(minutes=10),
            reason="Create the exact IMP-206 API test workload.",
            idempotency_key=f"credential-accessor-{canonical_digest(identity_id)[:24]}",
            correlation_id="correlation.credential-access-authorization-api-identity",
        )
    )
    return service, issued.token


def _payload() -> dict[str, str]:
    policy = code_owned_workflow_event_physical_transport_credential_access_authorization_policy()
    return {
        "freshness_admission_id": "credential-assignment-freshness-admission.api-0001",
        "freshness_admission_digest": "1" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "credential-access-authorization-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def _assert_minimized(item: dict[str, Any]) -> None:
    assert set(item) == {
        "lease_id",
        "freshness_admission_id",
        "assignment_revision",
        "credential_generation",
        "rotation_epoch",
        "policy_id",
        "policy_version",
        "scope",
        "accessor_subject_id",
        "issued_at",
        "valid_until",
        "state",
        "effective_state",
        "single_use",
        "renewable",
        "authority",
        "integrity_reference",
    }
    assert item["state"] == "authorized_unconsumed"
    assert item["effective_state"] == "active"
    assert item["single_use"] is True
    assert item["renewable"] is False
    assert item["accessor_subject_id"] == WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT
    assert len(item["authority"]) == 17
    assert item["authority"]["credential_access_authorized"] is True
    assert sum(value is True for value in item["authority"].values()) == 1
    assert datetime.fromisoformat(item["valid_until"]) - datetime.fromisoformat(
        item["issued_at"]
    ) == timedelta(seconds=15)
    forbidden_top_level = {
        "assignment_id",
        "freshness_admission_digest",
        "policy_digest",
        "canonical_digest",
        "idempotency_key",
        "request_fingerprint",
        "target_scope_commitment",
        "credential_profile",
        "credential_reference",
        "secret_reference",
        "broker_policy",
        "endpoint",
        "protected_artifact",
    }
    assert not forbidden_top_level.intersection(item)


def test_exact_workload_post_and_normal_password_session_get_minimized_inventory() -> None:
    workload_service, token = _workload_service_and_token()
    service = _Service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_credential_access_authorization_lease_service=cast(
            Any, service
        ),
    )

    with TestClient(app) as client:
        unauthenticated = client.get(ENDPOINT)
        csrf = _login(client)
        empty = client.get(ENDPOINT)
        browser_post = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
            ),
        )
        inventory = client.get(ENDPOINT)

    assert unauthenticated.status_code == 403
    assert empty.status_code == 200
    assert empty.json()["data"]["physical_transport_credential_access_authorization_leases"] == []
    assert browser_post.status_code == 401
    assert browser_post.json()["code"] == "workload_authentication_failed"
    assert created.status_code == 201
    item = dict(created.json()["data"])
    _assert_minimized(item)
    assert inventory.status_code == 200
    assert inventory.json()["data"][
        "physical_transport_credential_access_authorization_leases"
    ] == [item]
    assert inventory.json()["data"]["durable"] is False
    assert datetime.fromisoformat(inventory.json()["data"]["server_time"]).tzinfo is not None
    for response in (unauthenticated, empty, browser_post, created, inventory):
        _assert_no_store(response)
    _assert_no_step_up_language(inventory.text + browser_post.text)
    assert "authorized browser session" not in inventory.text.casefold()
    context = service.authorize_calls[0]["context"]
    assert context.subject_id == WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT
    assert context.credential_audience == WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE


def test_post_rejects_pat_wrong_audience_wrong_subject_and_extra_fields() -> None:
    workload_service, exact_token = _workload_service_and_token()
    wrong_service, wrong_subject_token = _workload_service_and_token(
        identity_id="service.workflow-physical-transport-credential-accessor-other"
    )
    service = _Service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_credential_access_authorization_lease_service=cast(
            Any, service
        ),
    )
    wrong_subject_app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=wrong_service,
        workflow_event_physical_transport_credential_access_authorization_lease_service=cast(
            Any, service
        ),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        pat = client.post(
            ENDPOINT,
            json=_payload(),
            headers={"Authorization": f"Bearer {personal_token}"},
        )
        wrong_audience = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(exact_token, "audience.workflow-worker"),
        )
        extra = client.post(
            ENDPOINT,
            json={**_payload(), "accessor_subject_id": "service.attacker", "ttl_seconds": 60},
            headers=_workload_headers(
                exact_token,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
            ),
        )
    with TestClient(wrong_subject_app) as client:
        wrong_subject = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                wrong_subject_token,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
            ),
        )

    for denied in (pat, wrong_audience, wrong_subject):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_store(denied)
        _assert_no_step_up_language(denied.text)
    assert extra.status_code == 422
    assert extra.json()["code"] == "validation_failed"
    _assert_no_store(extra)
    assert personal_token not in pat.text
    assert service.authorize_calls == []


def test_historical_policy_read_default_deny_scope_escape_and_errors_are_non_oracle() -> None:
    historical = _lease(
        policy_id="policy.workflow-event-physical-transport-credential-access-authorization-legacy",
        policy_version="0.9",
    )
    service = _Service((historical,))
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workflow_event_physical_transport_credential_access_authorization_lease_service=cast(
            Any, service
        ),
    )
    denied_app = create_app(
        Settings(
            environment="development",
            development_identity_enabled=True,
            development_role_ids=("role.unassigned",),
        ),
        audit_sink=_AuditSink(),
        workflow_event_physical_transport_credential_access_authorization_lease_service=cast(
            Any, service
        ),
    )
    escaped = _lease(
        lease_id="credential-access-authorization-lease.wrong-scope",
        scope=WorkflowScope("organization.other", "environment.development", "site.local"),
    )
    escaped_app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workflow_event_physical_transport_credential_access_authorization_lease_service=cast(
            Any, _Service((escaped,), ignore_scope=True)
        ),
    )

    with TestClient(app) as client:
        _login(client)
        inventory = client.get(ENDPOINT)
    with TestClient(denied_app) as client:
        _login(client)
        denied = client.get(ENDPOINT)
    with TestClient(escaped_app) as client:
        _login(client)
        scope_escape = client.get(ENDPOINT)

    assert inventory.status_code == 200
    item = inventory.json()["data"]["physical_transport_credential_access_authorization_leases"][0]
    assert item["policy_id"] == historical.policy_id
    assert item["policy_version"] == historical.policy_version
    assert denied.status_code == 403
    assert denied.json()["code"] == "authorization_denied"
    assert scope_escape.status_code == 503
    assert scope_escape.json()["code"].endswith("_service_unavailable")
    assert "scope" not in scope_escape.json()["detail"].casefold()
    for response in (inventory, denied, scope_escape):
        _assert_no_store(response)
        _assert_no_step_up_language(response.text)


def test_service_conflict_is_normalized_without_internal_evidence() -> None:
    workload_service, token = _workload_service_and_token()
    service = _Service(
        failure=WorkflowTransportCredentialAccessAuthorizationLeaseError(
            "workflow_physical_transport_credential_access_authorization_evidence_conflict",
            "Assignment secret locator and internal evidence must never be rendered.",
        )
    )
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_credential_access_authorization_lease_service=cast(
            Any, service
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
            ),
        )

    assert response.status_code == 409
    assert response.json()["code"] == (
        "workflow_physical_transport_credential_access_authorization_unavailable"
    )
    assert "secret" not in response.text.casefold()
    assert "evidence_conflict" not in response.text
    _assert_no_store(response)
