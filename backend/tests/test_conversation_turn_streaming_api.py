"""Pass 36 of this session's standing audit loop found that docs/050_API.md Section 21 ("Chat
and AI Streaming") -- SSE as the default browser streaming mechanism for chat, with typed event
names, sequence IDs, heartbeat, reconnection cursor, and a terminal event -- had zero
implementation anywhere.
`atlas.api.routes.conversations.append_operational_conversation_turn_stream`
(`POST /api/v1/conversations/{conversation_id}/turns/stream`) closes that gap additively, without
touching the existing synchronous `POST /api/v1/conversations/{conversation_id}/turns` endpoint.

The new endpoint runs the exact same `ConversationService.append_turn(...)` call the synchronous
endpoint uses (as an `asyncio` task) and narrates its real progress: a real `event: started`
before the task begins, a real `: heartbeat` SSE comment every
`CONVERSATION_STREAM_HEARTBEAT_INTERVAL_SECONDS` while it is genuinely still pending, and then
either a real `event: evidence_added` per evidence reference plus `event: status` and a terminal
`event: completed` carrying the real, validated turn/conversation (success), or a single terminal
`event: error` carrying the real `ConversationOperationsError` code/detail (failure). No token-
level or per-stage streaming is fabricated -- see the endpoint's own docstring for why that would
be dishonest given how `GroundedAnswerService.answer()` is invoked as one atomic call.

These tests use a light fixture (mirroring `test_conversation_api.py`'s own `api_fixture()`
convention, which the pass 23 audit note in that file endorses as still having standalone value
for a service's own wire-contract behavior) for the stream's shape, sequencing, heartbeat, and
failure-path behavior, and a real, fully-wired `create_app()` + real login (mirroring
`test_conversation_api_wiring_api.py`'s convention) for the two-stage authentication/authorization
denial proof this session has required for every new endpoint.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import cast
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from httpx import Response

from atlas.api.app import create_app
from atlas.api.errors import register_error_handlers
from atlas.api.routes.conversations import router
from atlas.api.security import (
    authenticated_subject,
    authorize_ai_grounded_query,
    authorize_conversation_create,
    authorize_conversation_read,
    authorize_conversation_turn_append,
)
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.authorization.domain.models import AuthorizationDecision, DecisionOutcome
from atlas.modules.conversations.adapters.memory import InMemoryConversationRepository
from atlas.modules.conversations.adapters.targets import DevelopmentConversationTargetAccessSource
from atlas.modules.conversations.application.service import ConversationService
from atlas.modules.conversations.domain.models import (
    NO_EXECUTION_SAFETY_NOTICE,
    AuthorizedConversationTarget,
    ConversationArtifactReference,
    ConversationAuthority,
    ConversationEvidenceReference,
    ConversationGenerationRequest,
    ConversationGenerationResult,
    ConversationScope,
    ConversationTurnStatus,
    canonical_digest,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
TARGET_ID = "asset.storage.lab.vsp-g400"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class GroundedGenerator:
    """Deterministic, fast generator double -- mirrors `test_conversation_api.py`'s own."""

    async def generate(
        self, request: ConversationGenerationRequest
    ) -> ConversationGenerationResult:
        evidence = (
            ConversationEvidenceReference(
                evidence_id="evidence.storage.health.1",
                artifact_id="artifact.storage.health",
                artifact_version="3",
                source_type="storage-health",
                source_reference="atlas://storage/health/1",
                observed_at=request.requested_at,
                citation="Controller health observation for the selected storage target.",
            ),
            ConversationEvidenceReference(
                evidence_id="evidence.storage.health.2",
                artifact_id="artifact.storage.capacity",
                artifact_version="1",
                source_type="storage-capacity",
                source_reference="atlas://storage/capacity/1",
                observed_at=request.requested_at,
                citation="Capacity observation for the selected storage target.",
            ),
        )
        artifacts = (
            ConversationArtifactReference(
                artifact_id="artifact.storage.health",
                artifact_type="storage-health",
                artifact_version=3,
            ),
        )
        authority = ConversationAuthority()
        values = {
            "artifact_references": [item.canonical_value() for item in artifacts],
            "assumptions": ("The observation represents the selected storage target.",),
            "authority": authority.canonical_value(),
            "confidence_basis": ("Two current governed observations are available.",),
            "conversation_id": request.conversation_id,
            "evidence_references": [item.canonical_value() for item in evidence],
            "failure_code": None,
            "observed_at": request.requested_at.isoformat(),
            "owner_subject_id": request.owner_subject_id,
            "request_digest": request.request_digest,
            "safety_notice": NO_EXECUTION_SAFETY_NOTICE,
            "scope": request.scope.canonical_value(),
            "status": ConversationTurnStatus.COMPLETED.value,
            "target_id": request.target_id,
            "text": "The available evidence reports normal controller health.",
            "unknowns": ("Workload path telemetry was not included.",),
        }
        return ConversationGenerationResult(
            request_digest=request.request_digest,
            conversation_id=request.conversation_id,
            scope=request.scope,
            owner_subject_id=request.owner_subject_id,
            target_id=request.target_id,
            status=ConversationTurnStatus.COMPLETED,
            text="The available evidence reports normal controller health.",
            observed_at=request.requested_at,
            evidence_references=evidence,
            artifact_references=artifacts,
            assumptions=("The observation represents the selected storage target.",),
            unknowns=("Workload path telemetry was not included.",),
            confidence_basis=("Two current governed observations are available.",),
            failure_code=None,
            safety_notice=NO_EXECUTION_SAFETY_NOTICE,
            authority=authority,
            result_digest=canonical_digest(values),
        )


