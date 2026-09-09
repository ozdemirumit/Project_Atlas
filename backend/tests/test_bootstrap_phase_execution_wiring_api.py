"""Pass 23 of the standing audit loop found that seven bootstrap phase-execution
endpoints -- ``phases/data``, ``phases/handoff``, ``phases/identity``,
``phases/integrations``, ``phases/services``, ``phases/verify`` (each with a real
``authorize_bootstrap_state_manage``-gated route in its own ``bootstrap_*.py`` file) and
``bootstrap_state.py``'s ``POST .../checkpoints`` and ``POST .../release`` -- were real,
gated by real permission wiring, and exercised at the service layer in their own test
files, but never actually invoked over HTTP anywhere in the test suite. Three sibling
phases with the exact same shape (``phases/acquire``, ``phases/configure``,
``phases/trust``) already had HTTP coverage; this file closes the gap for the rest by
driving a single bootstrap run through all nine real phase-execution endpoints, in their
real required order (``acquire -> configure -> trust -> data -> services -> identity ->
integrations -> verify -> handoff``, per ``atlas.modules.platform.application.
bootstrap_plan.PHASES`` and the hard-coded ``current_phase_id`` checks in the
repository), plus the checkpoint and release endpoints, over the real HTTP API.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings

RELEASE_ID = "release.atlas.lab-0.1.0"
PROFILE = "linux_lab"
ORGANIZATION_ID = "organization.development"
ENVIRONMENT_ID = "environment.test"
SITE_ID = "site.local"
PLAN_DIGEST = "a" * 64


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
        "bootstrap_artifact_root": tmp_path / "artifacts",
        "bootstrap_configuration_root": tmp_path / "configurations",
        "bootstrap_trust_root": tmp_path / "trust",
        "bootstrap_data_root": tmp_path / "data",
        "bootstrap_service_root": tmp_path / "services",
        "bootstrap_identity_root": tmp_path / "identity",
        "bootstrap_integration_root": tmp_path / "integrations",
        "bootstrap_verification_root": tmp_path / "verification",
        "bootstrap_handoff_root": tmp_path / "handoff",
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


def _headers(csrf: str, idempotency_key: str) -> dict[str, str]:
    return {"Idempotency-Key": idempotency_key, "X-CSRF-Token": csrf}


def test_all_bootstrap_phase_execution_endpoints_and_release_are_reachable_through_the_api(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        csrf = _login(client)

        # -- deployment configuration preview: produces the configuration_digest every
        # later phase is bound to.
        configuration_preview = client.post(
            "/api/v1/platform/deployment-configuration/preview",
            json={
                "schema_version": "atlas.deployment-configuration-request.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "overlay": {},
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert configuration_preview.status_code == 200, configuration_preview.text
        configuration_data = configuration_preview.json()["data"]
        configuration_digest = configuration_data["configuration_digest"]
        # The rendered configuration document has its own schema version, distinct from
        # the preview request's "-request.v1" schema_version echoed back above.
        configuration_schema_version = "atlas.deployment-configuration.v1"

        # -- claim the run, declaring all nine real phases in their real required order.
        claim = client.post(
            "/api/v1/platform/bootstrap-state/claims",
            json={
                "schema_version": "atlas.bootstrap-claim.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "plan_digest": PLAN_DIGEST,
                "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
                "configuration_digest": configuration_digest,
                "phase_ids": [
                    "phase.acquire",
                    "phase.configure",
                    "phase.trust",
                    "phase.data",
                    "phase.services",
                    "phase.identity",
                    "phase.integrations",
                    "phase.verify",
                    "phase.handoff",
                ],
                "lease_minutes": 15,
            },
            headers=_headers(csrf, "phase-wiring-claim-0001"),
        )
        assert claim.status_code == 201, claim.text
        run = claim.json()["data"]["run"]
        run_id = run["run_id"]
        assert run["version"] == 1
        assert run["current_phase_id"] == "phase.acquire"

        # -- phase.acquire (already HTTP-tested elsewhere; exercised here only as the
        # required predecessor of the six phases this file adds coverage for).
        preflight = client.get(
            "/api/v1/platform/release-preflight?mode=offline&profile=linux_lab"
        ).json()["data"]
        acquire = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/acquire",
            json={
                "schema_version": "atlas.bootstrap-artifact-acquisition.v1",
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "expected_version": 1,
                "plan_digest": PLAN_DIGEST,
                "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
                "phase_id": "phase.acquire",
                "release_id": RELEASE_ID,
                "manifest_digest": preflight["manifest_digest"],
                "mode": "offline",
                "profile": PROFILE,
                "preflight_report_id": preflight["report_id"],
                "preflight_state": preflight["state"],
                "warning_accepted": False,
                "justification": "Acquire artifacts before the six-phase wiring chain",
            },
            headers=_headers(csrf, "phase-wiring-acquire-0001"),
        )
        assert acquire.status_code == 200, acquire.text
        assert acquire.json()["data"]["run"]["version"] == 3
        assert acquire.json()["data"]["run"]["current_phase_id"] == "phase.configure"

        # -- phase.configure (already HTTP-tested elsewhere; required predecessor).
        configure = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/configure",
            json={
                "schema_version": "atlas.bootstrap-configuration-rendering.v1",
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "expected_version": 3,
                "plan_digest": PLAN_DIGEST,
                "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
                "phase_id": "phase.configure",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "configuration_schema_version": configuration_schema_version,
                "configuration_digest": configuration_digest,
                "overlay": {},
                "justification": "Render configuration before the six-phase wiring chain",
            },
            headers=_headers(csrf, "phase-wiring-configure-0001"),
        )
        assert configure.status_code == 200, configure.text
        assert configure.json()["data"]["run"]["version"] == 5
        assert configure.json()["data"]["run"]["current_phase_id"] == "phase.trust"

        # -- phase.trust (already HTTP-tested elsewhere; required predecessor of data).
        trust_preview = client.post(
            "/api/v1/platform/bootstrap-trust-plan/preview",
            json={
                "schema_version": "atlas.bootstrap-trust-plan-request.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "configuration_digest": configuration_digest,
                "overlay": {},
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert trust_preview.status_code == 200, trust_preview.text
        trust_plan = trust_preview.json()["data"]
        trust_plan_digest = trust_plan["trust_plan_digest"]
        trust_schema_version = trust_plan["schema_version"]
        trust = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/trust",
            json={
                "schema_version": "atlas.bootstrap-trust-provisioning.v1",
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "expected_version": 5,
                "plan_digest": PLAN_DIGEST,
                "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
                "phase_id": "phase.trust",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "configuration_digest": configuration_digest,
                "overlay": {},
                "trust_schema_version": trust_schema_version,
                "trust_plan_digest": trust_plan_digest,
                "justification": "Provision trust before the six-phase wiring chain",
            },
            headers=_headers(csrf, "phase-wiring-trust-0001"),
        )
        assert trust.status_code == 200, trust.text
        assert trust.json()["data"]["run"]["version"] == 7
        assert trust.json()["data"]["run"]["current_phase_id"] == "phase.data"

        # ================================================================
        # phase.data -- the first of the six genuinely uncovered endpoints.
        # ================================================================
        data_preview = client.post(
            "/api/v1/platform/bootstrap-data-plan/preview",
            json={
                "schema_version": "atlas.bootstrap-data-plan-request.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "configuration_digest": configuration_digest,
                "overlay": {},
                "trust_plan_digest": trust_plan_digest,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert data_preview.status_code == 200, data_preview.text
        data_plan = data_preview.json()["data"]
        data_plan_digest = data_plan["data_plan_digest"]
        migration_artifact_digest = data_plan["migration_artifact_digest"]
        data_schema_version = data_plan["schema_version"]
        data_target_id = data_plan["target_id"]
        data_target_state = data_plan["target_state"]
        assert data_target_state == "empty"
        assert len(data_plan["migrations"]) == 3

        data_payload = {
            "schema_version": "atlas.bootstrap-data-initialization.v1",
            "organization_id": ORGANIZATION_ID,
            "environment_id": ENVIRONMENT_ID,
            "site_id": SITE_ID,
            "expected_version": 7,
            "plan_digest": PLAN_DIGEST,
            "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
            "phase_id": "phase.data",
            "release_id": RELEASE_ID,
            "profile": PROFILE,
            "configuration_digest": configuration_digest,
            "overlay": {},
            "trust_plan_digest": trust_plan_digest,
            "data_schema_version": data_schema_version,
            "data_plan_digest": data_plan_digest,
            "migration_artifact_digest": migration_artifact_digest,
            "target_id": data_target_id,
            "expected_target_state": data_target_state,
            "justification": "Initialize the clean synthetic Atlas data schema",
        }
        # A request without the CSRF header must be rejected before it ever reaches the
        # execution service -- proving the endpoint is behind the same real CSRF/session
        # wiring as its already-tested siblings, not merely present on the router.
        data_denied = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/data",
            json=data_payload,
            headers={"Idempotency-Key": "phase-wiring-data-0001"},
        )
        assert data_denied.status_code == 403
        assert data_denied.json()["code"] == "csrf_validation_failed"
        # A payload with an unexpected field must be rejected by the strict schema.
        data_malformed = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/data",
            json={**data_payload, "unexpected": True},
            headers=_headers(csrf, "phase-wiring-data-malformed"),
        )
        assert data_malformed.status_code == 422
        data = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/data",
            json=data_payload,
            headers=_headers(csrf, "phase-wiring-data-0001"),
        )
        assert data.status_code == 200, data.text
        assert data.headers["Cache-Control"] == "no-store"
        data_response = data.json()["data"]
        assert data_response["run"]["version"] == 9
        assert data_response["run"]["current_phase_id"] == "phase.services"
        assert data_response["execution"]["state"] == "completed"
        assert data_response["execution"]["migration_count"] == 3
        assert data_response["execution"]["verified_object_count"] > 0
        assert data_response["schema_state_mutation_performed"] is True
        assert data_response["service_deployment_authorized"] is False
        assert data_response["infrastructure_mutation_authorized"] is False

        # ================================================================
        # phase.services -- second genuinely uncovered endpoint.
        # ================================================================
        service_preview = client.post(
            "/api/v1/platform/bootstrap-service-plan/preview",
            json={
                "schema_version": "atlas.bootstrap-service-plan-request.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "configuration_digest": configuration_digest,
                "overlay": {},
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "migration_artifact_digest": migration_artifact_digest,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert service_preview.status_code == 200, service_preview.text
        service_plan = service_preview.json()["data"]
        service_plan_digest = service_plan["service_plan_digest"]
        service_schema_version = service_plan["schema_version"]
        service_target_id = service_plan["target_id"]
        service_target_state = service_plan["target_state"]
        assert len(service_plan["services"]) > 0

        services = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/services",
            json={
                "schema_version": "atlas.bootstrap-service-deployment.v1",
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "expected_version": 9,
                "plan_digest": PLAN_DIGEST,
                "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
                "phase_id": "phase.services",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "configuration_digest": configuration_digest,
                "overlay": {},
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "migration_artifact_digest": migration_artifact_digest,
                "service_schema_version": service_schema_version,
                "service_plan_digest": service_plan_digest,
                "target_id": service_target_id,
                "expected_target_state": service_target_state,
                "justification": "Deploy the synthetic Atlas services for this lab run",
            },
            headers=_headers(csrf, "phase-wiring-services-0001"),
        )
        assert services.status_code == 200, services.text
        services_response = services.json()["data"]
        assert services_response["run"]["version"] == 11
        assert services_response["run"]["current_phase_id"] == "phase.identity"
        assert services_response["execution"]["state"] == "completed"
        assert services_response["execution"]["deployed_service_count"] > 0
        assert (
            services_response["execution"]["ready_service_count"]
            == services_response["execution"]["deployed_service_count"]
        )
        assert services_response["synthetic_state_mutation_performed"] is True

        # ================================================================
        # phase.identity -- third genuinely uncovered endpoint.
        # ================================================================
        identity_preview = client.post(
            "/api/v1/platform/bootstrap-identity-plan/preview",
            json={
                "schema_version": "atlas.bootstrap-identity-plan-request.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "configuration_digest": configuration_digest,
                "overlay": {},
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "migration_artifact_digest": migration_artifact_digest,
                "service_plan_digest": service_plan_digest,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert identity_preview.status_code == 200, identity_preview.text
        identity_plan = identity_preview.json()["data"]
        identity_plan_digest = identity_plan["identity_plan_digest"]
        identity_schema_version = identity_plan["schema_version"]
        identity_target_id = identity_plan["target_id"]
        identity_target_state = identity_plan["target_state"]

        identity_payload = {
            "schema_version": "atlas.bootstrap-identity-handoff.v1",
            "organization_id": ORGANIZATION_ID,
            "environment_id": ENVIRONMENT_ID,
            "site_id": SITE_ID,
            "expected_version": 11,
            "plan_digest": PLAN_DIGEST,
            "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
            "phase_id": "phase.identity",
            "release_id": RELEASE_ID,
            "profile": PROFILE,
            "configuration_digest": configuration_digest,
            "overlay": {},
            "trust_plan_digest": trust_plan_digest,
            "data_plan_digest": data_plan_digest,
            "migration_artifact_digest": migration_artifact_digest,
            "service_plan_digest": service_plan_digest,
            "identity_schema_version": identity_schema_version,
            "identity_plan_digest": identity_plan_digest,
            "target_id": identity_target_id,
            "expected_target_state": identity_target_state,
            "justification": "Bootstrap the administrator and pilot identities",
        }
        identity_malformed = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/identity",
            json={**identity_payload, "unexpected": True},
            headers=_headers(csrf, "phase-wiring-identity-malformed"),
        )
        assert identity_malformed.status_code == 422
        identity = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/identity",
            json=identity_payload,
            headers=_headers(csrf, "phase-wiring-identity-0001"),
        )
        assert identity.status_code == 200, identity.text
        identity_response = identity.json()["data"]
        assert identity_response["run"]["version"] == 13
        assert identity_response["run"]["current_phase_id"] == "phase.integrations"
        assert identity_response["execution"]["state"] == "completed"
        assert identity_response["execution"]["credential_replacement_required"] is True
        assert identity_response["execution"]["recovery_identity_verified"] is True
        assert identity_response["synthetic_state_mutation_performed"] is True

        # ================================================================
        # phase.integrations -- fourth genuinely uncovered endpoint.
        # ================================================================
        integration_preview = client.post(
            "/api/v1/platform/bootstrap-integration-plan/preview",
            json={
                "schema_version": "atlas.bootstrap-integration-plan-request.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "configuration_digest": configuration_digest,
                "overlay": {},
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "migration_artifact_digest": migration_artifact_digest,
                "service_plan_digest": service_plan_digest,
                "identity_plan_digest": identity_plan_digest,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert integration_preview.status_code == 200, integration_preview.text
        integration_plan = integration_preview.json()["data"]
        integration_plan_digest = integration_plan["integration_plan_digest"]
        integration_schema_version = integration_plan["schema_version"]
        integration_target_id = integration_plan["target_id"]
        integration_target_state = integration_plan["target_state"]

        integrations = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/integrations",
            json={
                "schema_version": "atlas.bootstrap-integration-validation.v1",
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "expected_version": 13,
                "plan_digest": PLAN_DIGEST,
                "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
                "phase_id": "phase.integrations",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "configuration_digest": configuration_digest,
                "overlay": {},
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "migration_artifact_digest": migration_artifact_digest,
                "service_plan_digest": service_plan_digest,
                "identity_plan_digest": identity_plan_digest,
                "integration_schema_version": integration_schema_version,
                "integration_plan_digest": integration_plan_digest,
                "target_id": integration_target_id,
                "expected_target_state": integration_target_state,
                "justification": "Validate the synthetic model and core integrations",
            },
            headers=_headers(csrf, "phase-wiring-integrations-0001"),
        )
        assert integrations.status_code == 200, integrations.text
        integrations_response = integrations.json()["data"]
        assert integrations_response["run"]["version"] == 15
        assert integrations_response["run"]["current_phase_id"] == "phase.verify"
        assert integrations_response["execution"]["state"] == "completed"
        assert integrations_response["execution"]["mandatory_pass_count"] > 0
        assert integrations_response["synthetic_state_mutation_performed"] is True

        # ================================================================
        # phase.verify -- fifth genuinely uncovered endpoint.
        # ================================================================
        run_version_before_verify = integrations_response["run"]["version"]
        verification_preview = client.post(
            "/api/v1/platform/bootstrap-verification-plan/preview",
            json={
                "schema_version": "atlas.bootstrap-verification-plan-request.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "source_run_id": run_id,
                "source_run_version": run_version_before_verify,
                "configuration_digest": configuration_digest,
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "service_plan_digest": service_plan_digest,
                "identity_plan_digest": identity_plan_digest,
                "integration_plan_digest": integration_plan_digest,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert verification_preview.status_code == 200, verification_preview.text
        verification_plan = verification_preview.json()["data"]
        verification_plan_digest = verification_plan["verification_plan_digest"]
        verification_schema_version = verification_plan["schema_version"]
        verification_suite_version = verification_plan["suite_version"]
        verification_target_id = verification_plan["target_id"]
        verification_target_state = verification_plan["target_state"]

        verify = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/verify",
            json={
                "schema_version": "atlas.bootstrap-verification.v1",
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "expected_version": run_version_before_verify,
                "plan_digest": PLAN_DIGEST,
                "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
                "phase_id": "phase.verify",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "configuration_digest": configuration_digest,
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "service_plan_digest": service_plan_digest,
                "identity_plan_digest": identity_plan_digest,
                "integration_plan_digest": integration_plan_digest,
                "verification_schema_version": verification_schema_version,
                "suite_version": verification_suite_version,
                "verification_plan_digest": verification_plan_digest,
                "target_id": verification_target_id,
                "expected_target_state": verification_target_state,
                "justification": "Run end-to-end verification before operational handoff",
            },
            headers=_headers(csrf, "phase-wiring-verify-0001"),
        )
        assert verify.status_code == 200, verify.text
        verify_response = verify.json()["data"]
        run_version_after_verify = verify_response["run"]["version"]
        assert run_version_after_verify == run_version_before_verify + 2
        assert verify_response["run"]["current_phase_id"] == "phase.handoff"
        assert verify_response["execution"]["state"] == "completed"
        assert verify_response["execution"]["failed_count"] == 0
        assert verify_response["execution"]["unresolved_mandatory_count"] == 0
        assert verify_response["synthetic_report_mutation_performed"] is True
        assert len(verify_response["execution"]["evidence"]) > 0
        verification_report_digest = verify_response["execution"]["evidence"][0]["sha256"]

        # ================================================================
        # phase.handoff -- sixth genuinely uncovered endpoint.
        # ================================================================
        handoff_preview = client.post(
            "/api/v1/platform/bootstrap-handoff-plan/preview",
            json={
                "schema_version": "atlas.bootstrap-handoff-plan-request.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "source_run_id": run_id,
                "source_run_version": run_version_after_verify,
                "configuration_digest": configuration_digest,
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "service_plan_digest": service_plan_digest,
                "identity_plan_digest": identity_plan_digest,
                "integration_plan_digest": integration_plan_digest,
                "verification_plan_digest": verification_plan_digest,
                "verification_report_digest": verification_report_digest,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert handoff_preview.status_code == 200, handoff_preview.text
        handoff_plan = handoff_preview.json()["data"]
        handoff_plan_digest = handoff_plan["handoff_plan_digest"]
        handoff_schema_version = handoff_plan["schema_version"]
        handoff_suite_version = handoff_plan["suite_version"]
        handoff_target_id = handoff_plan["target_id"]
        handoff_target_state = handoff_plan["target_state"]
        source_evidence_digest = handoff_plan["source_evidence_digest"]

        handoff = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/phases/handoff",
            json={
                "schema_version": "atlas.bootstrap-handoff.v1",
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "expected_version": run_version_after_verify,
                "plan_digest": PLAN_DIGEST,
                "resume_key": "resume.phase-wiring-aaaaaaaaaaaa",
                "phase_id": "phase.handoff",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "configuration_digest": configuration_digest,
                "trust_plan_digest": trust_plan_digest,
                "data_plan_digest": data_plan_digest,
                "service_plan_digest": service_plan_digest,
                "identity_plan_digest": identity_plan_digest,
                "integration_plan_digest": integration_plan_digest,
                "verification_plan_digest": verification_plan_digest,
                "verification_report_digest": verification_report_digest,
                "source_evidence_digest": source_evidence_digest,
                "handoff_schema_version": handoff_schema_version,
                "suite_version": handoff_suite_version,
                "handoff_plan_digest": handoff_plan_digest,
                "target_id": handoff_target_id,
                "expected_target_state": handoff_target_state,
                "justification": "Publish the reviewed developer and lab handoff evidence",
            },
            headers=_headers(csrf, "phase-wiring-handoff-0001"),
        )
        assert handoff.status_code == 200, handoff.text
        handoff_response = handoff.json()["data"]
        run_version_after_handoff = handoff_response["run"]["version"]
        assert run_version_after_handoff == run_version_after_verify + 2
        assert handoff_response["run"]["current_phase_id"] is None
        assert handoff_response["run"]["state"] == "completed"
        assert handoff_response["execution"]["state"] == "completed"
        assert handoff_response["synthetic_report_mutation_performed"] is True

        # ================================================================
        # release -- the second bootstrap_state.py endpoint this file adds coverage
        # for. It releases the lease on the now-completed run.
        # ================================================================
        release_denied = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/release",
            json={
                "schema_version": "atlas.bootstrap-release.v1",
                "expected_version": run_version_after_handoff,
            },
            headers={"Idempotency-Key": "phase-wiring-release-0001"},
        )
        assert release_denied.status_code == 403
        assert release_denied.json()["code"] == "csrf_validation_failed"
        release = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/release",
            json={
                "schema_version": "atlas.bootstrap-release.v1",
                "expected_version": run_version_after_handoff,
            },
            headers=_headers(csrf, "phase-wiring-release-0001"),
        )
        assert release.status_code == 200, release.text
        release_response = release.json()["data"]
        assert release_response["run"]["version"] == run_version_after_handoff + 1
        assert release_response["run"]["lease_expires_at"] is None
        assert release_response["run"]["state"] == "completed"

        current = client.get("/api/v1/platform/bootstrap-state/current")
        assert current.status_code == 200
        current_run = current.json()["data"]["run"]
        assert current_run["completed_phase_ids"] == [
            "phase.acquire",
            "phase.configure",
            "phase.trust",
            "phase.data",
            "phase.services",
            "phase.identity",
            "phase.integrations",
            "phase.verify",
            "phase.handoff",
        ]
        assert current.json()["data"]["lease_available"] is True

        forbidden = ("password", "authorization:", "bearer ", "session.phase-wiring")
        for response in (
            data,
            services,
            identity,
            integrations,
            verify,
            handoff,
            release,
            current,
        ):
            lowered = response.text.lower()
            assert not any(marker in lowered for marker in forbidden)


def test_bootstrap_checkpoint_endpoint_is_reachable_through_the_api(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        csrf = _login(client)
        configuration_preview = client.post(
            "/api/v1/platform/deployment-configuration/preview",
            json={
                "schema_version": "atlas.deployment-configuration-request.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "overlay": {},
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert configuration_preview.status_code == 200, configuration_preview.text
        configuration_digest = configuration_preview.json()["data"]["configuration_digest"]

        claim = client.post(
            "/api/v1/platform/bootstrap-state/claims",
            json={
                "schema_version": "atlas.bootstrap-claim.v1",
                "release_id": RELEASE_ID,
                "profile": PROFILE,
                "organization_id": ORGANIZATION_ID,
                "environment_id": ENVIRONMENT_ID,
                "site_id": SITE_ID,
                "plan_digest": PLAN_DIGEST,
                "resume_key": "resume.checkpoint-wiring-aaaaaaaa",
                "configuration_digest": configuration_digest,
                "phase_ids": ["phase.acquire"],
                "lease_minutes": 5,
            },
            headers=_headers(csrf, "checkpoint-wiring-claim-0001"),
        )
        assert claim.status_code == 201, claim.text
        run_id = claim.json()["data"]["run"]["run_id"]
        assert claim.json()["data"]["run"]["current_phase_id"] == "phase.acquire"

        checkpoint_payload = {
            "schema_version": "atlas.bootstrap-checkpoint.v1",
            "plan_digest": PLAN_DIGEST,
            "resume_key": "resume.checkpoint-wiring-aaaaaaaa",
            "phase_id": "phase.acquire",
            "state": "completed",
            "safe_output_references": ["result.checkpoint-wiring-test"],
            "expected_version": 1,
        }
        # No CSRF header: the checkpoint endpoint must be behind the same real
        # CSRF/session wiring as the phase-execution endpoints, not merely present.
        denied = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/checkpoints",
            json=checkpoint_payload,
            headers={"Idempotency-Key": "checkpoint-wiring-record-0001"},
        )
        assert denied.status_code == 403
        assert denied.json()["code"] == "csrf_validation_failed"
        malformed = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/checkpoints",
            json={**checkpoint_payload, "unexpected": True},
            headers=_headers(csrf, "checkpoint-wiring-malformed"),
        )
        assert malformed.status_code == 422
        recorded = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/checkpoints",
            json=checkpoint_payload,
            headers=_headers(csrf, "checkpoint-wiring-record-0001"),
        )
        assert recorded.status_code == 200, recorded.text
        assert recorded.headers["Cache-Control"] == "no-store"
        recorded_run = recorded.json()["data"]["run"]
        assert recorded_run["version"] == 2
        assert recorded_run["completed_phase_ids"] == ["phase.acquire"]
        assert recorded_run["current_phase_id"] is None
        assert recorded_run["state"] == "completed"
        assert recorded_run["checkpoints"] == [
            {
                "phase_id": "phase.acquire",
                "state": "completed",
                "safe_output_references": ["result.checkpoint-wiring-test"],
                "recorded_at": recorded_run["checkpoints"][0]["recorded_at"],
            }
        ]

        # A single-phase run is now fully completed: releasing it exercises the
        # release endpoint one more time against a run that reached completion
        # entirely through the checkpoint endpoint rather than a typed phase route.
        release = client.post(
            f"/api/v1/platform/bootstrap-state/{run_id}/release",
            json={"schema_version": "atlas.bootstrap-release.v1", "expected_version": 2},
            headers=_headers(csrf, "checkpoint-wiring-release-0001"),
        )
        assert release.status_code == 200, release.text
        assert release.json()["data"]["run"]["version"] == 3
        assert release.json()["data"]["run"]["lease_expires_at"] is None
