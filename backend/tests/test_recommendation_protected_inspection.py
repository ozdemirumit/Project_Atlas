from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_recommendation_reviewer_assignment import assignment_fixture, create_assignment
from test_target_session import development_target_session_operator

from atlas.api.app import create_app
from atlas.api.recommendation_protected_inspection_schemas import (
    RecommendationProtectedInspectionData,
    RecommendationProtectedInspectionInput,
)
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
    recommendation_protected_inspection_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    PermissionDefinition,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject
from atlas.modules.recommendations.adapters.protected_inspection_memory import (
    InMemoryRecommendationProtectedInspectionPolicySource,
    InMemoryRecommendationProtectedInspectionRepository,
)
from atlas.modules.recommendations.adapters.protected_inspection_postgres import (
    PostgreSQLRecommendationProtectedInspectionRepository,
)
from atlas.modules.recommendations.adapters.protected_inspection_synthetic import (
    SyntheticRecommendationProtectedInspectionBroker,
    UnavailableRecommendationProtectedInspectionBroker,
)
from atlas.modules.recommendations.application.protected_inspection import (
    RecommendationProtectedInspectionService,
    build_development_recommendation_protected_inspection_policy,
)
from atlas.modules.recommendations.application.protected_inspection_ports import (
    RecommendationProtectedInspectionError,
)
from atlas.modules.recommendations.domain.protected_inspection import (
    RecommendationProtectedInspectionGrant,
    RecommendationProtectedInspectionPolicySnapshot,
)
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentRecord,
)


class RecordingPermissionAuthorizer:
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
            raise RecommendationProtectedInspectionError(
                "recommendation_protected_inspection_permission_denied"
            )


