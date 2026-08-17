from __future__ import annotations

import base64
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
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.workflows.adapters.protected_runtime_context_users import (
    DenyAllWorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier,
    DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
    UnavailableWorkflowProtectedRuntimeContextTrustedUser,
    UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor,
)
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedRuntimeContextUseError,
    WorkflowProtectedRuntimeContextUsePresentation,
    WorkflowProtectedRuntimeContextUseReplayLookup,
    WorkflowProtectedRuntimeContextUseReplayStatus,
    WorkflowProtectedRuntimeContextUseRepository,
    WorkflowProtectedRuntimeContextUseService,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextUseAuthority,
    WorkflowProtectedRuntimeContextUseResultState,
    WorkflowScope,
    code_owned_workflow_protected_runtime_context_use_policy,
)

ENDPOINT = "/api/v1/workflows/protected-runtime-context-uses"
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")
OTHER_SCOPE = WorkflowScope("organization.other", "environment.development", "site.local")
NOW = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)
SERVER_TIME = NOW + timedelta(milliseconds=500)


def _presentation(
    *,
    suffix: str = "success",
    result_state: WorkflowProtectedRuntimeContextUseResultState | None = (
        WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY
    ),
    scope: WorkflowScope = SCOPE,
    started_at: datetime = NOW,
    use_deadline: datetime = NOW + timedelta(seconds=1),
    completed_at: datetime | None = NOW + timedelta(milliseconds=200),
    recorded_at: datetime = NOW + timedelta(milliseconds=300),
) -> WorkflowProtectedRuntimeContextUsePresentation:
    policy = code_owned_workflow_protected_runtime_context_use_policy()
    attempt = SimpleNamespace(
        use_id=f"workflow-protected-runtime-context-use.{suffix}",
        scope=scope,
        started_at=started_at,
        use_deadline=use_deadline,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        use_profile_digest=policy.use_profile_digest,
        authority=WorkflowProtectedRuntimeContextUseAuthority(),
    )
    result = (
        None
        if result_state is None
        else SimpleNamespace(
            state=result_state,
            completed_at=completed_at,
            recorded_at=recorded_at,
            authority=WorkflowProtectedRuntimeContextUseAuthority(),
        )
    )
    return WorkflowProtectedRuntimeContextUsePresentation(
        attempt=cast(Any, attempt),
        result=cast(Any, result),
    )


class _Service:
    durable = True

    def __init__(
        self,
        presentation: WorkflowProtectedRuntimeContextUsePresentation | None = None,
        *,
        presentations: tuple[WorkflowProtectedRuntimeContextUsePresentation, ...] | None = None,
        server_time: datetime = SERVER_TIME,
    ) -> None:
        self.repository = self
        self.presentation = presentation or _presentation()
        self.presentations = presentations or (self.presentation,)
        self.server_time = server_time
        self.calls: list[dict[str, Any]] = []

    async def get_authoritative_time(self) -> datetime:
        return self.server_time

    async def use(self, **kwargs: Any) -> WorkflowProtectedRuntimeContextUsePresentation:
        self.calls.append(kwargs)
        return self.presentation

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUsePresentation, ...]:
        del scope, limit
        return self.presentations


class _FailingService(_Service):
    async def get_authoritative_time(self) -> datetime:
        raise RuntimeError("database unavailable")

    async def use(self, **kwargs: Any) -> WorkflowProtectedRuntimeContextUsePresentation:
        del kwargs
        raise RuntimeError("database unavailable")

    async def list_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUsePresentation, ...]:
        del scope, limit
        raise RuntimeError("database unavailable")


class _IntegrityFailingService(_Service):
    def __init__(self, code: str) -> None:
        super().__init__()
        self.code = code

    async def use(self, **kwargs: Any) -> WorkflowProtectedRuntimeContextUsePresentation:
        del kwargs
        raise WorkflowProtectedRuntimeContextUseError(self.code)


class _DurableNoReplayRepository:
    durable = True

    def __init__(self) -> None:
        self.replay_calls = 0

    async def get_authoritative_time(self) -> datetime:
        return SERVER_TIME

    async def lookup_protected_runtime_context_use_replay(
        self, *_: object, **__: object
    ) -> WorkflowProtectedRuntimeContextUseReplayLookup:
        self.replay_calls += 1
        return WorkflowProtectedRuntimeContextUseReplayLookup(
            status=WorkflowProtectedRuntimeContextUseReplayStatus.NONE
        )


