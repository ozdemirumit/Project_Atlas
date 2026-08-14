from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from test_workflow_dispatch_event_envelope_api import _acquire_publication_lease
from test_workflow_event_transport_admission_api import (
    _admission_payload,
    _admission_url,
    _prepare_envelope,
)
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


def _read_url(chain: dict[str, Any], envelope: dict[str, Any], admission: dict[str, Any]) -> str:
    return (
        f"{_publication_url(chain).removesuffix('/publication-lease')}/event-envelope/"
        f"{envelope['event_id']}/transport-admission/"
        f"{admission['transport_admission_id']}/byte-artifact"
    )


def _materialization_url(
    chain: dict[str, Any],
    lease: dict[str, Any],
    envelope: dict[str, Any],
    admission: dict[str, Any],
) -> str:
    return (
        f"{_publication_url(chain)}/{lease['publication_lease_id']}/event-envelope/"
        f"{envelope['event_id']}/transport-admission/"
        f"{admission['transport_admission_id']}/byte-artifact"
    )


def _materialization_payload(
    chain: dict[str, Any],
    lease: dict[str, Any],
    envelope: dict[str, Any],
    admission: dict[str, Any],
) -> dict[str, object]:
    return {
        "schema_version": "atlas.workflow-event-byte-artifact-materialization-input.v1",
        "outbox_entry_digest": chain["outbox"]["canonical_digest"],
        "event_digest": envelope["canonical_digest"],
        "transport_admission_digest": admission["canonical_digest"],
        "policy_id": admission["policy"]["policy_id"],
        "policy_version": admission["policy"]["policy_version"],
        "policy_digest": admission["policy"]["policy_digest"],
        "publication_lease_digest": lease["canonical_digest"],
        "publication_fencing_token": lease["publication_fencing_token"],
        (
            "acknowledged_materialization_only_no_publication_delivery_dispatch_or_"
            "execution_authority"
        ): True,
    }


