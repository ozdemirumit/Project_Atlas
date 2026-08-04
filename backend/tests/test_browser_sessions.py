from __future__ import annotations

import asyncio
import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.identity.adapters.sessions import InMemorySessionRepository
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.application.sessions import SessionOperationsError, SessionService
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.identity.domain.sessions import CredentialKind, SessionState

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class SessionCreationFailingAuditSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.identity.session.created":
            raise RuntimeError("session audit unavailable")
        await super().record(event)


class BasicTestIdentityProvider:
    def __init__(self, authenticated_subject: AuthenticatedSubject | None = None) -> None:
        self.calls = 0
        self._authenticated_subject = authenticated_subject

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
        except ValueError:
            return None
        if decoded != "operator:correct-password":
            return None
        return self._authenticated_subject or subject()


def subject() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.development.operator",
        display_name="Session Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.test",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
        "session_absolute_timeout_minutes": 60,
        "session_idle_timeout_minutes": 15,
        "session_max_per_subject": 2,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def login(client: TestClient, password: str = "correct-password") -> Response:
    return cast(
        Response,
        client.post(
            "/api/v1/authentication/sessions",
            json={"username": "operator", "password": password},
            headers={"X-Correlation-ID": "cor_session_login"},
        ),
    )


def direct_service(
    *,
    clock: MutableClock | None = None,
    max_sessions: int = 2,
    audit_sink: CollectingAuditSink | None = None,
) -> tuple[SessionService, InMemorySessionRepository, CollectingAuditSink, MutableClock]:
    resolved_clock = clock or MutableClock()
    sink = audit_sink or CollectingAuditSink()
    identity_service = IdentityService(
        provider=BasicTestIdentityProvider(),
        audit_sink=sink,
        clock=resolved_clock,
    )
    repository = InMemorySessionRepository()
    return (
        SessionService(
            identity_service=identity_service,
            repository=repository,
            audit_sink=sink,
            absolute_timeout=timedelta(hours=1),
            idle_timeout=timedelta(minutes=15),
            max_sessions_per_subject=max_sessions,
            clock=resolved_clock,
        ),
        repository,
        sink,
        resolved_clock,
    )


def test_login_sets_opaque_http_only_strict_cookie_and_csrf_header() -> None:
    sink = CollectingAuditSink()
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
        )
    ) as client:
        response = login(client)

    assert response.status_code == 201
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(item for item in cookies if item.startswith("atlas_session="))
    csrf_cookie = next(item for item in cookies if item.startswith("atlas_csrf="))
    assert "HttpOnly" in session_cookie
    assert "SameSite=strict" in session_cookie
    assert "Path=/api" in session_cookie
    assert "Max-Age=3600" in session_cookie
    assert "Secure" not in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=strict" in csrf_cookie
    assert "Path=/" in csrf_cookie
    assert "Max-Age=3600" in csrf_cookie
    assert "Secure" not in csrf_cookie
    assert len(response.headers["X-CSRF-Token"]) >= 32
    assert "correct-password" not in response.text
    assert "atlas_session" not in response.text
    assert [item.event_type for item in sink.records[-2:]] == [
        "atlas.identity.authentication.succeeded",
        "atlas.identity.session.created",
    ]


def test_production_session_cookie_is_secure() -> None:
    with TestClient(
        create_app(
            settings(
                environment="production",
                enable_api_docs=False,
                development_identity_enabled=False,
            ),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=CollectingAuditSink(),
        )
    ) as client:
        response = login(client)

    assert response.status_code == 201
    assert all("Secure" in item for item in response.headers.get_list("set-cookie"))


def test_invalid_login_is_generic_and_does_not_issue_cookie() -> None:
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=CollectingAuditSink(),
        )
    ) as client:
        response = login(client, "wrong-password")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
    assert "set-cookie" not in response.headers
    assert "wrong-password" not in response.text