class SlowGroundedGenerator:
    """Wraps `GroundedGenerator` with a real, awaited delay so tests can deterministically
    observe the heartbeat path -- a genuinely slow real awaitable, not a simulated one.
    """

    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds
        self._inner = GroundedGenerator()

    async def generate(
        self, request: ConversationGenerationRequest
    ) -> ConversationGenerationResult:
        await asyncio.sleep(self._delay_seconds)
        return await self._inner.generate(request)


def subject(subject_id: str = "subject.storage-operator") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name="Storage Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.enterprise",
        role_ids=("role.infrastructure-operator",),
    )


def decision(subject_id: str = "subject.storage-operator") -> AuthorizationDecision:
    return AuthorizationDecision(
        decision_id=f"decision.conversation.{subject_id}",
        decided_at=NOW,
        outcome=DecisionOutcome.ALLOWED,
        reason_code="permission_granted",
        permission_id="permission.conversation.read",
        scope_reference="organization.enterprise/environment.test/site.local/conversation",
        subject_id=subject_id,
        role_references=("role.infrastructure-operator:v1",),
        assignment_references=("assignment.infrastructure-operator:v1",),
        correlation_id="correlation.conversation.stream.api",
    )


def api_fixture(*, generator: object | None = None) -> FastAPI:
    app = FastAPI()
    app.state.settings = Settings(environment="test", development_identity_enabled=False)
    app.state.conversation_service = ConversationService(
        repository=InMemoryConversationRepository(),
        generator=generator or GroundedGenerator(),  # type: ignore[arg-type]
        audit_sink=CollectingAuditSink(),
    )
    app.state.conversation_target_access_source = DevelopmentConversationTargetAccessSource(
        subject_id="subject.storage-operator",
        required_principal_ids=frozenset({"role.infrastructure-operator"}),
        scope=ConversationScope("organization.enterprise", "environment.test", "site.local"),
        targets=(
            AuthorizedConversationTarget(
                target_id=TARGET_ID,
                display_name="Primary storage",
                description="Authorized test storage target.",
            ),
        ),
    )

    @app.middleware("http")
    async def correlation(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.correlation_id = "correlation.conversation.stream.api"
        return await call_next(request)

    async def current_subject() -> AuthenticatedSubject:
        return subject()

    async def current_decision() -> AuthorizationDecision:
        return decision()

    app.dependency_overrides[authenticated_subject] = current_subject
    app.dependency_overrides[authorize_conversation_read] = current_decision
    app.dependency_overrides[authorize_conversation_create] = current_decision
    app.dependency_overrides[authorize_conversation_turn_append] = current_decision
    app.dependency_overrides[authorize_ai_grounded_query] = current_decision
    app.include_router(router, prefix="/api/v1")
    register_error_handlers(app)
    return app


def create_payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.operational-conversation-create.v1",
        "target_id": TARGET_ID,
        "target_type": "storage",
        "title": "Primary storage investigation",
        "acknowledged_decision_support_only": True,
    }


def turn_payload(question: str = "What is the current controller health?") -> dict[str, object]:
    return {
        "schema_version": "atlas.operational-conversation-turn-append.v1",
        "expected_version": 1,
        "question": question,
        "acknowledged_decision_support_only": True,
    }


def create(client: TestClient, key: str) -> Response:
    return cast(
        Response,
        client.post(
            "/api/v1/conversations",
            json=create_payload(),
            headers={"Idempotency-Key": key},
        ),
    )


