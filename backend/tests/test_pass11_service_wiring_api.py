"""Pass 11 found that RcaService.review()/close(), SyslogDestinationAdministrationService, and
EmbeddingModelLifecycleService (all built in earlier passes) were real, tested at the service
layer, but reachable through no route anywhere -- a governed service nobody can actually call.
These tests exercise each one through the real HTTP API, not just the service layer directly, to
prove the wiring genuinely closes that gap.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


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


def _rca_payload() -> dict[str, object]:
    return {
        "incident_id": "INC-2026-0099",
        "user_report": "Storage warning appeared during the service window.",
        "expected_behavior": "Storage paths remain healthy and redundant.",
        "actual_behavior": "Controller CTL01 reports a warning.",
        "window_start": (NOW - timedelta(hours=24)).isoformat(),
        "window_end": NOW.isoformat(),
        "max_evidence_records": 12,
    }


def test_rca_review_and_close_are_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        created = client.post(
            "/api/v1/rca/storage/asset.storage.lab.b28",
            json=_rca_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "rca-wiring-0001"},
        )
        assert created.status_code == 200
        case = created.json()["data"]

        reviewed = client.post(
            f"/api/v1/rca/cases/{case['case_id']}/review",
            json={
                "expected_version": case["version"],
                "status": "accepted",
                "decision_reason": "Evidence and hypotheses are sound.",
                "domain_confirmation_criterion": None,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert reviewed.status_code == 200
        reviewed_case = reviewed.json()["data"]
        assert reviewed_case["state"] == "reviewed"

        closed = client.post(
            f"/api/v1/rca/cases/{case['case_id']}/close",
            json={"expected_version": reviewed_case["version"]},
            headers={"X-CSRF-Token": csrf},
        )
        assert closed.status_code == 200
        assert closed.json()["data"]["state"] == "closed"


def test_syslog_destination_administration_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        registered = client.post(
            "/api/v1/security-export/destinations",
            json={
                "destination_id": "destination.siem-collector.wiring-test",
                "owner": "subject.security-engineer.primary",
                "purpose": "Forward security audit events to the enterprise SIEM.",
                "environment_id": "environment.test",
                "maintenance_windows": [],
                "health_alert_recipients": ["team.security-operations@example.com"],
                "mandatory": False,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert registered.status_code == 201
        assert registered.json()["data"]["active_version"] == 1

        steps = [
            "saved_non_active_version",
            "syntax_dns_route_port",
            "tls_trust_and_identity",
            "test_event_sent",
            "collector_receipt_confirmed",
            "mapping_previewed",
            "rate_and_capacity_estimated",
            "activated",
        ]
        for step in steps:
            step_response = client.post(
                "/api/v1/security-export/destinations/"
                "destination.siem-collector.wiring-test/validation-steps",
                json={"step": step},
                headers={"X-CSRF-Token": csrf},
            )
            assert step_response.status_code == 200

        activated = client.post(
            "/api/v1/security-export/destinations/destination.siem-collector.wiring-test/activate",
            headers={"X-CSRF-Token": csrf},
        )
        assert activated.status_code == 200
        assert activated.json()["data"]["active_version"] == 2

        disabled = client.post(
            "/api/v1/security-export/destinations/destination.siem-collector.wiring-test/disable",
            json={
                "reason": "Replacing with a new collector endpoint.",
                "elevated_authorization": False,
                "warning_acknowledged": False,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert disabled.status_code == 204


def test_embedding_model_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        registered = client.post(
            "/api/v1/knowledge/embedding-models/model.embedding.wiring-test",
            headers={"X-CSRF-Token": csrf},
        )
        assert registered.status_code == 201
        assert registered.json()["data"]["stage"] == "candidate"

        for target_stage in ("evaluating", "approved", "active"):
            transitioned = client.post(
                "/api/v1/knowledge/embedding-models/model.embedding.wiring-test/transitions",
                json={"target_stage": target_stage},
                headers={"X-CSRF-Token": csrf},
            )
            assert transitioned.status_code == 200
            assert transitioned.json()["data"]["stage"] == target_stage


def test_ai_model_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        registered = client.post(
            "/api/v1/ai/models/model.local-llama-70b-wiring-test",
            headers={"X-CSRF-Token": csrf},
        )
        assert registered.status_code == 201
        assert registered.json()["data"]["stage"] == "registered"

        for target_stage in ("under_evaluation", "approved_for_production_tasks"):
            transitioned = client.post(
                "/api/v1/ai/models/model.local-llama-70b-wiring-test/transitions",
                json={"target_stage": target_stage},
                headers={"X-CSRF-Token": csrf},
            )
            assert transitioned.status_code == 200
            assert transitioned.json()["data"]["stage"] == target_stage
