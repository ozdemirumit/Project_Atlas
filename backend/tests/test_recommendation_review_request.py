from __future__ import annotations

from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_protected_recommendation_adjudication import BROWSER_SESSION_ID
from test_recommendation_readiness import create_readiness, readiness_fixture

from atlas.api.app import create_app
from atlas.api.recommendation_review_request_schemas import (
    RecommendationReviewRequestInput,
    RecommendationReviewRequestResultData,
)
from atlas.core.config import Settings
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.adapters.review_request_memory import (
    InMemoryRecommendationReviewRequestPolicySource,
    MemoryRecommendationReviewRequestRepository,
)
from atlas.modules.recommendations.adapters.review_request_postgres import (
    PostgreSQLRecommendationReviewRequestRepository,
)
from atlas.modules.recommendations.adapters.review_request_synthetic import (
    SyntheticTrustedRecommendationReviewRequestOrchestrator,
    UnavailableTrustedRecommendationReviewRequestOrchestrator,
)
from atlas.modules.recommendations.application.readiness import (
    GovernedRecommendationReadinessService,
)
from atlas.modules.recommendations.application.review_request import (
    GovernedRecommendationReviewRequestService,
    build_development_recommendation_review_request_policy,
)
from atlas.modules.recommendations.application.review_request_ports import (
    RecommendationReviewRequestError,
)
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessResult
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestPolicySnapshot,
    RecommendationReviewRequestResult,
)


class RecordingReviewRequestPermissionAuthorizer:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.calls: list[tuple[str, str]] = []

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None:
        del actor, correlation_id
        self.calls.append((organization_id, environment_id))
        if self.deny:
            raise RecommendationReviewRequestError(
                "recommendation_review_request_permission_denied"
            )


