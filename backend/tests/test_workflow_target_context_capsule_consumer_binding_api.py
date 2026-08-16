from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    _assert_no_step_up_language,
    _login,
    _settings,
    _workload_headers,
)
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)
from test_workflow_target_context_capsule_consumer_bindings import (
    InMemoryCapsuleConsumerBindingRepository,
)

from atlas.api.app import create_app
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
    WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService,
)
from atlas.modules.workflows.domain import (
    code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy,
)

ENDPOINT = "/api/v1/workflows/physical-transport-target-context-capsule-consumer-bindings"


def _payload() -> dict[str, str]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
    )
    return {
        "opening_result_id": "target-context-artifact-opening.api-imp-210",
        "opening_result_digest": "a" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "capsule-consumer-binding-api-0001",
    }


def _service() -> WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService:
    return WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService(
        repository=InMemoryCapsuleConsumerBindingRepository()
    )


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def _assert_zero_authority(value: dict[str, Any]) -> None:
    assert len(value) == 17
    assert set(value.values()) == {False}


def test_exact_binder_workload_can_create_only_a_minimized_binding() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
    )
    with TestClient(
        create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_transport_target_context_capsule_consumer_binding_service=(
                _service()
            ),
        )
    ) as client:
        response = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
            ),
        )

    assert response.status_code == 201
    _assert_no_store(response)
    data = response.json()["data"]
    assert set(data) == {
        "binding_id",
        "binding_digest",
        "state",
        "bound_at",
        "effective_until",
        "policy",
        "authority",
    }
    assert data["state"] == "bound"
    assert len(data["binding_digest"]) == 64
    assert set(data["policy"]) == {"policy_id", "policy_version"}
    _assert_zero_authority(data["authority"])
    forbidden = {
        "sealed_capsule_id",
        "sealed_capsule_digest",
        "opening_result_digest",
        "event_artifact_id",
        "outbox_entry_id",
        "physical_transport_route_binding_id",
        "physical_transport_credential_assignment_binding_id",
        "idempotency_digest",
        "request_fingerprint",
    }
    assert not forbidden.intersection(data)


def test_post_rejects_wrong_workload_audience_subject_and_caller_fields() -> None:
    repository = InMemoryCapsuleConsumerBindingRepository()
    service = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService(
        repository=repository
    )
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
    )
    wrong_subject_service, wrong_subject_token = _workload_service_and_token(
        identity_id="service.workflow-protected-transport-target-context-capsule-consumer",
        audience=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
    )
    with TestClient(
        create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_transport_target_context_capsule_consumer_binding_service=service,
        )
    ) as client:
        wrong_audience = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(token, "audience.workflow.publisher"),
        )
        unsafe_payload = {
            **_payload(),
            "sealed_capsule_id": "sealed-capsule.caller-controlled",
            "consumer_subject_id": "service.caller-controlled",
            "outbox_entry_id": "outbox.caller-controlled",
        }
        caller_fields = client.post(
            ENDPOINT,
            json=unsafe_payload,
            headers=_workload_headers(
                token,
                WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
            ),
        )
    with TestClient(
        create_app(
            _settings(),
            workload_identity_service=wrong_subject_service,
            workflow_protected_transport_target_context_capsule_consumer_binding_service=service,
        )
    ) as client:
        wrong_subject = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                wrong_subject_token,
                WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
            ),
        )

    assert wrong_audience.status_code == 401
    assert wrong_subject.status_code == 401
    assert caller_fields.status_code == 422
    assert repository.calls == []


def test_human_reads_minimized_inventory_with_normal_password_session() -> None:
    service = _service()
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
    )
    with TestClient(
        create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_transport_target_context_capsule_consumer_binding_service=service,
        )
    ) as client:
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
            ),
        )
        assert created.status_code == 201
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 200
    _assert_no_store(response)
    _assert_no_step_up_language(response.text)
    body = response.json()
    assert set(body["data"]) == {
        "physical_transport_target_context_capsule_consumer_bindings",
        "server_time",
        "durable",
    }
    item = body["data"]["physical_transport_target_context_capsule_consumer_bindings"][0]
    assert set(item) == {
        "binding_id",
        "scope",
        "state",
        "bound_at",
        "effective_until",
        "consumer_contract_id",
        "consumer_contract_version",
        "purpose_id",
        "policy",
        "authority",
        "integrity_reference",
    }
    _assert_zero_authority(item["authority"])
    serialized = str(item).lower()
    for forbidden in (
        "sealed_capsule",
        "opening_result_digest",
        "event_artifact",
        "outbox_entry",
        "idempotency",
        "request_fingerprint",
    ):
        assert forbidden not in serialized


def test_human_session_cannot_bind_and_anonymous_read_fails_closed() -> None:
    with TestClient(
        create_app(
            _settings(),
            workflow_protected_transport_target_context_capsule_consumer_binding_service=(
                _service()
            ),
        )
    ) as client:
        anonymous = client.get(ENDPOINT)
        csrf = _login(client)
        human_post = client.post(
            ENDPOINT,
            json=_payload(),
            headers={"X-CSRF-Token": csrf},
        )

    assert anonymous.status_code == 403
    assert human_post.status_code == 401
    _assert_no_store(anonymous)
    _assert_no_store(human_post)


def test_default_composition_exposes_only_fail_closed_inventory() -> None:
    with TestClient(create_app(_settings())) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 503
    _assert_no_store(response)
    assert response.json()["code"] == (
        "workflow_target_context_capsule_consumer_binding_service_unavailable"
    )
