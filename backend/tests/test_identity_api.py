from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.identity.adapters.development import DevelopmentIdentityProvider
from atlas.modules.identity.domain.models import AuthenticationInput


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class FailingAuditSink:
    async def record(self, event: AuditRecord) -> None:
        raise RuntimeError("audit unavailable")


def test_protected_identity_endpoint_requires_authentication_by_default() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(Settings(environment="test"), audit_sink=audit_sink)) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"X-Correlation-ID": "cor_identity_required"},
        )

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "authentication_required"
    assert response.json()["correlation_id"] == "cor_identity_required"
    assert audit_sink.records[0].event_type == "atlas.identity.authentication.denied"
    assert audit_sink.records[0].subject_id is None


def test_development_identity_is_authorized_with_exact_server_configuration() -> None:
    audit_sink = CollectingAuditSink()
    settings = Settings(environment="test", development_identity_enabled=True)
    with TestClient(create_app(settings, audit_sink=audit_sink)) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"X-Correlation-ID": "cor_identity_allowed"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"]["subject_id"] == "subject.development.operator"
    assert payload["data"]["display_name"] == "Local Operator"
    assert payload["data"]["authentication"]["method"] == "development"
    assert payload["data"]["scope"]["capability_class"] == "C0"
    assert payload["data"]["effective_role_versions"] == ["role.development.operator:v1"]
    assert payload["meta"]["correlation_id"] == "cor_identity_allowed"
    assert [record.event_type for record in audit_sink.records] == [
        "atlas.identity.authentication.succeeded",
        "atlas.authorization.access.allowed",
    ]


@pytest.mark.asyncio
async def test_development_identity_accepts_only_exact_local_browser_credentials() -> None:
    settings = Settings(environment="test", development_identity_enabled=True)
    provider = DevelopmentIdentityProvider(settings)

    accepted = await provider.authenticate(
        AuthenticationInput(
            correlation_id="cor_development_browser_login",
            authorization_scheme="basic",
            credential=base64.b64encode(b"atlas-demo:local-demo").decode(),
        )
    )
    denied = await provider.authenticate(
        AuthenticationInput(
            correlation_id="cor_development_browser_login_denied",
            authorization_scheme="basic",
            credential=base64.b64encode(b"atlas-demo:wrong-password").decode(),
        )
    )

    assert accepted is not None
    assert accepted.subject_id == settings.development_subject_id
    assert denied is None


def test_authenticated_subject_without_assignment_receives_safe_denial() -> None:
    settings = Settings(
        environment="test",
        development_identity_enabled=True,
        development_role_ids=(),
    )
    with TestClient(create_app(settings, audit_sink=CollectingAuditSink())) as client:
        response = client.get("/api/v1/identity/me")

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "assignment" not in response.text.lower()
    assert "role" not in response.text.lower()


def test_client_identity_headers_and_unverified_bearer_token_cannot_elevate() -> None:
    settings = Settings(environment="test", development_identity_enabled=True)
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings, audit_sink=audit_sink)) as client:
        header_only_response = client.get(
            "/api/v1/identity/me",
            headers={
                "X-Atlas-Subject": "subject.attacker",
                "X-Atlas-Roles": "role.security.administrator",
            },
        )
        bearer_response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Bearer unverified-token"},
        )

    assert header_only_response.status_code == 200
    assert header_only_response.json()["data"]["subject_id"] == ("subject.development.operator")
    assert bearer_response.status_code == 401
    assert "unverified-token" not in repr(audit_sink.records)


def test_audit_failure_blocks_protected_identity_request() -> None:
    settings = Settings(environment="test", development_identity_enabled=True)
    with TestClient(
        create_app(settings, audit_sink=FailingAuditSink()),
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/api/v1/identity/me")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "subject.development.operator" not in response.text


def test_development_identity_cannot_be_enabled_in_production() -> None:
    try:
        Settings(environment="production", development_identity_enabled=True)
    except ValidationError as error:
        assert "cannot be enabled in production" in str(error)
    else:
        raise AssertionError("production configuration unexpectedly accepted development identity")


def test_interactive_api_documentation_cannot_be_enabled_in_production() -> None:
    try:
        Settings(environment="production", enable_api_docs=True)
    except ValidationError as error:
        assert "interactive API documentation cannot be enabled in production" in str(error)
    else:
        raise AssertionError("production configuration unexpectedly enabled interactive API docs")


def test_production_configuration_accepts_disabled_interactive_api_documentation() -> None:
    settings = Settings(environment="production", enable_api_docs=False)

    assert settings.enable_api_docs is False
