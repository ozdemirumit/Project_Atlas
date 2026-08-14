from __future__ import annotations

from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_dispatch_event_envelope_api import _acquire_publication_lease
from test_workflow_event_byte_artifact_api import (
    _admit,
    _materialization_payload,
    _materialization_url,
)
from test_workflow_event_transport_admission_api import _prepare_envelope
from test_workflow_outbox_publication_lease_api import (
    PUBLISHER_ID,
    WORKER_ID,
    _assert_no_step_up_language,
    _AuditSink,
    _ExplicitTargetAccessSource,
    _issue_api_token,
    _login,
    _publication_url,
    _seed_dispatch_outbox_chain,
    _settings,
    _workload_headers,
    _workload_service,
)

from atlas.api.app import create_app
from atlas.modules.workflows.application import (
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WORKFLOW_WORKER_AUDIENCE,
)
from atlas.modules.workflows.domain import code_owned_workflow_event_logical_channel_policy


def _binding_read_url(
    chain: dict[str, Any],
    envelope: dict[str, Any],
    admission: dict[str, Any],
    artifact: dict[str, Any],
) -> str:
    return (
        f"{_publication_url(chain).removesuffix('/publication-lease')}/event-envelope/"
        f"{envelope['event_id']}/transport-admission/"
        f"{admission['transport_admission_id']}/byte-artifact/"
        f"{artifact['byte_artifact_id']}/logical-channel-binding"
    )


def _binding_url(
    chain: dict[str, Any],
    lease: dict[str, Any],
    envelope: dict[str, Any],
    admission: dict[str, Any],
    artifact: dict[str, Any],
) -> str:
    return (
        f"{_publication_url(chain)}/{lease['publication_lease_id']}/event-envelope/"
        f"{envelope['event_id']}/transport-admission/"
        f"{admission['transport_admission_id']}/byte-artifact/"
        f"{artifact['byte_artifact_id']}/logical-channel-binding"
    )


def _binding_payload(artifact: dict[str, Any], lease: dict[str, Any]) -> dict[str, object]:
    policy = code_owned_workflow_event_logical_channel_policy()
    return {
        "schema_version": "atlas.workflow-event-logical-channel-binding-input.v1",
        "byte_artifact_digest": artifact["canonical_digest"],
        "content_sha256": artifact["content_sha256"],
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "publication_lease_digest": lease["canonical_digest"],
        "publication_fencing_token": lease["publication_fencing_token"],
        ("acknowledged_binding_only_no_publication_delivery_dispatch_or_execution_authority"): True,
    }


