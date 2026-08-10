from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_recommendation_protected_inspection import inspection_fixture

from atlas.api.app import create_app
from atlas.api.recommendation_protected_content_schemas import (
    RecommendationProtectedContentData,
    RecommendationProtectedContentInput,
)
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
    recommendation_protected_content_scope,
    recommendation_protected_inspection_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    PermissionDefinition,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.adapters.protected_content_memory import (
    InMemoryRecommendationProtectedContentPolicySource,
    InMemoryRecommendationProtectedContentRepository,
)
from atlas.modules.recommendations.adapters.protected_content_postgres import (
    PostgreSQLRecommendationProtectedContentRepository,
)
from atlas.modules.recommendations.adapters.protected_content_synthetic import (
    SyntheticRecommendationProtectedContentPresenter,
    UnavailableRecommendationProtectedContentPresenter,
)
from atlas.modules.recommendations.application.protected_content import (
    RecommendationProtectedContentService,
    build_development_recommendation_protected_content_policy,
)
from atlas.modules.recommendations.application.protected_content_ports import (
    RecommendationProtectedContentError,
)
from atlas.modules.recommendations.application.protected_inspection import (
    RecommendationProtectedInspectionService,
)
from atlas.modules.recommendations.domain.protected_content import (
    RecommendationProtectedContentGrant,
    RecommendationProtectedContentInstruction,
    RecommendationProtectedContentPolicySnapshot,
    RecommendationProtectedContentPresenterGrant,
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
            raise RecommendationProtectedContentError(
                "recommendation_protected_content_permission_denied"
            )


class DriftingRecommendationProtectedContentPresenter(
    SyntheticRecommendationProtectedContentPresenter
):
    async def present(
        self, instruction: RecommendationProtectedContentInstruction
    ) -> RecommendationProtectedContentPresenterGrant:
        return await super().present(
            replace(instruction, headline=f"{instruction.headline} replay drift")
        )


async def content_fixture(
    *, deny: bool = False, unavailable: bool = False
) -> tuple[
    RecommendationProtectedContentService,
    InMemoryRecommendationProtectedContentRepository,
    RecommendationProtectedInspectionService,
    RecommendationReviewerAssignmentRecord,
    RecommendationProtectedInspectionPolicySnapshot,
    RecommendationProtectedInspectionGrant,
    RecommendationProtectedContentPolicySnapshot,
    AuthenticatedSubject,
]:
    inspection, _, assignment, inspection_policy, actor, _, _ = await inspection_fixture()
    track, _queue, assignment_id, _reviewer, _status = assignment.track_assignments[0]
    lease = await inspection.create(
        actor=actor,
        recommendation_id=assignment.recommendation_id,
        source_assignment_set_id=assignment.assignment_set_id,
        source_assignment_set_digest=assignment.canonical_digest,
        track_code=track,
        opaque_assignment_id=assignment_id,
        inspection_policy_id=inspection_policy.policy_id,
        inspection_policy_digest=inspection_policy.canonical_digest,
        purpose="Open one assigned recommendation track before protected content presentation.",
        lease_only_acknowledged=True,
        browser_session_id="session_recommendation_inspection_001",
        idempotency_key="recommendation-content-source-lease-001",
        correlation_id="cor_recommendation_content_source_lease",
    )
    policy = build_development_recommendation_protected_content_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.assigned_at - timedelta(minutes=1),
        expires_at=assignment.assigned_at + timedelta(days=1),
    )
    repository = InMemoryRecommendationProtectedContentRepository()
    presenter = (
        UnavailableRecommendationProtectedContentPresenter()
        if unavailable
        else SyntheticRecommendationProtectedContentPresenter(clock=lambda: assignment.assigned_at)
    )
    service = RecommendationProtectedContentService(
        repository=repository,
        source=inspection,
        policy_source=InMemoryRecommendationProtectedContentPolicySource((policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(deny=deny),
        presenter=presenter,
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    return (
        service,
        repository,
        inspection,
        assignment,
        inspection_policy,
        lease,
        policy,
        actor,
    )


async def create_content(
    service: RecommendationProtectedContentService,
    assignment: RecommendationReviewerAssignmentRecord,
    lease: RecommendationProtectedInspectionGrant,
    policy: RecommendationProtectedContentPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    secret: str | None = None,
    recommendation_id: str | None = None,
    key: str = "recommendation-protected-content-001",
) -> RecommendationProtectedContentGrant:
    return await service.create(
        actor=actor,
        recommendation_id=recommendation_id or assignment.recommendation_id,
        source_lease_id=lease.record.lease_id,
        source_lease_digest=lease.record.canonical_digest,
        presentation_policy_id=policy.policy_id,
        presentation_policy_digest=policy.canonical_digest,
        purpose="Inspect the exact redacted recommendation snapshot as assigned reviewer.",
        sensitive_read_only_acknowledged=True,
        browser_session_id="session_recommendation_inspection_001",
        lease_secrets={lease.record.track_code: secret or str(lease.lease_secret)},
        idempotency_key=key,
        correlation_id="cor_recommendation_protected_content",
    )


@pytest.mark.asyncio
async def test_exact_assignee_receives_bounded_content_and_exact_replay() -> None:
    service, repository, _, assignment, _, lease, policy, actor = await content_fixture()
    first = await create_content(service, assignment, lease, policy, actor)
    repeated = await create_content(service, assignment, lease, policy, actor)

    assert "Recommendation review snapshot" in first.content
    assert first.record.content_disclosed
    assert first.record.protected_content_bytes_returned == len(first.content.encode("utf-8"))
    assert repeated.record.reused and repeated.content == first.content
    assert not first.record.human_findings_recorded
    assert not first.record.human_review_completed
    assert not first.record.recommendation_approved
    assert not first.record.workflow_created
    assert not first.record.itsm_record_created
    assert not first.record.execution_authorized
    assert not first.record.deployment_authorized
    assert not first.record.infrastructure_mutated
    assert "content" not in asdict(next(iter(repository._records.values())))


@pytest.mark.asyncio
async def test_replay_drift_and_audit_plaintext_fail_closed() -> None:
    service, _, _, assignment, _, lease, policy, actor = await content_fixture()
    audit = CollectingAuditSink()
    service._audit_sink = audit
    first = await create_content(service, assignment, lease, policy, actor)
    assert "Recommendation review snapshot" in first.content
    assert "Recommendation review snapshot" not in str([asdict(record) for record in audit.records])

    service._presenter = DriftingRecommendationProtectedContentPresenter(
        clock=lambda: assignment.assigned_at
    )
    with pytest.raises(RecommendationProtectedContentError, match="replay_drift"):
        await service.get(
            actor=actor,
            recommendation_id=assignment.recommendation_id,
            source_lease_id=lease.record.lease_id,
            presentation_id=first.record.presentation_id,
            browser_session_id="session_recommendation_inspection_001",
            lease_secrets={lease.record.track_code: str(lease.lease_secret)},
            correlation_id="cor_recommendation_protected_content_drift",
        )


@pytest.mark.asyncio
async def test_required_intent_audit_failure_prevents_claim_and_presentation() -> None:
    service, repository, _, assignment, _, lease, policy, actor = await content_fixture()
    presenter = SyntheticRecommendationProtectedContentPresenter(
        clock=lambda: assignment.assigned_at
    )
    service._presenter = presenter
    service._audit_sink = FailingAuditSink()

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await create_content(service, assignment, lease, policy, actor)
    assert not repository._claims_by_lease
    assert not repository._records
    assert not presenter.calls


@pytest.mark.asyncio
async def test_wrong_path_and_cookie_fail_before_claim() -> None:
    service, repository, _, assignment, _, lease, policy, actor = await content_fixture()
    with pytest.raises(RecommendationProtectedContentError, match="source_invalid"):
        await create_content(
            service,
            assignment,
            lease,
            policy,
            actor,
            recommendation_id="recommendation.other",
        )
    assert not repository._claims_by_lease

    with pytest.raises(RecommendationProtectedContentError, match="source_not_found"):
        await create_content(service, assignment, lease, policy, actor, secret="wrong-secret")
    assert not repository._claims_by_lease


@pytest.mark.asyncio
async def test_denied_or_unavailable_presenter_fails_closed() -> None:
    service, repository, _, assignment, _, lease, policy, actor = await content_fixture(deny=True)
    with pytest.raises(RecommendationProtectedContentError, match="permission_denied"):
        await create_content(service, assignment, lease, policy, actor)
    assert not repository._claims_by_lease

    service, repository, _, assignment, _, lease, policy, actor = await content_fixture(
        unavailable=True
    )
    with pytest.raises(RecommendationProtectedContentError, match="presenter_unavailable"):
        await create_content(service, assignment, lease, policy, actor)
    assert repository._claims_by_lease and not repository._records


@pytest.mark.asyncio
async def test_expiry_future_auth_and_cross_track_cookie_fail_closed() -> None:
    service, repository, _, assignment, _, lease, policy, actor = await content_fixture()
    service._clock = lambda: lease.record.expires_at
    with pytest.raises(RecommendationProtectedContentError, match="source_invalid"):
        await create_content(service, assignment, lease, policy, actor)
    assert not repository._claims_by_lease

    service._clock = lambda: assignment.assigned_at
    actor = replace(actor, authenticated_at=assignment.assigned_at + timedelta(seconds=1))
    with pytest.raises(RecommendationProtectedContentError, match="source_invalid"):
        await create_content(service, assignment, lease, policy, actor)
    assert not repository._claims_by_lease

    actor = replace(actor, authenticated_at=assignment.assigned_at)
    with pytest.raises(RecommendationProtectedContentError, match="source_not_found"):
        await service.create(
            actor=actor,
            recommendation_id=assignment.recommendation_id,
            source_lease_id=lease.record.lease_id,
            source_lease_digest=lease.record.canonical_digest,
            presentation_policy_id=policy.policy_id,
            presentation_policy_digest=policy.canonical_digest,
            purpose="Reject a cookie supplied for a different recommendation review track.",
            sensitive_read_only_acknowledged=True,
            browser_session_id="session_recommendation_inspection_001",
            lease_secrets={"review-track.service-impact": str(lease.lease_secret)},
            idempotency_key="recommendation-protected-content-cross-track",
            correlation_id="cor_recommendation_content_cross_track",
        )
    assert not repository._claims_by_lease


@pytest.mark.asyncio
async def test_postgres_round_trip_and_api_schema_exclude_private_bindings() -> None:
    service, repository, _, assignment, _, lease, policy, actor = await content_fixture()
    grant = await create_content(service, assignment, lease, policy, actor)
    payload = service._normalize(asdict(grant.record))
    assert isinstance(payload, dict)
    restored = PostgreSQLRecommendationProtectedContentRepository._record_to_domain(payload)
    assert restored == grant.record
    claim = next(iter(repository._claims_by_lease.values()))
    claim_payload = service._normalize(asdict(claim))
    assert isinstance(claim_payload, dict)
    assert (
        PostgreSQLRecommendationProtectedContentRepository._claim_to_domain(claim_payload) == claim
    )

    response = RecommendationProtectedContentData.from_grant(grant).model_dump()
    serialized = str(response).lower()
    for private in (
        "lease_secret",
        "lease_holder_subject_digest",
        "browser_session_binding_digest",
        "claim_id",
        "request_binding_digest",
        "idempotency_digest",
    ):
        assert private not in serialized
    assert response["content"] == grant.content


def test_input_forbids_content_identity_track_redaction_and_authority_controls() -> None:
    payload = {
        "source_lease_digest": "a" * 64,
        "presentation_policy_id": "recommendation-protected-content-policy.example",
        "presentation_policy_digest": "b" * 64,
        "purpose": "Inspect one exact redacted recommendation snapshot as assigned reviewer.",
        "acknowledged_sensitive_read_only_content": True,
        "acknowledged_no_finding_decision_approval_or_operational_authority": True,
    }
    RecommendationProtectedContentInput.model_validate(payload)
    for forbidden in (
        "reviewer_identity",
        "track_code",
        "content",
        "options",
        "redaction_profile",
        "maximum_content_bytes",
        "decision",
        "approved",
        "command",
    ):
        with pytest.raises(ValidationError):
            RecommendationProtectedContentInput.model_validate(
                {**payload, forbidden: "caller-controlled"}
            )


def _authorization(
    actor: AuthenticatedSubject, assignment: RecommendationReviewerAssignmentRecord
) -> AuthorizationService:
    permissions = (
        RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
        RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
        RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
        RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
    )
    scopes = {
        permission: (
            recommendation_protected_content_scope(
                assignment.organization_id,
                "test",
                CapabilityClass.C2_DIAGNOSTIC
                if permission.endswith("create")
                else CapabilityClass.C1_READ_ONLY,
            )
            if "protected-content" in permission
            else recommendation_protected_inspection_scope(
                assignment.organization_id,
                "test",
                CapabilityClass.C2_DIAGNOSTIC
                if permission.endswith("create")
                else CapabilityClass.C1_READ_ONLY,
            )
        )
        for permission in permissions
    }
    return AuthorizationService(
        permissions=tuple(
            PermissionDefinition(permission_id=item, description=item) for item in permissions
        ),
        roles=(
            RoleDefinition(
                role_id=actor.role_ids[0], version=1, permissions=frozenset(permissions)
            ),
        ),
        assignments=tuple(
            RoleAssignment(
                assignment_id=f"assignment.recommendation-content-{index}",
                version=1,
                subject_id=actor.subject_id,
                role_id=actor.role_ids[0],
                scope=scopes[permission],
                valid_from=datetime.min.replace(tzinfo=UTC),
            )
            for index, permission in enumerate(permissions)
        ),
        audit_sink=CollectingAuditSink(),
    )


@pytest.mark.asyncio
async def test_http_flow_sets_no_store_and_returns_content_only_after_lease_cookie() -> None:
    inspection, _, assignment, inspection_policy, actor, _, _ = await inspection_fixture()
    policy = build_development_recommendation_protected_content_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.assigned_at - timedelta(minutes=1),
        expires_at=assignment.assigned_at + timedelta(days=1),
    )
    service = RecommendationProtectedContentService(
        repository=InMemoryRecommendationProtectedContentRepository(),
        source=inspection,
        policy_source=InMemoryRecommendationProtectedContentPolicySource((policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(),
        presenter=SyntheticRecommendationProtectedContentPresenter(
            clock=lambda: assignment.assigned_at
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    track, _queue, assignment_id, _reviewer, _status = assignment.track_assignments[0]
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(actor),
            authorization_service=_authorization(actor, assignment),
            recommendation_protected_inspection_service=inspection,
            recommendation_protected_content_service=service,
        ),
        base_url="https://testserver",
    ) as client:
        assert login(client).status_code == 201
        csrf = str(client.cookies.get("atlas_csrf"))
        lease_response = client.post(
            f"/api/v1/recommendations/{assignment.recommendation_id}/protected-inspections/leases",
            headers={"Idempotency-Key": "recommendation-content-http-lease", "X-CSRF-Token": csrf},
            json={
                "source_assignment_set_id": assignment.assignment_set_id,
                "source_assignment_set_digest": assignment.canonical_digest,
                "track_code": track,
                "opaque_assignment_id": assignment_id,
                "inspection_policy_id": inspection_policy.policy_id,
                "inspection_policy_digest": inspection_policy.canonical_digest,
                "purpose": "Open one assigned recommendation track for HTTP content presentation.",
                "acknowledged_exact_assignee_and_track_required": True,
                "acknowledged_lease_returns_no_content_or_secret_in_json": True,
                "acknowledged_no_decision_approval_or_operational_authority": True,
            },
        )
        assert lease_response.status_code == 201
        lease_data = lease_response.json()["data"]
        response = client.post(
            (
                f"/api/v1/recommendations/{assignment.recommendation_id}/protected-inspections/"
                f"leases/{lease_data['lease_id']}/presentations"
            ),
            headers={
                "Idempotency-Key": "recommendation-content-http-present",
                "X-CSRF-Token": csrf,
            },
            json={
                "source_lease_digest": lease_data["canonical_digest"],
                "presentation_policy_id": policy.policy_id,
                "presentation_policy_digest": policy.canonical_digest,
                "purpose": "Present one exact redacted recommendation snapshot through HTTP.",
                "acknowledged_sensitive_read_only_content": True,
                "acknowledged_no_finding_decision_approval_or_operational_authority": True,
            },
        )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
    assert "Recommendation review snapshot" in response.json()["data"]["content"]
    assert response.json()["data"]["content_disclosed"] is True


def test_openapi_registers_recommendation_protected_content_routes() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    base = (
        "/api/v1/recommendations/{recommendation_id}/protected-inspections/"
        "leases/{lease_id}/presentations"
    )
    assert base in paths
    assert f"{base}/{{presentation_id}}" in paths
