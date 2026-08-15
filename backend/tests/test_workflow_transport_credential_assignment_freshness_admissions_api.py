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
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionError,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy,
)

ENDPOINT = "/api/v1/workflows/physical-transport-credential-assignment-freshness-admissions"
SCOPE = WorkflowScope(
    "organization.development",
    "environment.development",
    "site.local",
)
NOW = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)


def _admission(
    *,
    admission_id: str = "credential-assignment-freshness-admission.api-0001",
    policy_id: str | None = None,
    policy_version: str | None = None,
) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission:
    policy = code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy()
    authority = WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority()
    values: dict[str, Any] = {
        "freshness_admission_id": admission_id,
        "physical_transport_credential_assignment_binding_id": (
            "credential-assignment-binding.api-0001"
        ),
        "physical_transport_credential_assignment_binding_digest": "1" * 64,
        "credential_assignment_snapshot_id": "credential-assignment-snapshot.api-0001",
        "credential_assignment_snapshot_digest": "2" * 64,
        "assignment_id": "credential-assignment.api-0001",
        "assignment_revision": "13",
        "source_assignment_digest": "3" * 64,
        "credential_generation": 23,
        "rotation_epoch": 8,
        "assignment_activated_at": NOW - timedelta(days=1),
        "assignment_expires_at": NOW + timedelta(days=1),
        "assignment_active": True,
        "assignment_non_revoked": True,
        "policy_id": policy_id or policy.policy_id,
        "policy_version": policy_version or policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "scope": SCOPE,
        "admitter_subject_id": (
            WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT
        ),
        "evaluated_at": NOW,
        "valid_until": NOW + timedelta(seconds=60),
        "state": (
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState.ADMITTED_CURRENT
        ),
        "authority": authority,
    }
    payload = {
        "admitter_subject_id": values["admitter_subject_id"],
        "assignment_activated_at": values["assignment_activated_at"].isoformat(),
        "assignment_active": True,
        "assignment_expires_at": values["assignment_expires_at"].isoformat(),
        "assignment_id": values["assignment_id"],
        "assignment_non_revoked": True,
        "assignment_revision": values["assignment_revision"],
        "authority": authority.canonical_value(),
        "credential_assignment_snapshot_digest": values["credential_assignment_snapshot_digest"],
        "credential_assignment_snapshot_id": values["credential_assignment_snapshot_id"],
        "credential_generation": values["credential_generation"],
        "evaluated_at": values["evaluated_at"].isoformat(),
        "freshness_admission_id": values["freshness_admission_id"],
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
        "scope": SCOPE.canonical_value(),
        "source_assignment_digest": values["source_assignment_digest"],
        "state": "admitted_current",
        "valid_until": values["valid_until"].isoformat(),
    }
    return WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission(
        **values,
        canonical_digest=canonical_digest(payload),
    )


class _Service:
    durable = False

    def __init__(
        self,
        admissions: tuple[
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission, ...
        ] = (),
        *,
        failure: WorkflowTransportCredentialAssignmentFreshnessAdmissionError | None = None,
        unavailable: bool = False,
    ) -> None:
        self.repository = self
        self.admissions = list(admissions)
        self.failure = failure
        self.unavailable = unavailable
        self.admit_calls: list[dict[str, Any]] = []

    async def list_admissions(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission, ...]:
        if self.unavailable:
            raise RuntimeError("repository unavailable")
        return tuple(item for item in self.admissions if item.scope == scope)[:limit]

    async def admit(self, **kwargs: Any) -> Any:
        self.admit_calls.append(kwargs)
        if self.failure is not None:
            raise self.failure
        if kwargs["context"].subject_id != (
            WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT
        ):
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_physical_transport_credential_assignment_freshness_admitter_identity_required",
                "The exact workload identity is required.",
            )
        admission = _admission()
        if not self.admissions:
            self.admissions.append(admission)
        return self.admissions[0]


def _workload_service_and_token(
    *,
    identity_id: str = (
        WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT
    ),
    audience: str = (WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE),
) -> tuple[WorkloadIdentityService, str]:
    service = WorkloadIdentityService(
        repository=InMemoryWorkloadIdentityRepository(),
        audit_sink=_AuditSink(),
        environment_id="environment.development",
        signing_keys={7: b"credential-assignment-freshness-api-test-key" * 2},
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
            display_name="Credential-assignment freshness admitter",
            service_id=(
                "service.workflow-physical-transport-credential-assignment-freshness-admitter"
            ),
            instance_id="instance.credential-assignment-freshness.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Admit bounded assignment freshness without credential access authority.",
            audiences=(audience,),
            secret_reference_ids=("secret.credential-assignment-freshness.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the exact IMP-205 API test workload.",
            idempotency_key=f"identity-{identity_id[-40:]}",
            correlation_id="correlation.credential-assignment-freshness-api-identity",
        )
    )
    return service, issued.token


def _payload() -> dict[str, str]:
    policy = code_owned_workflow_event_physical_transport_credential_assignment_freshness_policy()
    return {
        "physical_transport_credential_assignment_binding_id": (
            "credential-assignment-binding.api-0001"
        ),
        "physical_transport_credential_assignment_binding_digest": "1" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "credential-assignment-freshness-api-0001",
    }


