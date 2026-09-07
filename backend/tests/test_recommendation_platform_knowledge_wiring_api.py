"""RecommendationOutcomeService, BootstrapRollbackService, and
KnowledgeSourceRegistrationService (all built in earlier passes) were real, tested at the service
layer, but reachable through no route anywhere -- a governed service nobody can actually call.
These tests exercise each one through the real HTTP API, not just the service layer directly, to
prove the wiring genuinely closes that gap.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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


def test_recommendation_outcome_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        started_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        payload = {
            "recommendation_version": 1,
            "plan_option_id": "plan-option.a",
            "recorded_by": "subject.reviewer.primary",
            "deviations_from_plan": [],
            "actual_started_at": started_at,
            "actual_duration_minutes": 45,
            "actual_interruption_minutes": None,
            "affected_scope": ["asset.storage.lab.b28"],
            "result": "success",
            "actual_root_cause": None,
            "root_cause_validated": False,
            "new_incidents": [],
            "side_effects": [],
            "reviewer_lessons": "The plan matched the actual remediation steps closely.",
            "follow_up": [],
        }

        recorded = client.post(
            "/api/v1/recommendations/recommendation.wiring-test/outcomes",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )
        assert recorded.status_code == 201
        data = recorded.json()["data"]
        assert data["recommendation_id"] == "recommendation.wiring-test"
        assert data["result"] == "success"

        fetched = client.get(
            "/api/v1/recommendations/recommendation.wiring-test/outcomes",
            headers={"X-CSRF-Token": csrf},
        )
        assert fetched.status_code == 200
        assert fetched.json()["data"]["outcome_id"] == data["outcome_id"]


def test_bootstrap_rollback_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        artifacts_available_until = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        plan_payload = {
            "plan_id": "plan.bootstrap-rollback.wiring-test",
            "release_id": "release.wiring-test.v2",
            "target_release_id": "release.wiring-test.v1",
            "support": {
                "release_id": "release.wiring-test.v2",
                "application_rollback_supported": True,
                "data_rollback_supported": True,
                "unsupported_rationale": None,
            },
            "schema_check": {
                "current_schema_revision": "schema.v2",
                "target_schema_revision": "schema.v1",
                "irreversible_migrations_applied": [],
                "compatible": True,
            },
            "component_compatibility": [],
            "configuration_rollback_independent": True,
            "secret_rollback_independent": True,
            "artifacts_available_until": artifacts_available_until,
        }

        planned = client.post(
            "/api/v1/platform/bootstrap-rollback/plans",
            json=plan_payload,
            headers={"X-CSRF-Token": csrf},
        )
        assert planned.status_code == 201
        plan_data = planned.json()["data"]
        assert plan_data["plan_id"] == "plan.bootstrap-rollback.wiring-test"
        assert plan_data["is_permitted"] is True

        started_at = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
        attempt_payload = {
            "attempt_id": "attempt.bootstrap-rollback.wiring-test",
            "started_at": started_at,
            "outcome": "succeeded",
            "post_rollback_health_check_passed": True,
            "post_rollback_security_check_passed": True,
            "failure_recovery_reference": None,
        }
        attempted = client.post(
            "/api/v1/platform/bootstrap-rollback/plans/"
            "plan.bootstrap-rollback.wiring-test/attempts",
            json=attempt_payload,
            headers={"X-CSRF-Token": csrf},
        )
        assert attempted.status_code == 201
        attempt_data = attempted.json()["data"]
        assert attempt_data["plan_id"] == "plan.bootstrap-rollback.wiring-test"
        assert attempt_data["outcome"] == "succeeded"


def test_knowledge_source_registration_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        registration_payload = {
            "display_name": "Vendor Documentation Portal",
            "source_type": "documentation_site",
            "source_class": "vendor_authoritative",
            "owner": "team.knowledge-operations",
            "technical_contact": "person.jane-doe",
            "acquisition_method": "scheduled_crawl",
            "acquisition_endpoint": "https://vendor.example.com/docs",
            "secret_reference_id": "secret.knowledge-source.wiring-test",
            "organization_id": "organization.atlas-dev",
            "tenant_id": "tenant.default",
            "environment_id": "environment.test",
            "vendor": "Example Vendor",
            "product": "Storage Array",
            "default_classification": "internal",
            "access_mapping_method": "role-based",
            "expected_version_behavior": "Content updates weekly with version tags.",
            "authority_trust_rationale": (
                "Vendor-authoritative documentation is the source of truth for supported "
                "configurations."
            ),
            "retention_policy": "Retain latest 5 versions.",
            "deletion_policy": "Purge on source retirement.",
            "license_or_usage_restrictions": "Internal use only.",
            "ingestion_schedule": "weekly",
            "failure_policy": "Alert knowledge-operations on ingestion failure.",
        }

        registered = client.post(
            "/api/v1/knowledge/sources/source.vendor-docs.wiring-test",
            json=registration_payload,
            headers={"X-CSRF-Token": csrf},
        )
        assert registered.status_code == 201
        assert registered.json()["data"]["state"] == "registered"

        for target_state in ("validating", "active"):
            transitioned = client.post(
                "/api/v1/knowledge/sources/source.vendor-docs.wiring-test/transitions",
                json={"target": target_state},
                headers={"X-CSRF-Token": csrf},
            )
            assert transitioned.status_code == 200
            assert transitioned.json()["data"]["state"] == target_state