def _admit(
    client: TestClient,
    chain: dict[str, Any],
    lease: dict[str, Any],
    envelope: dict[str, Any],
    publisher_token: str,
) -> dict[str, Any]:
    response = client.post(
        _admission_url(chain, lease, envelope),
        json=_admission_payload(chain, lease, envelope),
        headers={
            **_workload_headers(publisher_token, WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
            "Idempotency-Key": "byte-artifact-admission-0001",
        },
    )
    assert response.status_code == 201
    return dict(response.json()["data"])


def _assert_zero_authority(artifact: dict[str, Any]) -> None:
    assert not any(artifact["authority"].values())
    assert artifact["grants_publication_authority"] is False
    assert artifact["grants_delivery_authority"] is False
    assert artifact["grants_dispatch_authority"] is False
    assert artifact["grants_execution_authority"] is False


def test_publisher_materializes_exact_bytes_and_browser_reads_only_minimized_metadata() -> None:
    workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        chain = _seed_dispatch_outbox_chain(client, csrf=csrf, worker_token=tokens[WORKER_ID])
        lease = _acquire_publication_lease(client, chain, tokens[PUBLISHER_ID])
        envelope = _prepare_envelope(client, chain, lease, tokens[PUBLISHER_ID])
        admission = _admit(client, chain, lease, envelope, tokens[PUBLISHER_ID])
        read_endpoint = _read_url(chain, envelope, admission)
        empty = client.get(read_endpoint)
        endpoint = _materialization_url(chain, lease, envelope, admission)
        publisher_headers = {
            **_workload_headers(tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
            "Idempotency-Key": "workflow-event-byte-artifact-0001",
        }
        materialized_response = client.post(
            endpoint,
            json=_materialization_payload(chain, lease, envelope, admission),
            headers=publisher_headers,
        )
        replay_response = client.post(
            endpoint,
            json=_materialization_payload(chain, lease, envelope, admission),
            headers=publisher_headers,
        )
        browser_inventory = client.get(read_endpoint)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"] == {
        "transport_admission_id": admission["transport_admission_id"],
        "byte_artifacts": [],
        "durable": False,
    }
    assert materialized_response.status_code == 201
    assert materialized_response.headers["Cache-Control"].startswith("no-store")
    assert replay_response.status_code == 201
    artifact = materialized_response.json()["data"]
    assert replay_response.json()["data"] == artifact
    assert set(artifact) == {
        "byte_artifact_id",
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
        "representation_name",
        "encoding",
        "media_type",
        "byte_count",
        "content_sha256",
        "publisher_subject_id",
        "orchestration_lease_id",
        "orchestration_lease_digest",
        "orchestration_fencing_token",
        "publication_lease_id",
        "publication_lease_digest",
        "publication_fencing_token",
        "materialized_at",
        "state",
        "authority",
        "grants_publication_authority",
        "grants_delivery_authority",
        "grants_dispatch_authority",
        "grants_execution_authority",
        "canonical_digest",
    }
    assert artifact["transport_admission_id"] == admission["transport_admission_id"]
    assert artifact["transport_admission_digest"] == admission["canonical_digest"]
    assert artifact["event_id"] == envelope["event_id"]
    assert artifact["event_digest"] == envelope["canonical_digest"]
    assert artifact["byte_count"] == admission["canonical_byte_count"]
    assert artifact["representation_name"] == "canonical-json"
    assert artifact["encoding"] == "utf-8"
    assert artifact["media_type"] == "application/json"
    assert artifact["state"] == "materialized"
    _assert_zero_authority(artifact)
    assert browser_inventory.status_code == 200
    assert browser_inventory.headers["Cache-Control"].startswith("no-store")
    assert browser_inventory.json()["data"]["byte_artifacts"] == [artifact]
    _assert_no_step_up_language(browser_inventory.text)

    normalized = browser_inventory.text.casefold()
    for forbidden in (
        "canonical_bytes",
        "payload",
        "base64",
        "broker",
        "endpoint",
        "queue",
        "topic",
        "partition",
        "routing_key",
        "transport_credential",
        "provider_message",
        "publication_attempt",
        "delivery_receipt",
    ):
        assert forbidden not in normalized
    assert tokens[PUBLISHER_ID] not in browser_inventory.text


def test_byte_artifact_materialization_rejects_browser_pat_and_wrong_workload() -> None:
    workload_service, tokens = _workload_service()
    app = create_app(
        _settings(),
        audit_sink=_AuditSink(),
        workload_identity_service=workload_service,
        conversation_target_access_source=_ExplicitTargetAccessSource(),
    )

    with TestClient(app) as client:
        csrf = _login(client)
        chain = _seed_dispatch_outbox_chain(client, csrf=csrf, worker_token=tokens[WORKER_ID])
        api_token = _issue_api_token(client, csrf)
        lease = _acquire_publication_lease(client, chain, tokens[PUBLISHER_ID])
        envelope = _prepare_envelope(client, chain, lease, tokens[PUBLISHER_ID])
        admission = _admit(client, chain, lease, envelope, tokens[PUBLISHER_ID])
        endpoint = _materialization_url(chain, lease, envelope, admission)
        payload = _materialization_payload(chain, lease, envelope, admission)

        browser_mutation = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "byte-artifact-browser-denied-0001"},
        )
        client.cookies.clear()
        api_token_mutation = client.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Idempotency-Key": "byte-artifact-api-token-denied-0001",
            },
        )
        worker_mutation = client.post(
            endpoint,
            json=payload,
            headers={
                **_workload_headers(tokens[WORKER_ID], WORKFLOW_WORKER_AUDIENCE),
                "Idempotency-Key": "byte-artifact-worker-denied-0001",
            },
        )
        _login(client)
        browser_read = client.get(_read_url(chain, envelope, admission))

    for denied in (browser_mutation, api_token_mutation, worker_mutation):
        assert denied.status_code == 401
        assert denied.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(denied.text)
    assert api_token not in api_token_mutation.text
    assert browser_read.status_code == 200
    assert browser_read.json()["data"]["byte_artifacts"] == []
    _assert_no_step_up_language(browser_read.text)