class TamperingReviewRequestOrchestrator(SyntheticTrustedRecommendationReviewRequestOrchestrator):
    def __init__(self, field: str) -> None:
        self._field = field

    async def orchestrate(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        receipt, record = await super().orchestrate(*args, **kwargs)  # type: ignore[arg-type]
        if self._field == "routing_digest":
            receipt = replace(receipt, routing_digest="e" * 64)
        elif self._field == "request_digest":
            receipt = replace(receipt, request_digest="e" * 64)
        else:
            record = replace(record, source_binding_digest="e" * 64)
        if self._field in {"routing_digest", "request_digest"}:
            receipt = replace(
                receipt,
                canonical_digest=GovernedProtectedModelInvocationService._digest(
                    GovernedProtectedModelInvocationService._payload(
                        replace(receipt, canonical_digest="0" * 64)
                    )
                ),
            )
            record = replace(record, review_request_receipt_digest=receipt.canonical_digest)
        return receipt, record


async def review_request_fixture(
    *, deny: bool = False, unavailable: bool = False
) -> tuple[
    GovernedRecommendationReviewRequestService,
    MemoryRecommendationReviewRequestRepository,
    RecommendationReviewRequestPolicySnapshot,
    RecommendationReadinessResult,
    AuthenticatedSubject,
    RecordingReviewRequestPermissionAuthorizer,
]:
    readiness_service, _, readiness_policy, promotion, actor, _ = await readiness_fixture()
    readiness = await create_readiness(readiness_service, readiness_policy, promotion, actor)
    policy = build_development_recommendation_review_request_policy(
        organization_id=readiness.assessment.organization_id,
        environment_id=readiness.assessment.environment_id,
        issued_at=readiness.assessment.assessed_at - timedelta(hours=1),
        expires_at=readiness.assessment.assessed_at + timedelta(days=1),
    )
    permission = RecordingReviewRequestPermissionAuthorizer(deny=deny)
    repository = MemoryRecommendationReviewRequestRepository()
    orchestrator = (
        UnavailableTrustedRecommendationReviewRequestOrchestrator()
        if unavailable
        else SyntheticTrustedRecommendationReviewRequestOrchestrator()
    )
    service = GovernedRecommendationReviewRequestService(
        repository=repository,
        readiness_source=readiness_service,
        policy_source=InMemoryRecommendationReviewRequestPolicySource((policy,)),
        permission_authorizer=permission,
        orchestrator=orchestrator,
        audit_sink=readiness_service._audit_sink,
        environment_id=readiness.assessment.environment_id,
        clock=lambda: readiness.assessment.assessed_at,
    )
    return service, repository, policy, readiness, actor, permission


async def create_review_request(
    service: GovernedRecommendationReviewRequestService,
    policy: RecommendationReviewRequestPolicySnapshot,
    readiness: RecommendationReadinessResult,
    actor: AuthenticatedSubject,
) -> RecommendationReviewRequestResult:
    assessment = readiness.assessment
    return await service.create(
        actor=actor,
        recommendation_id=assessment.recommendation_id,
        recommendation_digest=assessment.source_artifact_digest,
        readiness_assessment_id=assessment.assessment_id,
        readiness_assessment_digest=assessment.canonical_digest,
        review_request_policy_id=policy.policy_id,
        review_request_policy_digest=policy.canonical_digest,
        purpose=assessment.purpose,
        request_is_not_assignment_or_review_acknowledged=True,
        routing_is_policy_owned_acknowledged=True,
        no_approval_or_operational_authority_acknowledged=True,
        browser_session_id=BROWSER_SESSION_ID,
        idempotency_key="recommendation-review-request-001",
        correlation_id="cor_recommendation_review_request",
    )


@pytest.mark.asyncio
async def test_request_creates_policy_routed_manifest_and_exact_replay() -> None:
    service, _, policy, readiness, actor, permission = await review_request_fixture()
    result = await create_review_request(service, policy, readiness, actor)
    repeated = await create_review_request(service, policy, readiness, actor)
    replay = await service.get(
        actor=actor,
        review_request_id=result.record.review_request_id,
        browser_session_id=BROWSER_SESSION_ID,
        correlation_id="cor_recommendation_review_request_read",
    )

    record = result.record
    assert record.state == "review_requested"
    assert record.review_requested
    assert record.track_codes == policy.track_codes
    assert record.queue_ids == policy.queue_ids
    assert record.track_statuses == tuple(
        (track, "awaiting_reviewer") for track in policy.track_codes
    )
    assert record.source_outcome == readiness.assessment.source_outcome
    assert not record.reviewer_assigned
    assert not record.content_inspection_opened
    assert not record.human_review_completed
    assert not record.recommendation_approved
    assert not record.workflow_created
    assert not record.itsm_record_created
    assert not record.execution_authorized
    assert not record.deployment_authorized
    assert not record.infrastructure_mutated
    assert repeated.record.reused and replay.record.reused
    assert len(permission.calls) == 4


@pytest.mark.asyncio
async def test_blocked_source_cannot_enter_review_request_orchestration() -> None:
    service, _, policy, readiness, _, _ = await review_request_fixture()
    assessment = readiness.assessment
    blocked = replace(
        assessment,
        evaluation_outcome="blocked",
        reason_codes=("source-content-incomplete",),
        passed_check_count=assessment.check_count - 1,
        state="blocked",
        recommendation_ready_for_review=False,
        canonical_digest="0" * 64,
    )
    blocked = replace(
        blocked,
        canonical_digest=GovernedRecommendationReadinessService._assessment_digest(blocked),
    )
    blocked_source = replace(readiness, assessment=blocked)
    with pytest.raises(RecommendationReviewRequestError, match="source_invalid"):
        service._verify_source(
            blocked_source,
            policy,
            blocked.recommendation_id,
            blocked.source_artifact_digest,
            blocked.canonical_digest,
            blocked.purpose,
            blocked.assessed_at,
        )


@pytest.mark.asyncio
async def test_review_request_response_exposes_safe_metadata_only() -> None:
    service, _, policy, readiness, actor, _ = await review_request_fixture()
    result = await create_review_request(service, policy, readiness, actor)
    response = RecommendationReviewRequestResultData.from_domain(result).model_dump()
    serialized = str(response).lower()
    for private in (
        "claim_id",
        "requester_subject_digest",
        "browser_session_binding_digest",
        "review_request_receipt_digest",
        "review_request_authorization_digest",
        "source_assessment_digest",
        "source_recommendation_digest",
        "source_binding_digest",
        "policy_digest",
        "attested_by",
        "tool_call",
        "<script",
    ):
        assert private not in serialized
    assert response["request"]["state"] == "review_requested"
    assert response["request"]["reviewer_assigned"] is False
    assert response["request"]["execution_authorized"] is False


@pytest.mark.asyncio
async def test_postgres_review_request_round_trip_preserves_record() -> None:
    service, _, policy, readiness, actor, _ = await review_request_fixture()
    result = await create_review_request(service, policy, readiness, actor)
    payload = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(payload, dict)
    restored = PostgreSQLRecommendationReviewRequestRepository._record_to_domain(payload)
    assert restored == result.record


@pytest.mark.asyncio
async def test_permission_denial_happens_before_review_request_claim() -> None:
    service, repository, policy, readiness, actor, permission = await review_request_fixture(
        deny=True
    )
    with pytest.raises(RecommendationReviewRequestError, match="permission_denied"):
        await create_review_request(service, policy, readiness, actor)
    assert permission.calls
    assert not repository._claims
    assert not repository._records


@pytest.mark.asyncio
async def test_unavailable_orchestrator_fails_closed() -> None:
    service, repository, policy, readiness, actor, _ = await review_request_fixture(
        unavailable=True
    )
    with pytest.raises(RecommendationReviewRequestError, match="orchestrator_unavailable"):
        await create_review_request(service, policy, readiness, actor)
    assert repository._claims
    assert not repository._records


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tampered_field",
    ("routing_digest", "request_digest", "source_binding_digest"),
)
async def test_review_request_rejects_cross_binding_tampering(tampered_field: str) -> None:
    service, repository, policy, readiness, actor, _ = await review_request_fixture()
    service._orchestrator = TamperingReviewRequestOrchestrator(tampered_field)
    with pytest.raises(RecommendationReviewRequestError, match="receipt_invalid"):
        await create_review_request(service, policy, readiness, actor)
    assert repository._claims
    assert not repository._records


