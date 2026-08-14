from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from test_workflow_event_logical_channel_binding_api import (
    _binding_payload,
    _binding_url,
    _seed_binding_chain,
)
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
from test_workflow_transport_profile_snapshot_api import (
    ENDPOINT as SNAPSHOT_ENDPOINT,
)
from test_workflow_transport_profile_snapshot_api import (
    _payload as _snapshot_payload,
)
from test_workflow_transport_profile_snapshot_api import (
    _registry_token,
    _source_profile,
)

from atlas.api.app import create_app
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
    WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
)
from atlas.modules.workflows.domain import (
    code_owned_workflow_event_transport_compatibility_policy,
)

ADMITTER_ID = "workload.atlas.workflow-transport-compatibility-admitter-01"
ENDPOINT = "/api/v1/workflows/transport-compatibility-admissions"


def _admitter_token(service: WorkloadIdentityService) -> str:
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
            display_name="Workflow transport compatibility admitter",
            service_id="service.workflow-transport-compatibility-admitter",
            instance_id="instance.workflow-transport-compatibility-admitter.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Compare exact immutable logical and physical transport declarations.",
            audiences=(WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,),
            secret_reference_ids=("secret.workflow-transport-compatibility-admitter.local-01",),
            lifetime=timedelta(minutes=10),
            reason="Create the dedicated transport compatibility API test identity.",
            idempotency_key="transport-compatibility-admitter-identity-0001",
            correlation_id="correlation.transport-compatibility-admitter-identity-0001",
        )
    )
    return issued.token


