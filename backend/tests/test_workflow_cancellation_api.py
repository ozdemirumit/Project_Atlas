from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import STORAGE_OVERVIEW_READ


def _settings() -> Settings:
    return Settings(environment="development", development_identity_enabled=True)


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def _plan_payload() -> dict[str, object]:
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


def _cancellation_payload(
    *, reason: str = "The diagnostic window is no longer required."
) -> dict[str, object]:
    return {
        "schema_version": "atlas.workflow-run-plan-cancellation-input.v1",
        "reason": reason,
        "acknowledge_no_external_undo": True,
    }


def _create_plan(client: TestClient, csrf: str, *, key: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/workflows/plans",
        json=_plan_payload(),
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
    )
    assert response.status_code == 201
    return dict(response.json()["data"])


def test_browser_cancellation_is_csrf_protected_idempotent_and_returns_history() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        planned = _create_plan(client, csrf, key="workflow-cancel-plan-0001")
        path = f"/api/v1/workflows/plans/{planned['plan_id']}/cancellation"
        headers = {
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "workflow-cancellation-0001",
        }

        missing_csrf = client.post(
            path,
            json=_cancellation_payload(),
            headers={"Idempotency-Key": "workflow-cancellation-no-csrf"},
        )
        cancelled = client.post(path, json=_cancellation_payload(), headers=headers)
        replay = client.post(path, json=_cancellation_payload(), headers=headers)
        reopened = client.get(f"/api/v1/workflows/plans/{planned['plan_id']}")

    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "csrf_validation_failed"
    assert cancelled.status_code == 200
    assert cancelled.headers["Cache-Control"].startswith("no-store")
    assert replay.status_code == 200
    assert replay.json()["data"] == cancelled.json()["data"]
    assert reopened.status_code == 200
    assert reopened.json()["data"] == cancelled.json()["data"]

    plan = cancelled.json()["data"]
    assert plan["state"] == "cancelled"
    assert {step["state"] for step in plan["steps"]} == {"not_started"}
    assert set(plan["authority"].values()) == {False}
    assert len(plan["transition_history"]) == 1
    transition = plan["transition_history"][0]
    assert transition["prior_state"] == "planned"
    assert transition["new_state"] == "cancelled"
    assert transition["reason"] == "The diagnostic window is no longer required."
    assert transition["target_id"] == planned["target_id"]
    assert transition["scope"] == planned["scope"]
    assert len(transition["reason_digest"]) == 64
    assert len(transition["canonical_digest"]) == 64


def test_api_token_cannot_cancel_a_workflow_plan() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        planned = _create_plan(client, csrf, key="workflow-cancel-plan-0002")
        issued = client.post(
            "/api/v1/authentication/api-credentials",
            json={
                "display_name": "Read-only workflow observer",
                "purpose": "Verify that API credentials cannot mutate workflow plan state.",
                "expires_in_minutes": 30,
                "permission_ids": [STORAGE_OVERVIEW_READ],
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert issued.status_code == 201
        token = issued.json()["data"]["token"]
        client.cookies.clear()
        rejected = client.post(
            f"/api/v1/workflows/plans/{planned['plan_id']}/cancellation",
            json=_cancellation_payload(),
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "workflow-cancellation-api-token",
            },
        )

    assert rejected.status_code == 403
    assert rejected.json()["code"] == "credential_unsafe_method_denied"


def test_cancellation_requires_literal_acknowledgement_and_bounded_reason() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        planned = _create_plan(client, csrf, key="workflow-cancel-plan-0003")
        path = f"/api/v1/workflows/plans/{planned['plan_id']}/cancellation"
        common_headers = {"X-CSRF-Token": csrf}

        missing_acknowledgement = client.post(
            path,
            json=_cancellation_payload() | {"acknowledge_no_external_undo": False},
            headers=common_headers | {"Idempotency-Key": "workflow-cancel-invalid-ack"},
        )
        oversized_reason = client.post(
            path,
            json=_cancellation_payload(reason="x" * 501),
            headers=common_headers | {"Idempotency-Key": "workflow-cancel-invalid-reason"},
        )

    assert missing_acknowledgement.status_code == 422
    assert oversized_reason.status_code == 422