class _LdapPasswordIdentityProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        self.calls += 1
        if authentication_input.authorization_scheme != "basic":
            return None
        credential = authentication_input.credential
        if credential is None:
            return None
        try:
            decoded = base64.b64decode(credential, validate=True).decode()
        except (UnicodeDecodeError, ValueError):
            return None
        if decoded != "operator:correct-password":
            return None
        return AuthenticatedSubject(
            subject_id="subject.development.operator",
            display_name="Directory Operator",
            kind=SubjectKind.HUMAN,
            provider_id="provider.ldap.enterprise",
            authentication_method=AuthenticationMethod.LDAP,
            assurance_level=AssuranceLevel.SINGLE_FACTOR,
            authenticated_at=datetime.now(UTC),
            organization_id="organization.development",
            role_ids=("role.development.operator",),
        )


def _request_payload() -> dict[str, object]:
    policy = code_owned_workflow_protected_runtime_context_use_policy()
    return {
        "authorization_consumption_result_id": (
            "workflow-protected-runtime-context-use-authorization-consumption-result."
            "0123456789abcdef01234567"
        ),
        "authorization_consumption_result_digest": "a" * 64,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "irreversible_use_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "idempotency_key": "protected-runtime-context-use-api-0001",
    }


def _assert_no_store(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def _assert_minimized(item: dict[str, Any]) -> None:
    assert set(item) == {
        "use_id",
        "attempt_state",
        "result_state",
        "started_at",
        "completed_at",
        "context_use_performed",
        "policy_id",
        "policy_version",
        "use_profile_reference",
        "authority",
        "integrity_reference",
    }
    assert len(item["authority"]) == 26
    assert set(item["authority"].values()) == {False}
    serialized = str({key: value for key, value in item.items() if key != "authority"}).lower()
    for forbidden in (
        "authorization_consumption_result_id",
        "authorization_lease",
        "injection_result",
        "destination",
        "fencing",
        "runtime_slot",
        "context_locator",
        "runtime_handle",
        "idempotency",
        "receipt",
        "credential",
        "secret",
    ):
        assert forbidden not in serialized


def _app(
    service: _Service | WorkflowProtectedRuntimeContextUseService,
    *,
    identity_id: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    identity_provider: _LdapPasswordIdentityProvider | None = None,
) -> tuple[FastAPI, str]:
    workload_service, token = _workload_service_and_token(
        identity_id=identity_id,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    return (
        create_app(
            _settings(),
            identity_provider=identity_provider,
            workload_identity_service=workload_service,
            workflow_protected_runtime_context_use_service=cast(Any, service),
        ),
        token,
    )


def test_exact_workload_only_post_and_password_browser_get_are_minimized_no_store() -> None:
    service = _Service()
    app, token = _app(service)
    with TestClient(app) as client:
        anonymous_get = client.get(ENDPOINT)
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
        ai_post = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers={"Authorization": "Bearer ai.identity.untrusted"},
        )
        mcp_post = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers={"Authorization": "Bearer mcp.identity.untrusted"},
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
    assert mcp_post.status_code == 401
    assert created.status_code == 201
    assert inventory.status_code == 200
    assert "WWW-Authenticate" not in inventory.headers
    assert "authorized browser" not in inventory.text.lower()
    assert "mfa" not in inventory.text.lower()
    assert personal_get.status_code == 403
    assert workload_get.status_code == 401
    item = dict(created.json()["data"])
    _assert_minimized(item)
    assert item["result_state"] == "context_used_once_in_protected_boundary"
    assert item["context_use_performed"] is True
    assert inventory.json()["data"] == {
        "uses": [item],
        "server_time": SERVER_TIME.isoformat().replace("+00:00", "Z"),
        "durable": True,
    }
    assert len(service.calls) == 1
    call = service.calls[0]
    assert set(call) == {
        "authorization_consumption_result_id",
        "authorization_consumption_result_digest",
        "policy_id",
        "policy_version",
        "irreversible_use_acknowledged",
        "uncertainty_no_retry_acknowledged",
        "idempotency_key",
        "context",
    }
    assert call["authorization_consumption_result_digest"] == "a" * 64
    assert call["context"].subject_id == (
        WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
    )
    assert call["context"].authentication_method == "workload_token"
    assert call["context"].scope == SCOPE
    for response in (created, inventory):
        _assert_no_store(response)


def test_valid_mcp_shaped_workload_cannot_replace_the_exact_consumer() -> None:
    service = _Service()
    app, token = _app(service, identity_id="service.mcp-connector")
    with TestClient(app) as client:
        response = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
            ),
        )

    assert response.status_code == 401
    assert response.json()["code"] == "workload_authentication_failed"
    assert service.calls == []