def _assert_minimized(item: dict[str, Any]) -> None:
    assert set(item) == {
        "freshness_admission_id",
        "physical_transport_credential_assignment_binding_id",
        "credential_assignment_snapshot_id",
        "assignment_id",
        "assignment_revision",
        "credential_generation",
        "rotation_epoch",
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
    assert item["state"] == "admitted_current"
    assert len(item["authority"]) == 17
    assert not any(item["authority"].values())
    assert datetime.fromisoformat(item["valid_until"]) - datetime.fromisoformat(
        item["evaluated_at"]
    ) <= timedelta(seconds=60)
    minimized_values = {key: value for key, value in item.items() if key != "authority"}
    normalized = str(minimized_values).casefold()
    for forbidden in (
        "digest",
        "credential_profile",
        "credential_requirement",
        "secret_reference",
        "endpoint",
        "broker_policy",
        "target_scope_commitment",
    ):
        assert forbidden not in normalized


def test_exact_workload_post_and_one_normal_browser_session_get_minimized_evidence() -> None:
    workload_service, token = _workload_service_and_token()
    service = _Service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_credential_assignment_freshness_admission_service=cast(
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
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE,
            ),
        )
        inventory = client.get(ENDPOINT)

    assert unauthenticated.status_code == 403
    assert empty.status_code == 200
    assert empty.json()["data"] == {
        "physical_transport_credential_assignment_freshness_admissions": [],
        "durable": False,
    }
    assert browser_post.status_code == 401
    assert browser_post.json()["code"] == "workload_authentication_failed"
    assert created.status_code == 201
    item = dict(created.json()["data"])
    _assert_minimized(item)
    assert inventory.status_code == 200
    assert inventory.json()["data"][
        "physical_transport_credential_assignment_freshness_admissions"
    ] == [item]
    assert created.headers["Cache-Control"].startswith("no-store")
    assert inventory.headers["Cache-Control"].startswith("no-store")
    _assert_no_step_up_language(inventory.text)
    assert "authorized browser session" not in inventory.text.casefold()
    context = service.admit_calls[0]["context"]
    assert context.subject_id == (
        WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_SUBJECT
    )
    assert context.credential_audience == (
        WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE
    )


def test_browser_get_preserves_historical_policy_identity() -> None:
    historical = _admission(
        policy_id=(
            "policy.workflow-event-physical-transport-credential-assignment-freshness-legacy"
        ),
        policy_version="0.9",
    )
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workflow_event_physical_transport_credential_assignment_freshness_admission_service=cast(
            Any,
            _Service((historical,)),
        ),
    )

    with TestClient(app) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 200
    item = response.json()["data"]["physical_transport_credential_assignment_freshness_admissions"][
        0
    ]
    assert item["policy_id"] == historical.policy_id
    assert item["policy_version"] == historical.policy_version


def test_post_rejects_personal_api_token_wrong_audience_and_wrong_workload_subject() -> None:
    workload_service, exact_token = _workload_service_and_token()
    wrong_service, wrong_subject_token = _workload_service_and_token(
        identity_id="service.workflow-physical-transport-credential-assignment-freshness-other"
    )
    service = _Service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_credential_assignment_freshness_admission_service=cast(
            Any, service
        ),
    )
    wrong_subject_app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=wrong_service,
        workflow_event_physical_transport_credential_assignment_freshness_admission_service=cast(
            Any, service
        ),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        personal = client.post(
            ENDPOINT,
            json=_payload(),
            headers={"Authorization": f"Bearer {personal_token}"},
        )
        wrong_audience = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(exact_token, "audience.workflow-worker"),
        )
    with TestClient(wrong_subject_app) as client:
        wrong_subject = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                wrong_subject_token,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE,
            ),
        )

    for denied in (personal, wrong_audience):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert wrong_subject.status_code == 401
    assert wrong_subject.json()["code"] == "workload_authentication_failed"
    assert personal_token not in personal.text


def test_get_is_rbac_protected_and_repository_failure_is_controlled() -> None:
    denied_app = create_app(
        Settings(
            environment="development",
            development_identity_enabled=True,
            development_role_ids=("role.unassigned",),
        ),
        audit_sink=_AuditSink(),
        workflow_event_physical_transport_credential_assignment_freshness_admission_service=cast(
            Any, _Service()
        ),
    )
    unavailable_app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workflow_event_physical_transport_credential_assignment_freshness_admission_service=cast(
            Any, _Service(unavailable=True)
        ),
    )

    with TestClient(denied_app) as client:
        _login(client)
        denied = client.get(ENDPOINT)
    with TestClient(unavailable_app) as client:
        _login(client)
        unavailable = client.get(ENDPOINT)

    assert denied.status_code == 403
    assert denied.json()["code"] == "authorization_denied"
    assert unavailable.status_code == 503
    assert unavailable.json()["code"].endswith("_repository_unavailable")
    _assert_no_step_up_language(denied.text + unavailable.text)


def test_service_conflicts_are_mapped_without_leaking_internal_evidence() -> None:
    workload_service, token = _workload_service_and_token()
    service = _Service(
        failure=WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
            "workflow_physical_transport_credential_assignment_freshness_evidence_conflict",
            "Internal evidence must not be rendered.",
        )
    )
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        workflow_event_physical_transport_credential_assignment_freshness_admission_service=cast(
            Any, service
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE,
            ),
        )

    assert response.status_code == 409
    assert response.json()["code"].endswith("_evidence_conflict")
    assert "Internal evidence" not in response.text
