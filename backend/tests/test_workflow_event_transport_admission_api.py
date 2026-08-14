from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from test_workflow_dispatch_event_envelope_api import (
    _acquire_publication_lease,
    _preparation_url,
    _prepare_payload,
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
from atlas.modules.workflows.domain import (
    code_owned_workflow_event_transport_admission_policy,
)


def _read_url(chain: dict[str, Any], envelope: dict[str, Any]) -> str:
    return (
        f"{_publication_url(chain).removesuffix('/publication-lease')}/event-envelope/"
        f"{envelope['event_id']}/transport-admission"
    )


def _admission_url(chain: dict[str, Any], lease: dict[str, Any], envelope: dict[str, Any]) -> str:
    return (
        f"{_publication_url(chain)}/{lease['publication_lease_id']}/event-envelope/"
        f"{envelope['event_id']}/transport-admission"
    )


def _admission_payload(
    chain: dict[str, Any], lease: dict[str, Any], envelope: dict[str, Any]
) -> dict[str, object]:
    policy = code_owned_workflow_event_transport_admission_policy()
    return {
        "schema_version": "atlas.workflow-event-transport-admission-input.v1",
        "outbox_entry_digest": chain["outbox"]["canonical_digest"],
        "event_digest": envelope["canonical_digest"],
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "publication_lease_digest": lease["canonical_digest"],
        "publication_fencing_token": lease["publication_fencing_token"],
        (
            "acknowledged_admission_only_no_publication_delivery_dispatch_or_execution_authority"
        ): True,
    }


def _prepare_envelope(
    client: TestClient,
    chain: dict[str, Any],
    lease: dict[str, Any],
    publisher_token: str,
) -> dict[str, Any]:
    response = client.post(
        _preparation_url(chain, lease),
        json=_prepare_payload(chain, lease),
        headers={
            **_workload_headers(publisher_token, WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
            "Idempotency-Key": "transport-admission-envelope-prepare-0001",
        },
    )
    assert response.status_code == 201
    return dict(response.json()["data"])


def _assert_zero_authority(admission: dict[str, Any]) -> None:
    assert not any(admission["authority"].values())
    assert admission["grants_publication_authority"] is False
    assert admission["grants_delivery_authority"] is False
    assert admission["grants_dispatch_authority"] is False
    assert admission["grants_execution_authority"] is False


def test_publisher_admits_one_envelope_and_browser_reads_policy_evidence() -> None:
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
        read_endpoint = _read_url(chain, envelope)
        empty = client.get(read_endpoint)
        admission_endpoint = _admission_url(chain, lease, envelope)
        publisher_headers = {
            **_workload_headers(tokens[PUBLISHER_ID], WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE),
            "Idempotency-Key": "workflow-event-transport-admission-0001",
        }
        admitted_response = client.post(
            admission_endpoint,
            json=_admission_payload(chain, lease, envelope),
            headers=publisher_headers,
        )
        replay_response = client.post(
            admission_endpoint,
            json=_admission_payload(chain, lease, envelope),
            headers=publisher_headers,
        )
        browser_inventory = client.get(read_endpoint)

    assert empty.status_code == 200
    assert empty.headers["Cache-Control"].startswith("no-store")
    assert empty.json()["data"] == {
        "event_id": envelope["event_id"],
        "transport_admissions": [],
        "durable": False,
    }
    assert admitted_response.status_code == 201
    assert admitted_response.headers["Cache-Control"].startswith("no-store")
    assert replay_response.status_code == 201
    admission = admitted_response.json()["data"]
    assert replay_response.json()["data"] == admission
    assert set(admission) == {
        "transport_admission_id",
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
        "policy",
        "canonical_byte_count",
        "publisher_subject_id",
        "orchestration_lease_id",
        "orchestration_lease_digest",
        "orchestration_fencing_token",
        "publication_lease_id",
        "publication_lease_digest",
        "publication_fencing_token",
        "admitted_at",
        "state",
        "authority",
        "grants_publication_authority",
        "grants_delivery_authority",
        "grants_dispatch_authority",
        "grants_execution_authority",
        "canonical_digest",
    }
    assert admission["event_id"] == envelope["event_id"]
    assert admission["event_digest"] == envelope["canonical_digest"]
    assert admission["outbox_entry_id"] == chain["outbox"]["outbox_entry_id"]
    assert admission["publication_lease_id"] == lease["publication_lease_id"]
    assert admission["publication_lease_digest"] == lease["canonical_digest"]
    assert admission["publication_fencing_token"] == lease["publication_fencing_token"]
    assert admission["publisher_subject_id"] == PUBLISHER_ID
    assert admission["state"] == "admitted"
    assert admission["policy"] == {
        "policy_id": "policy.workflow-event-transport-admission",
        "policy_version": "1.0",
        "policy_digest": code_owned_workflow_event_transport_admission_policy().canonical_digest,
        "allowed_event_type": "WorkflowStepDispatchRequested",
        "allowed_event_version": "1.0",
        "allowed_schema_uri": ("urn:project-atlas:event:workflow-step-dispatch-requested:1.0"),
        "allowed_data_classification": "internal",
        "representation_name": "canonical-json",
        "encoding": "utf-8",
        "maximum_canonical_byte_count": 65_536,
    }
    assert admission["canonical_byte_count"] <= 65_536
    _assert_zero_authority(admission)
    normalized = admitted_response.text.casefold()
    for forbidden in (
        "broker",
        "endpoint",
        "queue",
        "topic",
        "partition",
        "routing_key",
        "transport_credential",
        "wire_payload",
        "serialized_payload",
        "delivery_receipt",
    ):
        assert forbidden not in normalized
    assert tokens[PUBLISHER_ID] not in admitted_response.text

    assert browser_inventory.status_code == 200
    assert browser_inventory.headers["Cache-Control"].startswith("no-store")
    assert browser_inventory.json()["data"]["transport_admissions"] == [admission]
    _assert_no_step_up_language(browser_inventory.text)


def test_transport_admission_requires_exact_publisher_workload_credential() -> None:
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
        endpoint = _admission_url(chain, lease, envelope)
        payload = _admission_payload(chain, lease, envelope)

        browser_mutation = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "transport-admission-browser-denied-0001"},
        )
        client.cookies.clear()
        api_token_mutation = client.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Idempotency-Key": "transport-admission-api-token-denied-0001",
            },
        )
        worker_mutation = client.post(
            endpoint,
            json=payload,
            headers={
                **_workload_headers(tokens[WORKER_ID], WORKFLOW_WORKER_AUDIENCE),
                "Idempotency-Key": "transport-admission-worker-denied-0001",
            },
        )
        unauthenticated_read = client.get(_read_url(chain, envelope))
        _login(client)
        browser_read = client.get(_read_url(chain, envelope))

    for response in (browser_mutation, api_token_mutation, worker_mutation):
        assert response.status_code == 401
        assert response.json()["code"] == "workload_authentication_failed"
        _assert_no_step_up_language(response.text)
    assert api_token not in api_token_mutation.text
    assert unauthenticated_read.status_code == 403
    assert unauthenticated_read.json()["code"] == "browser_session_required"
    _assert_no_step_up_language(unauthenticated_read.text)
    assert browser_read.status_code == 200
    assert browser_read.json()["data"]["transport_admissions"] == []
