from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_reviewer_assignment import assign_reviewers, reviewer_assignment_fixture
from test_runtime_activation import FailSecondAuditSink
from test_target_session import development_target_session_operator, target_session_operator

from atlas.api.app import create_app
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.finding_presentation_memory import (
    InMemoryOperationalKnowledgeFindingPresentationPolicySource,
    InMemoryOperationalKnowledgeFindingPresentationRepository,
)
from atlas.modules.knowledge.adapters.finding_presentation_synthetic import (
    SyntheticOperationalKnowledgeFindingPresenter,
)
from atlas.modules.knowledge.adapters.protected_content_memory import (
    InMemoryOperationalKnowledgeProtectedContentPolicySource,
    InMemoryOperationalKnowledgeProtectedContentRepository,
)
from atlas.modules.knowledge.adapters.protected_content_synthetic import (
    SyntheticOperationalKnowledgeProtectedContentPresenter,
)
from atlas.modules.knowledge.adapters.protected_inspection_memory import (
    InMemoryOperationalKnowledgeProtectedInspectionPolicySource,
    InMemoryOperationalKnowledgeProtectedInspectionRepository,
)
from atlas.modules.knowledge.adapters.protected_inspection_postgres import (
    PostgreSQLOperationalKnowledgeProtectedInspectionRepository,
)
from atlas.modules.knowledge.adapters.protected_inspection_synthetic import (
    SyntheticOperationalKnowledgeProtectedInspectionBroker,
)
from atlas.modules.knowledge.adapters.review_decision_memory import (
    InMemoryOperationalKnowledgeTrackReviewDecisionPolicySource,
    InMemoryOperationalKnowledgeTrackReviewDecisionRepository,
)
from atlas.modules.knowledge.adapters.review_decision_synthetic import (
    SyntheticOperationalKnowledgeTrackReviewDecisionAttestor,
)
from atlas.modules.knowledge.adapters.review_finding_memory import (
    InMemoryOperationalKnowledgeReviewFindingPolicySource,
    InMemoryOperationalKnowledgeReviewFindingRepository,
)
from atlas.modules.knowledge.adapters.review_finding_synthetic import (
    SyntheticOperationalKnowledgeReviewFindingRecorder,
)
from atlas.modules.knowledge.application.finding_presentation import (
    OperationalKnowledgeFindingPresentationService,
    build_development_operational_knowledge_finding_presentation_policy,
)
from atlas.modules.knowledge.application.protected_content import (
    OperationalKnowledgeProtectedContentService,
    build_development_operational_knowledge_protected_content_policy,
)
from atlas.modules.knowledge.application.protected_inspection import (
    OperationalKnowledgeProtectedInspectionService,
    _signed_policy,
    build_development_operational_knowledge_protected_inspection_policy,
)
from atlas.modules.knowledge.application.protected_inspection_ports import (
    OperationalKnowledgeProtectedInspectionError,
    OperationalKnowledgeProtectedInspectionUncertainError,
)
from atlas.modules.knowledge.application.review_decision import (
    OperationalKnowledgeTrackReviewDecisionService,
    build_development_operational_knowledge_track_review_decision_policy,
)
from atlas.modules.knowledge.application.review_finding import (
    OperationalKnowledgeReviewFindingService,
    build_development_operational_knowledge_review_finding_policy,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionBrokerGrant,
    OperationalKnowledgeProtectedInspectionGrant,
    OperationalKnowledgeProtectedInspectionInstruction,
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)

ACKNOWLEDGEMENT_FIELD = "acknowledged_lease_returns_no_content_and_records_no_decision"


class RecordingProtectedInspectionPermissionAuthorizer:
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
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_permission_denied"
            )


