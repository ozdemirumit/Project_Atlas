from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

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
from atlas.modules.authorization.application.bootstrap import (
    build_development_authorization_service,
    workflow_protected_runtime_start_consumption_scope,
)
from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartConsumptionError,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionAttemptState,
    WorkflowProtectedRuntimeStartConsumptionResultState,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-start-consumptions"
NOW = datetime(2026, 8, 17, 8, 30, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _attempt(suffix: str) -> SimpleNamespace:
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    return SimpleNamespace(
        attempt_id=f"workflow-protected-runtime-start-attempt.{suffix}",
        consumption_id=f"workflow-protected-runtime-start-consumption.{suffix}",
        canonical_digest=(suffix[0] * 64),
        scope=SCOPE,
        state=(WorkflowProtectedRuntimeStartConsumptionAttemptState.RUNTIME_START_ATTEMPT_STARTED),
        started_at=NOW,
        invocation_deadline=NOW + timedelta(seconds=10),
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        runtime_start_profile_digest=policy.runtime_start_profile_digest,
    )


def _result(
    attempt: SimpleNamespace,
    state: WorkflowProtectedRuntimeStartConsumptionResultState,
) -> SimpleNamespace:
    terminal = state is not (
        WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_OUTCOME_UNCERTAIN
    )
    return SimpleNamespace(
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        consumption_id=attempt.consumption_id,
        scope=attempt.scope,
        state=state,
        completed_at=NOW + timedelta(seconds=1) if terminal else None,
        recorded_at=NOW + timedelta(seconds=2),
        runtime_started=(
            True
            if state
            is (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
            else (
                False
                if state
                is (
                    WorkflowProtectedRuntimeStartConsumptionResultState
                ).RUNTIME_START_FAILED_WITHOUT_START
                else None
            )
        ),
    )


def _presentations() -> tuple[SimpleNamespace, ...]:
    pending = _attempt("a-pending")
    success = _attempt("b-success")
    failed = _attempt("c-known-failure")
    uncertain = _attempt("d-uncertain")
    return (
        SimpleNamespace(attempt=pending, result=None),
        SimpleNamespace(
            attempt=success,
            result=_result(
                success,
                WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_STARTED_IN_PROTECTED_BOUNDARY,
            ),
        ),
        SimpleNamespace(
            attempt=failed,
            result=_result(
                failed,
                WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_FAILED_WITHOUT_START,
            ),
        ),
        SimpleNamespace(
            attempt=uncertain,
            result=_result(
                uncertain,
                WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_OUTCOME_UNCERTAIN,
            ),
        ),
    )


class _Service:
    durable = True

    def __init__(self, presentations: tuple[SimpleNamespace, ...] | None = None) -> None:
        self.repository = self
        self.presentations = presentations or (_presentations()[0],)
        self.calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return NOW + timedelta(seconds=3)

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[SimpleNamespace, ...]:
        assert scope == SCOPE
        assert limit == 256
        return self.presentations

    async def consume(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self.presentations[0]


class _FailingInventoryService(_Service):
    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[SimpleNamespace, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")


class _UncertainService(_Service):
    async def consume(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        raise WorkflowProtectedRuntimeStartConsumptionError(
            "protected_runtime_start_outcome_uncertain"
        )


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


def _payload() -> dict[str, object]:
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    return {
        "authorization_lease_id": (
            "workflow-protected-runtime-start-lease.0123456789abcdef01234567"
        ),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "idempotency_key": "runtime-start-consumption-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def _exact_workload() -> tuple[Any, str]:
    return _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )


def test_read_consumption_uses_distinct_c1_scope_and_role_assignment() -> None:
    settings = _settings()
    service = build_development_authorization_service(settings, _AuditSink())
    scope = workflow_protected_runtime_start_consumption_scope(
        settings.development_organization_id,
        settings.environment,
    )

    assert scope.resource_id == "resource.workflow.protected-runtime-start-consumptions"
    assert scope.capability_class.value == "C1"
    assignments = cast(Any, service)._assignments
    assert any(
        assignment.assignment_id
        == "assignment.development.workflow-protected-runtime-start-consumptions"
        and assignment.scope == scope
        for assignment in assignments
    )


def test_production_defaults_fail_closed_and_development_components_are_explicit() -> None:
    production = create_app(Settings(environment="production", enable_api_docs=False))
    development = create_app(_settings())

    with TestClient(production):
        service = cast(Any, production.state.workflow_protected_runtime_start_consumption_service)
        assert service.repository.durable is False
        assert service._starter.available is False
        assert service._instruction_signer.available is False
        assert type(service._instruction_signature_verifier).__name__ == (
            "DenyAllWorkflowProtectedRuntimeStartInstructionSignatureVerifier"
        )
        assert type(service._receipt_signature_verifier).__name__ == (
            "DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier"
        )
    with TestClient(development):
        service = cast(Any, development.state.workflow_protected_runtime_start_consumption_service)
        assert type(service._starter).__name__ == (
            "DeterministicDevelopmentWorkflowProtectedRuntimeStarter"
        )
        assert type(service._instruction_signer).__name__ == (
            "DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSigner"
        )
        assert type(service._instruction_signature_verifier).__name__ == (
            "DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier"
        )
        assert type(service._receipt_signature_verifier).__name__ == (
            "DeterministicDevelopmentWorkflowProtectedRuntimeStartReceiptSignatureVerifier"
        )
        assert service._starter.available is True
        assert service._instruction_signer.available is True


def test_password_session_get_returns_exact_minimized_outcome_projection() -> None:
    service = _Service(_presentations())
    app = create_app(
        _settings(),
        workflow_protected_runtime_start_consumption_service=cast(Any, service),
    )
    with TestClient(app) as client:
        csrf = _login(client)
        del csrf
        response = client.get(ENDPOINT)

    assert response.status_code == 200
    _assert_no_store(response)
    payload = response.json()["data"]
    assert set(payload) == {"starts", "server_time", "durable"}
    assert payload["durable"] is True
    starts = payload["starts"]
    assert len(starts) == 4
    expected_keys = {
        "start_id",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "recorded_at",
        "runtime_started",
        "policy_reference",
        "runtime_start_profile_reference",
        "effective_authority",
    }
    assert all(set(item) == expected_keys for item in starts)
    assert [item["result_state"] for item in starts] == [
        None,
        "runtime_started_in_protected_boundary",
        "runtime_start_failed_without_start",
        "runtime_start_outcome_uncertain",
    ]
    assert [item["runtime_started"] for item in starts] == [None, True, False, None]
    assert starts[0]["completed_at"] is None
    assert starts[0]["recorded_at"] is None
    assert starts[3]["completed_at"] is None
    assert starts[3]["recorded_at"] is not None
    assert all(item["effective_authority"] is False for item in starts)
    assert all(item["attempt_state"] == "runtime_start_attempt_started" for item in starts)
    protected_fragments = {
        "authorization",
        "claim",
        "digest",
        "envelope",
        "fence",
        "idempotency",
        "instruction",
        "locator",
        "nonce",
        "receipt",
        "slot",
    }
    assert not any(
        fragment in key for item in starts for key in item for fragment in protected_fragments
    )


def test_password_session_get_projects_expired_pending_attempt_as_uncertain() -> None:
    expired = _attempt("expired-pending")
    expired.invocation_deadline = NOW + timedelta(seconds=1)
    service = _Service((SimpleNamespace(attempt=expired, result=None),))
    app = create_app(
        _settings(),
        workflow_protected_runtime_start_consumption_service=cast(Any, service),
    )
    with TestClient(app) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 200
    start = response.json()["data"]["starts"][0]
    assert start["result_state"] == "runtime_start_outcome_uncertain"
    assert start["completed_at"] is None
    assert datetime.fromisoformat(start["recorded_at"].replace("Z", "+00:00")) == (
        NOW + timedelta(seconds=3)
    )
    assert start["runtime_started"] is None


def test_password_session_get_never_labels_nondurable_evidence_as_durable() -> None:
    service = _Service()
    service.durable = False
    app = create_app(
        _settings(),
        workflow_protected_runtime_start_consumption_service=cast(Any, service),
    )
    with TestClient(app) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 503
    assert response.json()["code"] == (
        "workflow_protected_runtime_start_consumption_service_unavailable"
    )
    _assert_no_store(response)


def test_get_rejects_anonymous_pat_and_workload_sessions() -> None:
    workload_service, token = _exact_workload()
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_start_consumption_service=cast(Any, service),
    )
    with TestClient(app) as client:
        anonymous = client.get(ENDPOINT)
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        client.cookies.clear()
        personal = client.get(
            ENDPOINT,
            headers={"Authorization": f"Bearer {personal_token}"},
        )
        workload = client.get(
            ENDPOINT,
            headers=_workload_headers(
                token,
                WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            ),
        )

    assert anonymous.status_code == 403
    assert personal.status_code == 403
    assert workload.status_code == 401
    for response in (anonymous, personal, workload):
        _assert_no_store(response)


def test_get_inventory_outage_and_default_repository_fail_closed() -> None:
    for app in (
        create_app(
            _settings(),
            workflow_protected_runtime_start_consumption_service=cast(
                Any, _FailingInventoryService()
            ),
        ),
        create_app(_settings()),
    ):
        with TestClient(app, raise_server_exceptions=False) as client:
            _login(client)
            response = client.get(ENDPOINT)

        assert response.status_code == 503
        assert response.json()["code"] == (
            "workflow_protected_runtime_start_consumption_service_unavailable"
        )
        _assert_no_store(response)


def test_only_exact_workload_can_post_and_response_is_minimized() -> None:
    workload_service, token = _exact_workload()
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_start_consumption_service=cast(Any, service),
    )
    with TestClient(app) as client:
        csrf = _login(client)
        human = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
        personal_token = _issue_api_token(client, csrf)
        client.cookies.clear()
        personal = client.post(
            ENDPOINT,
            json=_payload(),
            headers={"Authorization": f"Bearer {personal_token}"},
        )
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            ),
        )

    assert human.status_code == 401
    assert personal.status_code == 401
    assert created.status_code == 201
    item = created.json()["data"]
    assert set(item) == {
        "start_id",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "recorded_at",
        "runtime_started",
        "policy_reference",
        "runtime_start_profile_reference",
        "effective_authority",
    }
    assert item["result_state"] is None
    assert item["effective_authority"] is False
    assert len(service.calls) == 1
    assert set(service.calls[0]) == {
        "authorization_lease_id",
        "policy_id",
        "policy_version",
        "irreversible_consumption_acknowledged",
        "uncertainty_no_retry_acknowledged",
        "idempotency_key",
        "context",
    }
    for response in (human, personal, created):
        _assert_no_store(response)


def test_ai_mcp_connector_and_generic_workers_are_rejected_before_service_io() -> None:
    for identity_id in (
        "service.ai-agent",
        "service.mcp-tool",
        "service.connector-runtime",
        "service.generic-worker",
    ):
        workload_service, token = _workload_service_and_token(
            identity_id=identity_id,
            audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        )
        service = _Service()
        app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_start_consumption_service=cast(Any, service),
        )
        with TestClient(app) as client:
            response = client.post(
                ENDPOINT,
                json=_payload(),
                headers=_workload_headers(
                    token,
                    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
                ),
            )

        assert response.status_code == 401
        assert service.calls == []
        _assert_no_store(response)


