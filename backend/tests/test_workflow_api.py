from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings


def _settings() -> Settings:
    return Settings(environment="development", development_identity_enabled=True)


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def _payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.workflow-run-plan-create-input.v1",
        "definition_id": "workflow.evidence-grounded-query",
        "definition_version": 1,
        "target_id": "asset.storage.lab.vsp-g400",
        "target_type": "storage",
        "inputs": {
            "purpose": "Review current storage evidence.",
            "input_summary": "Use only authorized read-only observations.",
        },
        "acknowledged_planning_only_no_execution_authority": True,
    }


def test_workflow_endpoints_require_login_and_create_only_a_non_executable_plan() -> None:
    with TestClient(create_app(_settings())) as client:
        unauthenticated = client.get("/api/v1/workflows/definitions")
        browser_session_required = client.post(
            "/api/v1/workflows/plans",
            json=_payload(),
            headers={"Idempotency-Key": "workflow-plan-api-no-session"},
        )
        csrf = _login(client)
        definitions = client.get("/api/v1/workflows/definitions")
        created = client.post(
            "/api/v1/workflows/plans",
            json=_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-plan-api-0001"},
        )
        plans = client.get("/api/v1/workflows/plans")
        plan_id = created.json()["data"]["plan_id"]
        reopened = client.get(f"/api/v1/workflows/plans/{plan_id}")

    assert unauthenticated.status_code == 200
    assert browser_session_required.status_code == 403
    assert browser_session_required.json()["code"] == "browser_session_required"
    assert definitions.status_code == 200
    assert len(definitions.json()["data"]["definitions"]) == 3
    assert created.status_code == 201
    assert created.headers["Cache-Control"].startswith("no-store")
    plan = created.json()["data"]
    assert plan["state"] == "planned"
    assert {step["state"] for step in plan["steps"]} == {"not_started"}
    assert set(plan["authority"].values()) == {False}
    assert "cannot dispatch workers" in plan["safety_notice"]
    assert plans.status_code == 200
    assert plans.json()["data"]["plans"] == [plan]
    assert reopened.status_code == 200
    assert reopened.json()["data"] == plan


def test_workflow_plan_creation_requires_csrf_and_is_idempotent() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        missing_csrf = client.post(
            "/api/v1/workflows/plans",
            json=_payload(),
            headers={"Idempotency-Key": "workflow-plan-api-0002"},
        )
        first = client.post(
            "/api/v1/workflows/plans",
            json=_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-plan-api-0002"},
        )
        replay = client.post(
            "/api/v1/workflows/plans",
            json=_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-plan-api-0002"},
        )

    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "csrf_validation_failed"
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["data"] == first.json()["data"]
