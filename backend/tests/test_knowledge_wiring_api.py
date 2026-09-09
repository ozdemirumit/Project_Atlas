"""ATLAS-IMP-280 found that KnowledgeFeedbackService, KnowledgeReviewService, and
KnowledgeDeletionService (all built earlier, under ATLAS-027) were real, tested at the service
layer, but reachable through no HTTP route anywhere -- a governed service nobody can actually
call. These tests exercise each one through the real HTTP API, not just the service layer
directly, to prove the wiring genuinely closes that gap.
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


def test_knowledge_feedback_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        submitted = client.post(
            "/api/v1/knowledge/feedback",
            json={
                "item_id": "item.knowledge.wiring-test",
                "item_version": "v1",
                "kind": "incorrect_or_outdated",
                "description": "The failover steps reference a decommissioned controller.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert submitted.status_code == 201
        feedback = submitted.json()["data"]
        assert feedback["state"] == "open"

        triaged = client.post(
            f"/api/v1/knowledge/feedback/{feedback['feedback_id']}/triage",
            headers={"X-CSRF-Token": csrf},
        )
        assert triaged.status_code == 200
        assert triaged.json()["data"]["state"] == "triaged"

        resolved = client.post(
            f"/api/v1/knowledge/feedback/{feedback['feedback_id']}/resolve",
            json={
                "resolution_notes": "Updated the procedure to reference the current controller.",
                "dismissed": False,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resolved.status_code == 200
        assert resolved.json()["data"]["state"] == "resolved"


def test_knowledge_review_expiry_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        scheduled = client.post(
            "/api/v1/knowledge/review-expiry/item.knowledge.wiring-test",
            json={
                "item_version": "v1",
                "owner": "subject.knowledge-owner.primary",
                "review_interval_days": 90,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert scheduled.status_code == 201
        assert scheduled.json()["data"]["owner"] == "subject.knowledge-owner.primary"

        renewed = client.post(
            "/api/v1/knowledge/review-expiry/item.knowledge.wiring-test/renew",
            json={"evidence_reference": "evidence.review.wiring-test-0001"},
            headers={"X-CSRF-Token": csrf},
        )
        assert renewed.status_code == 200
        assert renewed.json()["data"]["evidence_reference"] == "evidence.review.wiring-test-0001"

        resolved = client.post(
            "/api/v1/knowledge/review-expiry/item.knowledge.wiring-test/owner-absence-resolution",
            json={
                "resolution": "suspended",
                "new_owner": None,
                "rationale": "The prior owner has left the organization.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resolved.status_code == 200
        assert resolved.json()["data"]["resolution"] == "suspended"


def test_knowledge_deletion_and_legal_hold_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        placed = client.post(
            "/api/v1/knowledge/deletion/legal-holds",
            json={
                "hold_id": "hold.wiring-test-0001",
                "item_id": "item.knowledge.wiring-test",
                "reason": "Pending litigation review.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert placed.status_code == 201
        assert placed.json()["data"]["released_at"] is None

        blocked_request = client.post(
            "/api/v1/knowledge/deletion/requests",
            json={
                "request_id": "deletion.wiring-test-0001",
                "item_id": "item.knowledge.wiring-test",
                "retention_policy_reference": "policy.retention.default",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert blocked_request.status_code == 201
        assert blocked_request.json()["data"]["state"] == "blocked_by_legal_hold"

        released = client.post(
            "/api/v1/knowledge/deletion/legal-holds/hold.wiring-test-0001/release",
            headers={"X-CSRF-Token": csrf},
        )
        assert released.status_code == 200
        assert released.json()["data"]["released_at"] is not None

        completed = client.post(
            "/api/v1/knowledge/deletion/requests/deletion.wiring-test-0001/complete",
            json={
                "tombstone_id": "tombstone.wiring-test-0001",
                "reason_code": "retention_policy_expired",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert completed.status_code == 200
        completed_data = completed.json()["data"]
        assert completed_data["state"] == "completed"
        assert completed_data["derived_artifacts_removed"] is True
        assert completed_data["tombstone_id"] == "tombstone.wiring-test-0001"


def test_knowledge_feedback_review_expiry_and_deletion_wiring_requires_authentication() -> None:
    """No session cookie and no development identity: the route must fail closed at
    authentication, not merely at authorization -- proving `browser_session_subject` really runs
    ahead of every permission dependency in this file's coverage.
    """
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post("/api/v1/knowledge/feedback", json={})

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_knowledge_feedback_review_expiry_and_deletion_wiring_requires_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must be denied by the
    real `AuthorizationService`, not by a faked dependency override, for every permission gating
    this file's coverage across ``knowledge_feedback.py``, ``knowledge_review_expiry.py``, and
    ``knowledge_deletion_legal_hold.py``. An empty body is deliberately used throughout: FastAPI
    resolves each route's `Depends(authorize_...)` sub-dependency before parsing the request body,
    so the denial fires before any placeholder, intentionally-nonexistent path identifier or empty
    body would ever reach real service logic.
    """
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)
        paths = (
            "/api/v1/knowledge/feedback",
            "/api/v1/knowledge/feedback/feedback.denied/triage",
            "/api/v1/knowledge/feedback/feedback.denied/resolve",
            "/api/v1/knowledge/review-expiry/item.denied",
            "/api/v1/knowledge/review-expiry/item.denied/renew",
            "/api/v1/knowledge/review-expiry/item.denied/owner-absence-resolution",
            "/api/v1/knowledge/deletion/legal-holds",
            "/api/v1/knowledge/deletion/legal-holds/hold.denied/release",
            "/api/v1/knowledge/deletion/requests",
            "/api/v1/knowledge/deletion/requests/deletion.denied/complete",
        )
        for path in paths:
            response = client.post(path, json={}, headers={"X-CSRF-Token": csrf})
            assert response.status_code == 403, f"POST {path}: {response.text}"
            assert response.json()["code"] == "authorization_denied", path
