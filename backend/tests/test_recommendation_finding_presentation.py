from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_recommendation_human_review_finding import (
    finding_fixture,
    record_finding,
)
from test_recommendation_protected_inspection import inspection_fixture

from atlas.api.app import create_app
from atlas.api.recommendation_finding_presentation_schemas import (
    RecommendationFindingPresentationData,
    RecommendationFindingPresentationInput,
)
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_FINDING_PRESENTATION_CREATE,
    RECOMMENDATION_FINDING_PRESENTATION_READ,
    RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
    RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_CREATE,
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTATION_READ,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_CREATE,
    RECOMMENDATION_PROTECTED_INSPECTION_LEASE_READ,
    recommendation_finding_presentation_scope,
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
from atlas.modules.recommendations.adapters.finding_presentation_memory import (
    InMemoryRecommendationFindingPresentationPolicySource,
    InMemoryRecommendationFindingPresentationRepository,
)
from atlas.modules.recommendations.adapters.finding_presentation_postgres import (
    PostgreSQLRecommendationFindingPresentationRepository,
)
from atlas.modules.recommendations.adapters.finding_presentation_synthetic import (
    SyntheticRecommendationFindingPresenter,
    UnavailableRecommendationFindingPresenter,
)
from atlas.modules.recommendations.adapters.human_review_finding_memory import (
    InMemoryRecommendationHumanReviewFindingPolicySource,
    InMemoryRecommendationHumanReviewFindingRepository,
)
from atlas.modules.recommendations.adapters.human_review_finding_synthetic import (
    SyntheticRecommendationHumanReviewFindingRecorder,
)
from atlas.modules.recommendations.adapters.protected_content_memory import (
    InMemoryRecommendationProtectedContentPolicySource,
    InMemoryRecommendationProtectedContentRepository,
)
from atlas.modules.recommendations.adapters.protected_content_synthetic import (
    SyntheticRecommendationProtectedContentPresenter,
)
from atlas.modules.recommendations.application.finding_presentation import (
    RecommendationFindingPresentationService,
    build_development_recommendation_finding_presentation_policy,
)
from atlas.modules.recommendations.application.finding_presentation_ports import (
    RecommendationFindingPresentationError,
)
from atlas.modules.recommendations.application.human_review_finding import (
    RecommendationHumanReviewFindingService,
    build_development_recommendation_human_review_finding_policy,
)
from atlas.modules.recommendations.application.protected_content import (
    RecommendationProtectedContentService,
    build_development_recommendation_protected_content_policy,
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
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_permission_denied"
            )