def test_invalid_password_shape_does_not_echo_secret_input() -> None:
    secret = "sensitive-password-material-" * 40
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=CollectingAuditSink(),
        )
    ) as client:
        response = login(client, secret)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
    assert secret not in response.text


@pytest.mark.parametrize("credential", ["short", "x" * 257, "A" * 43])
def test_malformed_and_unknown_session_credentials_fail_closed(credential: str) -> None:
    sink = CollectingAuditSink()
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
        )
    ) as client:
        client.cookies.set("atlas_session", credential, path="/api")
        response = client.get("/api/v1/identity/me")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
    assert credential not in response.text
    assert sink.records[-1].event_type == "atlas.identity.session.denied"


def test_missing_session_without_an_enabled_provider_fails_closed() -> None:
    with TestClient(
        create_app(
            settings(development_identity_enabled=False),
            audit_sink=CollectingAuditSink(),
        )
    ) as client:
        response = client.get("/api/v1/identity/me")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_authenticated_session_does_not_bypass_exact_rbac_assignment() -> None:
    unassigned_subject = replace(
        subject(),
        subject_id="subject.enterprise.unassigned",
        provider_id="provider.ldap.test",
    )
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(unassigned_subject),
            audit_sink=CollectingAuditSink(),
        )
    ) as client:
        login_response = login(client)
        response = client.get("/api/v1/identity/me")

    assert login_response.status_code == 201
    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"


@pytest.mark.parametrize(
    "overrides",
    [
        {"session_absolute_timeout_minutes": 4},
        {"session_idle_timeout_minutes": 0},
        {
            "session_absolute_timeout_minutes": 10,
            "session_idle_timeout_minutes": 11,
        },
        {"session_max_per_subject": 0},
    ],
)
def test_session_configuration_rejects_values_below_platform_bounds(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        settings(**overrides)


def test_cookie_session_allows_safe_read_and_requires_csrf_for_mutation() -> None:
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=CollectingAuditSink(),
        )
    ) as client:
        login_response = login(client)
        csrf = login_response.headers["X-CSRF-Token"]
        identity = client.get("/api/v1/identity/me")
        denied = client.post("/api/v1/security-export/test-event")
        allowed = client.post(
            "/api/v1/security-export/test-event",
            headers={"X-CSRF-Token": csrf},
        )

    assert identity.status_code == 200
    assert identity.json()["data"]["authentication"]["method"] == "ldap"
    assert denied.status_code == 403
    assert denied.json()["code"] == "csrf_validation_failed"
    assert allowed.status_code == 200
    assert allowed.json()["data"]["state"] == "transport_delivered"


def test_cookie_and_authorization_header_are_rejected_as_ambiguous() -> None:
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=CollectingAuditSink(),
        )
    ) as client:
        login(client)
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Bearer another-credential"},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "ambiguous_authentication"
    assert "another-credential" not in response.text


def test_logout_requires_csrf_revokes_session_and_clears_cookie() -> None:
    sink = CollectingAuditSink()
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
        )
    ) as client:
        login_response = login(client)
        csrf = login_response.headers["X-CSRF-Token"]
        denied = client.delete("/api/v1/authentication/sessions/current")
        response = client.delete(
            "/api/v1/authentication/sessions/current",
            headers={"X-CSRF-Token": csrf},
        )
        after_logout = client.get("/api/v1/identity/me")

    assert denied.status_code == 403
    assert response.status_code == 204
    cleared = response.headers.get_list("set-cookie")
    assert len(cleared) == 2
    assert all("Max-Age=0" in item for item in cleared)
    assert after_logout.status_code == 401
    assert any(item.event_type == "atlas.identity.session.revoked" for item in sink.records)


