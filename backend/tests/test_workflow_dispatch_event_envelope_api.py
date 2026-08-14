from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    PUBLISHER_ID,
    WORKER_ID,
    _acquire_payload,
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


def _envelope_url(chain: dict[str, Any]) -> str:
    return f"{_publication_url(chain).removesuffix('/publication-lease')}/event-envelope"


def _preparation_url(chain: dict[str, Any], lease: dict[str, Any]) -> str:
    return f"{_publication_url(chain)}/{lease['publication_lease_id']}/event-envelope/preparation"


def _prepare_payload(chain: dict[str, Any], lease: dict[str, Any]) -> dict[str, object]:
    return {
        "schema_version": "atlas.workflow-dispatch-event-envelope-prepare-input.v1",
        "outbox_entry_digest": chain["outbox"]["canonical_digest"],
        "publication_lease_digest": lease["canonical_digest"],
        "publication_fencing_token": lease["publication_fencing_token"],
        (
            "acknowledged_preparation_only_no_publication_delivery_dispatch_or_execution_authority"
        ): True,
    }


def _acquire_publication_lease(
    client: TestClient, chain: dict[str, Any], publisher_token: str
) -> dict[str, Any]:
    response = client.post(
        f"{_publication_url(chain)}/acquisition",
        json=_acquire_payload(chain),
        headers={
            **_workload_headers(publisher_token, WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
            "Idempotency-Key": "event-envelope-publication-lease-0001",
        },
    )
    assert response.status_code == 201
    return dict(response.json()["data"])


def _assert_zero_authority(envelope: dict[str, Any]) -> None:
    assert not any(envelope["authority"].values())
    assert envelope["grants_publication_authority"] is False
    assert envelope["grants_delivery_authority"] is False
    assert envelope["grants_dispatch_authority"] is False
    assert envelope["grants_execution_authority"] is False


def test_publisher_prepares_one_canonical_envelope_and_browser_reads_evidence() -> None:
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
        endpoint = _envelope_url(chain)
        empty = client.get(endpoint)
        preparation_endpoint = _preparation_url(chain, lease)
        publisher_headers = {
            **_workload_headers(tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
            "Idempotency-Key": "dispatch-event-envelope-prepare-0001",
        }
        prepared_response = client.post(
            preparation_endpoint,
            json=_prepare_payload(chain, lease),
            headers=publisher_headers,
        )
        replay_response = client.post(
            preparation_endpoint,
            json=_prepare_payload(chain, lease),
            headers=publisher_headers,
        )
        browser_inventory = client.get(endpoint)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"] == {
        "outbox_entry_id": chain["outbox"]["outbox_entry_id"],
        "event_envelopes": [],
        "durable": False,
    }
    assert prepared_response.status_code == 201
    assert replay_response.status_code == 201
    envelope = prepared_response.json()["data"]
    assert replay_response.json()["data"] == envelope
    assert set(envelope) == {
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "recorded_at",
        "producer",
        "producer_version",
        "subject_type",
        "subject_id",
        "organization_id",
        "environment_id",
        "correlation_id",
        "causation_id",
        "workflow_id",
        "data_classification",
        "schema_uri",
        "payload",
        "extensions",
        "orchestration_lease_id",
        "orchestration_lease_digest",
        "orchestration_fencing_token",
        "publication_lease_id",
        "publication_lease_digest",
        "publication_fencing_token",
        "publisher_subject_id",
        "prepared_at",
        "state",
        "authority",
        "grants_publication_authority",
        "grants_delivery_authority",
        "grants_dispatch_authority",
        "grants_execution_authority",
        "canonical_digest",
    }
    assert envelope["event_type"] == "WorkflowStepDispatchRequested"
    assert envelope["event_version"] == "1.0"
    assert envelope["state"] == "prepared"
    assert envelope["extensions"] == {}
    assert envelope["payload"]["outbox_entry_id"] == chain["outbox"]["outbox_entry_id"]
    assert envelope["payload"]["outbox_entry_digest"] == chain["outbox"]["canonical_digest"]
    assert envelope["publication_lease_id"] == lease["publication_lease_id"]
    assert envelope["publication_lease_digest"] == lease["canonical_digest"]
    assert envelope["publication_fencing_token"] == lease["publication_fencing_token"]
    assert envelope["publisher_subject_id"] == PUBLISHER_ID
    _assert_zero_authority(envelope)
    normalized = prepared_response.text.casefold()
    for forbidden in (
        "secret.",
        "broker",
        "queue",
        "topic",
        "routing_key",
        "transport_credential",
        "wire_payload",
        "serialized_payload",
    ):
        assert forbidden not in normalized
    assert tokens[PUBLISHER_ID] not in prepared_response.text

    assert browser_inventory.status_code == 200
    assert browser_inventory.headers["Cache-Control"].startswith("no-store")
    assert browser_inventory.json()["data"]["event_envelopes"] == [envelope]
    _assert_no_step_up_language(browser_inventory.text)


def test_event_envelope_preparation_requires_exact_publisher_workload_credential() -> None:
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
        endpoint = _preparation_url(chain, lease)
        payload = _prepare_payload(chain, lease)

        browser_mutation = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "event-envelope-browser-denied-0001"},
        )
        client.cookies.clear()
        api_token_mutation = client.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Idempotency-Key": "event-envelope-api-token-denied-0001",
            },
        )
        worker_mutation = client.post(
            endpoint,
            json=payload,
            headers={
                **_workload_headers(tokens[WORKER_ID], WORKFLOW_WORKER_AUDIENCE),
                "Idempotency-Key": "event-envelope-worker-denied-0001",
            },
        )
        unauthenticated_read = client.get(_envelope_url(chain))
        _login(client)
        browser_read = client.get(_envelope_url(chain))

    for response in (browser_mutation, api_token_mutation, worker_mutation):
        assert response.status_code == 401
        assert response.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(response.text)
    assert api_token not in api_token_mutation.text
    assert unauthenticated_read.status_code == 403
    assert unauthenticated_read.json()["code"] == "browser_session_required"
    _assert_no_step_up_language(unauthenticated_read.text)
    assert browser_read.status_code == 200
    assert browser_read.json()["data"]["event_envelopes"] == []
