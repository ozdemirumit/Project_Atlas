from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_recommendation_protected_content import content_fixture, create_content
from test_recommendation_protected_inspection import inspection_fixture

from atlas.api.app import create_app
from atlas.api.recommendation_human_review_finding_schemas import (
    RecommendationHumanReviewFindingData,
    RecommendationHumanReviewFindingInput,
)
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
    RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
    recommendation_human_review_finding_scope,
    recommendation_protected_content_scope,
    recommendation_protected_inspection_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    PermissionDefinition,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject
from atlas.modules.recommendations.adapters.human_review_finding_memory import (
    InMemoryRecommendationHumanReviewFindingPolicySource,
    InMemoryRecommendationHumanReviewFindingRepository,
)
from atlas.modules.recommendations.adapters.human_review_finding_postgres import (
    PostgreSQLRecommendationHumanReviewFindingRepository,
)
from atlas.modules.recommendations.adapters.human_review_finding_synthetic import (
    SyntheticRecommendationHumanReviewFindingRecorder,
    UnavailableRecommendationHumanReviewFindingRecorder,
)
from atlas.modules.recommendations.adapters.protected_content_memory import (
    InMemoryRecommendationProtectedContentPolicySource,
    InMemoryRecommendationProtectedContentRepository,
)
from atlas.modules.recommendations.adapters.protected_content_synthetic import (
    SyntheticRecommendationProtectedContentPresenter,
)
from atlas.modules.recommendations.application.human_review_finding import (
    RecommendationHumanReviewFindingService,
    build_development_recommendation_human_review_finding_policy,
)
from atlas.modules.recommendations.application.human_review_finding_ports import (
    RecommendationHumanReviewFindingError,
)
from atlas.modules.recommendations.application.protected_content import (
    RecommendationProtectedContentService,
    build_development_recommendation_protected_content_policy,
)
from atlas.modules.recommendations.domain.human_review_finding import (
    RecommendationHumanReviewFindingItem,
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
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_permission_denied"
            )