def parse_sse(text: str) -> tuple[list[tuple[str, dict[str, object], int]], int]:
    """Split a raw SSE response body into its typed events and a heartbeat comment count."""
    events: list[tuple[str, dict[str, object], int]] = []
    heartbeats = 0
    for block in text.replace("\r\n", "\n").strip("\n").split("\n\n"):
        if not block:
            continue
        if block.startswith(": heartbeat"):
            heartbeats += 1
            continue
        event_type = ""
        data: dict[str, object] = {}
        sequence_id = -1
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
            elif line.startswith("id: "):
                sequence_id = int(line[len("id: ") :])
        events.append((event_type, data, sequence_id))
    return events, heartbeats


def test_conversation_turn_stream_is_well_formed_with_one_terminal_event() -> None:
    app = api_fixture()
    with TestClient(app) as client:
        conversation_id = create(client, "stream-wellformed-create").json()["data"][
            "conversation_id"
        ]
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/turns/stream",
            json=turn_payload(),
            headers={"Idempotency-Key": "stream-wellformed-turn"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store, max-age=0"

    events, heartbeats = parse_sse(response.text)
    assert heartbeats == 0  # the real generator resolves faster than one heartbeat interval
    event_names = [event for event, _data, _seq in events]
    assert event_names[0] == "started"
    assert event_names[-1] == "completed"
    # exactly one terminal event: nothing follows "completed"
    assert event_names.count("completed") == 1
    assert "error" not in event_names
    assert event_names[1:-1] == ["evidence_added", "evidence_added", "status"]

    started_data = events[0][1]
    assert started_data["conversation_id"] == conversation_id
    assert started_data["idempotency_key"] == "stream-wellformed-turn"

    status_data = events[-2][1]
    assert status_data["status"] == "completed"

    completed_data = events[-1][1]
    assert completed_data["conversation_id"] == conversation_id
    assert completed_data["version"] == 2
    assert completed_data["turn_count"] == 2
    turns = cast(list[dict[str, object]], completed_data["turns"])
    assert [turn["role"] for turn in turns] == ["user", "assistant"]
    assistant_turn = turns[1]
    assert assistant_turn["status"] == "completed"
    assert len(cast(list[object], assistant_turn["evidence_references"])) == 2


def test_conversation_turn_stream_sequence_ids_are_monotonically_increasing() -> None:
    app = api_fixture()
    with TestClient(app) as client:
        conversation_id = create(client, "stream-sequence-create").json()["data"]["conversation_id"]
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/turns/stream",
            json=turn_payload(),
            headers={"Idempotency-Key": "stream-sequence-turn"},
        )

    events, _heartbeats = parse_sse(response.text)
    sequence_ids = [seq for _event, _data, seq in events]
    assert sequence_ids == sorted(sequence_ids)
    assert len(sequence_ids) == len(set(sequence_ids))
    assert sequence_ids[0] == 0
    assert sequence_ids == list(range(len(sequence_ids)))


def test_conversation_turn_stream_matches_synchronous_equivalent() -> None:
    app = api_fixture()
    with TestClient(app) as client:
        sync_conversation_id = create(client, "stream-parity-sync-create").json()["data"][
            "conversation_id"
        ]
        sync_response = client.post(
            f"/api/v1/conversations/{sync_conversation_id}/turns",
            json=turn_payload(),
            headers={"Idempotency-Key": "stream-parity-sync-turn"},
        )

        stream_conversation_id = create(client, "stream-parity-stream-create").json()["data"][
            "conversation_id"
        ]
        stream_response = client.post(
            f"/api/v1/conversations/{stream_conversation_id}/turns/stream",
            json=turn_payload(),
            headers={"Idempotency-Key": "stream-parity-stream-turn"},
        )

    assert sync_response.status_code == 200
    sync_assistant = sync_response.json()["data"]["turns"][1]

    events, _heartbeats = parse_sse(stream_response.text)
    completed_data = events[-1][1]
    stream_assistant = cast(list[dict[str, object]], completed_data["turns"])[1]

    for field in (
        "role",
        "status",
        "text",
        "assumptions",
        "unknowns",
        "confidence_basis",
        "failure_code",
        "safety_notice",
        "artifact_references",
    ):
        assert stream_assistant[field] == sync_assistant[field], field

    sync_evidence = cast(list[dict[str, object]], sync_assistant["evidence_references"])
    stream_evidence = cast(list[dict[str, object]], stream_assistant["evidence_references"])
    assert len(sync_evidence) == len(stream_evidence) == 2
    for sync_item, stream_item in zip(sync_evidence, stream_evidence, strict=True):
        for field in ("evidence_id", "artifact_id", "artifact_version", "source_type", "citation"):
            assert sync_item[field] == stream_item[field]