async def inspection_fixture(
    *, deny: bool = False, unavailable: bool = False
) -> tuple[
    RecommendationProtectedInspectionService,
    InMemoryRecommendationProtectedInspectionRepository,
    RecommendationReviewerAssignmentRecord,
    RecommendationProtectedInspectionPolicySnapshot,
    AuthenticatedSubject,
    RecordingPermissionAuthorizer,
    SyntheticRecommendationProtectedInspectionBroker
    | UnavailableRecommendationProtectedInspectionBroker,
]:
    assignment_service, _, assignment_policy, request, requester, _ = await assignment_fixture()
    assignment = (
        await create_assignment(assignment_service, assignment_policy, request, requester)
    ).record
    policy = build_development_recommendation_protected_inspection_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.assigned_at - timedelta(minutes=1),
        expires_at=assignment.assigned_at + timedelta(days=1),
    )
    actor = replace(
        development_target_session_operator("subject.synthetic-technical-reviewer"),
        organization_id=assignment.organization_id,
        authenticated_at=assignment.assigned_at,
    )
    permission = RecordingPermissionAuthorizer(deny=deny)
    repository = InMemoryRecommendationProtectedInspectionRepository()
    broker: (
        SyntheticRecommendationProtectedInspectionBroker
        | UnavailableRecommendationProtectedInspectionBroker
    )
    broker = (
        UnavailableRecommendationProtectedInspectionBroker()
        if unavailable
        else SyntheticRecommendationProtectedInspectionBroker(clock=lambda: assignment.assigned_at)
    )
    service = RecommendationProtectedInspectionService(
        repository=repository,
        source=assignment_service,
        policy_source=InMemoryRecommendationProtectedInspectionPolicySource((policy,)),
        permission_authorizer=permission,
        broker=broker,
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    return service, repository, assignment, policy, actor, permission, broker


async def create_lease(
    service: RecommendationProtectedInspectionService,
    assignment: RecommendationReviewerAssignmentRecord,
    policy: RecommendationProtectedInspectionPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    track_index: int = 0,
    key: str = "recommendation-protected-inspection-001",
) -> RecommendationProtectedInspectionGrant:
    track, _queue, assignment_id, _reviewer, _status = assignment.track_assignments[track_index]
    return await service.create(
        actor=actor,
        recommendation_id=assignment.recommendation_id,
        source_assignment_set_id=assignment.assignment_set_id,
        source_assignment_set_digest=assignment.canonical_digest,
        track_code=track,
        opaque_assignment_id=assignment_id,
        inspection_policy_id=policy.policy_id,
        inspection_policy_digest=policy.canonical_digest,
        purpose="Open one assigned recommendation review track without returning content.",
        lease_only_acknowledged=True,
        browser_session_id="session_recommendation_inspection_001",
        idempotency_key=key,
        correlation_id="cor_recommendation_protected_inspection",
    )


@pytest.mark.asyncio
async def test_exact_assignee_receives_cookie_only_grant_and_replay_has_no_secret() -> None:
    service, _, assignment, policy, actor, permission, broker = await inspection_fixture()
    first = await create_lease(service, assignment, policy, actor)
    repeated = await create_lease(service, assignment, policy, actor)

    assert actor.assurance_level is AssuranceLevel.DEVELOPMENT
    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert first.lease_secret is not None
    assert repeated.lease_secret is None and repeated.record.reused
    assert first.record.content_inspection_opened
    assert not first.record.content_disclosed
    assert first.record.protected_content_bytes_returned == 0
    assert not first.record.human_review_completed
    assert not first.record.recommendation_approved
    assert not first.record.workflow_created
    assert not first.record.itsm_record_created
    assert not first.record.execution_authorized
    assert not first.record.deployment_authorized
    assert not first.record.infrastructure_mutated
    assert permission.calls
    assert getattr(broker, "call_count", 0) == 1


@pytest.mark.asyncio
async def test_explicit_stronger_assurance_policy_denies_development_session() -> None:
    service, repository, assignment, policy, actor, _, broker = await inspection_fixture()
    stronger_policy = replace(
        policy,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        canonical_digest="0" * 64,
    )
    payload = asdict(stronger_policy)
    payload.pop("canonical_digest")
    stronger_policy = replace(
        stronger_policy,
        canonical_digest=service._digest(service._normalize(payload)),
    )
    service._policy_source = InMemoryRecommendationProtectedInspectionPolicySource(
        (stronger_policy,)
    )

    with pytest.raises(RecommendationProtectedInspectionError, match="assurance_required"):
        await create_lease(service, assignment, stronger_policy, actor)

    assert not repository._claims_by_idempotency
    assert getattr(broker, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_cross_track_and_wrong_path_fail_before_claim() -> None:
    service, repository, assignment, policy, actor, _, _ = await inspection_fixture()
    with pytest.raises(RecommendationProtectedInspectionError, match="source_not_found"):
        await create_lease(service, assignment, policy, actor, track_index=1)
    assert not repository._claims_by_source_track

    track, _queue, assignment_id, _reviewer, _status = assignment.track_assignments[0]
    with pytest.raises(RecommendationProtectedInspectionError, match="source_not_found"):
        await service.create(
            actor=actor,
            recommendation_id="recommendation.other",
            source_assignment_set_id=assignment.assignment_set_id,
            source_assignment_set_digest=assignment.canonical_digest,
            track_code=track,
            opaque_assignment_id=assignment_id,
            inspection_policy_id=policy.policy_id,
            inspection_policy_digest=policy.canonical_digest,
            purpose="Reject a mismatched recommendation path before creating a claim.",
            lease_only_acknowledged=True,
            browser_session_id="session_recommendation_inspection_001",
            idempotency_key="recommendation-protected-inspection-wrong-path",
            correlation_id="cor_recommendation_protected_inspection_wrong_path",
        )
    assert not repository._claims_by_source_track


@pytest.mark.asyncio
async def test_permission_denial_precedes_claim_and_broker_unavailable_is_claimed() -> None:
    service, repository, assignment, policy, actor, _, _ = await inspection_fixture(deny=True)
    with pytest.raises(RecommendationProtectedInspectionError, match="permission_denied"):
        await create_lease(service, assignment, policy, actor)
    assert not repository._claims_by_source_track

    service, repository, assignment, policy, actor, _, _ = await inspection_fixture(
        unavailable=True
    )
    with pytest.raises(RecommendationProtectedInspectionError, match="broker_unavailable"):
        await create_lease(service, assignment, policy, actor)
    assert repository._claims_by_source_track and not repository._records


@pytest.mark.asyncio
async def test_expired_source_and_future_authentication_fail_closed() -> None:
    service, repository, assignment, policy, actor, _, _ = await inspection_fixture()
    service._clock = lambda: assignment.expires_at
    with pytest.raises(RecommendationProtectedInspectionError, match="source_invalid"):
        await create_lease(service, assignment, policy, actor)
    assert not repository._claims_by_source_track

    service._clock = lambda: assignment.assigned_at
    actor = replace(actor, authenticated_at=assignment.assigned_at + timedelta(seconds=1))
    with pytest.raises(RecommendationProtectedInspectionError, match="authentication_invalid"):
        await create_lease(service, assignment, policy, actor)
    assert not repository._claims_by_source_track


@pytest.mark.asyncio
async def test_postgres_round_trip_and_response_redaction() -> None:
    service, repository, assignment, policy, actor, _, _ = await inspection_fixture()
    grant = await create_lease(service, assignment, policy, actor)
    payload = service._normalize(asdict(grant.record))
    assert isinstance(payload, dict)
    restored = PostgreSQLRecommendationProtectedInspectionRepository._record_to_domain(payload)
    assert restored == grant.record
    claim = next(iter(repository._claims_by_source_track.values()))
    claim_payload = service._normalize(asdict(claim))
    assert isinstance(claim_payload, dict)
    assert (
        PostgreSQLRecommendationProtectedInspectionRepository._claim_to_domain(claim_payload)
        == claim
    )

    response = RecommendationProtectedInspectionData.from_domain(grant.record).model_dump()
    serialized = str(response).lower()
    for private in (
        "lease_secret",
        "browser_session_binding_digest",
        "claim_id",
        "request_binding_digest",
        "idempotency_digest",
    ):
        assert private not in serialized
    assert response["content_disclosed"] is False
    assert response["protected_content_bytes_returned"] == 0


def test_input_forbids_identity_secret_duration_content_and_authority_controls() -> None:
    payload = {
        "source_assignment_set_id": "recommendation-review-assignment-set.example",
        "source_assignment_set_digest": "a" * 64,
        "track_code": "review-track.technical",
        "opaque_assignment_id": "recommendation-review-assignment.0.example",
        "inspection_policy_id": "recommendation-protected-inspection-policy.example",
        "inspection_policy_digest": "b" * 64,
        "purpose": "Open the exact assigned review track without returning content.",
        "acknowledged_exact_assignee_and_track_required": True,
        "acknowledged_lease_returns_no_content_or_secret_in_json": True,
        "acknowledged_no_decision_approval_or_operational_authority": True,
    }
    RecommendationProtectedInspectionInput.model_validate(payload)
    for forbidden in (
        "reviewer_identity",
        "lease_ttl_minutes",
        "lease_secret",
        "content",
        "decision",
        "approved",
        "command",
    ):
        with pytest.raises(ValidationError):
            RecommendationProtectedInspectionInput.model_validate(
                {**payload, forbidden: "caller-controlled"}
            )


@pytest.mark.asyncio
async def test_http_boundary_places_secret_only_in_strict_httponly_cookie() -> None:
    service, _, assignment, policy, actor, _, _ = await inspection_fixture()
    track, _queue, assignment_id, _reviewer, _status = assignment.track_assignments[0]
    audit = CollectingAuditSink()
    authorization = AuthorizationService(
        permissions=(
            PermissionDefinition(
                permission_id=RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
                description="Open exact assigned recommendation inspection lease.",
            ),
        ),
        roles=(
            RoleDefinition(
                role_id=actor.role_ids[0],
                version=1,
                permissions=frozenset({RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE}),
            ),
        ),
        assignments=(
            RoleAssignment(
                assignment_id="assignment.recommendation-inspection-test",
                version=1,
                subject_id=actor.subject_id,
                role_id=actor.role_ids[0],
                scope=recommendation_protected_inspection_scope(
                    assignment.organization_id,
                    "test",
                    CapabilityClass.C2_DIAGNOSTIC,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
        ),
        audit_sink=audit,
    )
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(actor),
            authorization_service=authorization,
            recommendation_protected_inspection_service=service,
        )
    ) as client:
        login_response = login(client)
        assert login_response.status_code == 201
        csrf = client.cookies.get("atlas_csrf")
        response = client.post(
            f"/api/v1/recommendations/{assignment.recommendation_id}/protected-inspections/leases",
            headers={
                "Idempotency-Key": "recommendation-protected-inspection-http-001",
                "X-CSRF-Token": str(csrf),
            },
            json={
                "source_assignment_set_id": assignment.assignment_set_id,
                "source_assignment_set_digest": assignment.canonical_digest,
                "track_code": track,
                "opaque_assignment_id": assignment_id,
                "inspection_policy_id": policy.policy_id,
                "inspection_policy_digest": policy.canonical_digest,
                "purpose": "Open one assigned recommendation track through the HTTP boundary.",
                "acknowledged_exact_assignee_and_track_required": True,
                "acknowledged_lease_returns_no_content_or_secret_in_json": True,
                "acknowledged_no_decision_approval_or_operational_authority": True,
            },
        )
    assert response.status_code == 201
    cookie = response.headers["set-cookie"].lower()
    assert "atlas_recommendation_inspection_technical=" in cookie
    assert "httponly" in cookie and "samesite=strict" in cookie and "secure" in cookie
    assert "/api/v1/recommendations/" in cookie
    serialized = response.text.lower()
    assert "lease_secret" not in serialized
    assert "browser_session_binding_digest" not in serialized
    assert response.json()["data"]["protected_content_bytes_returned"] == 0


def test_openapi_registers_recommendation_protected_inspection_routes() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    base = "/api/v1/recommendations/{recommendation_id}/protected-inspections/leases"
    assert base in paths
    assert f"{base}/{{lease_id}}" in paths