class UncertainProtectedInspectionBroker:
    def __init__(self) -> None:
        self.calls = 0

    async def issue(
        self, instruction: OperationalKnowledgeProtectedInspectionInstruction
    ) -> OperationalKnowledgeProtectedInspectionBrokerGrant:
        del instruction
        self.calls += 1
        raise OperationalKnowledgeProtectedInspectionUncertainError(
            "operational_knowledge_protected_inspection_broker_outcome_uncertain"
        )


class AlteredProtectedInspectionBroker(SyntheticOperationalKnowledgeProtectedInspectionBroker):
    async def issue(
        self, instruction: OperationalKnowledgeProtectedInspectionInstruction
    ) -> OperationalKnowledgeProtectedInspectionBrokerGrant:
        grant = await super().issue(instruction)
        altered = replace(grant.receipt, track_code="review-track.security")
        payload = cast(dict[str, object], asdict(altered))
        payload.pop("canonical_digest")
        receipt = replace(
            altered,
            canonical_digest=OperationalKnowledgeProtectedInspectionService._digest(
                OperationalKnowledgeProtectedInspectionService._normalize(payload)
            ),
        )
        return OperationalKnowledgeProtectedInspectionBrokerGrant(
            receipt=receipt, lease_secret=grant.lease_secret
        )


class BlockingProtectedInspectionBroker(SyntheticOperationalKnowledgeProtectedInspectionBroker):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def issue(
        self, instruction: OperationalKnowledgeProtectedInspectionInstruction
    ) -> OperationalKnowledgeProtectedInspectionBrokerGrant:
        self.started.set()
        await self.release.wait()
        return await super().issue(instruction)


async def protected_inspection_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingProtectedInspectionPermissionAuthorizer | None = None,
    broker: SyntheticOperationalKnowledgeProtectedInspectionBroker
    | UncertainProtectedInspectionBroker
    | AlteredProtectedInspectionBroker
    | BlockingProtectedInspectionBroker
    | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    OperationalKnowledgeProtectedInspectionService,
    InMemoryOperationalKnowledgeProtectedInspectionRepository,
    OperationalKnowledgeReviewerAssignmentRecord,
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    RecordingProtectedInspectionPermissionAuthorizer,
    SyntheticOperationalKnowledgeProtectedInspectionBroker
    | UncertainProtectedInspectionBroker
    | AlteredProtectedInspectionBroker
    | BlockingProtectedInspectionBroker,
    tuple[Any, ...],
]:
    assignment_parts = await reviewer_assignment_fixture()
    assignment_service, _, review_request, assignment_policy, *_ = assignment_parts
    assignment = await assign_reviewers(assignment_service, review_request, assignment_policy)
    policy = build_development_operational_knowledge_protected_inspection_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.created_at - timedelta(hours=1),
        expires_at=assignment.created_at + timedelta(days=1),
    )
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_policy(policy))
    repository = InMemoryOperationalKnowledgeProtectedInspectionRepository()
    authorizer = permission_authorizer or RecordingProtectedInspectionPermissionAuthorizer()
    resolved_broker = broker or SyntheticOperationalKnowledgeProtectedInspectionBroker(
        clock=lambda: assignment.created_at
    )
    service = OperationalKnowledgeProtectedInspectionService(
        repository=repository,
        source=assignment_service,
        policy_source=InMemoryOperationalKnowledgeProtectedInspectionPolicySource((policy,)),
        permission_authorizer=authorizer,
        broker=resolved_broker,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.created_at,
    )
    return (
        service,
        repository,
        assignment,
        policy,
        authorizer,
        resolved_broker,
        assignment_parts,
    )


def domain_reviewer() -> AuthenticatedSubject:
    return target_session_operator("subject.synthetic-domain-reviewer")


def development_domain_reviewer() -> AuthenticatedSubject:
    return development_target_session_operator("subject.synthetic-domain-reviewer")


