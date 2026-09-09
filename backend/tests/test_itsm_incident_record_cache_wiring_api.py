"""ATLAS-036 SS5/SS6: the normalized ITSM object model's `IncidentRecord`
(`itsm/domain/records.py`) was real, fully-tested domain code with no application service,
repository, route, or DI wiring calling it -- the same "built but structurally unreachable"
pattern found repeatedly this session. These tests exercise the new
`/itsm/incident-records/{integration_reference}` endpoints through the real HTTP API to prove the
wiring genuinely closes that gap.
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


def _incident_payload() -> dict[str, object]:
    created_at = (NOW - timedelta(hours=2)).isoformat()
    return {
        "profile_id": "itsm-integration.wiring-test",
        "external_system": "generic_rest",
        "external_instance": "itsm-instance.wiring-test",
        # a vendor-formatted record id -- exactly the shape that used to crash
        # validate_stable_identifier before the pass-16 fix.
        "external_record_id": "INC0012345",
        "display_number": "INC0012345",
        "title": "Storage array reporting elevated latency",
        "sanitized_summary": "Elevated latency observed on a synthetic storage array.",
        "state": "in_progress",
        "priority": "high",
        "impact": "moderate",
        "urgency": "high",
        "severity": "high",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "organizational_scope": "org.atlas",
        "created_at": created_at,
        "updated_at": NOW.isoformat(),
        # the vendor's own numeric concurrency token -- also previously crash-prone.
        "external_version": "42",
        "classification": "internal",
        "access_policy_reference": "access-policy.itsm.wiring-test",
        "retention_reference": "retention-policy.itsm.wiring-test",
        "last_synchronized_at": NOW.isoformat(),
        "last_synchronization_status": "synchronized",
        "detection_source": "monitoring_alert",
        "first_observed_at": created_at,
        "symptoms": "Elevated read latency on a synthetic storage array.",
        "affected_services": ["service.storage-health"],
        "current_impact_summary": "Degraded read performance for one lab array.",
        "evidence_references": ["evidence.wiring-test.0001"],
        "investigation_references": ["investigation.wiring-test.0001"],
        "probable_causes": ["controller_saturation"],
        "current_status_summary": "Investigation in progress.",
    }


def test_itsm_incident_record_cache_requires_authentication() -> None:
    """No session cookie and no development identity: the route must fail closed at
    authentication, not merely at authorization -- proving `authenticated_subject` really runs.
    """
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get(
            "/api/v1/itsm/incident-records/integration-reference.wiring-test-auth",
        )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_itsm_incident_record_cache_requires_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must still be denied
    by the real `AuthorizationService`, not by a faked dependency override. Covers both routes in
    this file, which share `authorize_itsm_incident_record_cache_manage`.
    """
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)

        upserted = client.post(
            "/api/v1/itsm/incident-records/integration-reference.wiring-test-denied",
            json=_incident_payload(),
            headers={"X-CSRF-Token": csrf},
        )
        fetched = client.get(
            "/api/v1/itsm/incident-records/integration-reference.wiring-test-denied",
        )

    assert upserted.status_code == 403
    assert upserted.json()["code"] == "authorization_denied"
    assert fetched.status_code == 403
    assert fetched.json()["code"] == "authorization_denied"


def test_itsm_incident_record_upsert_and_get_are_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        upserted = client.post(
            "/api/v1/itsm/incident-records/integration-reference.wiring-test-0001",
            json=_incident_payload(),
            headers={"X-CSRF-Token": csrf},
        )
        assert upserted.status_code == 201, upserted.text
        data = upserted.json()["data"]
        assert data["integration_reference"] == "integration-reference.wiring-test-0001"
        assert data["external_record_id"] == "INC0012345"
        assert data["external_version"] == "42"

        fetched = client.get(
            "/api/v1/itsm/incident-records/integration-reference.wiring-test-0001",
        )
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["data"]["title"] == "Storage array reporting elevated latency"


def test_itsm_incident_record_get_before_upsert_is_not_found() -> None:
    with TestClient(create_app(_settings())) as client:
        _login(client)
        response = client.get(
            "/api/v1/itsm/incident-records/integration-reference.wiring-test-missing",
        )
        assert response.status_code == 404
        assert response.json()["code"] == "itsm_incident_record_not_found"


def test_itsm_incident_record_rejects_an_unrecognized_classification() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        payload = _incident_payload()
        payload["classification"] = "not-a-real-classification"
        response = client.post(
            "/api/v1/itsm/incident-records/integration-reference.wiring-test-0002",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "itsm_incident_record_classification_unrecognized"