async def presentation_fixture(
    *, deny: bool = False, unavailable: bool = False, audit: Any | None = None
) -> tuple[Any, ...]:
    (
        finding_service,
        _finding_repository,
        recorder,
        _finding_audit,
        assignment,
        lease,
        presentation,
        finding_policy,
        actor,
    ) = await finding_fixture()
    finding = await record_finding(
        finding_service,
        assignment,
        lease,
        presentation,
        finding_policy,
        actor,
    )
    policy = build_development_recommendation_finding_presentation_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.assigned_at - timedelta(minutes=1),
        expires_at=assignment.assigned_at + timedelta(days=1),
    )
    repository = InMemoryRecommendationFindingPresentationRepository()
    assert isinstance(recorder, SyntheticRecommendationHumanReviewFindingRecorder)
    presenter = (
        UnavailableRecommendationFindingPresenter()
        if unavailable
        else SyntheticRecommendationFindingPresenter(
            recorder=recorder, clock=lambda: assignment.assigned_at
        )
    )
    audit_sink = audit or CollectingAuditSink()
    service = RecommendationFindingPresentationService(
        repository=repository,
        source=finding_service,
        policy_source=InMemoryRecommendationFindingPresentationPolicySource((policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(deny=deny),
        presenter=presenter,
        audit_sink=audit_sink,
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    return (
        service,
        repository,
        presenter,
        audit_sink,
        assignment,
        lease,
        presentation,
        finding,
        policy,
        actor,
    )


async def present_findings(
    service: RecommendationFindingPresentationService,
    assignment: Any,
    lease: Any,
    presentation: Any,
    finding: Any,
    policy: Any,
    actor: Any,
    *,
    recommendation_id: str | None = None,
    finding_digest: str | None = None,
    key: str = "recommendation-finding-presentation-001",
) -> Any:
    return await service.create(
        actor=actor,
        recommendation_id=recommendation_id or assignment.recommendation_id,
        source_lease_id=lease.record.lease_id,
        source_presentation_id=presentation.record.presentation_id,
        source_finding_packet_id=finding.finding_packet_id,
        source_finding_digest=finding_digest or finding.canonical_digest,
        presentation_policy_id=policy.policy_id,
        presentation_policy_digest=policy.canonical_digest,
        purpose="Present the sealed reviewer observations without recording a decision.",
        sensitive_findings_acknowledged=True,
        finding_is_not_decision_acknowledged=True,
        browser_session_id="session_recommendation_inspection_001",
        lease_secrets={lease.record.track_code: str(lease.lease_secret)},
        idempotency_key=key,
        correlation_id="cor_recommendation_finding_presentation",
    )


@pytest.mark.asyncio
async def test_default_policy_allows_single_factor_human_presentation() -> None:
    (
        service,
        _,
        _,
        _,
        assignment,
        lease,
        presentation,
        finding,
        policy,
        actor,
    ) = await presentation_fixture()
    single_factor_actor = replace(actor, assurance_level=AssuranceLevel.SINGLE_FACTOR)

    grant = await present_findings(
        service,
        assignment,
        lease,
        presentation,
        finding,
        policy,
        single_factor_actor,
    )

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert grant.record.human_findings_presented
    assert not grant.record.recommendation_approved
    assert not grant.record.infrastructure_mutated


@pytest.mark.asyncio
async def test_stronger_policy_denies_single_factor_human_presentation() -> None:
    (
        service,
        repository,
        _,
        _,
        assignment,
        lease,
        presentation,
        finding,
        policy,
        actor,
    ) = await presentation_fixture()
    stronger = replace(
        policy,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        canonical_digest="0" * 64,
    )
    stronger = replace(
        stronger,
        canonical_digest=service._digest(service._policy_payload(stronger)),
    )
    service._policy_source = InMemoryRecommendationFindingPresentationPolicySource((stronger,))
    single_factor_actor = replace(actor, assurance_level=AssuranceLevel.SINGLE_FACTOR)

    with pytest.raises(RecommendationFindingPresentationError, match="assurance_required"):
        await present_findings(
            service,
            assignment,
            lease,
            presentation,
            finding,
            stronger,
            single_factor_actor,
        )

    assert (
        await repository.get_by_source_finding(source_finding_packet_id=finding.finding_packet_id)
        is None
    )


@pytest.mark.asyncio
async def test_exact_assignee_presents_sealed_findings_and_replays_exact_snapshot() -> None:
    (
        service,
        repository,
        presenter,
        audit,
        assignment,
        lease,
        presentation,
        finding,
        policy,
        actor,
    ) = await presentation_fixture()
    first = await present_findings(service, assignment, lease, presentation, finding, policy, actor)
    repeated = await present_findings(
        service, assignment, lease, presentation, finding, policy, actor
    )

    assert first.record.human_findings_presented
    assert first.record.technical_findings_presented
    assert not first.record.service_impact_findings_presented
    assert repeated.record.reused
    assert repeated.record.canonical_digest == first.record.canonical_digest
    assert repeated.findings == first.findings
    assert first.findings[0].summary == "Recovery timing evidence needs validation"
    assert not first.record.human_review_completed
    assert not first.record.recommendation_approved
    assert not first.record.correction_created
    assert not first.record.workflow_created
    assert not first.record.itsm_record_created
    assert not first.record.execution_authorized
    assert not first.record.deployment_authorized
    assert not first.record.infrastructure_mutated
    assert len(presenter.calls) == 2

    serialized_record = str(asdict(next(iter(repository._records.values())))).lower()
    serialized_audit = str([asdict(record) for record in audit.records]).lower()
    for plaintext in ("recovery timing evidence", "proposed recovery timing"):
        assert plaintext not in serialized_record
        assert plaintext not in serialized_audit


@pytest.mark.asyncio
async def test_wrong_path_digest_and_permission_fail_before_claim() -> None:
    (
        service,
        repository,
        _presenter,
        _audit,
        assignment,
        lease,
        presentation,
        finding,
        policy,
        actor,
    ) = await presentation_fixture()
    with pytest.raises(RecommendationFindingPresentationError, match="source_invalid"):
        await present_findings(
            service,
            assignment,
            lease,
            presentation,
            finding,
            policy,
            actor,
            recommendation_id="recommendation.other",
        )
    with pytest.raises(RecommendationFindingPresentationError, match="source_invalid"):
        await present_findings(
            service,
            assignment,
            lease,
            presentation,
            finding,
            policy,
            actor,
            finding_digest="f" * 64,
            key="recommendation-finding-presentation-wrong-digest",
        )
    assert not repository._claims_by_finding

    (
        denied_service,
        denied_repository,
        *_rest,
        denied_assignment,
        denied_lease,
        denied_presentation,
        denied_finding,
        denied_policy,
        denied_actor,
    ) = await presentation_fixture(deny=True)
    with pytest.raises(RecommendationFindingPresentationError, match="permission_denied"):
        await present_findings(
            denied_service,
            denied_assignment,
            denied_lease,
            denied_presentation,
            denied_finding,
            denied_policy,
            denied_actor,
        )
    assert not denied_repository._claims_by_finding


@pytest.mark.asyncio
async def test_intent_audit_and_unavailable_presenter_fail_closed() -> None:
    values = await presentation_fixture(audit=FailingAuditSink())
    service, repository, _, _, assignment, lease, presentation, finding, policy, actor = values
    with pytest.raises(Exception, match="audit unavailable"):
        await present_findings(service, assignment, lease, presentation, finding, policy, actor)
    assert not repository._claims_by_finding

    values = await presentation_fixture(unavailable=True)
    service, repository, _, audit, assignment, lease, presentation, finding, policy, actor = values
    with pytest.raises(RecommendationFindingPresentationError, match="presenter_unavailable"):
        await present_findings(service, assignment, lease, presentation, finding, policy, actor)
    assert repository._claims_by_finding
    assert not repository._records
    assert any(
        record.result_code == "recommendation_finding_presentation_failed"
        for record in audit.records
    )


@pytest.mark.asyncio
async def test_schema_and_postgres_conversion_exclude_private_content() -> None:
    (
        service,
        _repository,
        _presenter,
        _audit,
        assignment,
        lease,
        presentation,
        finding,
        policy,
        actor,
    ) = await presentation_fixture()
    grant = await present_findings(service, assignment, lease, presentation, finding, policy, actor)
    data = RecommendationFindingPresentationData.from_grant(grant).model_dump(mode="json")
    assert data["findings"][0]["summary"] == "Recovery timing evidence needs validation"
    serialized = str(data).lower()
    for forbidden in (
        "finding_artifact_id",
        "browser_session_binding_digest",
        "lease_holder_subject_digest",
        "access_policy_id",
        "retention_policy_id",
        "encryption_profile_id",
    ):
        assert forbidden not in serialized

    raw = RecommendationFindingPresentationService._normalize(asdict(grant.record))
    assert isinstance(raw, dict)
    restored = PostgreSQLRecommendationFindingPresentationRepository._record_to_domain(raw)
    assert restored == grant.record
    assert "recovery timing evidence" not in str(raw).lower()


def test_input_forbids_identity_track_content_decision_and_operation_controls() -> None:
    payload: dict[str, object] = {
        "source_finding_digest": "a" * 64,
        "presentation_policy_id": "recommendation-finding-presentation-policy.development",
        "presentation_policy_digest": "b" * 64,
        "purpose": "Present one sealed finding packet without making a review decision.",
        "acknowledged_findings_are_sensitive": True,
        "acknowledged_finding_presentation_is_not_a_review_decision": True,
    }
    RecommendationFindingPresentationInput.model_validate(payload)
    for forbidden in (
        "subject_id",
        "organization_id",
        "track_code",
        "findings",
        "summary",
        "detail",
        "finding_artifact_id",
        "artifact_location",
        "decision",
        "approval",
        "workflow",
        "itsm",
        "command",
        "execution",
        "infrastructure_mutation",
    ):
        with pytest.raises(ValidationError):
            RecommendationFindingPresentationInput.model_validate(
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
        RECOMMENDATION_FINDING_PRESENTATION_CREATE,
        RECOMMENDATION_FINDING_PRESENTATION_READ,
    )

    def scope(permission: str, capability: CapabilityClass) -> Any:
        if "finding-presentations" in permission:
            return recommendation_finding_presentation_scope(organization_id, "test", capability)
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
                assignment_id=f"assignment.recommendation-presentation-http-{index}",
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
async def test_http_flow_requires_csrf_and_returns_no_store_plaintext_only() -> None:
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
    recorder = SyntheticRecommendationHumanReviewFindingRecorder(
        clock=lambda: assignment.assigned_at
    )
    finding_service = RecommendationHumanReviewFindingService(
        repository=InMemoryRecommendationHumanReviewFindingRepository(),
        source=content_service,
        policy_source=InMemoryRecommendationHumanReviewFindingPolicySource((finding_policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(),
        recorder=recorder,
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    presentation_policy = build_development_recommendation_finding_presentation_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.assigned_at - timedelta(minutes=1),
        expires_at=assignment.assigned_at + timedelta(days=1),
    )
    finding_presentation_service = RecommendationFindingPresentationService(
        repository=InMemoryRecommendationFindingPresentationRepository(),
        source=finding_service,
        policy_source=InMemoryRecommendationFindingPresentationPolicySource((presentation_policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(),
        presenter=SyntheticRecommendationFindingPresenter(
            recorder=recorder, clock=lambda: assignment.assigned_at
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
            recommendation_finding_presentation_service=finding_presentation_service,
        ),
        base_url="https://testserver",
    ) as client:
        assert login(client).status_code == 201
        csrf = str(client.cookies.get("atlas_csrf"))
        lease_response = client.post(
            f"/api/v1/recommendations/{assignment.recommendation_id}/protected-inspections/leases",
            headers={
                "Idempotency-Key": "recommendation-presentation-http-lease",
                "X-CSRF-Token": csrf,
            },
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
        content_response = client.post(
            (
                f"/api/v1/recommendations/{assignment.recommendation_id}/protected-inspections/"
                f"leases/{lease_data['lease_id']}/presentations"
            ),
            headers={
                "Idempotency-Key": "recommendation-presentation-http-content",
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
        assert content_response.status_code == 201
        content_data = content_response.json()["data"]
        finding_path = (
            f"/api/v1/recommendations/{assignment.recommendation_id}/protected-inspections/"
            f"leases/{lease_data['lease_id']}/presentations/{content_data['presentation_id']}/findings"
        )
        finding_response = client.post(
            finding_path,
            headers={
                "Idempotency-Key": "recommendation-presentation-http-finding",
                "X-CSRF-Token": csrf,
            },
            json={
                "source_presentation_digest": content_data["canonical_digest"],
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
            },
        )
        assert finding_response.status_code == 201
        finding_data = finding_response.json()["data"]
        presentation_path = f"{finding_path}/{finding_data['finding_packet_id']}/presentations"
        payload = {
            "source_finding_digest": finding_data["canonical_digest"],
            "presentation_policy_id": presentation_policy.policy_id,
            "presentation_policy_digest": presentation_policy.canonical_digest,
            "purpose": "Present sealed findings without recording a review decision.",
            "acknowledged_findings_are_sensitive": True,
            "acknowledged_finding_presentation_is_not_a_review_decision": True,
        }
        rejected = client.post(
            presentation_path,
            headers={"Idempotency-Key": "recommendation-presentation-http-no-csrf"},
            json=payload,
        )
        assert rejected.status_code == 403
        response = client.post(
            presentation_path,
            headers={
                "Idempotency-Key": "recommendation-presentation-http-present",
                "X-CSRF-Token": csrf,
            },
            json=payload,
        )
        assert response.status_code == 201
        replay = client.get(
            f"{presentation_path}/{response.json()['data']['finding_presentation_id']}"
        )
    assert replay.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
    data = response.json()["data"]
    assert data["findings"][0]["summary"] == "Recovery timing evidence needs validation"
    assert data["human_findings_presented"] is True
    assert data["human_review_completed"] is False
    assert data["recommendation_approved"] is False
    assert replay.json()["data"]["canonical_digest"] == data["canonical_digest"]


def test_openapi_registers_recommendation_finding_presentation_routes() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    base = (
        "/api/v1/recommendations/{recommendation_id}/protected-inspections/leases/{lease_id}/"
        "presentations/{presentation_id}/findings/{finding_packet_id}/presentations"
    )
    assert base in paths
    assert f"{base}/{{finding_presentation_id}}" in paths
