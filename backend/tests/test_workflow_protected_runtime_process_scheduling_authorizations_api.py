from datetime import UTC, datetime, timedelta
from hashlib import sha256
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
from atlas.modules.authorization.application.bootstrap import (
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_AUTHORIZATION_READ,
    build_development_authorization_service,
    workflow_protected_runtime_process_scheduling_authorization_scope,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationError,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_authorization_domain import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority,
    WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_scheduling_authorization_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-process-scheduling-authorizations"
NOW = datetime(2026, 8, 20, 10, 30, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _lease(*, scope: WorkflowScope = SCOPE) -> SimpleNamespace:
    policy = code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()
    return SimpleNamespace(
        authorization_lease_id=(
            "workflow-protected-runtime-process-scheduling-authorization-lease."
            "0123456789abcdef01234567"
        ),
        process_creation_result_id=("workflow-protected-runtime-process-creation-result.imp-228"),
        canonical_digest="c" * 64,
        scope=scope,
        state=(
            WorkflowProtectedRuntimeProcessSchedulingAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        issued_at=NOW,
        valid_until=NOW + timedelta(seconds=1),
        effective_until=NOW + timedelta(seconds=1),
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        purpose_id=policy.purpose_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        authority=WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthority(
            protected_runtime_process_scheduling_authority_granted=True
        ),
    )


class _Service:
    durable = True

    def __init__(self, *, ignore_scope: bool = False) -> None:
        self.repository = self
        self.lease: SimpleNamespace | None = None
        self.evaluated_at = NOW + timedelta(milliseconds=500)
        self.calls: list[dict[str, Any]] = []
        self.repository_calls = 0
        self.ignore_scope = ignore_scope

    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        self.repository_calls += 1
        self.lease = _lease()
        return self.lease

    def _presentation(self, lease: SimpleNamespace) -> SimpleNamespace:
        active = lease.issued_at <= self.evaluated_at < lease.valid_until
        return SimpleNamespace(
            lease=lease,
            consumed=False,
            evaluated_at=self.evaluated_at,
            effective_state=(
                WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState.ACTIVE
                if active
                else WorkflowProtectedRuntimeProcessSchedulingAuthorizationPresentationState.EXPIRED
            ),
            protected_runtime_process_scheduling_authority_granted=active,
        )

    async def list_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> SimpleNamespace:
        del limit
        self.repository_calls += 1
        presentations: tuple[SimpleNamespace, ...] = (
            ()
            if self.lease is None or (not self.ignore_scope and self.lease.scope != scope)
            else (self._presentation(self.lease),)
        )
        if authorization_lease_ids is not None:
            presentations = tuple(
                presentation
                for presentation in presentations
                if presentation.lease.authorization_lease_id in authorization_lease_ids
            )
        return SimpleNamespace(server_time=self.evaluated_at, presentations=presentations)


class _FailingService(_Service):
    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        self.repository_calls += 1
        raise WorkflowProtectedRuntimeProcessSchedulingAuthorizationError(
            "workflow_protected_runtime_process_scheduling_repository_unavailable"
        )

    async def list_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> SimpleNamespace:
        del scope, authorization_lease_ids, limit
        self.repository_calls += 1
        raise RuntimeError("database unavailable")


class _ConflictService(_Service):
    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        self.repository_calls += 1
        raise WorkflowProtectedRuntimeProcessSchedulingAuthorizationError(
            "workflow_protected_runtime_process_scheduling_idempotency_conflict"
        )


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


def _payload() -> dict[str, object]:
    policy = code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()
    return {
        "process_creation_result_id": (
            "workflow-protected-runtime-process-creation-result.imp-228"
        ),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "single_use_nonrenewable_nontransferable_future_request_acknowledged": True,
        "no_scheduling_resume_dispatch_or_execution_authority_acknowledged": True,
        "idempotency_key": "runtime-process-scheduling-authorization-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_read_authorization_has_dedicated_permission_c1_scope_and_assignment() -> None:
    settings = _settings()
    service = build_development_authorization_service(settings, _AuditSink())
    scope = workflow_protected_runtime_process_scheduling_authorization_scope(
        settings.development_organization_id,
        settings.environment,
    )

    assert WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_AUTHORIZATION_READ == (
        "workflow.protected-runtime-process-scheduling-authorizations.read"
    )
    assert scope.resource_id == (
        "resource.workflow.protected-runtime-process-scheduling-authorizations"
    )
    assert scope.capability_class.value == "C1"
    assignments = cast(Any, service)._assignments
    assert any(
        assignment.assignment_id
        == "assignment.development.workflow-protected-runtime-process-scheduling-authorizations"
        and assignment.scope == scope
        for assignment in assignments
    )


def test_exact_workload_post_and_password_session_get_are_minimized_without_mfa() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_process_scheduling_authorization_service=cast(Any, service),
    )

    with TestClient(app) as client:
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
        _login(client)
        inventory = client.get(ENDPOINT)

    assert created.status_code == 201
    assert inventory.status_code == 200
    item = created.json()["data"]
    assert set(item) == {
        "authorization_lease_id",
        "process_creation_result_reference",
        "state",
        "effective_state",
        "issued_at",
        "valid_until",
        "effective_until",
        "consumer_contract_id",
        "consumer_contract_version",
        "purpose_id",
        "policy_id",
        "policy_version",
        "authority",
        "integrity_reference",
    }
    assert item["process_creation_result_reference"] == (
        "integrity.workflow-protected-runtime-process-creation-result."
        f"{sha256(cast(str, _payload()['process_creation_result_id']).encode('utf-8')).hexdigest()[:24]}"  # noqa: E501
    )
    assert item["integrity_reference"] == (
        "integrity.workflow-protected-runtime-process-scheduling-authorization."
        f"{sha256(item['authorization_lease_id'].encode('utf-8')).hexdigest()[:24]}"
    )
    assert item["state"] == "authorized_unconsumed"
    assert item["effective_state"] == "active"
    assert item["authority"]["protected_runtime_process_scheduling_authority_granted"] is True
    assert sum(value is True for value in item["authority"].values()) == 1
    assert inventory.json()["data"]["authorizations"] == [item]
    assert inventory.json()["data"]["durable"] is True
    assert set(service.calls[0]) == {
        "process_creation_result_id",
        "policy_id",
        "policy_version",
        "single_use_nonrenewable_nontransferable_future_request_acknowledged",
        "no_scheduling_resume_dispatch_or_execution_authority_acknowledged",
        "idempotency_key",
        "context",
    }
    forbidden_material = {
        "command",
        "executable",
        "args",
        "env",
        "prompt",
        "model",
        "network",
        "connector",
        "provider",
        "runtime_locator",
        "process_identifier",
        "attestation",
        "receipt",
        "nonce",
        "idempotency_key",
    }
    assert forbidden_material.isdisjoint(item)
    _assert_no_store(created)
    _assert_no_store(inventory)


def test_active_and_expired_inventory_projects_authority_from_server_time() -> None:
    service = _Service()
    service.lease = _lease()
    app = create_app(
        _settings(),
        workflow_protected_runtime_process_scheduling_authorization_service=cast(Any, service),
    )

    with TestClient(app) as client:
        _login(client)
        active = client.get(ENDPOINT)
        service.evaluated_at = NOW + timedelta(seconds=1)
        expired = client.get(ENDPOINT)

    active_item = active.json()["data"]["authorizations"][0]
    expired_item = expired.json()["data"]["authorizations"][0]
    assert active_item["effective_state"] == "active"
    assert active_item["authority"]["protected_runtime_process_scheduling_authority_granted"]
    assert expired_item["effective_state"] == "expired"
    assert not any(expired_item["authority"].values())


def test_strict_post_rejects_operational_material_and_false_acknowledgements_before_io() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_process_scheduling_authorization_service=cast(Any, service),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    forbidden_inputs: tuple[tuple[str, object], ...] = (
        ("process_creation_result_digest", "a" * 64),
        ("ttl_seconds", 300),
        ("authority", {"execution_authorized": True}),
        ("schedule", {"priority": "high"}),
        ("queue", "runtime.queue"),
        ("runtime_locator", "runtime.untrusted"),
        ("process_identifier", "process.untrusted"),
        ("command", "start-service"),
        ("executable", "powershell.exe"),
        ("args", ["-Command", "Get-Service"]),
        ("env", {"TOKEN": "secret"}),
        ("prompt", "schedule a process"),
        ("model", "local-llm"),
        ("network", {"host": "example.invalid"}),
        ("connector", {"id": "connector.untrusted"}),
        ("provider", {"id": "provider.untrusted"}),
        ("process_state_attestation_id", "attestation.untrusted"),
    )

    with TestClient(app) as client:
        for field_name, value in forbidden_inputs:
            response = client.post(
                ENDPOINT,
                json={**_payload(), field_name: value},
                headers=headers,
            )
            assert response.status_code == 422
            _assert_no_store(response)
        for field_name in (
            "single_use_nonrenewable_nontransferable_future_request_acknowledged",
            "no_scheduling_resume_dispatch_or_execution_authority_acknowledged",
        ):
            response = client.post(
                ENDPOINT,
                json={**_payload(), field_name: False},
                headers=headers,
            )
            assert response.status_code == 422
            _assert_no_store(response)

    assert service.calls == []
    assert service.repository_calls == 0


def test_human_personal_token_ai_and_wrong_workload_boundary_fail_before_io() -> None:
    service = _Service()
    exact_service, _ = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    app = create_app(
        _settings(),
        workload_identity_service=exact_service,
        workflow_protected_runtime_process_scheduling_authorization_service=cast(Any, service),
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

    assert human.status_code == 401
    assert personal.status_code == 401
    assert service.calls == []
    assert service.repository_calls == 0

    for identity_id, audience in (
        ("service.ai-agent", WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
        ("service.mcp-tool", WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
        ("service.connector-runtime", WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
        (
            WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
            "audience.workflow-wrong-consumer",
        ),
    ):
        workload_service, token = _workload_service_and_token(
            identity_id=identity_id,
            audience=audience,
        )
        isolated_service = _Service()
        isolated_app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_process_scheduling_authorization_service=cast(
                Any, isolated_service
            ),
        )
        with TestClient(isolated_app) as client:
            response = client.post(
                ENDPOINT,
                json=_payload(),
                headers=_workload_headers(token, audience),
            )
        assert response.status_code == 401
        assert isolated_service.calls == []
        assert isolated_service.repository_calls == 0
        _assert_no_store(response)


def test_generic_conflict_repository_and_cross_tenant_errors_are_non_oracular() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)

    for service, method, expected_status in (
        (_ConflictService(), "POST", 409),
        (_FailingService(), "POST", 503),
        (_Service(ignore_scope=True), "GET", 503),
    ):
        if method == "GET":
            service.lease = _lease(
                scope=WorkflowScope("organization.other", "environment.development", "site.local")
            )
        app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_process_scheduling_authorization_service=cast(Any, service),
        )
        with TestClient(app, raise_server_exceptions=False) as client:
            if method == "GET":
                _login(client)
                response = client.get(ENDPOINT)
            else:
                response = client.post(ENDPOINT, json=_payload(), headers=headers)

        assert response.status_code == expected_status
        detail = response.json()["detail"].casefold()
        assert "result" not in detail
        assert "tenant" not in detail
        assert "idempotency" not in detail
        assert "attestation" not in detail
        _assert_no_store(response)


def test_default_inventory_fails_closed_without_a_durable_service() -> None:
    app = create_app(_settings())
    with TestClient(app, raise_server_exceptions=False) as client:
        service = cast(
            Any,
            app.state.workflow_protected_runtime_process_scheduling_authorization_service,
        )
        _login(client)
        response = client.get(ENDPOINT)

    assert type(service).__name__ == (
        "WorkflowProtectedRuntimeProcessSchedulingAuthorizationService"
    )
    assert service.repository.durable is False
    assert type(service._process_state_attestor).__name__ == (
        "DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingStateAttestor"
    )
    assert response.status_code == 503
    assert response.json()["code"] == (
        "workflow_protected_runtime_process_scheduling_authorization_service_unavailable"
    )
    _assert_no_store(response)
