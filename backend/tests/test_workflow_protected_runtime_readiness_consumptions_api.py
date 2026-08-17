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
    WORKFLOW_PROTECTED_RUNTIME_READINESS_CONSUMPTION_READ,
    build_development_authorization_service,
    workflow_protected_runtime_readiness_consumption_scope,
)
from atlas.modules.workflows.application.protected_runtime_readiness_consumption_ports import (
    WorkflowProtectedRuntimeReadinessConsumptionError,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WorkflowProtectedRuntimeReadinessConsumptionAttemptState,
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-readiness-consumptions"
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _attempt(suffix: str) -> SimpleNamespace:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    return SimpleNamespace(
        attempt_id=f"workflow-protected-runtime-readiness-attempt.{suffix}",
        consumption_id=f"workflow-protected-runtime-readiness-consumption.{suffix}",
        canonical_digest=(suffix[0] * 64),
        scope=SCOPE,
        state=(
            WorkflowProtectedRuntimeReadinessConsumptionAttemptState
        ).RUNTIME_READINESS_ATTEMPT_STARTED,
        started_at=NOW,
        invocation_deadline=NOW + timedelta(seconds=1),
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        readiness_profile_digest=policy.readiness_profile_digest,
    )


def _result(
    attempt: SimpleNamespace,
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState,
) -> SimpleNamespace:
    known = state in {
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READY_IN_PROTECTED_BOUNDARY,
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY,
    }
    failed = (
        state
        is (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
    )
    return SimpleNamespace(
        attempt_id=attempt.attempt_id,
        attempt_digest=attempt.canonical_digest,
        consumption_id=attempt.consumption_id,
        scope=attempt.scope,
        state=state,
        completed_at=None
        if state.value.endswith("uncertain")
        else NOW + timedelta(milliseconds=100),
        recorded_at=NOW + timedelta(milliseconds=200),
        runtime_ready=(
            True
            if state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
            else False
            if state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY
            else None
        ),
        outcome_known=known or failed,
    )


def _presentations() -> tuple[SimpleNamespace, ...]:
    pending = _attempt("a" * 24)
    ready = _attempt("b" * 24)
    not_ready = _attempt("c" * 24)
    failed = _attempt("d" * 24)
    uncertain = _attempt("e" * 24)
    states = WorkflowProtectedRuntimeReadinessConsumptionResultState
    return (
        SimpleNamespace(attempt=pending, result=None),
        SimpleNamespace(
            attempt=ready,
            result=_result(ready, states.RUNTIME_READY_IN_PROTECTED_BOUNDARY),
        ),
        SimpleNamespace(
            attempt=not_ready,
            result=_result(not_ready, states.RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY),
        ),
        SimpleNamespace(
            attempt=failed,
            result=_result(failed, states.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT),
        ),
        SimpleNamespace(
            attempt=uncertain,
            result=_result(uncertain, states.RUNTIME_READINESS_OUTCOME_UNCERTAIN),
        ),
    )


class _Service:
    durable = True

    def __init__(self) -> None:
        self.repository = self
        self.presentations = _presentations()
        self.calls: list[dict[str, Any]] = []
        self.inventory_calls = 0

    async def consume(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self.presentations[1]

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[SimpleNamespace, ...]:
        assert scope == SCOPE
        assert limit == 256
        self.inventory_calls += 1
        return self.presentations

    async def get_authoritative_time(self) -> datetime:
        return NOW + timedelta(milliseconds=500)


class _UnavailableService(_Service):
    async def consume(self, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        raise WorkflowProtectedRuntimeReadinessConsumptionError(
            "protected_runtime_readiness_consumption_repository_unavailable"
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[SimpleNamespace, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")


class _ConflictService(_Service):
    def __init__(self, code: str) -> None:
        super().__init__()
        self.code = code

    async def consume(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        raise WorkflowProtectedRuntimeReadinessConsumptionError(self.code)


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


def _payload() -> dict[str, object]:
    policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    return {
        "authorization_lease_id": (
            "workflow-protected-runtime-readiness-lease.0123456789abcdef01234567"
        ),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "idempotency_key": "runtime-readiness-consumption-api-0001",
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


def test_readiness_consumption_uses_distinct_c1_scope_and_role_assignment() -> None:
    settings = _settings()
    service = build_development_authorization_service(settings, _AuditSink())
    scope = workflow_protected_runtime_readiness_consumption_scope(
        settings.development_organization_id,
        settings.environment,
    )

    assert WORKFLOW_PROTECTED_RUNTIME_READINESS_CONSUMPTION_READ == (
        "workflow.protected-runtime-readiness-consumptions.read"
    )
    assert scope.resource_id == "resource.workflow.protected-runtime-readiness-consumptions"
    assert scope.capability_class.value == "C1"
    assignments = cast(Any, service)._assignments
    assert any(
        assignment.assignment_id
        == "assignment.development.workflow-protected-runtime-readiness-consumptions"
        and assignment.scope == scope
        for assignment in assignments
    )


def test_password_get_returns_exact_minimized_states_without_mfa_or_ad_management() -> None:
    service = _Service()
    app = create_app(
        _settings(),
        workflow_protected_runtime_readiness_consumption_service=cast(Any, service),
    )
    with TestClient(app) as client:
        anonymous = client.get(ENDPOINT)
        _login(client)
        response = client.get(ENDPOINT)

    assert anonymous.status_code == 403
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["durable"] is True
    items = body["data"]["readiness"]
    assert [item["result_state"] for item in items] == [
        None,
        "runtime_ready_in_protected_boundary",
        "runtime_not_ready_in_protected_boundary",
        "runtime_readiness_failed_without_assessment",
        "runtime_readiness_outcome_uncertain",
    ]
    assert set(items[0]) == {
        "readiness_id",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "recorded_at",
        "runtime_ready",
        "policy_reference",
        "readiness_profile_reference",
        "effective_authority",
    }
    assert [item["runtime_ready"] for item in items] == [None, True, False, None, None]
    assert all(item["effective_authority"] is False for item in items)
    serialized = str(body).lower()
    for forbidden in (
        "locator",
        "process_identifier",
        "runtime_context",
        "instruction",
        "nonce",
        "receipt",
        "endpoint",
        "credential",
        "mfa",
        "step-up",
        "authorized browser",
        "ad_management",
    ):
        assert forbidden not in serialized
    assert service.inventory_calls == 1
    _assert_no_store(anonymous)
    _assert_no_store(response)


def test_only_exact_workload_can_post_and_response_is_minimized() -> None:
    workload_service, token = _exact_workload()
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_readiness_consumption_service=cast(Any, service),
    )
    with TestClient(app) as client:
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        human = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
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
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )

    assert human.status_code == 401
    assert personal.status_code == 401
    assert created.status_code == 201, created.json()
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
    item = created.json()["data"]
    assert set(item) == {
        "readiness_id",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "recorded_at",
        "runtime_ready",
        "policy_reference",
        "readiness_profile_reference",
        "effective_authority",
    }
    for response in (human, personal, created):
        _assert_no_store(response)


def test_wrong_workloads_are_rejected_before_protected_state_io() -> None:
    for identity_id in (
        "service.ai-agent",
        "service.mcp-tool",
        "service.connector-runtime",
        "service.generic-worker",
        "service.recovery-worker",
    ):
        workload_service, token = _workload_service_and_token(
            identity_id=identity_id,
            audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        )
        service = _Service()
        app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_readiness_consumption_service=cast(Any, service),
        )
        with TestClient(app) as client:
            response = client.post(
                ENDPOINT,
                json=_payload(),
                headers=_workload_headers(
                    token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
                ),
            )

        assert response.status_code == 401
        assert service.calls == []
        assert service.inventory_calls == 0
        _assert_no_store(response)


def test_post_requires_acknowledgements_and_forbids_operational_fields() -> None:
    workload_service, token = _exact_workload()
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_readiness_consumption_service=cast(Any, service),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    invalid = (
        {**_payload(), "irreversible_consumption_acknowledged": False},
        {**_payload(), "uncertainty_no_retry_acknowledged": False},
        {**_payload(), "runtime_locator": "runtime.untrusted"},
        {**_payload(), "endpoint": "https://untrusted.invalid"},
        {**_payload(), "credential": "secret"},
        {**_payload(), "instruction": {"probe": True}},
        {**_payload(), "nonce": "caller-controlled"},
        {**_payload(), "receipt": {"ready": True}},
        {**_payload(), "authority": {"readiness_probe_authorized": True}},
    )
    with TestClient(app) as client:
        responses = [client.post(ENDPOINT, json=payload, headers=headers) for payload in invalid]

    assert all(response.status_code == 422 for response in responses)
    assert service.calls == []
    for response in responses:
        _assert_no_store(response)


def test_conflict_uncertainty_and_unavailable_are_non_oracular() -> None:
    workload_service, token = _exact_workload()
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    cases = (
        (_ConflictService("protected_runtime_readiness_consumption_lease_expired"), 409),
        (
            _ConflictService("protected_runtime_readiness_outcome_uncertain_no_retry"),
            409,
        ),
        (_UnavailableService(), 503),
    )
    for service, expected_status in cases:
        app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_readiness_consumption_service=cast(Any, service),
        )
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(ENDPOINT, json=_payload(), headers=headers)

        assert response.status_code == expected_status
        detail = response.json()["detail"].lower()
        for protected_name in ("lease", "slot", "attempt", "receipt"):
            assert protected_name not in detail
        if isinstance(service, _ConflictService) and "uncertain" in service.code:
            assert response.json()["retryable"] is False
        _assert_no_store(response)


def test_get_rejects_pat_and_workload_and_default_composition_fails_closed() -> None:
    workload_service, token = _exact_workload()
    app = create_app(_settings(), workload_identity_service=workload_service)
    with TestClient(app, raise_server_exceptions=False) as client:
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        unavailable = client.get(ENDPOINT)
        client.cookies.clear()
        personal = client.get(ENDPOINT, headers={"Authorization": f"Bearer {personal_token}"})
        workload = client.get(
            ENDPOINT,
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )

    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == (
        "workflow_protected_runtime_readiness_consumption_service_unavailable"
    )
    assert personal.status_code == 403
    assert workload.status_code == 401
    for response in (unavailable, personal, workload):
        _assert_no_store(response)


def test_production_defaults_fail_closed_and_development_components_are_explicit() -> None:
    production = create_app(Settings(environment="production", enable_api_docs=False))
    development = create_app(_settings())

    with TestClient(production):
        service = cast(
            Any, production.state.workflow_protected_runtime_readiness_consumption_service
        )
        assert service.repository.durable is False
        assert service._assessor.available is False
        assert service._instruction_signer.available is False
        assert service._instruction_signature_verifier.available is False
        assert service._receipt_signature_verifier.available is False
    with TestClient(development):
        service = cast(
            Any, development.state.workflow_protected_runtime_readiness_consumption_service
        )
        assert service.repository.durable is False
        assert type(service._assessor).__name__.startswith("DeterministicDevelopment")
        assert service._assessor.available is True
        assert service._instruction_signer.available is True
        assert service._instruction_signature_verifier.available is True
        assert service._receipt_signature_verifier.available is True