def _materialize_artifact(
    client: TestClient,
    chain: dict[str, Any],
    lease: dict[str, Any],
    envelope: dict[str, Any],
    admission: dict[str, Any],
    publisher_token: str,
) -> dict[str, Any]:
    response = client.post(
        _materialization_url(chain, lease, envelope, admission),
        json=_materialization_payload(chain, lease, envelope, admission),
        headers={
            **_workload_headers(publisher_token, WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
            "Idempotency-Key": "logical-channel-byte-artifact-0001",
        },
    )
    assert response.status_code == 201
    return dict(response.json()["data"])


def _seed_binding_chain(
    client: TestClient,
    *,
    csrf: str,
    worker_token: str,
    publisher_token: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    chain = _seed_dispatch_outbox_chain(client, csrf=csrf, worker_token=worker_token)
    lease = _acquire_publication_lease(client, chain, publisher_token)
    envelope = _prepare_envelope(client, chain, lease, publisher_token)
    admission = _admit(client, chain, lease, envelope, publisher_token)
    artifact = _materialize_artifact(
        client,
        chain,
        lease,
        envelope,
        admission,
        publisher_token,
    )
    return chain, lease, envelope, admission, artifact


def _assert_zero_authority(binding: dict[str, Any]) -> None:
    assert not any(binding["authority"].values())
    assert binding["grants_publication_authority"] is False
    assert binding["grants_delivery_authority"] is False
    assert binding["grants_dispatch_authority"] is False
    assert binding["grants_execution_authority"] is False


def test_publisher_binds_code_owned_channel_and_browser_reads_minimized_metadata() -> None:
    workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        chain, lease, envelope, admission, artifact = _seed_binding_chain(
            client,
            csrf=csrf,
            worker_token=tokens[WORKER_ID],
            publisher_token=tokens[PUBLISHER_ID],
        )
        read_endpoint = _binding_read_url(chain, envelope, admission, artifact)
        empty = client.get(read_endpoint)
        endpoint = _binding_url(chain, lease, envelope, admission, artifact)
        publisher_headers = {
            **_workload_headers(tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
            "Idempotency-Key": "workflow-event-logical-channel-binding-0001",
        }
        created = client.post(
            endpoint,
            json=_binding_payload(artifact, lease),
            headers=publisher_headers,
        )
        replay = client.post(
            endpoint,
            json=_binding_payload(artifact, lease),
            headers=publisher_headers,
        )
        inventory = client.get(read_endpoint)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"] == {
        "byte_artifact_id": artifact["byte_artifact_id"],
        "logical_channel_bindings": [],
        "durable": False,
    }
    assert created.status_code == 201
    assert created.headers["Cache-Control"].startswith("no-store")
    assert replay.status_code == 201
    binding = created.json()["data"]
    assert replay.json()["data"] == binding
    assert set(binding) == {
        "logical_channel_binding_id",
        "byte_artifact_id",
        "byte_artifact_digest",
        "content_sha256",
        "byte_count",
        "transport_admission_id",
        "transport_admission_digest",
        "event_id",
        "event_digest",
        "outbox_entry_id",
        "outbox_entry_digest",
        "dispatch_intent_id",
        "dispatch_intent_digest",
        "plan_id",
        "plan_digest",
        "run_id",
        "run_digest",
        "step_run_id",
        "step_run_digest",
        "step_id",
        "attempt_id",
        "attempt_digest",
        "attempt_number",
        "scope",
        "target_id",
        "target_type",
        "policy_id",
        "policy_version",
        "policy_digest",
        "logical_channel_id",
        "logical_channel_version",
        "delivery_semantics",
        "durability_required",
        "ordering_key_kind",
        "ordering_key_value",
        "retention_class",
        "publisher_subject_id",
        "orchestration_lease_id",
        "orchestration_lease_digest",
        "orchestration_fencing_token",
        "publication_lease_id",
        "publication_lease_digest",
        "publication_fencing_token",
        "bound_at",
        "state",
        "authority",
        "grants_publication_authority",
        "grants_delivery_authority",
        "grants_dispatch_authority",
        "grants_execution_authority",
        "canonical_digest",
    }
    assert binding["byte_artifact_id"] == artifact["byte_artifact_id"]
    assert binding["byte_artifact_digest"] == artifact["canonical_digest"]
    assert binding["content_sha256"] == artifact["content_sha256"]
    assert binding["byte_count"] == artifact["byte_count"]
    assert binding["logical_channel_id"] == "channel.workflow-dispatch.internal"
    assert binding["logical_channel_version"] == "1.0"
    assert binding["delivery_semantics"] == "at-least-once"
    assert binding["durability_required"] is True
    assert binding["ordering_key_kind"] == "workflow-run"
    assert binding["ordering_key_value"] == artifact["run_id"]
    assert binding["retention_class"] == "workflow-operational"
    assert binding["state"] == "bound"
    _assert_zero_authority(binding)
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"].startswith("no-store")
    assert inventory.json()["data"]["logical_channel_bindings"] == [binding]
    _assert_no_step_up_language(inventory.text)

    normalized = inventory.text.casefold()
    for forbidden in (
        "canonical_bytes",
        "raw_bytes",
        "payload",
        "base64",
        "provider",
        "broker",
        "endpoint",
        "topic",
        "stream",
        "queue",
        "partition",
        "routing_key",
        "credential",
        "secret",
        "encryption_key",
        "provider_message",
        "publication_attempt",
        "network_attempt",
    ):
        assert forbidden not in normalized
    assert tokens[PUBLISHER_ID] not in inventory.text


def test_logical_channel_binding_rejects_browser_pat_and_wrong_workload() -> None:
    workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        chain, lease, envelope, admission, artifact = _seed_binding_chain(
            client,
            csrf=csrf,
            worker_token=tokens[WORKER_ID],
            publisher_token=tokens[PUBLISHER_ID],
        )
        api_token = _issue_api_token(client, csrf)
        endpoint = _binding_url(chain, lease, envelope, admission, artifact)
        payload = _binding_payload(artifact, lease)
        browser_mutation = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "logical-channel-browser-denied-0001"},
        )
        client.cookies.clear()
        api_token_mutation = client.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Idempotency-Key": "logical-channel-api-token-denied-0001",
            },
        )
        worker_mutation = client.post(
            endpoint,
            json=payload,
            headers={
                **_workload_headers(tokens[WORKER_ID], WORKFLOW_WORKER_AUDIENCE),
                "Idempotency-Key": "logical-channel-worker-denied-0001",
            },
        )
        _login(client)
        browser_read = client.get(_binding_read_url(chain, envelope, admission, artifact))

    for denied in (browser_mutation, api_token_mutation, worker_mutation):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert api_token not in api_token_mutation.text
    assert browser_read.status_code == 200
    assert browser_read.json()["data"]["logical_channel_bindings"] == []
    _assert_no_step_up_language(browser_read.text)


