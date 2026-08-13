from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from httpx import Response

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
from atlas.modules.conversations.adapters.targets import (
    DevelopmentConversationTargetAccessSource,
)
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

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
TARGET_ID = "asset.storage.lab.vsp-g400"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class GroundedGenerator:
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
            "confidence_basis": ("One current governed health observation is available.",),
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
            confidence_basis=("One current governed health observation is available.",),
            failure_code=None,
            safety_notice=NO_EXECUTION_SAFETY_NOTICE,
            authority=authority,
            result_digest=canonical_digest(values),
        )


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
        correlation_id="correlation.conversation.api",
    )


def api_fixture() -> tuple[FastAPI, dict[str, AuthenticatedSubject]]:
    app = FastAPI()
    app.state.settings = Settings(environment="test", development_identity_enabled=False)
    app.state.conversation_service = ConversationService(
        repository=InMemoryConversationRepository(),
        generator=GroundedGenerator(),
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
    identity = {"subject": subject()}

    @app.middleware("http")
    async def correlation(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.correlation_id = "correlation.conversation.api"
        return await call_next(request)

    async def current_subject() -> AuthenticatedSubject:
        return identity["subject"]

    async def current_decision() -> AuthorizationDecision:
        return decision(identity["subject"].subject_id)

    app.dependency_overrides[authenticated_subject] = current_subject
    app.dependency_overrides[authorize_conversation_read] = current_decision
    app.dependency_overrides[authorize_conversation_create] = current_decision
    app.dependency_overrides[authorize_conversation_turn_append] = current_decision
    app.dependency_overrides[authorize_ai_grounded_query] = current_decision
    app.include_router(router, prefix="/api/v1")
    register_error_handlers(app)
    return app, identity


def create_payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.operational-conversation-create.v1",
        "target_id": TARGET_ID,
        "target_type": "storage",
        "title": "Primary storage investigation",
        "acknowledged_decision_support_only": True,
    }


def create(client: TestClient, key: str = "conversation-create-0001") -> Response:
    return cast(
        Response,
        client.post(
            "/api/v1/conversations",
            json=create_payload(),
            headers={"Idempotency-Key": key},
        ),
    )


def test_conversation_api_matches_the_fail_closed_frontend_wire_contract() -> None:
    app, _ = api_fixture()
    with TestClient(app) as client:
        created = create(client)
        created_data = created.json()["data"]
        inventory = client.get("/api/v1/conversations?limit=50")
        appended = client.post(
            f"/api/v1/conversations/{created_data['conversation_id']}/turns",
            json={
                "schema_version": "atlas.operational-conversation-turn-append.v1",
                "expected_version": 1,
                "question": "What is the current controller health?",
                "acknowledged_decision_support_only": True,
            },
            headers={"Idempotency-Key": "conversation-turn-0001"},
        )

    assert created.status_code == 201
    assert created.headers["Cache-Control"] == "no-store, max-age=0"
    assert set(created.json()) == {"data", "meta"}
    assert created_data["schema_version"] == "atlas.operational-conversation.v1"
    assert created_data["organization_id"] == "organization.enterprise"
    assert created_data["environment_id"] == "environment.test"
    assert created_data["site_id"] == "site.local"
    assert created_data["owner_subject_id"] == "subject.storage-operator"
    assert created_data["turn_count"] == 0
    assert created_data["turns"] == []
    assert inventory.status_code == 200
    assert inventory.json()["data"]["durable"] is False
    assert inventory.json()["data"]["truncated"] is False
    assert inventory.json()["data"]["authorized_targets"] == [
        {
            "target_id": TARGET_ID,
            "display_name": "Primary storage",
            "description": "Authorized test storage target.",
        }
    ]
    assert "turns" not in inventory.json()["data"]["conversations"][0]

    assert appended.status_code == 200
    updated = appended.json()["data"]
    assert updated["version"] == 2
    assert updated["turn_count"] == 2
    assert [item["role"] for item in updated["turns"]] == ["user", "assistant"]
    user_turn, assistant_turn = updated["turns"]
    assert user_turn["confidence_basis"] == ""
    assert assistant_turn["schema_version"] == "atlas.operational-conversation-turn.v1"
    assert assistant_turn["confidence_basis"] == (
        "One current governed health observation is available."
    )
    assert assistant_turn["artifact_references"] == [
        {
            "artifact_id": "artifact.storage.health",
            "artifact_type": "storage-health",
            "version": 3,
        }
    ]
    evidence = assistant_turn["evidence_references"][0]
    assert evidence["source_type"] == "storage-health"
    assert evidence["source_reference"] == "atlas://storage/health/1"
    assert evidence["artifact_version"] == "3"
    assert evidence["observed_at"] == assistant_turn["observed_at"]
    assert NO_EXECUTION_SAFETY_NOTICE in assistant_turn["safety_notice"]


def test_conversation_mutations_require_acknowledgement_and_exact_inputs() -> None:
    app, _ = api_fixture()
    payload = create_payload()
    payload["acknowledged_decision_support_only"] = False
    with TestClient(app) as client:
        denied = client.post(
            "/api/v1/conversations",
            json=payload,
            headers={"Idempotency-Key": "conversation-create-denied"},
        )
        payload = create_payload()
        payload["execution_authorized"] = True
        extra = client.post(
            "/api/v1/conversations",
            json=payload,
            headers={"Idempotency-Key": "conversation-create-extra"},
        )

    assert denied.status_code == 422
    assert denied.json()["code"] == "validation_failed"
    assert extra.status_code == 422
    assert extra.json()["code"] == "validation_failed"


def test_conversation_errors_do_not_disclose_record_existence() -> None:
    app, identity = api_fixture()
    with TestClient(app) as client:
        created = create(client).json()["data"]
        identity["subject"] = subject("subject.foreign-operator")
        foreign = client.get(f"/api/v1/conversations/{created['conversation_id']}")
        missing = client.get("/api/v1/conversations/conversation.missing")
        unavailable_target = client.post(
            "/api/v1/conversations",
            json={**create_payload(), "target_id": "asset.storage.lab.unknown"},
            headers={"Idempotency-Key": "conversation-create-unknown"},
        )

    assert foreign.status_code == missing.status_code == unavailable_target.status_code == 404
    assert foreign.json()["code"] == missing.json()["code"] == "conversation_not_found"
    assert foreign.json()["title"] == missing.json()["title"]
    assert foreign.json()["detail"] == missing.json()["detail"]
    assert unavailable_target.json()["detail"] == missing.json()["detail"]


def test_conversation_append_is_idempotent_and_version_bound() -> None:
    app, _ = api_fixture()
    body = {
        "schema_version": "atlas.operational-conversation-turn-append.v1",
        "expected_version": 1,
        "question": "What is the current controller health?",
        "acknowledged_decision_support_only": True,
    }
    with TestClient(app) as client:
        created = create(client).json()["data"]
        path = f"/api/v1/conversations/{created['conversation_id']}/turns"
        headers = {"Idempotency-Key": "conversation-turn-idempotent"}
        first = client.post(path, json=body, headers=headers)
        replay = client.post(path, json=body, headers=headers)
        stale = client.post(
            path,
            json={**body, "question": "Use a stale version for this question."},
            headers={"Idempotency-Key": "conversation-turn-stale"},
        )

    assert first.status_code == replay.status_code == 200
    assert replay.json()["data"]["canonical_digest"] == first.json()["data"]["canonical_digest"]
    assert stale.status_code == 409
    assert stale.json()["code"] == "conversation_version_conflict"
