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
    workflow_protected_runtime_start_authorization_scope,
)
from atlas.modules.workflows.application.protected_runtime_start_authorization_ports import (
    WorkflowProtectedRuntimeStartAuthorizationError,
    WorkflowProtectedRuntimeStartAuthorizationPresentationState,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationAuthority,
    WorkflowProtectedRuntimeStartAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_start_authorization_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-start-authorizations"
NOW = datetime(2026, 8, 17, 6, 30, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _lease() -> SimpleNamespace:
    policy = code_owned_workflow_protected_runtime_start_authorization_policy()
    return SimpleNamespace(
        authorization_lease_id="workflow-protected-runtime-start-lease.0123456789abcdef01234567",
        canonical_digest="c" * 64,
        scope=SCOPE,
        state=WorkflowProtectedRuntimeStartAuthorizationLeaseState.AUTHORIZED_UNCONSUMED,
        issued_at=NOW,
        valid_until=NOW + timedelta(seconds=1),
        effective_until=NOW + timedelta(seconds=1),
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        purpose_id=policy.purpose_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        destination_deployment_id="deployment.workflow-protected-runtime",
        destination_generation=1,
        destination_fencing_token_digest="d" * 64,
        authority=WorkflowProtectedRuntimeStartAuthorizationAuthority(
            protected_runtime_start_authority_granted=True
        ),
    )


class _Service:
    durable = True

    def __init__(self) -> None:
        self.repository = self
        self.lease: SimpleNamespace | None = None
        self.evaluated_at = NOW + timedelta(milliseconds=500)
        self.calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return self.evaluated_at

    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        self.lease = _lease()
        return self.lease

    def _presentation(self, lease: SimpleNamespace) -> SimpleNamespace:
        active = lease.issued_at <= self.evaluated_at < lease.valid_until
        return SimpleNamespace(
            lease=lease,
            consumed=False,
            evaluated_at=self.evaluated_at,
            effective_state=(
                WorkflowProtectedRuntimeStartAuthorizationPresentationState.ACTIVE
                if active
                else WorkflowProtectedRuntimeStartAuthorizationPresentationState.EXPIRED
            ),
            protected_runtime_start_authority_granted=active,
        )

    async def list_protected_runtime_start_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[SimpleNamespace, ...]:
        del limit
        presentations = (
            ()
            if self.lease is None or self.lease.scope != scope
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
        return await self.list_protected_runtime_start_authorization_presentations(
            scope=scope,
            limit=limit,
        )


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        raise WorkflowProtectedRuntimeStartAuthorizationError(
            "workflow_protected_runtime_start_repository_unavailable"
        )

    async def list_protected_runtime_start_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[SimpleNamespace, ...]:
        del scope, authorization_lease_ids, limit
        raise RuntimeError("database unavailable")


class _ConflictService(_Service):
    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        raise WorkflowProtectedRuntimeStartAuthorizationError(
            "workflow_protected_runtime_start_idempotency_conflict"
        )


def _payload() -> dict[str, str]:
    policy = code_owned_workflow_protected_runtime_start_authorization_policy()
    return {
        "use_result_id": "workflow-protected-runtime-context-use.imp-222",
        "use_result_digest": "a" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "runtime-start-authorization-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


class _TrustedRuntimeStartLifecycleAttestor:
    @property
    def available(self) -> bool:
        return True

    async def attest_runtime_start_lifecycle(self, request: Any) -> Any:
        del request
        raise AssertionError("composition test must not request protected evidence")

    def verify_runtime_start_lifecycle_attestation(self, attestation: Any) -> bool:
        del attestation
        return True


class _TrustedUseReceiptVerifier:
    def verify_receipt(self, receipt: Any) -> bool:
        del receipt
        return True


def test_read_authorization_uses_distinct_c1_scope_and_role_assignment() -> None:
    settings = _settings()
    service = build_development_authorization_service(settings, _AuditSink())
    scope = workflow_protected_runtime_start_authorization_scope(
        settings.development_organization_id,
        settings.environment,
    )

    assert scope.resource_id == "resource.workflow.protected-runtime-start-authorizations"
    assert scope.capability_class.value == "C1"
    assignments = cast(Any, service)._assignments
    assert any(
        assignment.assignment_id
        == "assignment.development.workflow-protected-runtime-start-authorizations"
        and assignment.scope == scope
        for assignment in assignments
    )


def test_production_composition_accepts_only_supplied_trusted_boundaries() -> None:
    attestor = _TrustedRuntimeStartLifecycleAttestor()
    receipt_verifier = _TrustedUseReceiptVerifier()
    app = create_app(
        Settings(environment="production", enable_api_docs=False),
        workflow_protected_runtime_start_lifecycle_attestor=cast(Any, attestor),
        workflow_protected_runtime_context_use_receipt_signature_verifier=cast(
            Any, receipt_verifier
        ),
    )

    with TestClient(app):
        service = cast(Any, app.state.workflow_protected_runtime_start_authorization_service)
        assert service._lifecycle_attestor is attestor
        assert service._lifecycle_signature_verifier is attestor
        assert service._use_receipt_signature_verifier is receipt_verifier
        assert service.repository.durable is False


def test_production_defaults_fail_closed_and_development_attestor_is_explicit() -> None:
    production = create_app(Settings(environment="production", enable_api_docs=False))
    development = create_app(_settings())

    with TestClient(production):
        service = cast(Any, production.state.workflow_protected_runtime_start_authorization_service)
        assert service._lifecycle_attestor.available is False
        assert service.repository.durable is False
    with TestClient(development):
        service = cast(
            Any, development.state.workflow_protected_runtime_start_authorization_service
        )
        assert type(service._lifecycle_attestor).__name__ == (
            "DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor"
        )
        assert service._lifecycle_signature_verifier is service._lifecycle_attestor


def test_exact_workload_post_and_password_session_get_are_minimized() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_start_authorization_service=cast(Any, service),
    )
    with TestClient(app) as client:
        anonymous = client.get(ENDPOINT)
        csrf = _login(client)
        personal_token = _issue_api_token(client, csrf)
        human_post = client.post(ENDPOINT, json=_payload(), headers={"X-CSRF-Token": csrf})
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
        inventory = client.get(ENDPOINT)
        client.cookies.clear()
        personal_inventory = client.get(
            ENDPOINT, headers={"Authorization": f"Bearer {personal_token}"}
        )
        workload_inventory = client.get(
            ENDPOINT,
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )

    assert anonymous.status_code == 403
    assert human_post.status_code == 401
    assert created.status_code == 201
    assert inventory.status_code == 200
    assert personal_inventory.status_code == 403
    assert workload_inventory.status_code == 401
    item = created.json()["data"]
    assert set(item) == {
        "authorization_lease_id",
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
        "runtime_start_profile_reference",
        "destination_profile_reference",
        "authority",
        "integrity_reference",
    }
    assert item["state"] == "authorized_unconsumed"
    assert item["effective_state"] == "active"
    assert item["authority"]["protected_runtime_start_authority_granted"] is True
    assert item["authority"]["runtime_start_authorized"] is False
    assert sum(value is True for value in item["authority"].values()) == 1
    assert inventory.json()["data"]["authorizations"] == [item]
    assert inventory.json()["data"]["durable"] is True
    assert set(service.calls[0]) == {
        "use_result_id",
        "use_result_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    assert not any(
        fragment in key
        for key in item
        for fragment in {
            "use_result",
            "runtime_slot",
            "attestation",
            "receipt",
            "nonce",
            "fence",
            "idempotency",
            "locator",
            "prompt",
        }
    )
    for response in (
        anonymous,
        human_post,
        created,
        inventory,
        personal_inventory,
        workload_inventory,
    ):
        _assert_no_store(response)


def test_post_rejects_all_caller_authority_and_internal_fields_before_service_io() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_start_authorization_service=cast(Any, service),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    with TestClient(app) as client:
        for field_name, value in (
            ("ttl_seconds", 300),
            ("authority", {"runtime_start_authorized": True}),
            ("runtime_slot_commitment", "s" * 64),
            ("runtime_envelope_locator", "runtime.untrusted"),
            ("destination_fencing_token_digest", "f" * 64),
            ("lifecycle_attestation_id", "attestation.untrusted"),
            ("prompt", "start the runtime"),
        ):
            response = client.post(
                ENDPOINT,
                json={**_payload(), field_name: value},
                headers=headers,
            )
            assert response.status_code == 422
            _assert_no_store(response)
    assert service.calls == []


def test_human_ai_mcp_connector_and_generic_workers_are_rejected_before_service_io() -> None:
    identities = (
        "service.ai-agent",
        "service.mcp-tool",
        "service.connector-runtime",
        "service.generic-worker",
    )
    for identity_id in identities:
        workload_service, token = _workload_service_and_token(
            identity_id=identity_id,
            audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        )
        service = _Service()
        app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_start_authorization_service=cast(Any, service),
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
        _assert_no_store(response)


def test_repository_outage_is_503_and_genuine_conflict_is_409_without_oracles() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    for service, expected_status in ((_FailingService(), 503), (_ConflictService(), 409)):
        app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_start_authorization_service=cast(Any, service),
        )
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(ENDPOINT, json=_payload(), headers=headers)
        assert response.status_code == expected_status
        assert "result" not in response.json()["detail"].lower()
        assert "slot" not in response.json()["detail"].lower()
        _assert_no_store(response)


def test_default_inventory_fails_closed_without_postgres() -> None:
    app = create_app(_settings())
    with TestClient(app, raise_server_exceptions=False) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 503
    assert response.json()["code"] == (
        "workflow_protected_runtime_start_authorization_service_unavailable"
    )
    _assert_no_store(response)