def test_pending_claim_only_uncertain_and_recorded_outcomes_are_distinct_and_minimized() -> None:
    presentations = (
        _presentation(
            suffix="pending",
            result_state=None,
            use_deadline=SERVER_TIME + timedelta(seconds=1),
            completed_at=None,
        ),
        _presentation(
            suffix="claim-only-uncertain",
            result_state=None,
            use_deadline=SERVER_TIME - timedelta(milliseconds=1),
            completed_at=None,
        ),
        _presentation(suffix="success"),
        _presentation(
            suffix="failure",
            result_state=(
                WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USE_FAILED_WITHOUT_USE
            ),
        ),
        _presentation(
            suffix="recorded-uncertain",
            result_state=(
                WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USE_OUTCOME_UNCERTAIN
            ),
            completed_at=None,
        ),
    )
    service = _Service(presentations=presentations)
    app, _ = _app(service)
    with TestClient(app) as client:
        _login(client)
        response = client.get(ENDPOINT)

    assert response.status_code == 200
    items = response.json()["data"]["uses"]
    assert len(items) == 5
    for item in items:
        _assert_minimized(item)
    projections = {
        item["use_id"].rsplit(".", maxsplit=1)[-1]: (
            item["attempt_state"],
            item["result_state"],
            item["context_use_performed"],
        )
        for item in items
    }
    assert projections == {
        "pending": ("started", "use_pending", None),
        "claim-only-uncertain": ("started", "context_use_outcome_uncertain", None),
        "success": ("completed", "context_used_once_in_protected_boundary", True),
        "failure": ("completed", "context_use_failed_without_use", False),
        "recorded-uncertain": ("completed", "context_use_outcome_uncertain", None),
    }
    _assert_no_store(response)


def test_post_requires_the_exact_schema_and_rejects_sensitive_caller_owned_fields() -> None:
    service = _Service()
    app, token = _app(service)
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    payload = _request_payload()
    unsafe_fields: tuple[tuple[str, object], ...] = (
        ("authorization_consumption_claim_id", "claim.untrusted"),
        ("authorization_lease_id", "lease.untrusted"),
        ("injection_result_id", "injection.untrusted"),
        ("destination_fencing_token_digest", "b" * 64),
        ("runtime_slot_commitment", "c" * 64),
        ("protected_operation_reference", "operation.untrusted"),
        ("context", {"protected": True}),
        ("receipt", {"canonical_digest": "d" * 64}),
        ("authority", {"execution_authorized": True}),
    )
    invalid_payloads = [
        {key: value for key, value in payload.items() if key != required} for required in payload
    ]
    invalid_payloads.extend(
        (
            {**payload, "irreversible_use_acknowledged": False},
            {**payload, "uncertainty_no_retry_acknowledged": False},
            {**payload, "authorization_consumption_result_id": "not valid"},
            {**payload, "policy_id": "policy.untrusted"},
            {**payload, "policy_version": "2.0"},
            {**payload, "idempotency_key": "short"},
            {**payload, "idempotency_key": "invalid key with spaces"},
        )
    )
    invalid_payloads.extend({**payload, field: value} for field, value in unsafe_fields)

    with TestClient(app) as client:
        responses = [
            client.post(ENDPOINT, json=invalid_payload, headers=headers)
            for invalid_payload in invalid_payloads
        ]

    assert responses
    assert all(response.status_code == 422 for response in responses)
    assert service.calls == []


def test_inventory_rejects_scope_time_and_duplicate_evidence_and_post_rejects_scope() -> None:
    invalid_sets = (
        (_presentation(suffix="wrong-scope", scope=OTHER_SCOPE),),
        (
            _presentation(suffix="duplicate"),
            _presentation(suffix="duplicate"),
        ),
        (
            _presentation(
                suffix="future-start",
                started_at=SERVER_TIME + timedelta(milliseconds=1),
                completed_at=SERVER_TIME + timedelta(milliseconds=2),
                recorded_at=SERVER_TIME + timedelta(milliseconds=3),
                use_deadline=SERVER_TIME + timedelta(seconds=1),
            ),
        ),
        (
            _presentation(
                suffix="future-completion",
                completed_at=SERVER_TIME + timedelta(milliseconds=1),
                recorded_at=SERVER_TIME + timedelta(milliseconds=2),
                use_deadline=SERVER_TIME + timedelta(seconds=1),
            ),
        ),
    )
    responses = []
    for presentations in invalid_sets:
        app, _ = _app(_Service(presentations=presentations))
        with TestClient(app) as client:
            _login(client)
            responses.append(client.get(ENDPOINT))

    wrong_scope_service = _Service(_presentation(suffix="post-wrong-scope", scope=OTHER_SCOPE))
    wrong_scope_app, token = _app(wrong_scope_service)
    with TestClient(wrong_scope_app) as client:
        responses.append(
            client.post(
                ENDPOINT,
                json=_request_payload(),
                headers=_workload_headers(
                    token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
                ),
            )
        )

    assert all(response.status_code == 503 for response in responses)
    assert all(
        response.json()["code"] == "workflow_protected_runtime_context_use_service_unavailable"
        for response in responses
    )


def test_service_outage_is_503_and_non_oracular() -> None:
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
            "workflow_protected_runtime_context_use_service_unavailable"
        )
        detail = response.json()["detail"].lower()
        for forbidden in ("context id", "context digest", "slot", "receipt", "fence"):
            assert forbidden not in detail


