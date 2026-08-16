from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
)
from test_workflow_protected_resident_context_access_consumption_domain import (
    NOW,
    SUCCESS,
    _attempt,
    _result,
)
from test_workflow_protected_resident_context_access_consumption_domain import (
    _payload as _domain_payload,
)
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)

from atlas.api.app import create_app
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedResidentContextAccessConsumptionPresentation,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessConsumptionAttempt,
    WorkflowProtectedResidentContextAccessConsumptionResult,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_resident_context_access_consumption_policy,
)

ENDPOINT = "/api/v1/workflows/protected-resident-context-access-consumptions"
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")
SERVER_TIME = NOW + timedelta(milliseconds=400)


def _copy_values(value: Any) -> dict[str, object]:
    return {
        field.name: getattr(value, field.name)
        for field in fields(value)
        if field.name != "canonical_digest"
    }


def _presentation() -> WorkflowProtectedResidentContextAccessConsumptionPresentation:
    attempt_values = _copy_values(_attempt())
    attempt_values["scope"] = SCOPE
    attempt = WorkflowProtectedResidentContextAccessConsumptionAttempt(
        **cast(Any, attempt_values),
        canonical_digest=canonical_digest(_domain_payload(attempt_values)),
    )
    result_values = _copy_values(_result(SUCCESS))
    result_values["scope"] = SCOPE
    result_values["attempt_digest"] = attempt.canonical_digest
    result = WorkflowProtectedResidentContextAccessConsumptionResult(
        **cast(Any, result_values),
        canonical_digest=canonical_digest(_domain_payload(result_values)),
    )
    return WorkflowProtectedResidentContextAccessConsumptionPresentation(attempt, result)


class _Service:
    durable = True

    def __init__(self) -> None:
        self.repository = self
        self.presentation = _presentation()
        self.calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return SERVER_TIME

    async def consume(
        self, **kwargs: Any
    ) -> WorkflowProtectedResidentContextAccessConsumptionPresentation:
        self.calls.append(kwargs)
        return self.presentation

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedResidentContextAccessConsumptionPresentation, ...]:
        return (self.presentation,) if scope == SCOPE and limit == 256 else ()


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def consume(
        self, **kwargs: Any
    ) -> WorkflowProtectedResidentContextAccessConsumptionPresentation:
        del kwargs
        raise RuntimeError("database unavailable")

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedResidentContextAccessConsumptionPresentation, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")


def _request_payload() -> dict[str, object]:
    policy = code_owned_workflow_protected_resident_context_access_consumption_policy()
    return {
        "authorization_lease_id": (
            "workflow-protected-resident-context-access-lease.0123456789abcdef01234567"
        ),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "resident-context-access-consumption-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def _app(
    service: _Service,
    *,
    identity_id: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
) -> tuple[FastAPI, str]:
    workload_service, token = _workload_service_and_token(
        identity_id=identity_id,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    return (
        create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_resident_context_access_consumption_service=cast(Any, service),
        ),
        token,
    )


def test_workload_post_and_password_browser_session_get_are_minimized_no_store() -> None:
    service = _Service()
    app, token = _app(service)
    with TestClient(app) as client:
        anonymous_get = client.get(ENDPOINT)
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        human_post = client.post(ENDPOINT, json=_request_payload(), headers={"X-CSRF-Token": csrf})
        personal_post = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers={"Authorization": f"Bearer {personal_token}"},
        )
        ai_post = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers={"Authorization": "Bearer ai.identity.untrusted"},
        )
        created = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
        inventory = client.get(ENDPOINT)
        client.cookies.clear()
        personal_get = client.get(ENDPOINT, headers={"Authorization": f"Bearer {personal_token}"})
        workload_get = client.get(
            ENDPOINT,
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )

    assert anonymous_get.status_code == 403
    assert human_post.status_code == 401
    assert personal_post.status_code == 401
    assert ai_post.status_code == 401
    assert created.status_code == 201
    assert inventory.status_code == 200
    assert personal_get.status_code == 403
    assert workload_get.status_code == 401
    item = dict(created.json()["data"])
    assert set(item) == {
        "access_id",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "consumer_contract_id",
        "consumer_contract_version",
        "purpose_id",
        "accessor_contract_id",
        "accessor_contract_version",
        "accessor_profile_reference",
        "runtime_profile_reference",
        "policy_id",
        "policy_version",
        "authority",
        "integrity_reference",
    }
    assert item["result_state"] == "handle_established_in_protected_boundary"
    assert len(item["authority"]) == 20
    assert all(value is False for value in item["authority"].values())
    assert inventory.json()["data"]["consumptions"] == [item]
    forbidden_key_fragments = {
        "lease",
        "opening",
        "context_id",
        "handle_id",
        "receipt",
        "attestation",
        "fence",
        "idempotency",
        "nonce",
        "fingerprint",
    }
    assert not any(fragment in key for key in item for fragment in forbidden_key_fragments)
    for response in (
        anonymous_get,
        human_post,
        personal_post,
        ai_post,
        created,
        inventory,
        personal_get,
        workload_get,
    ):
        _assert_no_store(response)


def test_post_forbids_caller_owned_digest_context_handle_and_internal_fields() -> None:
    service = _Service()
    app, token = _app(service)
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    unsafe_fields: tuple[tuple[str, object], ...] = (
        ("authorization_lease_digest", "a" * 64),
        ("protected_resident_context_id", "resident-context.untrusted"),
        ("runtime_handle_profile_id", "profile.untrusted"),
        ("runtime_handle_locator", "locator.untrusted"),
        ("destination_fencing_token_digest", "b" * 64),
        ("access_deadline", SERVER_TIME.isoformat()),
        ("authority", {"execution_authorized": True}),
    )
    with TestClient(app) as client:
        for field, value in unsafe_fields:
            response = client.post(
                ENDPOINT,
                json={**_request_payload(), field: value},
                headers=headers,
            )
            assert response.status_code == 422
            _assert_no_store(response)
    assert service.calls == []


def test_wrong_workload_and_repository_outage_fail_closed_non_oracle() -> None:
    wrong_service = _Service()
    wrong_app, wrong_token = _app(wrong_service, identity_id="service.workflow-unrelated")
    with TestClient(wrong_app) as client:
        wrong = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                wrong_token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
    assert wrong.status_code == 401
    assert wrong_service.calls == []
    _assert_no_store(wrong)

    failing_app, token = _app(_FailingService())
    with TestClient(failing_app, raise_server_exceptions=False) as client:
        _login(client)
        inventory = client.get(ENDPOINT)
        created = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
    for response in (inventory, created):
        assert response.status_code == 503
        assert response.json()["code"] == (
            "workflow_protected_resident_context_access_consumption_service_unavailable"
        )
        assert "lease" not in response.json()["detail"].lower()
        assert "context" not in response.json()["detail"].lower()
        _assert_no_store(response)
