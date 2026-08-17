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
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_AUTHORIZATION_READ,
    build_development_authorization_service,
    workflow_protected_runtime_process_creation_authorization_scope,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessCreationAuthorizationError,
    WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_process_creation_authorization_domain import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority,
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_creation_authorization_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-process-creation-authorizations"
NOW = datetime(2026, 8, 18, 10, 30, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _lease(*, scope: WorkflowScope = SCOPE) -> SimpleNamespace:
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    return SimpleNamespace(
        authorization_lease_id=(
            "workflow-protected-runtime-process-creation-lease.0123456789abcdef01234567"
        ),
        readiness_result_id="workflow-protected-runtime-readiness-result.imp-226",
        canonical_digest="c" * 64,
        scope=scope,
        state=(
            WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        issued_at=NOW,
        valid_until=NOW + timedelta(seconds=1),
        effective_until=NOW + timedelta(seconds=1),
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        purpose_id=policy.purpose_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        authority=WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority(
            protected_runtime_process_creation_authority_granted=True
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

    async def get_authoritative_time(self) -> datetime:
        self.repository_calls += 1
        return self.evaluated_at

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
                WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState.ACTIVE
                if active
                else WorkflowProtectedRuntimeProcessCreationAuthorizationPresentationState.EXPIRED
            ),
            protected_runtime_process_creation_authority_granted=active,
        )

    async def list_protected_runtime_process_creation_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[SimpleNamespace, ...]:
        del limit
        self.repository_calls += 1
        presentations = (
            ()
            if self.lease is None or (not self.ignore_scope and self.lease.scope != scope)
            else (self._presentation(self.lease),)
        )
        if authorization_lease_ids is None:
            return presentations
        return tuple(
            presentation
            for presentation in presentations
            if presentation.lease.authorization_lease_id in authorization_lease_ids
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[SimpleNamespace, ...]:
        return await self.list_protected_runtime_process_creation_authorization_presentations(
            scope=scope,
            limit=limit,
        )


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        self.repository_calls += 1
        raise RuntimeError("database unavailable")

    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        self.repository_calls += 1
        raise WorkflowProtectedRuntimeProcessCreationAuthorizationError(
            "workflow_protected_runtime_process_creation_repository_unavailable"
        )

    async def list_protected_runtime_process_creation_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[SimpleNamespace, ...]:
        del scope, authorization_lease_ids, limit
        self.repository_calls += 1
        raise RuntimeError("database unavailable")


class _ConflictService(_Service):
    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        self.repository_calls += 1
        raise WorkflowProtectedRuntimeProcessCreationAuthorizationError(
            "workflow_protected_runtime_process_creation_idempotency_conflict"
        )


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


class _TrustedProcessCreationLifecycleAttestor:
    @property
    def available(self) -> bool:
        return True

    async def attest_runtime_process_creation_lifecycle(self, request: Any) -> Any:
        del request
        raise AssertionError("composition test must not request protected evidence")

    def verify_runtime_process_creation_lifecycle_attestation(self, attestation: Any) -> bool:
        del attestation
        return True


def _payload() -> dict[str, str]:
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    return {
        "readiness_result_id": "workflow-protected-runtime-readiness-result.imp-226",
        "readiness_result_digest": "a" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "runtime-process-creation-authorization-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_read_authorization_has_dedicated_permission_c1_scope_and_assignment() -> None:
    settings = _settings()
    service = build_development_authorization_service(settings, _AuditSink())
    scope = workflow_protected_runtime_process_creation_authorization_scope(
        settings.development_organization_id,
        settings.environment,
    )

    assert WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_AUTHORIZATION_READ == (
        "workflow.protected-runtime-process-creation-authorizations.read"
    )
    assert scope.resource_id == (
        "resource.workflow.protected-runtime-process-creation-authorizations"
    )
    assert scope.capability_class.value == "C1"
    assignments = cast(Any, service)._assignments
    assert any(
        assignment.assignment_id
        == "assignment.development.workflow-protected-runtime-process-creation-authorizations"
        and assignment.scope == scope
        for assignment in assignments
    )


def test_production_repository_and_attestor_fail_closed_while_development_is_explicit() -> None:
    production = create_app(Settings(environment="production", enable_api_docs=False))
    development = create_app(_settings())

    with TestClient(production):
        service = cast(
            Any,
            production.state.workflow_protected_runtime_process_creation_authorization_service,
        )
        assert service.repository.durable is False
        assert service._lifecycle_attestor.available is False
    with TestClient(development):
        service = cast(
            Any,
            development.state.workflow_protected_runtime_process_creation_authorization_service,
        )
        assert type(service._lifecycle_attestor).__name__ == (
            "DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationLifecycleAttestor"
        )
        assert service._lifecycle_signature_verifier is service._lifecycle_attestor


def test_production_composition_accepts_an_explicit_trusted_lifecycle_boundary() -> None:
    attestor = _TrustedProcessCreationLifecycleAttestor()
    app = create_app(
        Settings(environment="production", enable_api_docs=False),
        workflow_protected_runtime_process_creation_lifecycle_attestor=cast(Any, attestor),
    )

    with TestClient(app):
        service = cast(
            Any,
            app.state.workflow_protected_runtime_process_creation_authorization_service,
        )
        assert service.repository.durable is False
        assert service._lifecycle_attestor is attestor
        assert service._lifecycle_signature_verifier is attestor


def test_exact_workload_post_and_password_session_get_are_minimized_without_mfa() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_process_creation_authorization_service=cast(Any, service),
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
        "readiness_result_reference",
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
        "process_creation_profile_reference",
        "authority",
        "integrity_reference",
    }
    assert item["readiness_result_reference"] == (
        "integrity.workflow-protected-runtime-readiness-result."
        f"{sha256(_payload()['readiness_result_id'].encode('utf-8')).hexdigest()[:24]}"
    )
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    assert item["process_creation_profile_reference"] == (
        "integrity.workflow-protected-runtime-process-creation-profile."
        f"{sha256(policy.process_creation_profile_digest.encode('utf-8')).hexdigest()[:24]}"
    )
    assert item["integrity_reference"] == (
        "integrity.workflow-protected-runtime-process-creation-authorization."
        f"{sha256(item['authorization_lease_id'].encode('utf-8')).hexdigest()[:24]}"
    )
    assert item["state"] == "authorized_unconsumed"
    assert item["effective_state"] == "active"
    assert item["authority"]["protected_runtime_process_creation_authority_granted"] is True
    assert sum(value is True for value in item["authority"].values()) == 1
    assert inventory.json()["data"]["authorizations"] == [item]
    assert inventory.json()["data"]["durable"] is True
    assert set(service.calls[0]) == {
        "readiness_result_id",
        "readiness_result_digest",
        "policy_id",
        "policy_version",
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
        "runtime_locator",
        "process_identifier",
        "attestation",
        "receipt",
        "nonce",
        "idempotency",
    }
    assert forbidden_material.isdisjoint(item)
    _assert_no_store(created)
    _assert_no_store(inventory)


def test_active_and_expired_inventory_projects_authority_from_server_time() -> None:
    service = _Service()
    service.lease = _lease()
    app = create_app(
        _settings(),
        workflow_protected_runtime_process_creation_authorization_service=cast(Any, service),
    )

    with TestClient(app) as client:
        _login(client)
        active = client.get(ENDPOINT)
        service.evaluated_at = NOW + timedelta(seconds=1)
        expired = client.get(ENDPOINT)

    active_item = active.json()["data"]["authorizations"][0]
    expired_item = expired.json()["data"]["authorizations"][0]
    assert active_item["effective_state"] == "active"
    assert active_item["authority"]["protected_runtime_process_creation_authority_granted"] is True
    assert expired_item["effective_state"] == "expired"
    assert (
        expired_item["authority"]["protected_runtime_process_creation_authority_granted"] is False
    )
    assert not any(expired_item["authority"].values())
    _assert_no_store(active)
    _assert_no_store(expired)


def test_strict_post_rejects_authority_and_all_operational_material_before_io() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_process_creation_authorization_service=cast(Any, service),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    forbidden_inputs: tuple[tuple[str, object], ...] = (
        ("ttl_seconds", 300),
        ("authority", {"execution_authorized": True}),
        ("runtime", {"slot": "runtime.untrusted"}),
        ("runtime_locator", "runtime.untrusted"),
        ("process", {"name": "untrusted"}),
        ("process_identifier", "process.untrusted"),
        ("command", "start-service"),
        ("executable", "powershell.exe"),
        ("args", ["-Command", "Get-Service"]),
        ("env", {"TOKEN": "secret"}),
        ("prompt", "create a process"),
        ("model", "local-llm"),
        ("network", {"host": "example.invalid"}),
        ("connector", {"id": "connector.untrusted"}),
        ("lifecycle_attestation_id", "attestation.untrusted"),
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
        workflow_protected_runtime_process_creation_authorization_service=cast(Any, service),
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
    _assert_no_store(human)
    _assert_no_store(personal)

    wrong_boundaries = (
        ("service.ai-agent", WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
        ("service.mcp-tool", WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
        ("service.connector-runtime", WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
        (
            WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
            "audience.workflow-wrong-consumer",
        ),
    )
    for identity_id, audience in wrong_boundaries:
        workload_service, token = _workload_service_and_token(
            identity_id=identity_id,
            audience=audience,
        )
        isolated_service = _Service()
        isolated_app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_process_creation_authorization_service=cast(
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


def test_generic_conflict_and_repository_errors_are_non_oracle_no_store() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)

    for service, expected_status in ((_ConflictService(), 409), (_FailingService(), 503)):
        app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_process_creation_authorization_service=cast(Any, service),
        )
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(ENDPOINT, json=_payload(), headers=headers)

        assert response.status_code == expected_status
        detail = response.json()["detail"].casefold()
        assert "result" not in detail
        assert "runtime" not in detail
        assert "readiness" not in detail
        assert "idempotency" not in detail
        _assert_no_store(response)


def test_cross_tenant_projection_is_rejected_as_a_generic_503() -> None:
    service = _Service(ignore_scope=True)
    service.lease = _lease(
        scope=WorkflowScope("organization.other", "environment.development", "site.local")
    )
    app = create_app(
        _settings(),
        workflow_protected_runtime_process_creation_authorization_service=cast(Any, service),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 503
    assert response.json()["code"] == (
        "workflow_protected_runtime_process_creation_authorization_service_unavailable"
    )
    assert "scope" not in response.json()["detail"].casefold()
    assert "tenant" not in response.json()["detail"].casefold()
    _assert_no_store(response)


def test_default_inventory_fails_closed_without_postgres() -> None:
    app = create_app(_settings())
    with TestClient(app, raise_server_exceptions=False) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 503
    assert response.json()["code"] == (
        "workflow_protected_runtime_process_creation_authorization_service_unavailable"
    )
    _assert_no_store(response)