async def finding_fixture(*, deny: bool = False, unavailable: bool = False):  # type: ignore[no-untyped-def]
    content, _, _, assignment, _, lease, content_policy, actor = await content_fixture()
    presentation = await create_content(
        content,
        assignment,
        lease,
        content_policy,
        actor,
    )
    policy = build_development_recommendation_human_review_finding_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.assigned_at - timedelta(minutes=1),
        expires_at=assignment.assigned_at + timedelta(days=1),
    )
    repository = InMemoryRecommendationHumanReviewFindingRepository()
    recorder = (
        UnavailableRecommendationHumanReviewFindingRecorder()
        if unavailable
        else SyntheticRecommendationHumanReviewFindingRecorder(clock=lambda: assignment.assigned_at)
    )
    audit = CollectingAuditSink()
    service = RecommendationHumanReviewFindingService(
        repository=repository,
        source=content,
        policy_source=InMemoryRecommendationHumanReviewFindingPolicySource((policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(deny=deny),
        recorder=recorder,
        audit_sink=audit,
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    return service, repository, recorder, audit, assignment, lease, presentation, policy, actor


async def record_finding(
    service: Any,
    assignment: Any,
    lease: Any,
    presentation: Any,
    policy: Any,
    actor: Any,
    *,
    category: str = "finding-category.technical-accuracy",
    recommendation_id: str | None = None,
    key: str = "recommendation-human-review-finding-001",
) -> Any:
    return await service.create(
        actor=actor,
        recommendation_id=recommendation_id or assignment.recommendation_id,
        source_lease_id=lease.record.lease_id,
        source_presentation_id=presentation.record.presentation_id,
        source_presentation_digest=presentation.record.canonical_digest,
        finding_policy_id=policy.policy_id,
        finding_policy_digest=policy.canonical_digest,
        findings=(
            RecommendationHumanReviewFindingItem(
                category_code=category,
                severity_code="finding-severity.material",
                summary="Recovery timing evidence needs validation",
                detail=(
                    "The proposed recovery timing is not supported by a current vendor or site "
                    "measurement and must remain an explicit unknown."
                ),
            ),
        ),
        purpose="Record one accountable technical observation without making a decision.",
        evidence_review_acknowledged=True,
        finding_is_not_decision_acknowledged=True,
        browser_session_id="session_recommendation_inspection_001",
        lease_secrets={lease.record.track_code: str(lease.lease_secret)},
        idempotency_key=key,
        correlation_id="cor_recommendation_human_review_finding",
    )


@pytest.mark.asyncio
async def test_exact_assignee_records_metadata_only_finding_and_replay() -> None:
    (
        service,
        repository,
        recorder,
        audit,
        assignment,
        lease,
        presentation,
        policy,
        actor,
    ) = await finding_fixture()
    first = await record_finding(service, assignment, lease, presentation, policy, actor)
    repeated = await record_finding(service, assignment, lease, presentation, policy, actor)

    assert actor.assurance_level is AssuranceLevel.DEVELOPMENT
    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert first.human_findings_recorded and first.technical_finding_recorded
    assert not first.service_impact_finding_recorded
    assert repeated.reused and repeated.canonical_digest == first.canonical_digest
    assert not first.human_review_completed
    assert not first.recommendation_approved
    assert not first.workflow_created
    assert not first.itsm_record_created
    assert not first.execution_authorized
    assert not first.deployment_authorized
    assert not first.infrastructure_mutated
    stored = asdict(next(iter(repository._records.values())))
    serialized = str(stored).lower()
    assert "recovery timing evidence needs validation" not in serialized
    assert "proposed recovery timing" not in serialized
    assert (
        "recovery timing evidence needs validation"
        not in str([asdict(record) for record in audit.records]).lower()
    )
    assert isinstance(recorder, SyntheticRecommendationHumanReviewFindingRecorder)
    assert recorder.read_artifact(finding_artifact_id=first.finding_artifact_id) is not None


@pytest.mark.asyncio
async def test_explicit_stronger_assurance_policy_denies_development_session() -> None:
    (
        service,
        repository,
        _,
        _,
        assignment,
        lease,
        presentation,
        policy,
        actor,
    ) = await finding_fixture()
    stronger_policy = replace(
        policy,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        canonical_digest="0" * 64,
    )
    stronger_policy = replace(
        stronger_policy,
        canonical_digest=service._digest(service._policy_payload(stronger_policy)),
    )
    service._policy_source = InMemoryRecommendationHumanReviewFindingPolicySource(
        (stronger_policy,)
    )

    with pytest.raises(RecommendationHumanReviewFindingError, match="assurance_required"):
        await record_finding(
            service,
            assignment,
            lease,
            presentation,
            stronger_policy,
            actor,
        )

    assert not repository._claims_by_idempotency


@pytest.mark.asyncio
async def test_wrong_path_cross_track_category_and_denial_fail_before_claim() -> None:
    (
        service,
        repository,
        _,
        _,
        assignment,
        lease,
        presentation,
        policy,
        actor,
    ) = await finding_fixture()
    with pytest.raises(RecommendationHumanReviewFindingError, match="source_invalid"):
        await record_finding(
            service,
            assignment,
            lease,
            presentation,
            policy,
            actor,
            recommendation_id="recommendation.other",
        )
    assert not repository._claims_by_presentation

    with pytest.raises(RecommendationHumanReviewFindingError, match="items_invalid"):
        await record_finding(
            service,
            assignment,
            lease,
            presentation,
            policy,
            actor,
            category="finding-category.business-impact",
        )
    assert not repository._claims_by_presentation

    (
        service,
        repository,
        _,
        _,
        assignment,
        lease,
        presentation,
        policy,
        actor,
    ) = await finding_fixture(deny=True)
    with pytest.raises(RecommendationHumanReviewFindingError, match="permission_denied"):
        await record_finding(service, assignment, lease, presentation, policy, actor)
    assert not repository._claims_by_presentation


@pytest.mark.asyncio
async def test_intent_audit_and_unavailable_recorder_fail_closed() -> None:
    (
        service,
        repository,
        recorder,
        _,
        assignment,
        lease,
        presentation,
        policy,
        actor,
    ) = await finding_fixture()
    service._audit_sink = FailingAuditSink()
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await record_finding(service, assignment, lease, presentation, policy, actor)
    assert not repository._claims_by_presentation
    assert not recorder.calls

    (
        service,
        repository,
        _,
        _,
        assignment,
        lease,
        presentation,
        policy,
        actor,
    ) = await finding_fixture(unavailable=True)
    with pytest.raises(RecommendationHumanReviewFindingError, match="recorder_unavailable"):
        await record_finding(service, assignment, lease, presentation, policy, actor)
    assert repository._claims_by_presentation and not repository._records


@pytest.mark.asyncio
async def test_postgres_conversion_and_api_schema_exclude_private_content() -> None:
    (
        service,
        repository,
        _,
        _,
        assignment,
        lease,
        presentation,
        policy,
        actor,
    ) = await finding_fixture()
    record = await record_finding(service, assignment, lease, presentation, policy, actor)
    raw = service._normalize(asdict(record))
    assert isinstance(raw, dict)
    assert PostgreSQLRecommendationHumanReviewFindingRepository._record_to_domain(raw) == record
    claim = next(iter(repository._claims_by_presentation.values()))
    claim_raw = service._normalize(asdict(claim))
    assert isinstance(claim_raw, dict)
    assert PostgreSQLRecommendationHumanReviewFindingRepository._claim_to_domain(claim_raw) == claim

    response = RecommendationHumanReviewFindingData.from_record(record).model_dump()
    serialized = str(response).lower()
    for private in (
        "finding_artifact_id",
        "lease_holder_subject_digest",
        "browser_session_binding_digest",
        "summary",
        "detail",
        "idempotency_digest",
    ):
        assert private not in serialized


def test_input_forbids_identity_track_artifact_decision_and_operation_controls() -> None:
    payload: dict[str, Any] = {
        "source_presentation_digest": "a" * 64,
        "finding_policy_id": "recommendation-human-review-finding-policy.example",
        "finding_policy_digest": "b" * 64,
        "findings": [
            {
                "category_code": "finding-category.technical-accuracy",
                "severity_code": "finding-severity.material",
                "summary": "A bounded accountable observation",
                "detail": "A bounded detail describing evidence uncertainty without a decision.",
            }
        ],
        "purpose": "Record an accountable observation without creating a review decision.",
        "acknowledged_evidence_was_reviewed": True,
        "acknowledged_finding_is_not_a_review_decision": True,
    }
    RecommendationHumanReviewFindingInput.model_validate(payload)
    with pytest.raises(ValidationError):
        RecommendationHumanReviewFindingInput.model_validate(
            {
                **payload,
                "findings": [
                    {
                        **payload["findings"][0],
                        "summary": "too short",
                    }
                ],
            }
        )
    with pytest.raises(ValidationError):
        RecommendationHumanReviewFindingInput.model_validate(
            {
                **payload,
                "findings": [
                    {
                        **payload["findings"][0],
                        "detail": "too short",
                    }
                ],
            }
        )
    for forbidden in (
        "reviewer_identity",
        "track_code",
        "finding_artifact_id",
        "decision",
        "approved",
        "workflow_id",
        "command",
    ):
        with pytest.raises(ValidationError):
            RecommendationHumanReviewFindingInput.model_validate(
                {**payload, forbidden: "caller-controlled"}
            )


def _http_authorization(actor: AuthenticatedSubject, organization_id: str) -> AuthorizationService:
    permissions = (
        RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
        RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
        RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
        RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
        RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
        RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
    )

    def scope(permission: str, capability: CapabilityClass) -> Any:
        if "human-review-findings" in permission:
            return recommendation_human_review_finding_scope(organization_id, "test", capability)
        if "protected-content" in permission:
            return recommendation_protected_content_scope(organization_id, "test", capability)
        return recommendation_protected_inspection_scope(organization_id, "test", capability)

    return AuthorizationService(
        permissions=tuple(
            PermissionDefinition(permission_id=permission, description=permission)
            for permission in permissions
        ),
        roles=(
            RoleDefinition(
                role_id=actor.role_ids[0], version=1, permissions=frozenset(permissions)
            ),
        ),
        assignments=tuple(
            RoleAssignment(
                assignment_id=f"assignment.recommendation-finding-http-{index}",
                version=1,
                subject_id=actor.subject_id,
                role_id=actor.role_ids[0],
                scope=scope(
                    permission,
                    CapabilityClass.C2_DIAGNOSTIC
                    if permission.endswith("create")
                    else CapabilityClass.C1_READ_ONLY,
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            )
            for index, permission in enumerate(permissions)
        ),
        audit_sink=CollectingAuditSink(),
    )


@pytest.mark.asyncio
async def test_http_flow_requires_csrf_and_returns_metadata_only() -> None:
    inspection, _, assignment, inspection_policy, actor, _, _ = await inspection_fixture()
    content_policy = build_development_recommendation_protected_content_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.assigned_at - timedelta(minutes=1),
        expires_at=assignment.assigned_at + timedelta(days=1),
    )
    content_service = RecommendationProtectedContentService(
        repository=InMemoryRecommendationProtectedContentRepository(),
        source=inspection,
        policy_source=InMemoryRecommendationProtectedContentPolicySource((content_policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(),
        presenter=SyntheticRecommendationProtectedContentPresenter(
            clock=lambda: assignment.assigned_at
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    finding_policy = build_development_recommendation_human_review_finding_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.assigned_at - timedelta(minutes=1),
        expires_at=assignment.assigned_at + timedelta(days=1),
    )
    finding_service = RecommendationHumanReviewFindingService(
        repository=InMemoryRecommendationHumanReviewFindingRepository(),
        source=content_service,
        policy_source=InMemoryRecommendationHumanReviewFindingPolicySource((finding_policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(),
        recorder=SyntheticRecommendationHumanReviewFindingRecorder(
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
            authorization_service=_http_authorization(actor, assignment.organization_id),
            recommendation_protected_inspection_service=inspection,
            recommendation_protected_content_service=content_service,
            recommendation_human_review_finding_service=finding_service,
        ),
        base_url="https://testserver",
    ) as client:
        assert login(client).status_code == 201
        csrf = str(client.cookies.get("atlas_csrf"))
        lease_response = client.post(
            f"/api/v1/recommendations/{assignment.recommendation_id}/protected-inspections/leases",
            headers={"Idempotency-Key": "recommendation-finding-http-lease", "X-CSRF-Token": csrf},
            json={
                "source_assignment_set_id": assignment.assignment_set_id,
                "source_assignment_set_digest": assignment.canonical_digest,
                "track_code": track,
                "opaque_assignment_id": assignment_id,
                "inspection_policy_id": inspection_policy.policy_id,
                "inspection_policy_digest": inspection_policy.canonical_digest,
                "purpose": "Open one exact assigned recommendation track for finding review.",
                "acknowledged_exact_assignee_and_track_required": True,
                "acknowledged_lease_returns_no_content_or_secret_in_json": True,
                "acknowledged_no_decision_approval_or_operational_authority": True,
            },
        )
        assert lease_response.status_code == 201
        lease_data = lease_response.json()["data"]
        presentation_response = client.post(
            (
                f"/api/v1/recommendations/{assignment.recommendation_id}/protected-inspections/"
                f"leases/{lease_data['lease_id']}/presentations"
            ),
            headers={
                "Idempotency-Key": "recommendation-finding-http-present",
                "X-CSRF-Token": csrf,
            },
            json={
                "source_lease_digest": lease_data["canonical_digest"],
                "presentation_policy_id": content_policy.policy_id,
                "presentation_policy_digest": content_policy.canonical_digest,
                "purpose": "Present one exact recommendation snapshot for finding review.",
                "acknowledged_sensitive_read_only_content": True,
                "acknowledged_no_finding_decision_approval_or_operational_authority": True,
            },
        )
        assert presentation_response.status_code == 201
        presentation_data = presentation_response.json()["data"]
        path = (
            f"/api/v1/recommendations/{assignment.recommendation_id}/protected-inspections/"
            f"leases/{lease_data['lease_id']}/presentations/"
            f"{presentation_data['presentation_id']}/findings"
        )
        payload = {
            "source_presentation_digest": presentation_data["canonical_digest"],
            "finding_policy_id": finding_policy.policy_id,
            "finding_policy_digest": finding_policy.canonical_digest,
            "findings": [
                {
                    "category_code": "finding-category.technical-accuracy",
                    "severity_code": "finding-severity.material",
                    "summary": "Recovery timing evidence needs validation",
                    "detail": "The proposed timing lacks a current vendor or site measurement.",
                }
            ],
            "purpose": "Record one accountable observation without making a review decision.",
            "acknowledged_evidence_was_reviewed": True,
            "acknowledged_finding_is_not_a_review_decision": True,
        }
        rejected = client.post(
            path,
            headers={"Idempotency-Key": "recommendation-finding-http-no-csrf"},
            json=payload,
        )
        assert rejected.status_code == 403
        response = client.post(
            path,
            headers={
                "Idempotency-Key": "recommendation-finding-http-record",
                "X-CSRF-Token": csrf,
            },
            json=payload,
        )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store, max-age=0"
    data = response.json()["data"]
    assert data["human_findings_recorded"] is True
    assert data["human_review_completed"] is False
    assert data["recommendation_approved"] is False
    serialized = str(data).lower()
    assert "recovery timing evidence" not in serialized
    assert "proposed timing" not in serialized


def test_openapi_registers_recommendation_human_review_finding_routes() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    base = (
        "/api/v1/recommendations/{recommendation_id}/protected-inspections/leases/{lease_id}/"
        "presentations/{presentation_id}/findings"
    )
    assert base in paths
    assert f"{base}/{{finding_packet_id}}" in paths