def test_conversation_turn_stream_evidence_events_match_completed_evidence() -> None:
    app = api_fixture()
    with TestClient(app) as client:
        conversation_id = create(client, "stream-evidence-create").json()["data"]["conversation_id"]
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/turns/stream",
            json=turn_payload(),
            headers={"Idempotency-Key": "stream-evidence-turn"},
        )

    events, _heartbeats = parse_sse(response.text)
    evidence_events = [data for event, data, _seq in events if event == "evidence_added"]
    completed_data = events[-1][1]
    assistant_turn = cast(list[dict[str, object]], completed_data["turns"])[1]
    completed_evidence = cast(list[dict[str, object]], assistant_turn["evidence_references"])

    assert [item["evidence_id"] for item in evidence_events] == [
        item["evidence_id"] for item in completed_evidence
    ]


def test_conversation_turn_stream_unknown_conversation_emits_single_error_event() -> None:
    app = api_fixture()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/conversations/conversation.does-not-exist/turns/stream",
            json=turn_payload(),
            headers={"Idempotency-Key": "stream-missing-turn"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events, heartbeats = parse_sse(response.text)
    assert heartbeats == 0
    event_names = [event for event, _data, _seq in events]
    assert event_names == ["started", "error"]

    error_data = events[-1][1]
    assert error_data["code"] == "conversation_not_found"
    assert error_data["detail"]


def test_conversation_turn_stream_emits_heartbeats_while_generation_is_pending() -> None:
    app = api_fixture(generator=SlowGroundedGenerator(delay_seconds=0.25))
    with (
        TestClient(app) as client,
        patch(
            "atlas.api.routes.conversations.CONVERSATION_STREAM_HEARTBEAT_INTERVAL_SECONDS",
            0.05,
        ),
    ):
        conversation_id = create(client, "stream-heartbeat-create").json()["data"][
            "conversation_id"
        ]
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/turns/stream",
            json=turn_payload(),
            headers={"Idempotency-Key": "stream-heartbeat-turn"},
        )

    assert response.status_code == 200
    events, heartbeats = parse_sse(response.text)
    # A 0.25s real delay against a 0.05s heartbeat tick guarantees several heartbeats; assert a
    # generous lower bound rather than an exact count to avoid coupling to scheduler timing.
    assert heartbeats >= 2
    event_names = [event for event, _data, _seq in events]
    assert event_names[0] == "started"
    assert event_names[-1] == "completed"
    # sequence numbering only counts typed events, and must still be contiguous and monotonic
    sequence_ids = [seq for _event, _data, seq in events]
    assert sequence_ids == list(range(len(sequence_ids)))


def _wiring_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "development",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _wiring_login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def test_conversation_turn_stream_requires_authentication() -> None:
    """No session cookie and no development identity: the streaming route must fail closed at
    authentication, not merely at authorization -- proving `authenticated_subject` really runs
    before any SSE body is ever streamed back.
    """
    with TestClient(create_app(Settings(environment="development"))) as client:
        response = client.post(
            "/api/v1/conversations/conversation.wiring.missing/turns/stream",
            json=turn_payload(),
            headers={"Idempotency-Key": "stream-wiring-auth-0001"},
        )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
    assert not response.headers["content-type"].startswith("text/event-stream")


def test_conversation_turn_stream_requires_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must still be denied
    by the real `AuthorizationService`, not by a faked dependency override, and the denial must
    happen before any SSE body is streamed.
    """
    with TestClient(create_app(_wiring_settings(development_role_ids=()))) as client:
        csrf = _wiring_login(client)
        response = client.post(
            "/api/v1/conversations/conversation.wiring.missing/turns/stream",
            json=turn_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "stream-wiring-authz-0001"},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert not response.headers["content-type"].startswith("text/event-stream")


def test_conversation_turn_stream_reachable_through_real_authorization() -> None:
    with TestClient(create_app(_wiring_settings())) as client:
        csrf = _wiring_login(client)
        headers = {"X-CSRF-Token": csrf}

        created = client.post(
            "/api/v1/conversations",
            json={
                "schema_version": "atlas.operational-conversation-create.v1",
                "target_id": TARGET_ID,
                "target_type": "storage",
                "title": "Streaming wiring test investigation",
                "acknowledged_decision_support_only": True,
            },
            headers={**headers, "Idempotency-Key": "stream-wiring-create-0001"},
        )
        assert created.status_code == 201, created.text
        conversation_id = created.json()["data"]["conversation_id"]

        response = client.post(
            f"/api/v1/conversations/{conversation_id}/turns/stream",
            json=turn_payload("What is the current controller health for this target?"),
            headers={**headers, "Idempotency-Key": "stream-wiring-turn-0001"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events, _heartbeats = parse_sse(response.text)
    event_names = [event for event, _data, _seq in events]
    assert event_names[0] == "started"
    assert event_names[-1] == "completed"
    completed_data = events[-1][1]
    assert completed_data["conversation_id"] == conversation_id
    assert completed_data["version"] == 2
