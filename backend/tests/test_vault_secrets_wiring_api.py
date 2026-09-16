"""Production cutover plan (self-built connector-credential vault, Part B): HTTP-level wiring
for `atlas.api.routes.vault_secrets`.

Proves: (a) a real human actor can set and list vault secret metadata end to end over HTTP, and
the plaintext value is never echoed back; (b) the established two-stage denial pattern (true 401
for no session, true 403 for a session with zero granted permissions) holds for both routes.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from test_browser_sessions import settings

from atlas.api.app import create_app

_SECRET_REFERENCE_ID = "secret.hitachi.readonly"


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201, response.text
    return str(response.headers["X-CSRF-Token"])


def test_set_then_list_connector_vault_secret_over_http() -> None:
    with TestClient(
        create_app(settings(development_subject_id="subject.vault-secrets-wiring.set-list"))
    ) as client:
        csrf = _login(client)

        put_response = client.put(
            f"/api/v1/connectors/vault-secrets/{_SECRET_REFERENCE_ID}",
            json={"value": "Basic dGVzdDp0ZXN0"},
            headers={"X-CSRF-Token": csrf},
        )
        assert put_response.status_code == 200, put_response.text
        body = put_response.json()["data"]
        assert body["secret_reference_id"] == _SECRET_REFERENCE_ID
        assert "value" not in body
        assert put_response.headers["Cache-Control"] == "no-store"
        assert "dGVzdDp0ZXN0" not in put_response.text

        list_response = client.get("/api/v1/connectors/vault-secrets")
        assert list_response.status_code == 200, list_response.text
        references = list_response.json()["data"]
        assert any(item["secret_reference_id"] == _SECRET_REFERENCE_ID for item in references)
        assert all("value" not in item for item in references)


def test_set_connector_vault_secret_rejects_an_invalid_reference_format() -> None:
    with TestClient(
        create_app(settings(development_subject_id="subject.vault-secrets-wiring.invalid"))
    ) as client:
        csrf = _login(client)

        response = client.put(
            "/api/v1/connectors/vault-secrets/not-a-valid-reference",
            json={"value": "Basic dGVzdDp0ZXN0"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422, response.text


def test_connector_vault_secrets_require_authentication() -> None:
    """No session cookie and development identity disabled: both routes must fail closed at
    authentication, not merely at authorization."""
    with TestClient(create_app(settings(development_identity_enabled=False))) as client:
        put_response = client.put(
            f"/api/v1/connectors/vault-secrets/{_SECRET_REFERENCE_ID}",
            json={"value": "Basic dGVzdDp0ZXN0"},
        )
        get_response = client.get("/api/v1/connectors/vault-secrets")

    assert put_response.status_code == 401, put_response.text
    assert get_response.status_code == 401, get_response.text


def test_connector_vault_secrets_deny_an_authenticated_subject_with_no_granted_permissions() -> (
    None
):
    """A real, logged-in human subject with zero granted role permissions must still be denied by
    the real `AuthorizationService` at the vault-secret permission check, not by a faked
    dependency override."""
    with TestClient(create_app(settings(development_role_ids=()))) as client:
        csrf = _login(client)

        put_response = client.put(
            f"/api/v1/connectors/vault-secrets/{_SECRET_REFERENCE_ID}",
            json={"value": "Basic dGVzdDp0ZXN0"},
            headers={"X-CSRF-Token": csrf},
        )
        get_response = client.get("/api/v1/connectors/vault-secrets")

    assert put_response.status_code == 403, put_response.text
    assert get_response.status_code == 403, get_response.text
