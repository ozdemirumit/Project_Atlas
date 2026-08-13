from __future__ import annotations

from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_protected_recommendation_adjudication import BROWSER_SESSION_ID
from test_recommendation_review_request import create_review_request, review_request_fixture

from atlas.api.app import create_app
from atlas.api.recommendation_reviewer_assignment_schemas import (
    RecommendationReviewerAssignmentInput,
    RecommendationReviewerAssignmentResultData,
)
from atlas.core.config import Settings
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE,
    RECOMMENDATION_REVIEWER_ASSIGNMENT_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
)
from atlas.modules.recommendations.adapters.reviewer_assignment_memory import (
    InMemoryRecommendationReviewerAssignmentPolicySource,
    MemoryRecommendationReviewerAssignmentRepository,
)
from atlas.modules.recommendations.adapters.reviewer_assignment_postgres import (
    PostgreSQLRecommendationReviewerAssignmentRepository,
)
from atlas.modules.recommendations.adapters.reviewer_assignment_synthetic import (
    SyntheticTrustedRecommendationReviewerAssignmentAdapter,
    UnavailableTrustedRecommendationReviewerAssignmentAdapter,
)
from atlas.modules.recommendations.application.reviewer_assignment import (
    GovernedRecommendationReviewerAssignmentService,
    build_development_recommendation_reviewer_assignment_policy,
)
from atlas.modules.recommendations.application.reviewer_assignment_ports import (
    RecommendationReviewerAssignmentError,
)
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestResult
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentPolicySnapshot,
    RecommendationReviewerAssignmentResult,
)


class RecordingReviewerAssignmentPermissionAuthorizer:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.calls: list[tuple[str, str, str]] = []

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        permission_id: str,
        correlation_id: str,
    ) -> None:
        del actor, correlation_id
        self.calls.append((organization_id, environment_id, permission_id))
        if self.deny:
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_permission_denied"
            )


class TamperingReviewerAssignmentAdapter(SyntheticTrustedRecommendationReviewerAssignmentAdapter):
    def __init__(self, field: str) -> None:
        self._field = field

    async def assign(self, instruction, source):  # type: ignore[no-untyped-def]
        receipt = await super().assign(instruction, source)
        if self._field == "routing_digest":
            receipt = replace(receipt, routing_digest="e" * 64)
        elif self._field == "review_request_digest":
            receipt = replace(receipt, review_request_digest="e" * 64)
        else:
            first, second = receipt.track_assignments
            first = (
                first[0],
                first[1],
                first[2],
                instruction.exclusion_subject_digests[0],
                first[4],
            )
            assignments = (first, second)
            reviewers = tuple(item[3] for item in assignments)
            receipt = replace(
                receipt,
                track_assignments=assignments,
                separation_digest=GovernedProtectedModelInvocationService._digest(
                    [
                        instruction.separation_profile_digest,
                        instruction.exclusion_subject_digests,
                        reviewers,
                    ]
                ),
            )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(
            receipt,
            canonical_digest=GovernedProtectedModelInvocationService._digest(payload),
        )


async def assignment_fixture(
    *,
    deny: bool = False,
    unavailable: bool = False,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    GovernedRecommendationReviewerAssignmentService,
    MemoryRecommendationReviewerAssignmentRepository,
    RecommendationReviewerAssignmentPolicySnapshot,
    RecommendationReviewRequestResult,
    AuthenticatedSubject,
    RecordingReviewerAssignmentPermissionAuthorizer,
]:
    review_service, _, review_policy, readiness, actor, _ = await review_request_fixture()
    review_request = await create_review_request(review_service, review_policy, readiness, actor)
    policy = build_development_recommendation_reviewer_assignment_policy(
        organization_id=review_request.record.organization_id,
        environment_id=review_request.record.environment_id,
        issued_at=review_request.record.requested_at - timedelta(hours=1),
        expires_at=review_request.record.requested_at + timedelta(days=1),
    )
    policy = replace(
        policy,
        required_assurance_level=required_assurance_level,
        canonical_digest="0" * 64,
    )
    policy = replace(
        policy,
        canonical_digest=GovernedProtectedModelInvocationService._digest(
            GovernedProtectedModelInvocationService._payload(policy)
        ),
    )
    permission = RecordingReviewerAssignmentPermissionAuthorizer(deny=deny)
    repository = MemoryRecommendationReviewerAssignmentRepository()
    adapter = (
        UnavailableTrustedRecommendationReviewerAssignmentAdapter()
        if unavailable
        else SyntheticTrustedRecommendationReviewerAssignmentAdapter()
    )
    service = GovernedRecommendationReviewerAssignmentService(
        repository=repository,
        review_request_source=review_service,
        policy_source=InMemoryRecommendationReviewerAssignmentPolicySource((policy,)),
        permission_authorizer=permission,
        adapter=adapter,
        audit_sink=review_service._audit_sink,
        environment_id=review_request.record.environment_id,
        clock=lambda: review_request.record.requested_at,
    )
    return service, repository, policy, review_request, actor, permission


