"""Pass 23 of this session's standing audit loop found that `atlas.api.routes.conversations` (4
endpoints: list, create, get, append-turn) has exactly one test file -- test_conversation_api.py
-- whose `api_fixture()` helper mounts the router on a bare `FastAPI()` instance with
`app.dependency_overrides[authenticated_subject]`,
`app.dependency_overrides[authorize_conversation_read]`,
`app.dependency_overrides[authorize_conversation_create]`,
`app.dependency_overrides[authorize_conversation_turn_append]`, and
`app.dependency_overrides[authorize_ai_grounded_query]` all replaced with fakes that always
resolve to a fixed, pre-approved subject and decision. That bypasses real RBAC/`RoleAssignment`
resolution and the permission-decorator wiring in `atlas.api.app.create_app` entirely.

These tests drive all 4 endpoints through the real, wired app instead: a real login against
`/api/v1/authentication/sessions`, real session/CSRF handling, and real permission resolution
against the live authorization catalog (`DEVELOPMENT_ROLE_ID` is granted `CONVERSATION_READ`,
`CONVERSATION_CREATE`, `CONVERSATION_TURN_APPEND`, and `AI_GROUNDED_QUERY_CREATE`; see
`atlas.modules.authorization.application.bootstrap`). They do not replace
test_conversation_api.py, whose fake-generator fixture (a fixed, evidence-bearing
`GroundedGenerator` double) still has standalone value for exercising the conversation service's
own wire-contract logic (turn ordering, idempotency, version conflicts, cross-owner 404 hiding)
deterministically, independent of the real grounded-answer/retrieval pipeline's behavior.

`environment="development"` is required here, not this repo's usual wiring-test
`environment="test"`: `atlas.api.app.create_app` only builds a non-empty
`DevelopmentConversationTargetAccessSource` (real, synthetic authorized storage targets --
`asset.storage.lab.vsp-g400` and `asset.storage.lab.vsp-one-b28`) when
`resolved_settings.environment == "development"`; under `environment="test"` it substitutes an
`EmptyConversationTargetAccessSource`, and every create/read call would then correctly reject
`target_id` as unauthorized -- which would prove authorization is *deniable* but never let this
pass demonstrate the routes' real *authorized* path end-to-end.

Appending a turn drives the real `GroundedConversationGenerator` -> `GroundedAnswerService` ->
`KnowledgeRetrievalService` chain (`atlas.api.app`'s real
`resolved_grounded_answer_service`/`resolved_conversation_service` wiring), not a test double.
This development-environment retrieval service is backed by a fixed, code-owned synthetic
knowledge profile (Hitachi VSP controller-health/capacity guidance) that deterministically matches
a "controller health" question with two citations -- verified empirically by driving this exact
request through the real app once (`GroundedAnswerService.answer()`'s `retrieval.hits`-populated
branch, `model_invoked=True`) -- so the assistant turn's exact content is asserted precisely below
rather than merely checked for shape. This is real, HTTP-observable behavior of the actual wired
pipeline, not a canned double; `ConversationService.append_turn` also has its own generic
generation-failure fallback (any generator exception degrades to a `status="failed"` assistant
turn rather than an HTTP error) so this path cannot flake into a request failure either way.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings

TARGET_ID = "asset.storage.lab.vsp-g400"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "development",
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


def test_conversation_api_requires_authentication() -> None:
    """No session cookie and no development identity: the route must fail closed at
    authentication, not merely at authorization -- proving `authenticated_subject` really runs.
    """
    with TestClient(create_app(Settings(environment="development"))) as client:
        response = client.get("/api/v1/conversations")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_conversation_api_requires_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must still be denied
    by the real `AuthorizationService`, not by a faked dependency override.
    """
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)
        response = client.get("/api/v1/conversations", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"


def test_conversation_lifecycle_is_reachable_through_real_authorization() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        headers = {"X-CSRF-Token": csrf}

        inventory_before = client.get("/api/v1/conversations?limit=50", headers=headers)
        assert inventory_before.status_code == 200
        authorized_target_ids = {
            item["target_id"] for item in inventory_before.json()["data"]["authorized_targets"]
        }
        assert TARGET_ID in authorized_target_ids

        created = client.post(
            "/api/v1/conversations",
            json={
                "schema_version": "atlas.operational-conversation-create.v1",
                "target_id": TARGET_ID,
                "target_type": "storage",
                "title": "Wiring test investigation",
                "acknowledged_decision_support_only": True,
            },
            headers={**headers, "Idempotency-Key": "conversation-wiring-create-0001"},
        )
        assert created.status_code == 201, created.text
        assert created.headers["Cache-Control"] == "no-store, max-age=0"
        conversation = created.json()["data"]
        assert conversation["owner_subject_id"] == "subject.development.operator"
        assert conversation["organization_id"] == "organization.development"
        assert conversation["environment_id"] == "environment.development"
        assert conversation["site_id"] == "site.local"
        assert conversation["target_id"] == TARGET_ID
        assert conversation["turn_count"] == 0
        assert conversation["turns"] == []

        fetched = client.get(
            f"/api/v1/conversations/{conversation['conversation_id']}", headers=headers
        )
        assert fetched.status_code == 200
        assert fetched.json()["data"]["conversation_id"] == conversation["conversation_id"]

        missing = client.get("/api/v1/conversations/conversation.wiring.missing", headers=headers)
        assert missing.status_code == 404
        assert missing.json()["code"] == "conversation_not_found"

        appended = client.post(
            f"/api/v1/conversations/{conversation['conversation_id']}/turns",
            json={
                "schema_version": "atlas.operational-conversation-turn-append.v1",
                "expected_version": 1,
                "question": "What is the current controller health for this target?",
                "acknowledged_decision_support_only": True,
            },
            headers={**headers, "Idempotency-Key": "conversation-wiring-turn-0001"},
        )
        assert appended.status_code == 200, appended.text
        updated = appended.json()["data"]
        assert updated["version"] == 2
        assert updated["turn_count"] == 2
        assert [turn["role"] for turn in updated["turns"]] == ["user", "assistant"]
        user_turn, assistant_turn = updated["turns"]
        assert user_turn["status"] == "completed"
        assert assistant_turn["status"] == "completed"
        assert len(assistant_turn["evidence_references"]) == 2
        assert {item["artifact_id"] for item in assistant_turn["evidence_references"]} == {
            "item.hitachi.health-guidance",
            "item.hitachi.capacity-guidance",
        }
        assert assistant_turn["unknowns"] == [
            "Live infrastructure state was not queried by this model request.",
            "The synthetic knowledge profile cannot confirm current service impact.",
        ]
        assert assistant_turn["confidence_basis"] == (
            "Governed grounded-answer service returned 2 authorized citation(s)."
        )
        assert assistant_turn["failure_code"] is None

        replayed = client.post(
            f"/api/v1/conversations/{conversation['conversation_id']}/turns",
            json={
                "schema_version": "atlas.operational-conversation-turn-append.v1",
                "expected_version": 1,
                "question": "What is the current controller health for this target?",
                "acknowledged_decision_support_only": True,
            },
            headers={**headers, "Idempotency-Key": "conversation-wiring-turn-0001"},
        )
        assert replayed.status_code == 200
        assert replayed.json()["data"]["canonical_digest"] == updated["canonical_digest"]

        inventory_after = client.get("/api/v1/conversations?limit=50", headers=headers)
        assert inventory_after.status_code == 200
        inventory_data = inventory_after.json()["data"]
        assert inventory_data["durable"] is False
        listed_ids = {item["conversation_id"] for item in inventory_data["conversations"]}
        assert conversation["conversation_id"] in listed_ids
        assert "turns" not in inventory_data["conversations"][0]