def test_repository_and_commit_integrity_errors_are_503_not_authorization_denials() -> None:
    for code in (
        "protected_runtime_context_use_repository_contract_violation",
        "protected_runtime_context_use_repository_violation",
        "protected_runtime_context_use_claim_commit_uncertain",
        "protected_runtime_context_use_instruction_envelope_invalid",
    ):
        app, token = _app(_IntegrityFailingService(code))
        with TestClient(app) as client:
            response = client.post(
                ENDPOINT,
                json=_request_payload(),
                headers=_workload_headers(
                    token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
                ),
            )

        assert response.status_code == 503
        assert response.json()["code"] == (
            "workflow_protected_runtime_context_use_service_unavailable"
        )
        _assert_no_store(response)


def test_default_composition_is_503_without_durability_or_trusted_components() -> None:
    workload_service, token = _workload_service_and_token(
        identity_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    )
    with TestClient(create_app(_settings(), workload_identity_service=workload_service)) as client:
        service = cast(
            WorkflowProtectedRuntimeContextUseService,
            cast(Any, client.app).state.workflow_protected_runtime_context_use_service,
        )
        assert service.repository.durable is False
        assert isinstance(
            service._eligibility_attestor,
            UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor,
        )
        assert isinstance(
            service._trusted_user,
            UnavailableWorkflowProtectedRuntimeContextTrustedUser,
        )
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
            "workflow_protected_runtime_context_use_service_unavailable"
        )

    repository = _DurableNoReplayRepository()
    unavailable_service = WorkflowProtectedRuntimeContextUseService(
        repository=cast(WorkflowProtectedRuntimeContextUseRepository, repository),
        eligibility_attestor=UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor(),
        eligibility_signature_verifier=(
            DenyAllWorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier()
        ),
        trusted_user=UnavailableWorkflowProtectedRuntimeContextTrustedUser(),
        receipt_signature_verifier=(
            DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier()
        ),
    )
    unavailable_app, unavailable_token = _app(unavailable_service)
    with TestClient(unavailable_app) as client:
        unavailable = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                unavailable_token,
                WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            ),
        )
    assert unavailable.status_code == 503
    assert repository.replay_calls == 1

    with TestClient(create_app(Settings(environment="test"))) as client:
        production_service = cast(
            WorkflowProtectedRuntimeContextUseService,
            cast(Any, client.app).state.workflow_protected_runtime_context_use_service,
        )
        assert production_service.repository.durable is False


def test_ldap_username_password_is_authentication_only_without_operation_authority() -> None:
    provider = _LdapPasswordIdentityProvider()
    service = _Service()
    app, _ = _app(service, identity_provider=provider)
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/authentication/sessions",
            json={"username": "operator", "password": "correct-password"},
        )
        csrf = str(login.headers["X-CSRF-Token"])
        inventory = client.get(ENDPOINT)
        operation = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers={"X-CSRF-Token": csrf},
        )

    assert provider.calls == 1
    assert login.status_code == 201
    assert inventory.status_code == 200
    assert "authorized browser" not in inventory.text.lower()
    assert "mfa" not in inventory.text.lower()
    assert operation.status_code == 401
    assert service.calls == []
    _assert_minimized(dict(inventory.json()["data"]["uses"][0]))
    _assert_no_store(inventory)


def test_denied_validation_and_error_responses_are_also_no_store() -> None:
    service = _Service()
    app, token = _app(service)
    headers = _workload_headers(token, WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE)
    with TestClient(app) as client:
        anonymous_get = client.get(ENDPOINT)
        csrf = _login(client)
        human_post = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers={"X-CSRF-Token": csrf},
        )
        invalid_schema = client.post(
            ENDPOINT,
            json={**_request_payload(), "runtime_slot_commitment": "a" * 64},
            headers=headers,
        )

    failing_app, failing_token = _app(_FailingService())
    with TestClient(failing_app, raise_server_exceptions=False) as client:
        _login(client)
        unavailable_get = client.get(ENDPOINT)
        unavailable_post = client.post(
            ENDPOINT,
            json=_request_payload(),
            headers=_workload_headers(
                failing_token,
                WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
            ),
        )

    responses = {
        "anonymous_get": anonymous_get,
        "human_post": human_post,
        "invalid_schema": invalid_schema,
        "unavailable_get": unavailable_get,
        "unavailable_post": unavailable_post,
    }
    missing = {
        name: dict(response.headers)
        for name, response in responses.items()
        if response.headers.get("Cache-Control") != "no-store, max-age=0"
        or response.headers.get("Pragma") != "no-cache"
        or response.headers.get("Referrer-Policy") != "no-referrer"
    }
    assert missing == {}
