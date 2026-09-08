"""ATLAS-035 SS19: the detection content contract, nine-stage lifecycle, and SIEM-originated
incident handoff summary (`baseline_detections.py`, `detection_content.py`,
`detection_lifecycle.py`, `handoff_metrics.py`, `application/detection_audit.py`) were real,
fully-tested domain code with no application service, repository, route, or DI wiring calling
them -- the same "built but structurally unreachable" pattern found repeatedly this session.
These tests exercise the new `/security-export/detections/...` endpoints through the real HTTP
API to prove the wiring genuinely closes that gap.
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


def test_siem_detection_lifecycle_full_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        registered = client.post(
            "/api/v1/security-export/detections/deployment.siem-uc-001.wiring-test",
            json={
                "detection_id": "SIEM-UC-001",
                "destination_id": "destination.siem-collector.wiring-test",
                "owner": "team.security-operations",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert registered.status_code == 201, registered.text
        data = registered.json()["data"]
        assert data["stage"] == "registered"
        assert data["detection_id"] == "SIEM-UC-001"

        for target_stage in (
            "configured_inactive",
            "validated",
            "fixtures_replayed",
            "verified",
            "deployed_test_mode",
            "production_active",
        ):
            transitioned = client.post(
                "/api/v1/security-export/detections/deployment.siem-uc-001.wiring-test/transitions",
                json={"target_stage": target_stage},
                headers={"X-CSRF-Token": csrf},
            )
            assert transitioned.status_code == 200, transitioned.text
            assert transitioned.json()["data"]["stage"] == target_stage

        handoff = client.post(
            "/api/v1/security-export/detections/"
            "deployment.siem-uc-001.wiring-test/incident-handoffs",
            json={
                "alert_reference": "alert.wiring-test.0001",
                "event_references": ["event.wiring-test.0001"],
                "confidence": "high",
                "triage_status": "new",
                "affected_deployment": "environment.test",
                "affected_services": ["service.storage-health"],
                "affected_targets": ["target.storage.lab.a01"],
                "investigation_summary": "Synthetic detection fired during the wiring test.",
                "evidence_link_kinds": ["audit_ledger_reference"],
                "ownership": "team.security-operations",
                "synchronization_state": "synced",
                "ai_generated_summary": False,
                "summary_labeled_as_ai_generated": False,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert handoff.status_code == 201, handoff.text
        handoff_data = handoff.json()["data"]
        assert handoff_data["alert_reference"] == "alert.wiring-test.0001"
        assert handoff_data["detection_id"] == "SIEM-UC-001"


def test_siem_detection_handoff_denied_before_the_detection_is_live() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        client.post(
            "/api/v1/security-export/detections/deployment.siem-uc-002.wiring-test",
            json={
                "detection_id": "SIEM-UC-002",
                "destination_id": "destination.siem-collector.wiring-test",
                "owner": "team.security-operations",
            },
            headers={"X-CSRF-Token": csrf},
        )
        handoff = client.post(
            "/api/v1/security-export/detections/"
            "deployment.siem-uc-002.wiring-test/incident-handoffs",
            json={
                "alert_reference": "alert.wiring-test.0002",
                "event_references": ["event.wiring-test.0002"],
                "confidence": "high",
                "triage_status": "new",
                "affected_deployment": "environment.test",
                "affected_services": [],
                "affected_targets": [],
                "investigation_summary": "Attempted before the detection is live.",
                "evidence_link_kinds": ["audit_ledger_reference"],
                "ownership": "team.security-operations",
                "synchronization_state": "synced",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert handoff.status_code == 422
        assert handoff.json()["code"] == "siem_detection_not_live"


def test_siem_detection_lifecycle_rejects_an_invalid_transition() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        client.post(
            "/api/v1/security-export/detections/deployment.siem-uc-003.wiring-test",
            json={
                "detection_id": "SIEM-UC-003",
                "destination_id": "destination.siem-collector.wiring-test",
                "owner": "team.security-operations",
            },
            headers={"X-CSRF-Token": csrf},
        )
        skipped = client.post(
            "/api/v1/security-export/detections/deployment.siem-uc-003.wiring-test/transitions",
            json={"target_stage": "production_active"},
            headers={"X-CSRF-Token": csrf},
        )
        assert skipped.status_code == 422
        assert skipped.json()["code"] == "siem_detection_lifecycle_transition_invalid"
