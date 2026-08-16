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
from atlas.modules.workflows.adapters import (
    DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector,
    DeterministicDevelopmentWorkflowProtectedRuntimeSlotReadinessAttestor,
    UnavailableWorkflowProtectedRuntimeContextTrustedInjector,
    UnavailableWorkflowProtectedRuntimeSlotReadinessAttestor,
)
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedRuntimeContextInjectionConsumptionPresentation,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextInjectionConsumptionResultState,
    WorkflowScope,
    code_owned_workflow_protected_runtime_context_injection_consumption_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-context-injection-consumptions"
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
SERVER_TIME = NOW + timedelta(milliseconds=400)


def _presentation() -> WorkflowProtectedRuntimeContextInjectionConsumptionPresentation:
    policy = code_owned_workflow_protected_runtime_context_injection_consumption_policy()
    attempt = SimpleNamespace(
        injection_id=(
            "workflow-protected-runtime-context-injection-consumption.0123456789abcdef01234567"
        ),
        scope=SCOPE,
        started_at=NOW,
        injection_deadline=NOW + timedelta(seconds=1),
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        approved_injector_id=policy.approved_injector_id,
        approved_injector_version=policy.approved_injector_version,
        runtime_slot_profile_digest=policy.runtime_slot_profile_digest,
    )
    result = SimpleNamespace(
        state=(
            WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTED_INTO_PROTECTED_RUNTIME_SLOT
        ),
        completed_at=NOW + timedelta(milliseconds=200),
    )
    return WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(
        attempt=cast(Any, attempt),
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
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionPresentation:
        self.calls.append(kwargs)
        return self.presentation

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextInjectionConsumptionPresentation, ...]:
        return (self.presentation,) if scope == SCOPE and limit == 256 else ()


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def consume(
        self, **kwargs: Any
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionPresentation:
        del kwargs
        raise RuntimeError("database unavailable")

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextInjectionConsumptionPresentation, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")


def _request_payload() -> dict[str, object]:
    policy = code_owned_workflow_protected_runtime_context_injection_consumption_policy()
    return {
        "authorization_lease_id": (
            "workflow-protected-runtime-context-injection-lease.0123456789abcdef01234567"
        ),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "runtime-context-injection-consumption-api-0001",
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
            workflow_protected_runtime_context_injection_consumption_service=cast(Any, service),
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
        "injection_id",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "policy_id",
        "policy_version",
        "injector_profile_reference",
        "runtime_slot_profile_reference",
        "integrity_reference",
    }
    assert item["result_state"] == "injected_into_protected_runtime_slot"
    assert inventory.json()["data"] == {
        "consumptions": [item],
        "server_time": SERVER_TIME.isoformat().replace("+00:00", "Z"),
        "durable": True,
    }
    forbidden_key_fragments = {
        "lease",
        "handle",
        "locator",
        "receipt",
        "slot_commitment",
        "pre_generation",
        "post_generation",
        "idempotency",
        "nonce",
        "fence",
        "credential",
        "secret",
    }
    assert not any(fragment in key for key in item for fragment in forbidden_key_fragments)
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


def test_post_forbids_caller_owned_handle_slot_receipt_and_internal_fields() -> None:
    service = _Service()
    app, token = _app(service)
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    unsafe_fields: tuple[tuple[str, object], ...] = (
        ("authorization_lease_digest", "a" * 64),
        ("protected_runtime_handle_id", "runtime-handle.untrusted"),
        ("protected_runtime_handle_digest", "b" * 64),
        ("runtime_handle_locator", "locator.untrusted"),
        ("runtime_slot_commitment", "c" * 64),
        ("runtime_slot_pre_generation", 7),
        ("injector_receipt", {"canonical_digest": "d" * 64}),
        ("injection_deadline", SERVER_TIME.isoformat()),
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
            "workflow_protected_runtime_context_injection_consumption_service_unavailable"
        )
        detail = response.json()["detail"].lower()
        assert "lease" not in detail
        assert "handle" not in detail
        assert "slot" not in detail
        assert "receipt" not in detail
        _assert_no_store(response)


def test_default_composition_is_fail_closed_and_development_adapters_are_io_free() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        production_service = cast(
            Any,
            cast(
                Any, client.app
            ).state.workflow_protected_runtime_context_injection_consumption_service,
        )
        assert production_service.repository.durable is False
        assert isinstance(
            production_service._slot_readiness_attestor,
            UnavailableWorkflowProtectedRuntimeSlotReadinessAttestor,
        )
        assert isinstance(
            production_service._injector,
            UnavailableWorkflowProtectedRuntimeContextTrustedInjector,
        )
        assert production_service._slot_readiness_attestor.available is False
        assert production_service._injector.available is False

    with TestClient(create_app(_settings())) as client:
        development_service = cast(
            Any,
            cast(
                Any, client.app
            ).state.workflow_protected_runtime_context_injection_consumption_service,
        )
        assert development_service.repository.durable is False
        assert isinstance(
            development_service._slot_readiness_attestor,
            DeterministicDevelopmentWorkflowProtectedRuntimeSlotReadinessAttestor,
        )
        assert isinstance(
            development_service._injector,
            DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector,
        )
        assert development_service._slot_readiness_attestor.available is True
        assert development_service._injector.available is True
        assert development_service._slot_readiness_attestor.calls == []
        assert development_service._injector.calls == []
