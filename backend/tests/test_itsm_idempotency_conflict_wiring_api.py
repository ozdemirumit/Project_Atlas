"""ATLAS-036 SS15/SS16: `ItsmCreationIntent` and `ItsmConflictRecord`
(`itsm/domain/idempotency_conflict.py`) were real, fully-tested domain code with no application
service, repository, route, or DI wiring calling them -- the same "built but structurally
unreachable" pattern found repeatedly this session. These tests exercise the new
`/itsm/idempotency-conflicts/...` endpoints through the real HTTP API to prove the wiring
genuinely closes that gap.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings


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


def test_itsm_idempotency_conflict_requires_authentication() -> None:
    """No session cookie and no development identity: the route must fail closed at
    authentication, not merely at authorization -- proving `authenticated_subject` really runs.
    """
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-auth",
            json={
                "idempotency_key": "idem-key-wiring-test-auth",
                "profile_id": "itsm-integration.wiring-test",
                "operation": "create_incident_draft",
                "deduplication_signature": "dedup-sig-wiring-test-auth",
            },
        )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_itsm_idempotency_conflict_requires_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must still be denied
    by the real `AuthorizationService`, not by a faked dependency override. Covers every route in
    this file, all of which share `authorize_itsm_idempotency_conflict_manage`.
    """
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)

        intent_recorded = client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-denied",
            json={
                "idempotency_key": "idem-key-wiring-test-denied",
                "profile_id": "itsm-integration.wiring-test",
                "operation": "create_incident_draft",
                "deduplication_signature": "dedup-sig-wiring-test-denied",
            },
            headers={"X-CSRF-Token": csrf},
        )
        intent_dispatched = client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-denied/dispatch",
            headers={"X-CSRF-Token": csrf},
        )
        intent_resolved = client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-denied/resolution",
            json={"resolution": "confirmed_created", "external_record_id": "INC0000002"},
            headers={"X-CSRF-Token": csrf},
        )
        conflict_recorded = client.post(
            "/api/v1/itsm/idempotency-conflicts/conflicts/conflict.wiring-test-denied",
            json={
                "profile_id": "itsm-integration.wiring-test",
                "external_record_id": "INC0099998",
                "kind": "concurrent_edit",
                "last_known_source_version": "7",
                "observed_source_version": "9",
                "field_ownership": "human_owned",
            },
            headers={"X-CSRF-Token": csrf},
        )
        conflict_resolved = client.post(
            "/api/v1/itsm/idempotency-conflicts/conflicts/conflict.wiring-test-denied/resolution",
            json={"resolution_summary": "Denied before reaching the service layer."},
            headers={"X-CSRF-Token": csrf},
        )

    for response in (
        intent_recorded,
        intent_dispatched,
        intent_resolved,
        conflict_recorded,
        conflict_resolved,
    ):
        assert response.status_code == 403
        assert response.json()["code"] == "authorization_denied"


def test_itsm_creation_intent_full_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        recorded = client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-0001",
            json={
                "idempotency_key": "idem-key-wiring-test-0001",
                "profile_id": "itsm-integration.wiring-test",
                "operation": "create_incident_draft",
                "deduplication_signature": "dedup-sig-wiring-test-0001",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert recorded.status_code == 201, recorded.text
        assert recorded.json()["data"]["state"] == "pending"

        replayed = client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-0001-replay",
            json={
                "idempotency_key": "idem-key-wiring-test-0001",
                "profile_id": "itsm-integration.wiring-test",
                "operation": "create_incident_draft",
                "deduplication_signature": "dedup-sig-wiring-test-0001",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert replayed.status_code == 201
        assert replayed.json()["data"]["intent_id"] == "intent.wiring-test-0001"

        dispatched = client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-0001/dispatch",
            headers={"X-CSRF-Token": csrf},
        )
        assert dispatched.status_code == 200
        assert dispatched.json()["data"]["state"] == "dispatched"

        resolved = client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-0001/resolution",
            json={
                "resolution": "confirmed_created",
                "external_record_id": "INC0012345",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resolved.status_code == 200, resolved.text
        resolved_data = resolved.json()["data"]
        assert resolved_data["state"] == "confirmed_created"
        assert resolved_data["external_record_id"] == "INC0012345"


def test_itsm_conflict_full_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        recorded = client.post(
            "/api/v1/itsm/idempotency-conflicts/conflicts/conflict.wiring-test-0001",
            json={
                "profile_id": "itsm-integration.wiring-test",
                "external_record_id": "INC0099999",
                "kind": "concurrent_edit",
                "last_known_source_version": "7",
                "observed_source_version": "9",
                "field_ownership": "human_owned",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert recorded.status_code == 201, recorded.text
        data = recorded.json()["data"]
        assert data["kind"] == "concurrent_edit"
        assert data["resolved_at"] is None

        resolved = client.post(
            "/api/v1/itsm/idempotency-conflicts/conflicts/conflict.wiring-test-0001/resolution",
            json={"resolution_summary": "Reviewed both versions; kept the human edit."},
            headers={"X-CSRF-Token": csrf},
        )
        assert resolved.status_code == 200, resolved.text
        resolved_data = resolved.json()["data"]
        assert resolved_data["resolution_summary"] is not None
        assert resolved_data["resolved_by"] is not None


def test_itsm_creation_intent_cannot_resolve_before_dispatch() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-0002",
            json={
                "idempotency_key": "idem-key-wiring-test-0002",
                "profile_id": "itsm-integration.wiring-test",
                "operation": "create_incident_draft",
                "deduplication_signature": "dedup-sig-wiring-test-0002",
            },
            headers={"X-CSRF-Token": csrf},
        )
        premature = client.post(
            "/api/v1/itsm/idempotency-conflicts/intents/intent.wiring-test-0002/resolution",
            json={"resolution": "confirmed_created", "external_record_id": "INC0000001"},
            headers={"X-CSRF-Token": csrf},
        )
        assert premature.status_code == 409
        assert premature.json()["code"] == "itsm_creation_intent_not_dispatched"