@pytest.mark.asyncio
async def test_absolute_expiry_terminates_session_without_extending_it() -> None:
    service, repository, sink, clock = direct_service()
    issued = await service.create(
        AuthenticationInput(
            correlation_id="cor_expiry_create",
            authorization_scheme="basic",
            credential=base64.b64encode(b"operator:correct-password").decode(),
        )
    )
    clock.now = NOW + timedelta(hours=1)

    context = await service.authenticate(
        issued.token,
        csrf_token=None,
        unsafe_request=False,
        correlation_id="cor_expiry_validate",
    )
    record = await repository.get_by_token_digest(issued.record.token_digest)

    assert context is None
    assert record is not None and record.state is SessionState.EXPIRED
    assert record.absolute_expires_at == NOW + timedelta(hours=1)
    assert sink.records[-1].event_type == "atlas.identity.session.expired"


@pytest.mark.asyncio
async def test_idle_timeout_expires_session() -> None:
    service, repository, _, clock = direct_service()
    issued = await service.create(
        AuthenticationInput(
            correlation_id="cor_idle_create",
            authorization_scheme="basic",
            credential=base64.b64encode(b"operator:correct-password").decode(),
        )
    )
    clock.now = NOW + timedelta(minutes=15)

    context = await service.authenticate(
        issued.token,
        csrf_token=None,
        unsafe_request=False,
        correlation_id="cor_idle_validate",
    )
    record = await repository.get_by_token_digest(issued.record.token_digest)

    assert context is None
    assert record is not None and record.state is SessionState.EXPIRED


@pytest.mark.asyncio
async def test_concurrent_session_limit_fails_closed() -> None:
    service, _, _, _ = direct_service(max_sessions=1)
    authentication = AuthenticationInput(
        correlation_id="cor_limit",
        authorization_scheme="basic",
        credential=base64.b64encode(b"operator:correct-password").decode(),
    )
    results = await asyncio.gather(
        service.create(authentication),
        service.create(authentication),
        return_exceptions=True,
    )

    assert sum(not isinstance(item, BaseException) for item in results) == 1
    errors = [item for item in results if isinstance(item, SessionOperationsError)]
    assert len(errors) == 1
    assert errors[0].code == "session_limit_exceeded"


@pytest.mark.asyncio
async def test_stale_session_update_cannot_resurrect_revoked_state() -> None:
    service, repository, _, _ = direct_service()
    issued = await service.create(
        AuthenticationInput(
            correlation_id="cor_race_create",
            authorization_scheme="basic",
            credential=base64.b64encode(b"operator:correct-password").decode(),
        )
    )
    original = issued.record
    revoked = replace(
        original,
        version=2,
        state=SessionState.REVOKED,
        revoked_at=NOW,
        revocation_reason="user_logout",
    )
    stale_touch = replace(
        original,
        version=2,
        last_seen_at=NOW + timedelta(seconds=1),
        idle_expires_at=NOW + timedelta(minutes=15, seconds=1),
    )

    assert await repository.update(revoked, expected_version=1) is True
    assert await repository.update(stale_touch, expected_version=1) is False
    stored = await repository.get_by_token_digest(original.token_digest)

    assert stored is not None
    assert stored.state is SessionState.REVOKED


def test_required_session_creation_audit_failure_blocks_cookie_issuance() -> None:
    sink = SessionCreationFailingAuditSink()
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
        ),
        raise_server_exceptions=False,
    ) as client:
        response = login(client)

    assert response.status_code == 500
    assert "set-cookie" not in response.headers
    assert "correct-password" not in response.text


@pytest.mark.asyncio
async def test_repository_retains_only_digests_and_api_token_kind_is_not_issued() -> None:
    service, repository, _, _ = direct_service()
    issued = await service.create(
        AuthenticationInput(
            correlation_id="cor_digest",
            authorization_scheme="basic",
            credential=base64.b64encode(b"operator:correct-password").decode(),
        )
    )
    stored = await repository.get_by_token_digest(issued.record.token_digest)

    assert stored is not None
    assert stored.credential_kind is CredentialKind.BROWSER_SESSION
    assert issued.token not in repr(stored)
    assert issued.csrf_token not in repr(stored)
    assert len(stored.token_digest) == len(stored.csrf_digest) == 64
    assert CredentialKind.API_TOKEN.value == "api_token"
