"""Pass 23 of this session's standing audit loop found that
`atlas.api.routes.bundled_connector_catalog` (`GET /connectors/catalog`,
`POST /connectors/catalog/{id}/instances`) has exactly one test file --
test_bundled_connector_catalog.py -- and its only HTTP-level check
(`test_catalog_router_uses_safe_envelopes_and_existing_authorization_dependencies`) mounts the
router on a bare `FastAPI()` instance with `app.dependency_overrides[browser_session_subject]`,
`app.dependency_overrides[authorize_connector_instance_read]`, and
`app.dependency_overrides[authorize_connector_instance_create]` all replaced with fakes. That
bypasses real RBAC/`RoleAssignment` resolution and the permission-decorator wiring in
`atlas.api.app.create_app` entirely -- only the route handlers' own internal logic has ever been
exercised over HTTP, with authorization faked out.

These tests drive both endpoints through the real, wired app instead: a real login against
`/api/v1/authentication/sessions`, real browser-session/CSRF handling, and real permission
resolution against the live ~150-permission authorization catalog (see
`atlas.modules.authorization.application.bootstrap`, where `DEVELOPMENT_ROLE_ID`'s
`RoleDefinition` is granted `CONNECTOR_INSTANCE_READ`/`CONNECTOR_INSTANCE_CREATE`). They do not
replace test_bundled_connector_catalog.py, whose service-layer and fake-dependency-override
coverage still has standalone value for the route handlers' own contrived-edge-case logic.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings

CATALOG_ITEM_ID = "catalog.connector.hitachi.opscenter"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def test_bundled_connector_catalog_requires_authentication() -> None:
    """No session cookie and no development identity: the route must fail closed at
    authentication, not merely at authorization -- proving `browser_session_subject` really runs.
    """
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/connectors/catalog")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_bundled_connector_catalog_requires_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must still be denied
    by the real `AuthorizationService`, not by a faked dependency override.
    """
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)
        listed = client.get("/api/v1/connectors/catalog")
        created = client.post(
            f"/api/v1/connectors/catalog/{CATALOG_ITEM_ID}/instances",
            json={
                "catalog_item_digest": "f" * 64,
                "instance_key": "hitachi-denied",
                "display_name": "Hitachi Denied",
                "purpose": "Prove that a real unprivileged identity is denied, not faked.",
                "acknowledged_instance_is_disabled_and_grants_no_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "catalog-wiring-denied-0001"},
        )

    assert listed.status_code == 403
    assert listed.json()["code"] == "authorization_denied"
    assert created.status_code == 403
    assert created.json()["code"] == "authorization_denied"


def test_bundled_connector_catalog_lists_and_creates_instance_through_real_authorization() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)

        listed = client.get("/api/v1/connectors/catalog", headers={"X-CSRF-Token": csrf})
        assert listed.status_code == 200
        assert listed.headers["Cache-Control"] == "no-store"
        descriptors = {item["catalog_item_id"]: item for item in listed.json()["data"]}
        assert CATALOG_ITEM_ID in descriptors
        descriptor = descriptors[CATALOG_ITEM_ID]
        assert descriptor["catalog_evidence_only"] is True
        assert descriptor["network_authority_granted"] is False
        assert descriptor["development_only"] is True

        created = client.post(
            f"/api/v1/connectors/catalog/{CATALOG_ITEM_ID}/instances",
            json={
                "catalog_item_digest": descriptor["canonical_digest"],
                "instance_key": "hitachi-wiring",
                "display_name": "Hitachi Wiring Instance",
                "purpose": "Prove the bundled connector catalog routes are reachable through "
                "real authorization.",
                "acknowledged_instance_is_disabled_and_grants_no_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "catalog-wiring-create-0001"},
        )
        assert created.status_code == 201, created.text
        assert created.headers["Cache-Control"] == "no-store"
        created_data = created.json()["data"]
        assert created_data["instance_state"] == "disabled_unconfigured"
        assert created_data["connector_enabled"] is False
        assert created_data["execution_authorized"] is False
        assert created_data["reused"] is False
        rendered = created.text.lower()
        for hidden in (
            "source_installation_receipt",
            "installation_store",
            "idempotency_key",
            "request_fingerprint",
            "package_digest",
            "target_endpoint",
            "credential_reference",
            "authorization_header",
        ):
            assert hidden not in rendered

        replayed = client.post(
            f"/api/v1/connectors/catalog/{CATALOG_ITEM_ID}/instances",
            json={
                "catalog_item_digest": descriptor["canonical_digest"],
                "instance_key": "hitachi-wiring",
                "display_name": "Hitachi Wiring Instance",
                "purpose": "Prove the bundled connector catalog routes are reachable through "
                "real authorization.",
                "acknowledged_instance_is_disabled_and_grants_no_authority": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "catalog-wiring-create-0001"},
        )
        assert replayed.status_code == 201, replayed.text
        replayed_data = replayed.json()["data"]
        assert replayed_data["reused"] is True
        assert replayed_data["record_id"] == created_data["record_id"]