def _seed_sources(
    client: TestClient,
    *,
    csrf: str,
    worker_token: str,
    publisher_token: str,
    registry_token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    chain, lease, envelope, transport_admission, artifact = _seed_binding_chain(
        client,
        csrf=csrf,
        worker_token=worker_token,
        publisher_token=publisher_token,
    )
    binding_response = client.post(
        _binding_url(chain, lease, envelope, transport_admission, artifact),
        json=_binding_payload(artifact, lease),
        headers={
            **_workload_headers(publisher_token, WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
            "Idempotency-Key": "transport-compatibility-logical-binding-0001",
        },
    )
    assert binding_response.status_code == 201

    source = _source_profile(client.app)
    snapshot_response = client.post(
        SNAPSHOT_ENDPOINT,
        json=_snapshot_payload(
            source,
            idempotency_key="transport-compatibility-profile-snapshot-0001",
        ),
        headers=_workload_headers(
            registry_token,
            WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
        ),
    )
    assert snapshot_response.status_code == 201
    return dict(binding_response.json()["data"]), dict(snapshot_response.json()["data"])


def _payload(
    binding: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    idempotency_key: str = "transport-compatibility-admission-0001",
) -> dict[str, object]:
    policy = code_owned_workflow_event_transport_compatibility_policy()
    return {
        "logical_channel_binding_id": binding["logical_channel_binding_id"],
        "logical_channel_binding_digest": binding["canonical_digest"],
        "transport_profile_snapshot_id": snapshot["snapshot_id"],
        "transport_profile_snapshot_digest": snapshot["canonical_digest"],
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "idempotency_key": idempotency_key,
    }


def _read_url(payload: dict[str, object]) -> str:
    return f"{ENDPOINT}?logical_channel_binding_id={payload['logical_channel_binding_id']}"


def _assert_minimized(admission: dict[str, Any]) -> None:
    assert set(admission) == {
        "compatibility_admission_id",
        "logical_channel_binding_id",
        "logical_channel_binding_digest",
        "transport_profile_snapshot_id",
        "transport_profile_snapshot_digest",
        "transport_profile_id",
        "transport_profile_revision",
        "policy_id",
        "policy_version",
        "policy_digest",
        "scope",
        "event_type",
        "event_version",
        "schema_uri",
        "data_classification",
        "representation_name",
        "encoding",
        "delivery_semantics",
        "durability_required",
        "ordering_key_kind",
        "retention_class",
        "logical_maximum_byte_count",
        "artifact_byte_count",
        "profile_maximum_message_byte_count",
        "admitter_subject_id",
        "admitted_at",
        "state",
        "authority",
        "canonical_digest",
    }
    assert admission["state"] == "admitted"
    assert admission["admitter_subject_id"] == ADMITTER_ID
    assert not any(admission["authority"].values())


def test_dedicated_workload_admits_and_one_browser_login_reads_exact_minimized_record() -> None:
    workload_service, tokens = _workload_service()
    registry_token = _registry_token(workload_service)
    admitter_token = _admitter_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        binding, snapshot = _seed_sources(
            client,
            csrf=csrf,
            worker_token=tokens[WORKER_ID],
            publisher_token=tokens[PUBLISHER_ID],
            registry_token=registry_token,
        )
        payload = _payload(binding, snapshot)
        empty = client.get(_read_url(payload))
        headers = _workload_headers(
            admitter_token,
            WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
        )
        created = client.post(ENDPOINT, json=payload, headers=headers)
        replay = client.post(ENDPOINT, json=payload, headers=headers)
        inventory = client.get(_read_url(payload))

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"]["transport_compatibility_admissions"] == []
    assert created.status_code == 201
    assert created.headers["Cache-Control"].startswith("no-store")
    admission = created.json()["data"]
    _assert_minimized(admission)
    assert admission["logical_channel_binding_id"] == binding["logical_channel_binding_id"]
    assert admission["logical_channel_binding_digest"] == binding["canonical_digest"]
    assert admission["transport_profile_snapshot_id"] == snapshot["snapshot_id"]
    assert admission["transport_profile_snapshot_digest"] == snapshot["canonical_digest"]
    assert replay.status_code == 201
    assert replay.json()["data"] == admission
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert inventory.json()["data"]["transport_compatibility_admissions"] == [admission]
    _assert_no_step_up_language(inventory.text)

    normalized = inventory.text.casefold()
    for forbidden in (
        "route_id",
        "route_binding_id",
        "endpoint",
        "hostname",
        "namespace",
        "topic",
        "stream",
        "queue",
        "partition",
        "routing_key",
        "credential_reference",
        "secret_reference",
        "vault_path",
        "certificate_reference",
        "health_result",
        "publication_attempt",
        "provider_message_id",
        "readiness",
    ):
        assert f'"{forbidden}"' not in normalized
    assert admitter_token not in inventory.text


def test_creation_rejects_browser_pat_and_wrong_workload_audiences() -> None:
    workload_service, tokens = _workload_service()
    registry_token = _registry_token(workload_service)
    admitter_token = _admitter_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        binding, snapshot = _seed_sources(
            client,
            csrf=csrf,
            worker_token=tokens[WORKER_ID],
            publisher_token=tokens[PUBLISHER_ID],
            registry_token=registry_token,
        )
        payload = _payload(binding, snapshot)
        browser = client.post(ENDPOINT, json=payload, headers={"X-CSRF-Token": csrf})
        api_token = _issue_api_token(client, csrf)
        pat = client.post(
            ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {api_token}"},
        )
        publisher = client.post(
            ENDPOINT,
            json=payload,
            headers=_workload_headers(
                tokens[PUBLISHER_ID],
                WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
            ),
        )
        registry = client.post(
            ENDPOINT,
            json=payload,
            headers=_workload_headers(
                registry_token,
                WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
            ),
        )
        admitted = client.post(
            ENDPOINT,
            json=payload,
            headers=_workload_headers(
                admitter_token,
                WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
            ),
        )

    for denied in (browser, pat, publisher, registry):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert admitted.status_code == 201
    assert api_token not in pat.text


def test_creation_rejects_caller_controlled_route_credential_and_readiness_fields() -> None:
    workload_service, _ = _workload_service()
    admitter_token = _admitter_token(workload_service)
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
    )
    base = {
        "logical_channel_binding_id": "workflow-event-logical-channel-binding.source-01",
        "logical_channel_binding_digest": "1" * 64,
        "transport_profile_snapshot_id": "event-physical-transport-profile-snapshot.source-01",
        "transport_profile_snapshot_digest": "2" * 64,
        "policy_id": "policy.workflow-event-transport-compatibility",
        "policy_version": "1.0",
        "policy_digest": "3" * 64,
        "idempotency_key": "transport-compatibility-extra-field-0001",
    }

    with TestClient(app) as client:
        headers = _workload_headers(
            admitter_token,
            WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
        )
        for index, (field, value) in enumerate(
            (
                ("route_id", "route.caller-selected"),
                ("endpoint", "https://example.invalid"),
                ("topic", "caller-selected"),
                ("credential_reference", "secret.caller-selected"),
                ("health_probe", True),
                ("ready", True),
                ("publish", True),
            ),
            start=1,
        ):
            response = client.post(
                ENDPOINT,
                json=base
                | {
                    "idempotency_key": f"transport-compatibility-extra-field-{index:04d}",
                    field: value,
                },
                headers=headers,
            )
            assert response.status_code == 422


def test_inventory_is_default_deny_without_explicit_assignment() -> None:
    app = create_app(
        Settings(
            environment="development",
            development_identity_enabled=True,
            development_role_ids=("role.unassigned",),
        ),
        audit_sink=_AuditSink(),
    )
    query = {
        "logical_channel_binding_id": "workflow-event-logical-channel-binding.source-01",
    }

    with TestClient(app) as client:
        _login(client)
        denied = client.get(ENDPOINT, params=query)

    assert denied.status_code == 403
    assert denied.json()["code"] == "authorization_denied"
    _assert_no_step_up_language(denied.text)