async def create_assignment(
    service: GovernedRecommendationReviewerAssignmentService,
    policy: RecommendationReviewerAssignmentPolicySnapshot,
    review_request: RecommendationReviewRequestResult,
    actor: AuthenticatedSubject,
) -> RecommendationReviewerAssignmentResult:
    record = review_request.record
    return await service.create(
        actor=actor,
        recommendation_id=record.recommendation_id,
        review_request_id=record.review_request_id,
        review_request_digest=record.canonical_digest,
        assignment_policy_id=policy.policy_id,
        assignment_policy_digest=policy.canonical_digest,
        purpose=record.purpose,
        caller_cannot_select_reviewers_acknowledged=True,
        distinct_reviewers_required_acknowledged=True,
        no_inspection_decision_or_authority_acknowledged=True,
        browser_session_id=BROWSER_SESSION_ID,
        idempotency_key="recommendation-reviewer-assignment-001",
        correlation_id="cor_recommendation_reviewer_assignment",
    )


@pytest.mark.asyncio
async def test_assignment_creates_distinct_policy_owned_reviewers_and_exact_replay() -> None:
    service, _, policy, source, actor, permission = await assignment_fixture()
    result = await create_assignment(service, policy, source, actor)
    repeated = await create_assignment(service, policy, source, actor)
    replay = await service.get(
        actor=actor,
        assignment_set_id=result.record.assignment_set_id,
        browser_session_id=BROWSER_SESSION_ID,
        correlation_id="cor_recommendation_reviewer_assignment_read",
    )

    assignments = result.record.track_assignments
    assert tuple(item[0] for item in assignments) == policy.track_codes
    assert tuple(item[1] for item in assignments) == policy.queue_ids
    assert len({item[3] for item in assignments}) == 2
    assert all(item[4] == "assigned" for item in assignments)
    assert result.record.state == "reviewers_assigned"
    assert result.record.reviewer_assigned
    assert not result.record.content_inspection_opened
    assert not result.record.human_review_completed
    assert not result.record.recommendation_approved
    assert not result.record.workflow_created
    assert not result.record.itsm_record_created
    assert not result.record.execution_authorized
    assert not result.record.deployment_authorized
    assert not result.record.infrastructure_mutated
    assert repeated.record.reused and replay.record.reused
    assert permission.calls[0][2] == RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE
    assert permission.calls[-1][2] == RECOMMENDATION_REVIEWER_ASSIGNMENT_READ


@pytest.mark.asyncio
async def test_default_policy_allows_development_authentication() -> None:
    service, _, policy, source, actor, _ = await assignment_fixture()
    actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    result = await create_assignment(service, policy, source, actor)

    assert result.record.reviewer_assigned
    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR


@pytest.mark.asyncio
async def test_explicit_stronger_policy_rejects_development_authentication() -> None:
    service, _, policy, source, actor, _ = await assignment_fixture(
        required_assurance_level=AssuranceLevel.MULTI_FACTOR
    )
    actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(RecommendationReviewerAssignmentError, match="policy_assurance_required"):
        await create_assignment(service, policy, source, actor)


@pytest.mark.asyncio
async def test_assignment_response_exposes_only_salted_opaque_reviewer_metadata() -> None:
    service, _, policy, source, actor, _ = await assignment_fixture()
    result = await create_assignment(service, policy, source, actor)
    response = RecommendationReviewerAssignmentResultData.from_domain(result).model_dump()
    serialized = str(response).lower()
    for private in (
        "claim_id",
        "requester_subject_digest",
        "browser_session_binding_digest",
        "assignment_policy_digest",
        "assignment_receipt_digest",
        "source_review_request_digest",
        "source_binding_digest",
        "routing_digest",
        "eligibility_digest",
        "separation_digest",
        "artifact_digest",
        "directory_source",
        "attested_by",
        "tool_call",
        "<script",
    ):
        assert private not in serialized
    assert response["assignment"]["state"] == "reviewers_assigned"
    assert response["assignment"]["execution_authorized"] is False


@pytest.mark.asyncio
async def test_postgres_assignment_round_trip_preserves_record() -> None:
    service, _, policy, source, actor, _ = await assignment_fixture()
    result = await create_assignment(service, policy, source, actor)
    payload = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(payload, dict)
    restored = PostgreSQLRecommendationReviewerAssignmentRepository._record_to_domain(payload)
    assert restored == result.record


