from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi.testclient import TestClient
from test_workflow_outbox_publication_lease_api import (
    _issue_api_token,
    _login,
    _settings,
    _workload_headers,
)
from test_workflow_protected_runtime_context_injection_authorization_domain import (
    _lease as _domain_lease,
)
from test_workflow_protected_runtime_context_injection_authorization_domain import (
    _payload as _canonical_payload,
)
from test_workflow_target_context_access_authorization_lease_api import (
    _workload_service_and_token,
)

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    build_development_authorization_service,
    workflow_physical_transport_target_context_capsule_opening_authorization_lease_scope,
    workflow_protected_runtime_context_injection_authorization_scope,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowPlanningService,
    WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation,
    WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextInjectionAuthorizationLease,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_runtime_context_injection_authorization_policy,
    code_owned_workflow_registry,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-context-injection-authorizations"
NOW = datetime(2026, 8, 16, 23, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _lease() -> WorkflowProtectedRuntimeContextInjectionAuthorizationLease:
    base = _domain_lease()
    values = {
        field.name: getattr(base, field.name)
        for field in fields(base)
        if field.name != "canonical_digest"
    }
    values.update(
        {
            "authorization_lease_id": (
                "workflow-protected-runtime-context-injection-lease.0123456789abcdef01234567"
            ),
            "scope": SCOPE,
        }
    )
    return WorkflowProtectedRuntimeContextInjectionAuthorizationLease(
        **cast(Any, values), canonical_digest=canonical_digest(_canonical_payload(values))
    )


class _Service:
    durable = True

    def __init__(self) -> None:
        self.repository = self
        self.lease: WorkflowProtectedRuntimeContextInjectionAuthorizationLease | None = None
        self.evaluated_at = NOW + timedelta(milliseconds=500)
        self.calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return self.evaluated_at

    async def authorize(
        self, **kwargs: Any
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationLease:
        self.calls.append(kwargs)
        self.lease = _lease()
        return self.lease

    def _presentation(
        self, lease: WorkflowProtectedRuntimeContextInjectionAuthorizationLease
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation:
        active = lease.is_active(evaluated_at=self.evaluated_at)
        return WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation(
            lease=lease,
            consumed=False,
            evaluated_at=self.evaluated_at,
            effective_state=(
                WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState.ACTIVE
                if active
                else WorkflowProtectedRuntimeContextInjectionAuthorizationPresentationState.EXPIRED
            ),
            protected_runtime_context_injection_authority_granted=active,
        )

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation, ...]:
        del limit
        return (
            ()
            if self.lease is None or self.lease.scope != scope
            else (self._presentation(self.lease),)
        )

    async def get_presentation(
        self, *, scope: WorkflowScope, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation:
        assert self.lease is not None
        assert self.lease.scope == scope
        assert self.lease.authorization_lease_id == authorization_lease_id
        return self._presentation(self.lease)


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def authorize(
        self, **kwargs: Any
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationLease:
        del kwargs
        raise RuntimeError("database unavailable")

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")

    async def get_presentation(
        self, *, scope: WorkflowScope, authorization_lease_id: str
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation:
        del scope, authorization_lease_id
        raise RuntimeError("database unavailable")


def _payload() -> dict[str, str]:
    policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
    return {
        "access_result_id": "workflow-protected-resident-context-access.imp-217",
        "access_result_digest": "a" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "idempotency_key": "runtime-injection-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


class _AuditSink:
    async def record(self, event: object) -> None:
        del event


class _TrustedRuntimeHandleLifecycleAttestor:
    @property
    def available(self) -> bool:
        return True

    async def attest_runtime_handle_lifecycle(self, request: Any) -> Any:
        del request
        raise AssertionError("composition test must not request lifecycle evidence")


class _TrustedRuntimeHandleLifecycleSignatureVerifier:
    def verify_runtime_handle_lifecycle_attestation(self, attestation: Any) -> bool:
        del attestation
        return True


class _TrustedAccessorReceiptSignatureVerifier:
    def verify_receipt(self, receipt: Any) -> bool:
        del receipt
        return True


class _DisposableEngine:
    async def dispose(self) -> None:
        return None


def test_read_authorization_uses_a_distinct_c1_scope_and_role_assignment() -> None:
    settings = _settings()
    service = build_development_authorization_service(settings, _AuditSink())
    injection_scope = workflow_protected_runtime_context_injection_authorization_scope(
        settings.development_organization_id,
        settings.environment,
    )
    opening_scope = (
        workflow_physical_transport_target_context_capsule_opening_authorization_lease_scope(
            settings.development_organization_id,
            settings.environment,
        )
    )

    assert injection_scope != opening_scope
    assert injection_scope.resource_id == (
        "resource.workflow.protected-runtime-context-injection-authorizations"
    )
    assert injection_scope.capability_class.value == "C1"
    assignments = cast(Any, service)._assignments
    assert any(
        assignment.assignment_id
        == "assignment.development.workflow-protected-runtime-context-injection-authorizations"
        and assignment.scope == injection_scope
        for assignment in assignments
    )


def test_production_composition_accepts_only_supplied_trusted_boundaries() -> None:
    attestor = _TrustedRuntimeHandleLifecycleAttestor()
    lifecycle_verifier = _TrustedRuntimeHandleLifecycleSignatureVerifier()
    receipt_verifier = _TrustedAccessorReceiptSignatureVerifier()
    app = create_app(
        Settings(environment="production", enable_api_docs=False),
        workflow_protected_runtime_handle_lifecycle_attestor=attestor,
        workflow_protected_runtime_handle_lifecycle_signature_verifier=lifecycle_verifier,
        workflow_protected_resident_context_trusted_accessor_receipt_signature_verifier=(
            receipt_verifier
        ),
    )

    with TestClient(app):
        service = cast(
            Any, app.state.workflow_protected_runtime_context_injection_authorization_service
        )
        assert service._lifecycle_attestor is attestor
        assert service._lifecycle_signature_verifier is lifecycle_verifier
        assert service._accessor_receipt_signature_verifier is receipt_verifier


def test_production_postgres_repository_uses_the_shared_receipt_verifier() -> None:
    receipt_verifier = _TrustedAccessorReceiptSignatureVerifier()
    repository = object.__new__(PostgreSQLWorkflowPlanRepository)
    repository._engine = cast(Any, _DisposableEngine())
    repository._protected_resident_context_access_receipt_signature_verifier = None
    app = create_app(
        Settings(environment="production", enable_api_docs=False),
        workflow_planning_service=WorkflowPlanningService(
            registry=code_owned_workflow_registry(),
            repository=cast(Any, repository),
            audit_sink=_AuditSink(),
        ),
        workflow_protected_runtime_handle_lifecycle_attestor=(
            _TrustedRuntimeHandleLifecycleAttestor()
        ),
        workflow_protected_resident_context_trusted_accessor_receipt_signature_verifier=(
            receipt_verifier
        ),
    )
    with TestClient(app):
        service = cast(
            Any, app.state.workflow_protected_runtime_context_injection_authorization_service
        )
        composed_repository = service.repository

        assert composed_repository is repository
        assert (
            repository._protected_resident_context_access_receipt_signature_verifier
            is receipt_verifier
        )


def test_production_composition_defaults_all_trust_boundaries_to_fail_closed() -> None:
    app = create_app(Settings(environment="production", enable_api_docs=False))

    with TestClient(app):
        service = cast(
            Any, app.state.workflow_protected_runtime_context_injection_authorization_service
        )
        assert service._lifecycle_attestor.available is False
        assert service._lifecycle_signature_verifier is service._lifecycle_attestor
        assert (
            type(service._accessor_receipt_signature_verifier).__name__
            == "UnavailableWorkflowProtectedResidentContextTrustedAccessor"
        )


def test_development_composition_explicitly_uses_deterministic_adapters() -> None:
    app = create_app(_settings())

    with TestClient(app):
        service = cast(
            Any, app.state.workflow_protected_runtime_context_injection_authorization_service
        )
        assert type(service._lifecycle_attestor).__name__ == (
            "DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor"
        )
        assert service._lifecycle_signature_verifier is service._lifecycle_attestor
        assert type(service._accessor_receipt_signature_verifier).__name__ == (
            "DeterministicDevelopmentWorkflowProtectedResidentContextTrustedAccessor"
        )


def test_exact_workload_post_and_password_session_get_are_minimized() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_context_injection_authorization_service=cast(Any, service),
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
        "injector_profile_reference",
        "runtime_slot_profile_reference",
        "destination_profile_reference",
        "authority",
        "integrity_reference",
    }
    assert item["state"] == "authorized_unconsumed"
    assert item["effective_state"] == "active"
    assert len(item["authority"]) == 21
    assert item["authority"]["protected_runtime_context_injection_authority_granted"] is True
    assert sum(value is True for value in item["authority"].values()) == 1
    assert inventory.json()["data"]["authorizations"] == [item]
    forbidden_fragments = {
        "access_result",
        "access_lease",
        "claim",
        "handle_id",
        "handle_digest",
        "attestation",
        "nonce",
        "fence",
        "idempotency",
        "raw",
    }
    assert not any(fragment in key for key in item for fragment in forbidden_fragments)
    for response in (
        anonymous,
        human_post,
        created,
        inventory,
        personal_inventory,
        workload_inventory,
    ):
        _assert_no_store(response)


def test_expired_inventory_projects_zero_dedicated_and_prior_authority() -> None:
    service = _Service()
    service.lease = _lease()
    service.evaluated_at = NOW + timedelta(seconds=1)
    app = create_app(
        _settings(),
        workflow_protected_runtime_context_injection_authorization_service=cast(Any, service),
    )
    with TestClient(app) as client:
        _login(client)
        response = client.get(ENDPOINT)
    assert response.status_code == 200
    item = response.json()["data"]["authorizations"][0]
    assert item["effective_state"] == "expired"
    assert set(item["authority"].values()) == {False}
    _assert_no_store(response)


def test_post_forbids_caller_owned_lifetime_authority_and_internal_fields() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_context_injection_authorization_service=cast(Any, service),
    )
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    with TestClient(app) as client:
        for field_name, value in (
            ("ttl_seconds", 300),
            ("authority", {"execution_authorized": True}),
            ("protected_runtime_handle_id", "handle.untrusted"),
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


def test_personal_human_ai_wrong_workload_and_wrong_audience_fail_closed() -> None:
    wrong_workload_service, wrong_token = _workload_service_and_token(
        identity_id="service.ai-agent",
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    service = _Service()
    app = create_app(
        _settings(),
        workload_identity_service=wrong_workload_service,
        workflow_protected_runtime_context_injection_authorization_service=cast(Any, service),
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
        ai = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                wrong_token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
        wrong_audience = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(wrong_token, "audience.workflow-worker"),
        )
    assert {
        human.status_code,
        personal.status_code,
        ai.status_code,
        wrong_audience.status_code,
    } == {401}
    assert service.calls == []
    for response in (human, personal, ai, wrong_audience):
        _assert_no_store(response)


def test_repository_outages_fail_closed_as_non_oracle_no_store_503() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    app = create_app(
        _settings(),
        workload_identity_service=workload_service,
        workflow_protected_runtime_context_injection_authorization_service=cast(
            Any, _FailingService()
        ),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        _login(client)
        inventory = client.get(ENDPOINT)
        created = client.post(
            ENDPOINT,
            json=_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )
    for response in (inventory, created):
        assert response.status_code == 503
        assert response.json()["code"] == (
            "workflow_protected_runtime_context_injection_authorization_service_unavailable"
        )
        assert "handle" not in response.json()["detail"].lower()
        _assert_no_store(response)
