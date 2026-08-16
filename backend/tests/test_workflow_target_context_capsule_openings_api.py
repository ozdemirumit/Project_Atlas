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
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)
from test_workflow_target_context_capsule_opening_consumption_domain import (
    NOW,
    SUCCESS_STATE,
    _attempt,
    _result,
)
from test_workflow_target_context_capsule_opening_consumption_domain import (
    _payload as _domain_payload,
)

from atlas.api.app import create_app
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResult,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy,
)

ENDPOINT = "/api/v1/workflows/physical-transport-target-context-capsule-openings"
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")
SERVER_TIME = NOW + timedelta(milliseconds=400)


def _copy_values(value: Any) -> dict[str, object]:
    return {
        field.name: getattr(value, field.name)
        for field in fields(value)
        if field.name != "canonical_digest"
    }


def _presentation() -> WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation:
    attempt_values = _copy_values(_attempt())
    attempt_values["scope"] = SCOPE
    attempt = WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt(
        **cast(Any, attempt_values),
        canonical_digest=canonical_digest(_domain_payload(attempt_values)),
    )
    result_values = _copy_values(_result(SUCCESS_STATE))
    result_values["scope"] = SCOPE
    result_values["attempt_digest"] = attempt.canonical_digest
    result = WorkflowProtectedTransportTargetContextCapsuleOpeningResult(
        **cast(Any, result_values),
        canonical_digest=canonical_digest(_domain_payload(result_values)),
    )
    return WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(attempt, result)


class _Service:
    durable = True

    def __init__(self) -> None:
        self.repository = self
        self.presentation = _presentation()
        self.calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return SERVER_TIME

    async def open(
        self, **kwargs: Any
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation:
        self.calls.append(kwargs)
        return self.presentation

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation, ...]:
        return (self.presentation,) if scope == SCOPE and limit == 256 else ()


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def open(
        self, **kwargs: Any
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation:
        del kwargs
        raise RuntimeError("database unavailable")

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")


class _CrossScopeService(_Service):
    def __init__(self) -> None:
        super().__init__()
        self.presentation = WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation(
            _attempt(), _result(SUCCESS_STATE)
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningPresentation, ...]:
        del scope, limit
        return (self.presentation,)


def _request_payload() -> dict[str, object]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    return {
        "authorization_lease_id": "target-context-capsule-opening-lease.api01",
        "authorization_lease_digest": "1" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "capsule-opening-api-0001",
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
            workflow_protected_transport_target_context_capsule_opening_service=cast(Any, service),
        ),
        token,
    )


def test_workload_post_and_human_session_get_are_minimized_and_no_store() -> None:
    service = _Service()
    app, token = _app(service)
    with TestClient(app) as client:
        anonymous = client.get(ENDPOINT)
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        human_post = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers={"X-CSRF-Token": csrf},
        )
        personal_post = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers={"Authorization": f"Bearer {personal_token}"},
        )
        created = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
        inventory = client.get(ENDPOINT)

    assert anonymous.status_code == 403
    assert human_post.status_code == 401
    assert personal_post.status_code == 401
    assert created.status_code == 201
    assert inventory.status_code == 200
    item = created.json()["data"]
    assert item == inventory.json()["data"]["physical_transport_target_context_capsule_openings"][0]
    assert set(item) == {
        "opening_id",
        "scope",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "consumer_contract_id",
        "consumer_contract_version",
        "purpose_id",
        "opener_contract_id",
        "opener_contract_version",
        "resident_context_profile_reference",
        "capsule_opened_in_protected_boundary",
        "target_context_pair_verified",
        "resident_context_is_bearer_capability",
        "policy_id",
        "policy_version",
        "authority",
        "integrity_reference",
    }
    assert item["attempt_state"] == "completed"
    assert item["result_state"] == "opened_in_protected_consumer_boundary"
    assert item["capsule_opened_in_protected_boundary"] is True
    assert item["target_context_pair_verified"] is True
    assert item["resident_context_is_bearer_capability"] is False
    assert len(item["authority"]) == 19
    assert not any(item["authority"].values())
    serialized = str(item)
    for protected_name in (
        "authorization_lease_id",
        "sealed_capsule_id",
        "consumer_receipt_id",
        "protected_resident_context_id",
        "canonical_digest",
    ):
        assert protected_name not in serialized
    assert len(service.calls) == 1
    for response in (anonymous, human_post, personal_post, created, inventory):
        _assert_no_store(response)


def test_post_rejects_wrong_workload_false_acknowledgement_and_protected_fields() -> None:
    wrong_service = _Service()
    wrong_app, wrong_token = _app(wrong_service, identity_id="service.workflow-unrelated")
    with TestClient(wrong_app) as client:
        wrong_identity = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                wrong_token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
    assert wrong_identity.status_code == 401
    _assert_no_store(wrong_identity)
    assert wrong_service.calls == []

    service = _Service()
    app, token = _app(service)
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    with TestClient(app) as client:
        for payload in (
            {**_request_payload(), "irreversible_consumption_acknowledged": False},
            {**_request_payload(), "sealed_capsule_id": "sealed-capsule.forbidden"},
            {**_request_payload(), "opener_id": "opener.untrusted"},
        ):
            response = client.post(ENDPOINT, json=payload, headers=headers)
            assert response.status_code == 422
            _assert_no_store(response)
    assert service.calls == []


def test_repository_outages_are_non_oracle_no_store_503_for_get_and_post() -> None:
    app, token = _app(_FailingService())
    with TestClient(app, raise_server_exceptions=False) as client:
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
            "workflow_target_context_capsule_opening_service_unavailable"
        )
        assert "database" not in response.text.lower()
        _assert_no_store(response)


def test_cross_scope_service_output_is_rejected_before_presentation() -> None:
    app, token = _app(_CrossScopeService())
    with TestClient(app, raise_server_exceptions=False) as client:
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
        assert "scope" not in response.text.lower()
        _assert_no_store(response)
