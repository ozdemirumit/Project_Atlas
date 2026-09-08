"""ATLAS-036 SS13: `ItsmCiMappingRule` and `ItsmCiReconciliationConflict`
(`itsm/domain/cmdb_reconciliation.py`) were real, fully-tested domain code with no application
service, repository, route, or DI wiring calling them -- the same "built but structurally
unreachable" pattern found repeatedly this session. These tests exercise the new
`/itsm/cmdb-reconciliation/...` endpoints through the real HTTP API to prove the wiring genuinely
closes that gap.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings

NOW = datetime.now(UTC)


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


def test_itsm_ci_mapping_rule_registration_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/itsm/cmdb-reconciliation/mapping-rules/rule.wiring-test-0001",
            json={
                "version": 1,
                "external_ci_class": "cmdb_ci_server",
                "atlas_entity_type": "storage_system",
                "profile_id": "itsm-integration.wiring-test",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["rule_id"] == "rule.wiring-test-0001"
        assert data["external_ci_class"] == "cmdb_ci_server"


def test_itsm_ci_reconciliation_conflict_full_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        cmdb_observed_at = (NOW - timedelta(hours=1)).isoformat()
        live_observed_at = NOW.isoformat()
        recorded = client.post(
            "/api/v1/itsm/cmdb-reconciliation/conflicts/conflict.wiring-test-0001",
            json={
                # a vendor-formatted CI id (numeric-leading, uppercase) -- this is exactly the
                # shape that used to crash validate_stable_identifier before the pass-16 fix.
                "external_ci_id": "7f3a9c1e4b2d",
                "mapped_atlas_entity_id": "entity.storage-system.lab-a01",
                "field": "lifecycle_state",
                "cmdb_value": "in_service",
                "cmdb_observed_at": cmdb_observed_at,
                "live_value": "retired",
                "live_observed_at": live_observed_at,
                "proposed_authority": "live_observation",
                "confidence": 0.8,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert recorded.status_code == 201, recorded.text
        data = recorded.json()["data"]
        assert data["external_ci_id"] == "7f3a9c1e4b2d"
        assert data["match_state"] == "ambiguous"

        updated = client.post(
            "/api/v1/itsm/cmdb-reconciliation/conflicts/conflict.wiring-test-0001/match-state",
            json={"match_state": "matched"},
            headers={"X-CSRF-Token": csrf},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["data"]["match_state"] == "matched"


def test_itsm_ci_reconciliation_conflict_requires_disagreeing_values() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        cmdb_observed_at = (NOW - timedelta(hours=1)).isoformat()
        live_observed_at = NOW.isoformat()
        response = client.post(
            "/api/v1/itsm/cmdb-reconciliation/conflicts/conflict.wiring-test-0002",
            json={
                "external_ci_id": "9a8b7c6d5e4f",
                "mapped_atlas_entity_id": "entity.storage-system.lab-a02",
                "field": "criticality",
                "cmdb_value": "high",
                "cmdb_observed_at": cmdb_observed_at,
                "live_value": "high",
                "live_observed_at": live_observed_at,
                "proposed_authority": "cmdb",
                "confidence": 0.5,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "itsm_ci_reconciliation_conflict_invalid"
