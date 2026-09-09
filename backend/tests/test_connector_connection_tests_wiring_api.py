"""Pass 23 of this session's standing audit loop found that
`atlas.api.routes.connector_connection_tests` (7 endpoints: connection-configuration GET/PUT,
connection-tests POST/GET latest, runtime-state GET, enable/disable POST) has exactly one test
file -- test_bundled_connector_connection.py -- whose `build_app()` helper mounts the router on a
bare `FastAPI()` instance with `app.dependency_overrides[browser_session_subject]`,
`app.dependency_overrides[authorize_connector_target_session_create]`, and
`app.dependency_overrides[authorize_connector_target_session_read]` all replaced with fakes. That
bypasses real RBAC/`RoleAssignment` resolution and the permission-decorator wiring in
`atlas.api.app.create_app` entirely.

These tests drive all 7 endpoints through the real, wired app instead: a real login against
`/api/v1/authentication/sessions`, real browser-session/CSRF handling, and real permission
resolution against the live authorization catalog (`DEVELOPMENT_ROLE_ID` is granted
`CONNECTOR_TARGET_SESSION_READ`/`CONNECTOR_TARGET_SESSION_CREATE`; see
`atlas.modules.authorization.application.bootstrap`). They do not replace
test_bundled_connector_connection.py, whose service-layer coverage (vendor probe wiring, secret
minimization, fail-closed production behavior) has standalone value the real HTTPS probe cannot
reproduce deterministically over the network.

`BundledConnectionConfigurationService`, `ConnectorConnectionTestService`, and
`BundledConnectorRuntimeStateService` all gate their real business logic on
`deployment_environment == "development"` (see each service's `_require_development_human`), so
`environment="development"` is required here -- `environment="test"` would make every one of
these 7 endpoints fail closed with a `..._development_only` error before ever reaching the
authorization-wiring question this pass is closing. The connection-test step deliberately never
sets `ATLAS_HITACHI_AUTHORIZATION` (and actively deletes it via `monkeypatch`, in case it happens
to be set in the ambient shell), so `DevelopmentEnvironmentCredentialMaterializer` fails closed at
credential leasing with a real, deterministic `connection_test_credentials_unavailable` result --
before the real `HitachiOpsCenterConnectionTestHttpsFactory` transport ever attempts a network
call, exactly like test_bundled_connector_connection.py's own
`test_credential_unavailable_failure_is_stored_as_latest_without_secret`. This keeps the test
deterministic and network-free while still exercising the real, wired service instance from
`atlas.api.app.create_app`, not a test double.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings

CATALOG_ITEM_ID = "catalog.connector.hitachi.opscenter"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "development",
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


def _create_instance(client: TestClient, csrf: str, *, idempotency_key: str) -> dict[str, object]:
    listed = client.get("/api/v1/connectors/catalog", headers={"X-CSRF-Token": csrf})
    assert listed.status_code == 200
    descriptor = next(
        item for item in listed.json()["data"] if item["catalog_item_id"] == CATALOG_ITEM_ID
    )
    created = client.post(
        f"/api/v1/connectors/catalog/{CATALOG_ITEM_ID}/instances",
        json={
            "catalog_item_digest": descriptor["canonical_digest"],
            "instance_key": "hitachi-connection-wiring",
            "display_name": "Hitachi Connection Wiring Instance",
            "purpose": "Prove the connector connection-test routes are reachable through real "
            "authorization.",
            "acknowledged_instance_is_disabled_and_grants_no_authority": True,
        },
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": idempotency_key},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]  # type: ignore[no-any-return]


def test_connector_connection_tests_require_authentication() -> None:
    """No session cookie and no development identity: the routes must fail closed at
    authentication, not merely at authorization -- proving `browser_session_subject` really runs.
    """
    with TestClient(create_app(Settings(environment="development"))) as client:
        response = client.get(
            "/api/v1/connectors/bundled-instances/instance.wiring.unauth-check/runtime-state"
        )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_connector_connection_tests_require_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must still be denied
    by the real `AuthorizationService`, not by a faked dependency override.
    """
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)
        response = client.get(
            "/api/v1/connectors/bundled-instances/instance.wiring.unauth-check/runtime-state",
            headers={"X-CSRF-Token": csrf},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"


def test_connector_connection_tests_full_lifecycle_through_real_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_HITACHI_AUTHORIZATION", raising=False)
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        instance = _create_instance(client, csrf, idempotency_key="connection-wiring-create-0001")
        base = f"/api/v1/connectors/bundled-instances/{instance['instance_id']}"
        headers = {"X-CSRF-Token": csrf}

        initial_state = client.get(f"{base}/runtime-state", headers=headers)
        assert initial_state.status_code == 200
        assert initial_state.json()["data"]["state"] == "disabled"
        assert initial_state.json()["data"]["version"] == 0

        configured = client.put(
            f"{base}/connection-configuration",
            json={
                "hostname": "opscenter.storage.example",
                "port": 23451,
                "trust_profile_id": "trust.system-ca",
                "secret_reference_id": "secret.hitachi.readonly",
            },
            headers=headers,
        )
        assert configured.status_code == 200, configured.text
        assert configured.json()["data"]["protocol"] == "https"
        assert configured.json()["data"]["secret_material_stored"] is False

        fetched_configuration = client.get(f"{base}/connection-configuration", headers=headers)
        assert fetched_configuration.status_code == 200
        assert fetched_configuration.json()["data"] == configured.json()["data"]

        tested = client.post(f"{base}/connection-tests", headers=headers)
        assert tested.status_code == 200, tested.text
        tested_data = tested.json()["data"]
        assert tested_data["outcome"] == "failed"
        assert tested_data["result_code"] == "connection_test_credentials_unavailable"
        assert tested_data["managed_infrastructure_contacted"] is False
        assert tested_data["infrastructure_mutation_performed"] is False

        latest = client.get(f"{base}/connection-tests/latest", headers=headers)
        assert latest.status_code == 200
        assert latest.json()["data"] == tested_data
        assert latest.headers["cache-control"] == "no-store"

        enabled = client.post(
            f"{base}/enable",
            json={"acknowledged_read_only_operation": True},
            headers=headers,
        )
        assert enabled.status_code == 403
        assert enabled.json()["code"] == "bundled_runtime_passing_test_required"

        disabled = client.post(
            f"{base}/disable",
            json={
                "reason": "Confirm disable is refused while the runtime was never enabled.",
                "acknowledged_runtime_stop": True,
            },
            headers=headers,
        )
        assert disabled.status_code == 422
        assert disabled.json()["code"] == "bundled_runtime_not_enabled"