def test_post_requires_both_acknowledgements_and_forbids_extra_fields() -> None:
    workload_service, token = _exact_workload()
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_start_consumption_service=cast(Any, service),
    )
    headers = _workload_headers(
        token,
        WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    invalid_payloads = (
        {**_payload(), "irreversible_consumption_acknowledged": False},
        {**_payload(), "uncertainty_no_retry_acknowledged": False},
        {
            key: value
            for key, value in _payload().items()
            if key != "irreversible_consumption_acknowledged"
        },
        {
            key: value
            for key, value in _payload().items()
            if key != "uncertainty_no_retry_acknowledged"
        },
        {**_payload(), "retry_allowed": True},
        {**_payload(), "starter_id": "executor.untrusted"},
    )
    with TestClient(app) as client:
        responses = [
            client.post(ENDPOINT, json=payload, headers=headers) for payload in invalid_payloads
        ]

    assert all(response.status_code == 422 for response in responses)
    assert service.calls == []
    for response in responses:
        _assert_no_store(response)


def test_uncertain_post_is_conflict_and_explicitly_forbids_retry() -> None:
    workload_service, token = _exact_workload()
    service = _UncertainService()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_start_consumption_service=cast(Any, service),
    )
    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token,
                WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            ),
        )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "workflow_protected_runtime_start_outcome_uncertain"
    assert body["retryable"] is False
    assert "must not be retried" in body["detail"]
    assert len(service.calls) == 1
    _assert_no_store(response)