async def lease_domain_inspection(
    service: OperationalKnowledgeProtectedInspectionService,
    assignment: OperationalKnowledgeReviewerAssignmentRecord,
    policy: OperationalKnowledgeProtectedInspectionPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "knowledge-protected-inspection-001",
    browser_session_id: str = "session_knowledge_inspection_001",
) -> OperationalKnowledgeProtectedInspectionGrant:
    return await service.create(
        actor=actor or domain_reviewer(),
        source_assignment_set_id=assignment.assignment_set_id,
        source_assignment_set_digest=assignment.canonical_digest,
        track_code="review-track.domain",
        inspection_policy_id=policy.policy_id,
        inspection_policy_digest=policy.canonical_digest,
        purpose="Open one short-lived domain-track inspection boundary without returning content.",
        lease_only_acknowledged=True,
        browser_session_id=browser_session_id,
        idempotency_key=key,
        correlation_id="cor_knowledge_protected_inspection",
    )


@pytest.mark.asyncio
async def test_protected_inspection_is_exact_assignee_cookie_only_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, assignment, policy, authorizer, broker, _ = await protected_inspection_fixture(
        audit_sink=audit
    )
    grant = await lease_domain_inspection(service, assignment, policy)
    repeated = await lease_domain_inspection(service, assignment, policy)
    record = grant.record

    assert record.instance_state == "operational_knowledge_protected_inspection_leased"
    assert record.content_inspection_opened and not record.content_disclosed
    assert record.content_bytes_read == 0
    assert record.exact_assignee_verified and record.browser_session_bound
    assert not record.domain_review_completed and not record.security_review_completed
    assert not record.knowledge_approved and not record.retrieval_published
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert grant.lease_secret is not None and repeated.lease_secret is None
    assert repeated.record.reused and repeated.record.lease_id == record.lease_id
    assert isinstance(broker, SyntheticOperationalKnowledgeProtectedInspectionBroker)
    assert broker.call_count == 1
    assert authorizer.calls == [(assignment.organization_id, assignment.environment_id)]
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_protected_inspection_requested",
        "operational_knowledge_assignment_track_claimed_for_inspection",
        "operational_knowledge_protected_inspection_leased",
    ]


@pytest.mark.asyncio
async def test_protected_inspection_accepts_development_identity_under_default_policy() -> None:
    service, _, assignment, policy, _, _, _ = await protected_inspection_fixture()

    grant = await lease_domain_inspection(
        service,
        assignment,
        policy,
        actor=development_domain_reviewer(),
    )

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert grant.record.content_inspection_opened and not grant.record.content_disclosed