@pytest.mark.asyncio
async def test_permission_denial_happens_before_assignment_claim() -> None:
    service, repository, policy, source, actor, permission = await assignment_fixture(deny=True)
    with pytest.raises(RecommendationReviewerAssignmentError, match="permission_denied"):
        await create_assignment(service, policy, source, actor)
    assert permission.calls
    assert not repository._claims
    assert not repository._records


@pytest.mark.asyncio
async def test_unavailable_assignment_adapter_fails_closed_after_claim() -> None:
    service, repository, policy, source, actor, _ = await assignment_fixture(unavailable=True)
    with pytest.raises(RecommendationReviewerAssignmentError, match="adapter_unavailable"):
        await create_assignment(service, policy, source, actor)
    assert repository._claims
    assert not repository._records


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tampered_field",
    ("routing_digest", "review_request_digest", "excluded_reviewer"),
)
async def test_assignment_rejects_receipt_tampering(tampered_field: str) -> None:
    service, repository, policy, source, actor, _ = await assignment_fixture()
    service._adapter = TamperingReviewerAssignmentAdapter(tampered_field)
    with pytest.raises(RecommendationReviewerAssignmentError, match="receipt_invalid"):
        await create_assignment(service, policy, source, actor)
    assert repository._claims
    assert not repository._records


@pytest.mark.asyncio
async def test_exact_replay_rejects_tampered_assignment_claim() -> None:
    service, repository, policy, source, actor, _ = await assignment_fixture()
    await create_assignment(service, policy, source, actor)
    claim_id, claim = next(iter(repository._claims.items()))
    repository._claims[claim_id] = replace(claim, review_request_digest="e" * 64)
    with pytest.raises(RecommendationReviewerAssignmentError, match="integrity_failed"):
        await create_assignment(service, policy, source, actor)


@pytest.mark.asyncio
async def test_assignment_rejects_source_older_than_signed_policy_limit() -> None:
    service, _, policy, source, _, _ = await assignment_fixture()
    with pytest.raises(RecommendationReviewerAssignmentError, match="source_invalid"):
        service._verify_source(
            source,
            policy,
            source.record.recommendation_id,
            source.record.canonical_digest,
            source.record.purpose,
            source.record.requested_at + timedelta(minutes=policy.maximum_source_age_minutes + 1),
        )


@pytest.mark.asyncio
async def test_mismatched_recommendation_path_is_rejected_before_claim() -> None:
    service, repository, policy, source, actor, permission = await assignment_fixture()
    record = source.record
    with pytest.raises(RecommendationReviewerAssignmentError, match="source_invalid"):
        await service.create(
            actor=actor,
            recommendation_id="recommendation.promoted.other",
            review_request_id=record.review_request_id,
            review_request_digest=record.canonical_digest,
            assignment_policy_id=policy.policy_id,
            assignment_policy_digest=policy.canonical_digest,
            purpose=record.purpose,
            caller_cannot_select_reviewers_acknowledged=True,
            distinct_reviewers_required_acknowledged=True,
            no_inspection_decision_or_authority_acknowledged=True,
            browser_session_id=BROWSER_SESSION_ID,
            idempotency_key="recommendation-reviewer-assignment-wrong-path",
            correlation_id="cor_recommendation_reviewer_assignment_wrong_path",
        )
    assert permission.calls
    assert not repository._claims
    assert not repository._records


def test_input_forbids_caller_selected_reviewer_routing_or_authority() -> None:
    payload = {
        "review_request_id": "recommendation-review-request.example",
        "review_request_digest": "a" * 64,
        "assignment_policy_id": "recommendation-reviewer-assignment-policy.development",
        "assignment_policy_digest": "b" * 64,
        "purpose": "Assign accountable enterprise reviewers without opening content.",
        "acknowledged_caller_cannot_select_reviewers": True,
        "acknowledged_distinct_reviewers_required": True,
        "acknowledged_no_inspection_decision_or_operational_authority": True,
        "reviewer_id": "subject.caller-selected-reviewer",
        "track_code": "review-track.caller-selected",
        "queue_id": "review-queue.caller-selected",
        "directory_query": "engineering-admins",
        "decision": "approved",
        "command": "restart-controller",
    }
    with pytest.raises(ValidationError):
        RecommendationReviewerAssignmentInput.model_validate(payload)


def test_openapi_registers_recommendation_reviewer_assignment_routes() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/recommendations/{recommendation_id}/reviewer-assignments" in paths
    assert (
        "/api/v1/recommendations/{recommendation_id}/reviewer-assignments/"
        "{assignment_set_id}" in paths
    )