@pytest.mark.asyncio
async def test_exact_replay_rejects_tampered_review_request_claim() -> None:
    service, repository, policy, readiness, actor, _ = await review_request_fixture()
    await create_review_request(service, policy, readiness, actor)
    claim_id, claim = next(iter(repository._claims.items()))
    repository._claims[claim_id] = replace(
        claim, recommendation_id="recommendation.promoted.tampered"
    )
    with pytest.raises(RecommendationReviewRequestError, match="integrity_failed"):
        await create_review_request(service, policy, readiness, actor)


def test_input_schema_forbids_caller_shaped_routing_or_authority() -> None:
    payload = {
        "recommendation_digest": "a" * 64,
        "readiness_assessment_id": "recommendation-readiness-assessment.example",
        "readiness_assessment_digest": "b" * 64,
        "review_request_policy_id": "recommendation-review-request-policy.development",
        "review_request_policy_digest": "c" * 64,
        "purpose": "Request accountable human review of the exact recommendation.",
        "acknowledged_request_is_not_assignment_or_review": True,
        "acknowledged_routing_is_policy_owned": True,
        "acknowledged_no_approval_or_operational_authority": True,
        "track_codes": ["review-track.caller-selected"],
        "queue_id": "review-queue.caller-selected",
        "reviewer_id": "subject.reviewer",
        "decision": "approved",
        "command": "restart-controller",
    }
    with pytest.raises(ValidationError):
        RecommendationReviewRequestInput.model_validate(payload)


def test_openapi_registers_recommendation_review_request_routes() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/recommendations/{recommendation_id}/human-review-requests" in paths
    assert (
        "/api/v1/recommendations/{recommendation_id}/human-review-requests/"
        "{review_request_id}" in paths
    )