@pytest.mark.parametrize(
    "required_assurance_level",
    [AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED],
)
@pytest.mark.asyncio
async def test_protected_inspection_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, assignment, policy, authorizer, broker, _ = await protected_inspection_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(OperationalKnowledgeProtectedInspectionError, match="assurance_required"):
        await lease_domain_inspection(
            service,
            assignment,
            policy,
            actor=development_domain_reviewer(),
        )

    assert authorizer.calls == []
    assert getattr(broker, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_protected_inspection_denies_non_human_identity() -> None:
    service, _, assignment, policy, authorizer, broker, _ = await protected_inspection_fixture()
    actor = replace(development_domain_reviewer(), kind=SubjectKind.SERVICE)

    with pytest.raises(OperationalKnowledgeProtectedInspectionError, match="human_required"):
        await lease_domain_inspection(service, assignment, policy, actor=actor)

    assert authorizer.calls == []
    assert getattr(broker, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_protected_inspection_rejects_wrong_assignee_before_claim() -> None:
    service, repository, assignment, policy, _, broker, _ = await protected_inspection_fixture()
    with pytest.raises(OperationalKnowledgeProtectedInspectionError, match="source_not_found"):
        await lease_domain_inspection(
            service,
            assignment,
            policy,
            actor=target_session_operator("subject.synthetic-security-reviewer"),
        )
    assert (
        await repository.get_claim_by_source_track(
            source_assignment_set_id=assignment.assignment_set_id,
            track_code="review-track.domain",
        )
        is None
    )
    assert isinstance(broker, SyntheticOperationalKnowledgeProtectedInspectionBroker)
    assert broker.call_count == 0


@pytest.mark.asyncio
async def test_protected_inspection_atomically_rejects_concurrent_second_claim() -> None:
    broker = BlockingProtectedInspectionBroker()
    service, _, assignment, policy, _, _, _ = await protected_inspection_fixture(broker=broker)
    first = asyncio.create_task(
        lease_domain_inspection(service, assignment, policy, key="inspection-first")
    )
    await broker.started.wait()
    with pytest.raises(OperationalKnowledgeProtectedInspectionError, match="idempotency_conflict"):
        await lease_domain_inspection(service, assignment, policy, key="inspection-second")
    broker.release.set()
    grant = await first
    assert grant.record.content_inspection_opened and broker.call_count == 1


@pytest.mark.asyncio
async def test_protected_inspection_permission_denial_happens_before_claim() -> None:
    service, repository, assignment, policy, _, broker, _ = await protected_inspection_fixture(
        permission_authorizer=RecordingProtectedInspectionPermissionAuthorizer(deny=True)
    )
    with pytest.raises(OperationalKnowledgeProtectedInspectionError, match="permission_denied"):
        await lease_domain_inspection(service, assignment, policy)
    assert (
        await repository.get_claim_by_source_track(
            source_assignment_set_id=assignment.assignment_set_id,
            track_code="review-track.domain",
        )
        is None
    )
    assert isinstance(broker, SyntheticOperationalKnowledgeProtectedInspectionBroker)
    assert broker.call_count == 0


@pytest.mark.asyncio
async def test_protected_inspection_uncertain_or_altered_receipt_stays_claimed() -> None:
    uncertain = UncertainProtectedInspectionBroker()
    service, repository, assignment, policy, _, _, _ = await protected_inspection_fixture(
        broker=uncertain
    )
    with pytest.raises(OperationalKnowledgeProtectedInspectionUncertainError, match="uncertain"):
        await lease_domain_inspection(service, assignment, policy)
    assert uncertain.calls == 1
    assert await repository.get_claim_by_source_track(
        source_assignment_set_id=assignment.assignment_set_id,
        track_code="review-track.domain",
    )
    with pytest.raises(OperationalKnowledgeProtectedInspectionError, match="already_claimed"):
        await lease_domain_inspection(service, assignment, policy)

    altered = AlteredProtectedInspectionBroker(clock=lambda: assignment.created_at)
    (
        altered_service,
        _,
        altered_assignment,
        altered_policy,
        _,
        _,
        _,
    ) = await protected_inspection_fixture(broker=altered)
    with pytest.raises(
        OperationalKnowledgeProtectedInspectionUncertainError, match="receipt_invalid"
    ):
        await lease_domain_inspection(altered_service, altered_assignment, altered_policy)


@pytest.mark.asyncio
async def test_protected_inspection_claim_audit_failure_stays_claimed() -> None:
    service, repository, assignment, policy, _, broker, _ = await protected_inspection_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await lease_domain_inspection(service, assignment, policy)
    assert await repository.get_claim_by_source_track(
        source_assignment_set_id=assignment.assignment_set_id,
        track_code="review-track.domain",
    )
    assert isinstance(broker, SyntheticOperationalKnowledgeProtectedInspectionBroker)
    assert broker.call_count == 0


@pytest.mark.asyncio
async def test_protected_inspection_postgres_round_trip_excludes_secret_and_identity() -> None:
    service, repository, assignment, policy, _, _, _ = await protected_inspection_fixture()
    grant = await lease_domain_inspection(service, assignment, policy)
    claim = await repository.get_claim_by_source_track(
        source_assignment_set_id=assignment.assignment_set_id,
        track_code="review-track.domain",
    )
    assert claim is not None
    raw_claim = OperationalKnowledgeProtectedInspectionService._normalize(asdict(claim))
    raw_record = OperationalKnowledgeProtectedInspectionService._normalize(asdict(grant.record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert (
        PostgreSQLOperationalKnowledgeProtectedInspectionRepository._claim_to_domain(raw_claim)
        == claim
    )
    assert (
        PostgreSQLOperationalKnowledgeProtectedInspectionRepository._record_to_domain(raw_record)
        == grant.record
    )
    for hidden in (
        "lease_secret",
        "raw_subject_id",
        "reviewer_name",
        "reviewer_email",
        "directory_attributes",
        "draft_content",
        "idempotency_key",
        "browser_session_id",
    ):
        assert hidden not in raw_claim and hidden not in raw_record


def test_protected_inspection_api_sets_http_only_cookie_and_returns_minimized_metadata(
    tmp_path: Path,
) -> None:
    service, _, assignment, policy, _, _, assignment_parts = asyncio.run(
        protected_inspection_fixture()
    )
    assignment_service, _, _, _, _, _, review_parts = assignment_parts
    review_service, _, _, _, _, _, draft_parts = review_parts
    draft_service = draft_parts[0]
    source = draft_parts[6]
    evidence_service = source[1]
    evidence_parts = source[2]
    bounded = evidence_parts[5]
    bounded_service, authorization_service, target_service, runtime_service, brokerage_service = (
        bounded[:5]
    )
    runtime_fixture = bounded[5]
    (
        runtime_trust_service,
        enablement_service,
        validation_service,
        credential_assignment_service,
        target_configuration_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = domain_reviewer()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.operational-knowledge-protected-inspection-input.v1",
        "source_assignment_set_id": assignment.assignment_set_id,
        "source_assignment_set_digest": assignment.canonical_digest,
        "track_code": "review-track.domain",
        "inspection_policy_id": policy.policy_id,
        "inspection_policy_digest": policy.canonical_digest,
        "purpose": (
            "Open one short-lived domain-track inspection boundary without returning content."
        ),
        ACKNOWLEDGEMENT_FIELD: True,
    }
    content_policy = build_development_operational_knowledge_protected_content_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=datetime(2026, 8, 1, tzinfo=UTC),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    content_service = OperationalKnowledgeProtectedContentService(
        repository=InMemoryOperationalKnowledgeProtectedContentRepository(),
        source=service,
        policy_source=InMemoryOperationalKnowledgeProtectedContentPolicySource((content_policy,)),
        permission_authorizer=RecordingProtectedInspectionPermissionAuthorizer(),
        presenter=SyntheticOperationalKnowledgeProtectedContentPresenter(
            clock=lambda: assignment.created_at
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.created_at,
    )
    finding_policy = build_development_operational_knowledge_review_finding_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=datetime(2026, 8, 1, tzinfo=UTC),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    finding_recorder = SyntheticOperationalKnowledgeReviewFindingRecorder(
        clock=lambda: assignment.created_at
    )
    finding_service = OperationalKnowledgeReviewFindingService(
        repository=InMemoryOperationalKnowledgeReviewFindingRepository(),
        source=content_service,
        policy_source=InMemoryOperationalKnowledgeReviewFindingPolicySource((finding_policy,)),
        permission_authorizer=RecordingProtectedInspectionPermissionAuthorizer(),
        recorder=finding_recorder,
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.created_at,
    )
    finding_presentation_policy = (
        build_development_operational_knowledge_finding_presentation_policy(
            organization_id=assignment.organization_id,
            environment_id=assignment.environment_id,
            issued_at=datetime(2026, 8, 1, tzinfo=UTC),
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
    )
    finding_presentation_service = OperationalKnowledgeFindingPresentationService(
        repository=InMemoryOperationalKnowledgeFindingPresentationRepository(),
        source=finding_service,
        policy_source=InMemoryOperationalKnowledgeFindingPresentationPolicySource(
            (finding_presentation_policy,)
        ),
        permission_authorizer=RecordingProtectedInspectionPermissionAuthorizer(),
        presenter=SyntheticOperationalKnowledgeFindingPresenter(
            recorder=finding_recorder, clock=lambda: assignment.created_at
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.created_at,
    )
    review_decision_policy = build_development_operational_knowledge_track_review_decision_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=datetime(2026, 8, 1, tzinfo=UTC),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    review_decision_service = OperationalKnowledgeTrackReviewDecisionService(
        repository=InMemoryOperationalKnowledgeTrackReviewDecisionRepository(),
        source=finding_presentation_service,
        policy_source=InMemoryOperationalKnowledgeTrackReviewDecisionPolicySource(
            (review_decision_policy,)
        ),
        permission_authorizer=RecordingProtectedInspectionPermissionAuthorizer(),
        attestor=SyntheticOperationalKnowledgeTrackReviewDecisionAttestor(
            clock=lambda: assignment.created_at
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.created_at,
    )
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=instance_service,
            target_configuration_service=target_configuration_service,
            credential_assignment_service=credential_assignment_service,
            configuration_validation_service=validation_service,
            capability_enablement_service=enablement_service,
            runtime_trust_service=runtime_trust_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=runtime_service,
            target_session_service=target_service,
            invocation_authorization_service=authorization_service,
            bounded_invocation_service=bounded_service,
            invocation_evidence_service=evidence_service,
            operational_evidence_knowledge_draft_service=draft_service,
            operational_knowledge_review_request_service=review_service,
            operational_knowledge_reviewer_assignment_service=assignment_service,
            operational_knowledge_protected_inspection_service=service,
            operational_knowledge_protected_content_service=content_service,
            operational_knowledge_review_finding_service=finding_service,
            operational_knowledge_finding_presentation_service=(finding_presentation_service),
            operational_knowledge_track_review_decision_service=review_decision_service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/knowledge/protected-inspections/leases"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "lease-api-1"})
        forbidden = client.post(
            endpoint,
            json={**payload, "lease_secret": "caller-selected"},
            headers={
                "Idempotency-Key": "lease-api-2",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "lease-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        lease_id = created.json()["data"]["lease_id"]
        read = client.get(f"{endpoint}/{lease_id}")
        content = client.post(
            f"{endpoint}/{lease_id}/presentations",
            json={
                "schema_version": "atlas.operational-knowledge-protected-content-input.v1",
                "source_lease_digest": created.json()["data"]["canonical_digest"],
                "presentation_policy_id": content_policy.policy_id,
                "presentation_policy_digest": content_policy.canonical_digest,
                "purpose": (
                    "Inspect the exact assigned-track operational knowledge snapshot in a "
                    "read-only boundary."
                ),
                "acknowledged_sensitive_read_only_content_grants_no_review_authority": True,
            },
            headers={
                "Idempotency-Key": "protected-content-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        content_data = content.json()["data"]
        finding = client.post(
            f"{endpoint}/{lease_id}/presentations/{content_data['presentation_id']}/findings",
            json={
                "schema_version": "atlas.operational-knowledge-review-finding-input.v1",
                "source_presentation_digest": content_data["canonical_digest"],
                "finding_policy_id": finding_policy.policy_id,
                "finding_policy_digest": finding_policy.canonical_digest,
                "findings": [
                    {
                        "category_code": "finding-category.accuracy",
                        "severity_code": "finding-severity.material",
                        "summary": "The controller count conflicts with the inventory evidence.",
                        "detail": (
                            "The protected snapshot reports one controller while collected "
                            "inventory evidence reports two."
                        ),
                    }
                ],
                "purpose": (
                    "Record the domain review observation without creating a review decision."
                ),
                "acknowledged_evidence_was_reviewed": True,
                "acknowledged_finding_is_not_a_review_decision": True,
            },
            headers={
                "Idempotency-Key": "review-finding-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        finding_data = finding.json()["data"]
        finding_presentation_endpoint = (
            f"{endpoint}/{lease_id}/presentations/{content_data['presentation_id']}"
            f"/findings/{finding_data['finding_packet_id']}/presentations"
        )
        finding_presentation_payload = {
            "schema_version": "atlas.operational-knowledge-finding-presentation-input.v1",
            "source_finding_digest": finding_data["canonical_digest"],
            "presentation_policy_id": finding_presentation_policy.policy_id,
            "presentation_policy_digest": finding_presentation_policy.canonical_digest,
            "purpose": "Inspect the exact sealed findings before recording a domain decision.",
            "acknowledged_findings_are_sensitive": True,
            "acknowledged_finding_presentation_is_not_a_review_decision": True,
        }
        finding_presentation_denied = client.post(
            finding_presentation_endpoint,
            json=finding_presentation_payload,
            headers={"Idempotency-Key": "finding-presentation-api-denied"},
        )
        finding_presentation_forbidden = client.post(
            finding_presentation_endpoint,
            json={**finding_presentation_payload, "finding_artifact_id": "caller-selected"},
            headers={
                "Idempotency-Key": "finding-presentation-api-forbidden",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        finding_presentation = client.post(
            finding_presentation_endpoint,
            json=finding_presentation_payload,
            headers={
                "Idempotency-Key": "finding-presentation-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        finding_presentation_data = finding_presentation.json()["data"]
        finding_replay = client.get(
            f"{endpoint}/{lease_id}/presentations/{content_data['presentation_id']}"
            f"/findings/{finding_data['finding_packet_id']}/presentations/"
            f"{finding_presentation_data['finding_presentation_id']}"
        )
        decision_endpoint = (
            f"{endpoint}/{lease_id}/presentations/{content_data['presentation_id']}"
            f"/findings/{finding_data['finding_packet_id']}/presentations/"
            f"{finding_presentation_data['finding_presentation_id']}/decisions"
        )
        decision_payload = {
            "schema_version": "atlas.operational-knowledge-track-review-decision-input.v1",
            "source_finding_presentation_digest": finding_presentation_data["canonical_digest"],
            "decision_policy_id": review_decision_policy.policy_id,
            "decision_policy_digest": review_decision_policy.canonical_digest,
            "disposition_code": "review-disposition.changes-required",
            "basis_codes": [
                "review-basis.technical-accuracy",
                "review-basis.evidence-quality",
            ],
            "purpose": "Record the accountable domain review decision for this exact packet.",
            "acknowledged_exact_findings_reviewed": True,
            "acknowledged_human_track_decision": True,
            "acknowledged_no_approval_or_operational_authority": True,
        }
        decision_denied = client.post(
            decision_endpoint,
            json=decision_payload,
            headers={"Idempotency-Key": "review-decision-api-denied"},
        )
        decision_forbidden = client.post(
            decision_endpoint,
            json={**decision_payload, "finding_summary": "caller-selected"},
            headers={
                "Idempotency-Key": "review-decision-api-forbidden",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        decision = client.post(
            decision_endpoint,
            json=decision_payload,
            headers={
                "Idempotency-Key": "review-decision-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        decision_data = decision.json()["data"]
        decision_replay = client.get(f"{decision_endpoint}/{decision_data['decision_id']}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert content.status_code == 201, content.text
    assert finding.status_code == 201, finding.text
    assert finding_presentation_denied.status_code == 403
    assert finding_presentation_forbidden.status_code == 422
    assert finding_presentation.status_code == 201, finding_presentation.text
    assert finding_replay.status_code == 200, finding_replay.text
    assert decision_denied.status_code == 403
    assert decision_forbidden.status_code == 422
    assert decision.status_code == 201, decision.text
    assert decision_replay.status_code == 200, decision_replay.text
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    assert content.headers["Cache-Control"] == "no-store, max-age=0"
    cookie = created.headers["Set-Cookie"]
    assert "atlas_knowledge_inspection_domain=" in cookie
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "Path=/api/v1/knowledge/protected-inspections" in cookie
    data = created.json()["data"]
    assert data["content_inspection_opened"] is True
    assert data["content_disclosed"] is False and data["content_bytes_read"] == 0
    assert data["domain_review_completed"] is False
    assert data["execution_authorized"] is False
    for hidden in (
        "lease_secret",
        "lease_secret_digest",
        "browser_session_id",
        "browser_session_binding_digest",
        "raw_subject_id",
        "reviewer_name",
        "directory_attributes",
        "draft_content",
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
    ):
        assert hidden not in data
    assert content_data["content"].startswith("Operational knowledge review snapshot")
    assert content_data["output_media_type"] == "media-type.text-plain"
    assert content_data["redaction_applied"] is True
    assert finding.headers["Cache-Control"] == "no-store, max-age=0"
    assert finding_data["finding_recorded"] is True
    assert finding_data["domain_finding_recorded"] is True
    assert finding_data["domain_review_completed"] is False
    assert finding_data["knowledge_approved"] is False
    assert finding_data["execution_authorized"] is False
    for hidden in (
        "summary",
        "detail",
        "finding_artifact_id",
        "lease_holder_subject_digest",
        "browser_session_binding_digest",
    ):
        assert hidden not in finding_data
    assert finding_presentation.headers["Cache-Control"] == "no-store, max-age=0"
    assert finding_presentation.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert finding_presentation_data["finding_presented"] is True
    assert finding_presentation_data["domain_review_completed"] is False
    assert finding_presentation_data["knowledge_approved"] is False
    assert finding_presentation_data["execution_authorized"] is False
    assert finding_presentation_data["findings"] == [
        {
            "category_code": "finding-category.accuracy",
            "severity_code": "finding-severity.material",
            "summary": "The controller count conflicts with the inventory evidence.",
            "detail": (
                "The protected snapshot reports one controller while collected inventory "
                "evidence reports two."
            ),
        }
    ]
    assert finding_replay.json()["data"]["findings"] == finding_presentation_data["findings"]
    for hidden in (
        "source_finding_artifact_id",
        "lease_holder_subject_digest",
        "browser_session_binding_digest",
        "source_cleanup_digest",
        "presentation_cleanup_digest",
    ):
        assert hidden not in finding_presentation_data
    assert decision.headers["Cache-Control"] == "no-store, max-age=0"
    assert decision.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert decision_data["disposition_code"] == "review-disposition.changes-required"
    assert decision_data["domain_review_completed"] is True
    assert decision_data["domain_review_passed"] is False
    assert decision_data["correction_required"] is True
    assert decision_data["correction_created"] is False
    assert decision_data["all_tracks_passed"] is False
    assert decision_data["knowledge_approved"] is False
    assert decision_data["retrieval_published"] is False
    assert decision_data["execution_authorized"] is False
    assert decision_replay.json()["data"]["canonical_digest"] == decision_data["canonical_digest"]
    for hidden in (
        "findings",
        "summary",
        "detail",
        "decided_by_subject_digest",
        "browser_session_binding_digest",
        "source_finding_digest",
        "source_lease_digest",
        "basis_digest",
    ):
        assert hidden not in decision_data
    assert content_data["domain_review_completed"] is False
    assert content_data["knowledge_approved"] is False
    assert content_data["execution_authorized"] is False
    for hidden in (
        "lease_secret",
        "lease_secret_digest",
        "browser_session_id",
        "browser_session_binding_digest",
        "lease_holder_subject_digest",
        "draft_artifact_id",
        "draft_content_digest",
        "request_binding_digest",
        "idempotency_digest",
    ):
        assert hidden not in content_data