def test_logical_channel_binding_rejects_caller_controlled_route_fields() -> None:
    workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        chain, lease, envelope, admission, artifact = _seed_binding_chain(
            client,
            csrf=csrf,
            worker_token=tokens[WORKER_ID],
            publisher_token=tokens[PUBLISHER_ID],
        )
        endpoint = _binding_url(chain, lease, envelope, admission, artifact)
        headers = _workload_headers(tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE)
        for index, (field, value) in enumerate(
            (
                ("logical_channel_id", "channel.caller-selected"),
                ("delivery_semantics", "at-most-once"),
                ("ordering_key_value", "run.caller-selected"),
                ("retention_class", "caller-selected"),
                ("provider", "caller-selected"),
                ("topic", "caller-selected"),
                ("routing_key", "caller-selected"),
            ),
            start=1,
        ):
            response = client.post(
                endpoint,
                json=_binding_payload(artifact, lease) | {field: value},
                headers={
                    **headers,
                    "Idempotency-Key": f"logical-channel-extra-denied-{index:04d}",
                },
            )
            assert response.status_code == 422
        acknowledgement = _binding_payload(artifact, lease)
        acknowledgement[
            "acknowledged_binding_only_no_publication_delivery_dispatch_or_execution_authority"
        ] = False
        denied_acknowledgement = client.post(
            endpoint,
            json=acknowledgement,
            headers={
                **headers,
                "Idempotency-Key": "logical-channel-ack-denied-0001",
            },
        )

    assert denied_acknowledgement.status_code == 422


def test_logical_channel_binding_get_fails_closed_for_tampered_lineage() -> None:
    workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        chain, lease, envelope, admission, artifact = _seed_binding_chain(
            client,
            csrf=csrf,
            worker_token=tokens[WORKER_ID],
            publisher_token=tokens[PUBLISHER_ID],
        )
        endpoint = _binding_url(chain, lease, envelope, admission, artifact)
        created = client.post(
            endpoint,
            json=_binding_payload(artifact, lease),
            headers={
                **_workload_headers(tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
                "Idempotency-Key": "logical-channel-tamper-0001",
            },
        )
        assert created.status_code == 201
        repository = cast(Any, app.state.workflow_event_logical_channel_binding_repository)
        stored = repository._event_logical_channel_bindings_by_artifact[
            artifact["byte_artifact_id"]
        ]
        object.__setattr__(stored, "target_id", "asset.storage.tampered")
        tampered = client.get(_binding_read_url(chain, envelope, admission, artifact))
        wrong_route = client.get(
            _binding_read_url(chain, envelope, admission, artifact).replace(
                f"/{artifact['byte_artifact_id']}/",
                "/workflow-event-byte-artifact.wrong/",
            )
        )

    assert tampered.status_code == 503
    assert tampered.json()["code"] == ("workflow_event_logical_channel_binding_service_unavailable")
    assert wrong_route.status_code == 404
    assert wrong_route.json()["code"] == "workflow_resource_unavailable"
