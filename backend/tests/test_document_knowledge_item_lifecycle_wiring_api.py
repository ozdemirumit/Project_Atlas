"""Pass 37: docs/027_Knowledge_Engine.md SS8/SS21 HTTP-level wiring for the real document-sourced
knowledge pipeline's item lifecycle and conflict routes
(``atlas.api.routes.document_knowledge_lifecycle``).

Proves: (a) each mutating route performs a real state transition reachable only through the real
HTTP API, with real 409s for wrong-state attempts; (b) conflict recording, resolution, and listing
work end to end over HTTP; (c) the established two-stage denial pattern (true 401, true 403) for
every new route.

Named ``..._item_lifecycle_...`` (not ``..._document_lifecycle_...``) to avoid colliding with the
pre-existing ``test_knowledge_document_lifecycle_wiring_api.py``, which covers something unrelated
despite the similar name -- the operational-knowledge document *governance pipeline*'s wiring, not
a per-item lifecycle state machine. See atlas.modules.knowledge.domain.document_knowledge_lifecycle
for the real distinction.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings

_ORGANIZATION_ID = Settings().development_organization_id


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
    assert response.status_code == 201, response.text
    return str(response.headers["X-CSRF-Token"])


# ---------------------------------------------------------------------------
# (a) Real state transitions over HTTP, including 409s for wrong-state attempts.
# ---------------------------------------------------------------------------


def test_suspend_then_get_lifecycle_over_http() -> None:
    with TestClient(
        create_app(_settings(development_subject_id="subject.lifecycle-wiring.suspend"))
    ) as client:
        csrf = _login(client)
        item_id = "knowledge-item.wiring-suspend-0001"

        before = client.get(f"/api/v1/knowledge/documents/{item_id}/lifecycle")
        assert before.status_code == 200, before.text
        assert before.json()["data"]["state"] == "active"
        assert before.json()["data"]["reason"] is None

        suspend = client.post(
            f"/api/v1/knowledge/documents/{item_id}/lifecycle/suspend",
            json={"reason": "Flagged for a factual accuracy review."},
            headers={"X-CSRF-Token": csrf},
        )
        assert suspend.status_code == 200, suspend.text
        assert suspend.json()["data"]["state"] == "suspended"
        assert suspend.headers["Cache-Control"] == "no-store"

        after = client.get(f"/api/v1/knowledge/documents/{item_id}/lifecycle")
        assert after.status_code == 200, after.text
        assert after.json()["data"]["state"] == "suspended"
        assert after.json()["data"]["reason"] == "Flagged for a factual accuracy review."


def test_resume_after_suspend_over_http() -> None:
    with TestClient(
        create_app(_settings(development_subject_id="subject.lifecycle-wiring.resume"))
    ) as client:
        csrf = _login(client)
        item_id = "knowledge-item.wiring-resume-0001"
        client.post(
            f"/api/v1/knowledge/documents/{item_id}/lifecycle/suspend",
            json={"reason": "Temporary suspension for wiring test."},
            headers={"X-CSRF-Token": csrf},
        )

        resume = client.post(
            f"/api/v1/knowledge/documents/{item_id}/lifecycle/resume",
            json={"reason": "Review concluded; content stands."},
            headers={"X-CSRF-Token": csrf},
        )
        assert resume.status_code == 200, resume.text
        assert resume.json()["data"]["state"] == "active"


def test_resume_without_prior_suspension_returns_409() -> None:
    with TestClient(
        create_app(_settings(development_subject_id="subject.lifecycle-wiring.resume-409"))
    ) as client:
        csrf = _login(client)
        item_id = "knowledge-item.wiring-resume-409-0001"

        response = client.post(
            f"/api/v1/knowledge/documents/{item_id}/lifecycle/resume",
            json={"reason": "Nothing to resume."},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "document_knowledge_lifecycle_transition_not_allowed"


def test_supersede_then_retire_over_http() -> None:
    with TestClient(
        create_app(_settings(development_subject_id="subject.lifecycle-wiring.supersede"))
    ) as client:
        csrf = _login(client)
        item_id = "knowledge-item.wiring-supersede-0001"
        replacement_id = "knowledge-item.wiring-supersede-replacement"

        supersede = client.post(
            f"/api/v1/knowledge/documents/{item_id}/lifecycle/supersede",
            json={
                "superseded_by_item_id": replacement_id,
                "reason": "Replaced by an updated runbook.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert supersede.status_code == 200, supersede.text
        assert supersede.json()["data"]["state"] == "superseded"
        assert supersede.json()["data"]["superseded_by_item_id"] == replacement_id

        retire = client.post(
            f"/api/v1/knowledge/documents/{item_id}/lifecycle/retire",
            json={"reason": "Retention period elapsed."},
            headers={"X-CSRF-Token": csrf},
        )
        assert retire.status_code == 200, retire.text
        assert retire.json()["data"]["state"] == "retired"

        # RETIRED is terminal.
        retire_again = client.post(
            f"/api/v1/knowledge/documents/{item_id}/lifecycle/retire",
            json={"reason": "Attempting to retire again."},
            headers={"X-CSRF-Token": csrf},
        )
        assert retire_again.status_code == 409, retire_again.text
        assert retire_again.json()["code"] == "document_knowledge_lifecycle_transition_not_allowed"


def test_supersede_rejects_a_non_active_replacement_over_http() -> None:
    with TestClient(
        create_app(_settings(development_subject_id="subject.lifecycle-wiring.supersede-invalid"))
    ) as client:
        csrf = _login(client)
        replacement_id = "knowledge-item.wiring-supersede-invalid-replacement"
        client.post(
            f"/api/v1/knowledge/documents/{replacement_id}/lifecycle/suspend",
            json={"reason": "Suspended for unrelated reasons."},
            headers={"X-CSRF-Token": csrf},
        )

        response = client.post(
            "/api/v1/knowledge/documents/knowledge-item.wiring-supersede-invalid-source"
            "/lifecycle/supersede",
            json={
                "superseded_by_item_id": replacement_id,
                "reason": "Attempting to supersede by a suspended item.",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "document_knowledge_lifecycle_supersession_target_invalid"


# ---------------------------------------------------------------------------
# (b) Conflict recording, resolution, and listing over HTTP.
# ---------------------------------------------------------------------------


def test_record_resolve_and_list_conflict_over_http() -> None:
    with TestClient(
        create_app(_settings(development_subject_id="subject.lifecycle-wiring.conflict"))
    ) as client:
        csrf = _login(client)
        item_a = "knowledge-item.wiring-conflict-a"
        item_b = "knowledge-item.wiring-conflict-b"

        record = client.post(
            "/api/v1/knowledge/documents/conflicts",
            json={
                "knowledge_item_id_a": item_b,
                "knowledge_item_id_b": item_a,
                "conflict_type": "contradictory_guidance",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert record.status_code == 201, record.text
        body = record.json()["data"]
        # Canonical (lexicographic) order, regardless of request argument order.
        assert (body["knowledge_item_id_a"], body["knowledge_item_id_b"]) == (item_a, item_b)
        assert body["resolution"] is None
        conflict_id = body["conflict_id"]

        listed = client.get(f"/api/v1/knowledge/documents/conflicts?knowledge_item_id={item_a}")
        assert listed.status_code == 200, listed.text
        assert [item["conflict_id"] for item in listed.json()["data"]] == [conflict_id]

        resolve = client.post(
            f"/api/v1/knowledge/documents/conflicts/{conflict_id}/resolve",
            json={"resolution": "Superseded the older item with contradictory guidance."},
            headers={"X-CSRF-Token": csrf},
        )
        assert resolve.status_code == 200, resolve.text
        assert resolve.json()["data"]["resolution"] is not None
        assert resolve.json()["data"]["resolved_by"] == "subject.lifecycle-wiring.conflict"

        resolve_again = client.post(
            f"/api/v1/knowledge/documents/conflicts/{conflict_id}/resolve",
            json={"resolution": "Trying to resolve a second time."},
            headers={"X-CSRF-Token": csrf},
        )
        assert resolve_again.status_code == 409, resolve_again.text
        assert resolve_again.json()["code"] == "document_knowledge_conflict_already_resolved"


def test_record_conflict_rejects_unknown_conflict_type_over_http() -> None:
    with TestClient(
        create_app(_settings(development_subject_id="subject.lifecycle-wiring.conflict-type"))
    ) as client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/knowledge/documents/conflicts",
            json={
                "knowledge_item_id_a": "knowledge-item.wiring-bad-type-a",
                "knowledge_item_id_b": "knowledge-item.wiring-bad-type-b",
                "conflict_type": "not-a-real-conflict-type",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "document_knowledge_conflict_type_invalid"


# ---------------------------------------------------------------------------
# (c) Two-stage denial pattern (true 401, true 403) for every new route.
# ---------------------------------------------------------------------------

_ROUTE_CASES: tuple[tuple[str, str, str, dict[str, object] | None], ...] = (
    (
        "suspend",
        "POST",
        "/api/v1/knowledge/documents/knowledge-item.wiring-denial-example/lifecycle/suspend",
        {"reason": "Example reason."},
    ),
    (
        "resume",
        "POST",
        "/api/v1/knowledge/documents/knowledge-item.wiring-denial-example/lifecycle/resume",
        {"reason": "Example reason."},
    ),
    (
        "supersede",
        "POST",
        "/api/v1/knowledge/documents/knowledge-item.wiring-denial-example/lifecycle/supersede",
        {
            "superseded_by_item_id": "knowledge-item.wiring-denial-replacement",
            "reason": "Example reason.",
        },
    ),
    (
        "retire",
        "POST",
        "/api/v1/knowledge/documents/knowledge-item.wiring-denial-example/lifecycle/retire",
        {"reason": "Example reason."},
    ),
    (
        "get_lifecycle",
        "GET",
        "/api/v1/knowledge/documents/knowledge-item.wiring-denial-example/lifecycle",
        None,
    ),
    (
        "record_conflict",
        "POST",
        "/api/v1/knowledge/documents/conflicts",
        {
            "knowledge_item_id_a": "knowledge-item.wiring-denial-a",
            "knowledge_item_id_b": "knowledge-item.wiring-denial-b",
            "conflict_type": "contradictory_guidance",
        },
    ),
    (
        "resolve_conflict",
        "POST",
        "/api/v1/knowledge/documents/conflicts/document-knowledge-conflict.wiring-denial-example"
        "/resolve",
        {"resolution": "Example resolution."},
    ),
    (
        "list_conflicts",
        "GET",
        "/api/v1/knowledge/documents/conflicts?knowledge_item_id=knowledge-item.wiring-denial-example",
        None,
    ),
)


@pytest.mark.parametrize(
    "name,method,path,body", _ROUTE_CASES, ids=[case[0] for case in _ROUTE_CASES]
)
def test_route_requires_authentication(
    name: str, method: str, path: str, body: dict[str, object] | None
) -> None:
    app = create_app(_settings(development_identity_enabled=False))
    with TestClient(app) as client:
        response = client.request(method, path, json=body)
    assert response.status_code == 401, response.text
    assert response.json()["code"] == "authentication_required"


@pytest.mark.parametrize(
    "name,method,path,body", _ROUTE_CASES, ids=[case[0] for case in _ROUTE_CASES]
)
def test_route_requires_permission(
    name: str, method: str, path: str, body: dict[str, object] | None
) -> None:
    app = create_app(_settings(development_role_ids=()))
    with TestClient(app) as client:
        csrf = _login(client)
        headers = {"X-CSRF-Token": csrf} if method == "POST" else {}
        response = client.request(method, path, json=body, headers=headers)
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "authorization_denied"
