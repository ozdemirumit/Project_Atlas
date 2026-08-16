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
    workflow_protected_runtime_context_use_authorization_scope,
)
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedRuntimeContextUseAuthorizationPresentationState,
    WorkflowProtectedRuntimeContextUseAuthorizationService,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextUseAuthorizationAuthority,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseState,
    WorkflowScope,
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-context-use-authorizations"
NOW = datetime(2026, 8, 16, 23, 30, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _lease() -> SimpleNamespace:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()
    return SimpleNamespace(
        authorization_lease_id=(
            "workflow-protected-runtime-context-use-lease.0123456789abcdef01234567"
        ),
        canonical_digest="c" * 64,
        scope=SCOPE,
        state=WorkflowProtectedRuntimeContextUseAuthorizationLeaseState.AUTHORIZED_UNCONSUMED,
        issued_at=NOW,
        valid_until=NOW + timedelta(seconds=1),
        effective_until=NOW + timedelta(seconds=1),
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        purpose_id=policy.purpose_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        destination_boundary_id="boundary.workflow-protected-runtime",
        destination_deployment_id="deployment.workflow-protected-runtime",
        destination_generation=1,
        destination_fencing_token_digest="d" * 64,
        authority=WorkflowProtectedRuntimeContextUseAuthorizationAuthority(
            protected_runtime_context_use_authority_granted=True
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
                WorkflowProtectedRuntimeContextUseAuthorizationPresentationState.ACTIVE
                if active
                else WorkflowProtectedRuntimeContextUseAuthorizationPresentationState.EXPIRED
            ),
            protected_runtime_context_use_authority_granted=active,
        )

    async def list_protected_runtime_context_use_authorization_presentations(
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
        if not self.durable:
            raise RuntimeError("durable repository required")
        return await self.list_protected_runtime_context_use_authorization_presentations(
            scope=scope,
            limit=limit,
        )


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        raise RuntimeError("database unavailable")

    async def list_protected_runtime_context_use_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[SimpleNamespace, ...]:
        del scope, authorization_lease_ids, limit
        raise RuntimeError("database unavailable")


def _payload() -> dict[str, str]:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()
    return {
        "injection_result_id": "workflow-protected-runtime-context-injection.imp-219",
        "injection_result_digest": "a" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "runtime-context-use-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


class _TrustedSlotLifecycleAttestor:
    @property
    def available(self) -> bool:
        return True

    async def attest_runtime_slot_lifecycle(self, request: Any) -> Any:
        del request
        raise AssertionError("composition test must not request slot evidence")

    def verify_runtime_slot_lifecycle_attestation(self, attestation: Any) -> bool:
        del attestation
        return True


class _TrustedInjectorReceiptVerifier:
    def verify_receipt(self, receipt: Any) -> bool:
        del receipt
        return True


class _NonDurableRepository:
    durable = False

    def __init__(self) -> None:
        self.list_calls = 0

    async def get_authoritative_time(self) -> datetime:
        raise AssertionError("non-durable repository time must not be queried")

    async def list_protected_runtime_context_use_authorization_presentations(
        self,
        *,
        scope: WorkflowScope,
        authorization_lease_ids: tuple[str, ...] | None = None,
        limit: int = 256,
    ) -> tuple[Any, ...]:
        del scope, authorization_lease_ids, limit
        self.list_calls += 1
        return ()


def test_read_authorization_uses_a_distinct_c1_scope_and_role_assignment() -> None:
    settings = _settings()
    service = build_development_authorization_service(settings, _AuditSink())
    scope = workflow_protected_runtime_context_use_authorization_scope(
        settings.development_organization_id,
        settings.environment,
    )

    assert scope.resource_id == "resource.workflow.protected-runtime-context-use-authorizations"
    assert scope.capability_class.value == "C1"
    assignments = cast(Any, service)._assignments
    assert any(
        assignment.assignment_id
        == "assignment.development.workflow-protected-runtime-context-use-authorizations"
        and assignment.scope == scope
        for assignment in assignments
    )


def test_production_composition_accepts_only_supplied_trusted_boundaries() -> None:
    attestor = _TrustedSlotLifecycleAttestor()
    receipt_verifier = _TrustedInjectorReceiptVerifier()
    app = create_app(
        Settings(environment="production", enable_api_docs=False),
        workflow_protected_runtime_slot_lifecycle_attestor=attestor,
        workflow_protected_runtime_context_trusted_injector_receipt_signature_verifier=(
            receipt_verifier
        ),
    )

    with TestClient(app):
        service = cast(Any, app.state.workflow_protected_runtime_context_use_authorization_service)
        assert service._lifecycle_attestor is attestor
        assert service._lifecycle_signature_verifier is attestor
        assert service._injector_receipt_signature_verifier is receipt_verifier
        assert service.repository.durable is False


def test_production_defaults_fail_closed_and_development_is_explicit() -> None:
    production = create_app(Settings(environment="production", enable_api_docs=False))
    development = create_app(_settings())

    with TestClient(production):
        service = cast(
            Any, production.state.workflow_protected_runtime_context_use_authorization_service
        )
        assert service._lifecycle_attestor.available is False
        assert service.repository.durable is False
    with TestClient(development):
        service = cast(
            Any, development.state.workflow_protected_runtime_context_use_authorization_service
        )
        assert type(service._lifecycle_attestor).__name__ == (
            "DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor"
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
        workflow_protected_runtime_context_use_authorization_service=cast(Any, service),
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
        "use_profile_reference",
        "runtime_slot_profile_reference",
        "destination_profile_reference",
        "authority",
        "integrity_reference",
    }
    assert item["state"] == "authorized_unconsumed"
    assert item["effective_state"] == "active"
    assert item["authority"]["protected_runtime_context_use_authority_granted"] is True
    assert sum(value is True for value in item["authority"].values()) == 1
    assert inventory.json()["data"]["authorizations"] == [item]
    assert inventory.json()["data"]["durable"] is True
    assert not any(
        fragment in key
        for key in item
        for fragment in {
            "injection_result",
            "runtime_slot_commitment",
            "attestation",
            "receipt",
            "nonce",
            "fence",
            "idempotency",
            "locator",
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


def test_post_rejects_caller_authority_lifetime_and_internal_fields() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_context_use_authorization_service=cast(Any, service),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    with TestClient(app) as client:
        for field_name, value in (
            ("ttl_seconds", 300),
            ("authority", {"execution_authorized": True}),
            ("runtime_slot_commitment", "s" * 64),
            ("destination_fencing_token_digest", "f" * 64),
            ("lifecycle_attestation_id", "attestation.untrusted"),
        ):
            response = client.post(
                ENDPOINT,
                json={**_payload(), field_name: value},
                headers=headers,
            )
            assert response.status_code == 422
            _assert_no_store(response)
    assert service.calls == []


def test_wrong_workload_and_repository_outage_fail_closed_non_oracle() -> None:
    wrong_service, wrong_token = _workload_service_and_token(
        identity_id="service.ai-agent",
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    app = create_app(
        _settings(),
        workload_identity_service=wrong_service,
        workflow_protected_runtime_context_use_authorization_service=cast(Any, _FailingService()),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        _login(client)
        inventory = client.get(ENDPOINT)
        denied = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                wrong_token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )

    assert denied.status_code == 401
    assert inventory.status_code == 503
    assert inventory.json()["code"] == (
        "workflow_protected_runtime_context_use_authorization_service_unavailable"
    )
    assert "slot" not in inventory.json()["detail"].lower()
    _assert_no_store(denied)
    _assert_no_store(inventory)


def test_human_get_fails_closed_before_reading_a_non_durable_repository() -> None:
    repository = _NonDurableRepository()
    attestor = _TrustedSlotLifecycleAttestor()
    service = WorkflowProtectedRuntimeContextUseAuthorizationService(
        authorization_repository=cast(Any, repository),
        lifecycle_attestor=attestor,
        lifecycle_signature_verifier=attestor,
        injector_receipt_signature_verifier=_TrustedInjectorReceiptVerifier(),
        audit_sink=_AuditSink(),
    )
    app = create_app(
        _settings(),
        workflow_protected_runtime_context_use_authorization_service=service,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 503
    assert response.json()["code"] == (
        "workflow_protected_runtime_context_use_authorization_service_unavailable"
    )
    assert response.json()["detail"] == (
        "Runtime-context use authorization metadata is temporarily unavailable."
    )
    assert repository.list_calls == 0
    _assert_no_store(response)


def test_ai_and_mcp_workloads_cannot_request_runtime_context_use_authority() -> None:
    for identity_id in ("service.ai-agent", "service.mcp-tool"):
        workload_service, token = _workload_service_and_token(
            identity_id=identity_id,
            audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        )
        service = _Service()
        app = create_app(
            _settings(),
            workload_identity_service=workload_service,
            workflow_protected_runtime_context_use_authorization_service=cast(Any, service),
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
