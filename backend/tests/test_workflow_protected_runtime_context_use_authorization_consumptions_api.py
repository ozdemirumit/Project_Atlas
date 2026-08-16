from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
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

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState,
    WorkflowScope,
    code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-context-use-authorization-consumptions"
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
SERVER_TIME = NOW + timedelta(milliseconds=200)


def _presentation() -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()
    consumption_id = (
        "workflow-protected-runtime-context-use-authorization-consumption.0123456789abcdef01234567"
    )
    claim = SimpleNamespace(
        consumption_claim_id=(
            "workflow-protected-runtime-context-use-authorization-consumption-claim."
            "0123456789abcdef01234567"
        ),
        consumption_id=consumption_id,
        canonical_digest="a" * 64,
        authorization_lease_id=(
            "workflow-protected-runtime-context-use-lease.0123456789abcdef01234567"
        ),
        authorization_lease_digest="b" * 64,
        scope=SCOPE,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        policy_digest=policy.canonical_digest,
        source_policy_digest=policy.source_policy_digest,
        claimed_at=NOW,
    )
    result = SimpleNamespace(
        consumption_id=consumption_id,
        consumption_claim_id=claim.consumption_claim_id,
        consumption_claim_digest=claim.canonical_digest,
        authorization_lease_id=claim.authorization_lease_id,
        authorization_lease_digest=claim.authorization_lease_digest,
        scope=SCOPE,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        purpose_id=policy.purpose_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_digest=policy.canonical_digest,
        source_policy_digest=policy.source_policy_digest,
        state=(
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState.AUTHORIZATION_CONSUMED_WITHOUT_RUNTIME_USE
        ),
        consumed_at=NOW,
        authorization_lease_consumed=True,
        authority=WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority(),
    )
    return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation(
        claim=cast(Any, claim),
        result=cast(Any, result),
    )


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
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation:
        self.calls.append(kwargs)
        return self.presentation

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation, ...]:
        return (self.presentation,) if scope == SCOPE and limit == 256 else ()


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def consume(
        self, **kwargs: Any
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation:
        del kwargs
        raise RuntimeError("database unavailable")

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")


def _request_payload() -> dict[str, object]:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()
    return {
        "authorization_lease_id": (
            "workflow-protected-runtime-context-use-lease.0123456789abcdef01234567"
        ),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "idempotency_key": "runtime-context-use-authorization-consumption-api-0001",
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
            workflow_protected_runtime_context_use_authorization_consumption_service=cast(
                Any, service
            ),
        ),
        token,
    )


def test_password_browser_get_and_exact_workload_post_are_minimized_no_store() -> None:
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
    assert "WWW-Authenticate" not in inventory.headers
    assert "authorized browser" not in inventory.text.lower()
    assert "mfa" not in inventory.text.lower()
    assert personal_get.status_code == 403
    assert workload_get.status_code == 401
    item = dict(created.json()["data"])
    assert set(item) == {
        "consumption_id",
        "state",
        "consumed_at",
        "consumer_contract_id",
        "consumer_contract_version",
        "purpose_id",
        "policy_id",
        "policy_version",
        "lease_consumed",
        "protected_runtime_context_use_authority_granted",
        "authority",
        "integrity_reference",
    }
    assert item["state"] == "authorization_consumed_without_runtime_use"
    assert item["lease_consumed"] is True
    assert item["protected_runtime_context_use_authority_granted"] is False
    assert set(item["authority"].values()) == {False}
    assert inventory.json()["data"] == {
        "consumptions": [item],
        "server_time": SERVER_TIME.isoformat().replace("+00:00", "Z"),
        "durable": True,
    }
    serialized = str(item).lower()
    for forbidden in (
        "authorization_lease_id",
        "upstream",
        "context_id",
        "context_digest",
        "context_locator",
        "runtime_slot",
        "destination",
        "fencing",
        "idempotency",
        "audit",
    ):
        assert forbidden not in serialized
    assert len(service.calls) == 1
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


def test_post_forbids_caller_owned_lineage_context_and_authority_fields() -> None:
    service = _Service()
    app, token = _app(service)
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    unsafe_fields: tuple[tuple[str, object], ...] = (
        ("authorization_lease_digest", "a" * 64),
        ("authorization_claim_id", "claim.untrusted"),
        ("injection_result_id", "injection.untrusted"),
        ("runtime_slot_commitment", "b" * 64),
        ("destination_fencing_token_digest", "c" * 64),
        ("context", {"protected": True}),
        ("authority", {"execution_authorized": True}),
        ("consumption_audit_payload", {"event": "untrusted"}),
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


def test_wrong_workload_and_service_outage_fail_closed_non_oracle() -> None:
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
            "workflow_protected_runtime_context_use_authorization_consumption_service_unavailable"
        )
        detail = response.json()["detail"].lower()
        for forbidden in (
            "lease id",
            "context id",
            "context digest",
            "slot commitment",
            "destination",
            "fence",
        ):
            assert forbidden not in detail
        _assert_no_store(response)


def test_default_composition_is_fail_closed_without_memory_fallback() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        service = cast(
            Any,
            cast(
                Any, client.app
            ).state.workflow_protected_runtime_context_use_authorization_consumption_service,
        )
        assert service.repository.durable is False

    with TestClient(create_app(_settings())) as client:
        service = cast(
            Any,
            cast(
                Any, client.app
            ).state.workflow_protected_runtime_context_use_authorization_consumption_service,
        )
        assert service.repository.durable is False
