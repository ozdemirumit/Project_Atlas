from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_draft_review_request import request_review, review_request_fixture
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_target_session import development_target_session_operator, target_session_operator

from atlas.api.app import create_app
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.reviewer_assignment_memory import (
    InMemoryOperationalKnowledgeReviewerAssignmentPolicySource,
    InMemoryOperationalKnowledgeReviewerAssignmentRepository,
)
from atlas.modules.knowledge.adapters.reviewer_assignment_postgres import (
    PostgreSQLOperationalKnowledgeReviewerAssignmentRepository,
)
from atlas.modules.knowledge.adapters.reviewer_assignment_synthetic import (
    SyntheticOperationalKnowledgeReviewerAssignmentAdapter,
)
from atlas.modules.knowledge.application.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentService,
    _signed_policy,
    build_development_operational_knowledge_reviewer_assignment_policy,
)
from atlas.modules.knowledge.application.reviewer_assignment_ports import (
    OperationalKnowledgeReviewerAssignmentError,
    OperationalKnowledgeReviewerAssignmentUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentInstruction,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentReceipt,
    OperationalKnowledgeReviewerAssignmentRecord,
)

ACKNOWLEDGEMENT_FIELD = "acknowledged_assignment_opens_no_content_and_records_no_decision"


class RecordingReviewerAssignmentPermissionAuthorizer:
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
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_permission_denied"
            )


class UncertainReviewerAssignmentAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def assign_reviewers(
        self, instruction: OperationalKnowledgeReviewerAssignmentInstruction
    ) -> OperationalKnowledgeReviewerAssignmentReceipt:
        del instruction
        self.calls += 1
        raise OperationalKnowledgeReviewerAssignmentUncertainError(
            "operational_knowledge_reviewer_assignment_directory_outcome_uncertain"
        )


class AlteredReviewerAssignmentReceiptAdapter(
    SyntheticOperationalKnowledgeReviewerAssignmentAdapter
):
    async def assign_reviewers(
        self, instruction: OperationalKnowledgeReviewerAssignmentInstruction
    ) -> OperationalKnowledgeReviewerAssignmentReceipt:
        receipt = await super().assign_reviewers(instruction)
        altered = replace(
            receipt,
            routing_digest="f" * 64,
        )
        payload = cast(dict[str, object], asdict(altered))
        payload.pop("canonical_digest")
        return replace(
            altered,
            canonical_digest=OperationalKnowledgeReviewerAssignmentService._digest(
                OperationalKnowledgeReviewerAssignmentService._normalize(payload)
            ),
        )


class BlockingReviewerAssignmentAdapter(SyntheticOperationalKnowledgeReviewerAssignmentAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def assign_reviewers(
        self, instruction: OperationalKnowledgeReviewerAssignmentInstruction
    ) -> OperationalKnowledgeReviewerAssignmentReceipt:
        self.started.set()
        await self.release.wait()
        return await super().assign_reviewers(instruction)


async def reviewer_assignment_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingReviewerAssignmentPermissionAuthorizer | None = None,
    adapter: SyntheticOperationalKnowledgeReviewerAssignmentAdapter
    | UncertainReviewerAssignmentAdapter
    | AlteredReviewerAssignmentReceiptAdapter
    | BlockingReviewerAssignmentAdapter
    | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    OperationalKnowledgeReviewerAssignmentService,
    InMemoryOperationalKnowledgeReviewerAssignmentRepository,
    OperationalKnowledgeReviewRequestRecord,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    RecordingReviewerAssignmentPermissionAuthorizer,
    SyntheticOperationalKnowledgeReviewerAssignmentAdapter
    | UncertainReviewerAssignmentAdapter
    | AlteredReviewerAssignmentReceiptAdapter
    | BlockingReviewerAssignmentAdapter,
    tuple[Any, ...],
]:
    review_parts = await review_request_fixture()
    review_service, _, draft, review_policy, *_ = review_parts
    review_request = await request_review(review_service, draft, review_policy)
    policy = build_development_operational_knowledge_reviewer_assignment_policy(
        organization_id=review_request.organization_id,
        environment_id=review_request.environment_id,
        issued_at=review_request.created_at - timedelta(hours=1),
        expires_at=review_request.created_at + timedelta(days=1),
    )
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_policy(policy))
    repository = InMemoryOperationalKnowledgeReviewerAssignmentRepository()
    authorizer = permission_authorizer or RecordingReviewerAssignmentPermissionAuthorizer()
    resolved_adapter = adapter or SyntheticOperationalKnowledgeReviewerAssignmentAdapter(
        clock=lambda: review_request.created_at
    )
    service = OperationalKnowledgeReviewerAssignmentService(
        repository=repository,
        source=review_service,
        policy_source=InMemoryOperationalKnowledgeReviewerAssignmentPolicySource((policy,)),
        permission_authorizer=authorizer,
        adapter=resolved_adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=review_request.environment_id,
        clock=lambda: review_request.created_at,
    )
    return (
        service,
        repository,
        review_request,
        policy,
        authorizer,
        resolved_adapter,
        review_parts,
    )


async def assign_reviewers(
    service: OperationalKnowledgeReviewerAssignmentService,
    review_request: OperationalKnowledgeReviewRequestRecord,
    policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "knowledge-reviewer-assignment-001",
) -> OperationalKnowledgeReviewerAssignmentRecord:
    return await service.create(
        actor=actor or target_session_operator("subject.knowledge-review-coordinator"),
        source_review_request_id=review_request.review_request_id,
        source_review_request_digest=review_request.canonical_digest,
        assignment_policy_id=policy.policy_id,
        assignment_policy_digest=policy.canonical_digest,
        purpose="Assign distinct eligible domain and security reviewers without exposing identity.",
        assignment_only_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_knowledge_reviewer_assignment",
    )


@pytest.mark.asyncio
async def test_reviewer_assignment_is_minimized_distinct_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, review_request, policy, authorizer, adapter, _ = await reviewer_assignment_fixture(
        audit_sink=audit
    )
    record = await assign_reviewers(service, review_request, policy)
    repeated = await assign_reviewers(service, review_request, policy)

    assert record.knowledge_lifecycle == "reviewer_assigned"
    assert record.reviewer_assigned and record.immutable_assignments_confirmed
    assert record.domain_status == record.security_status == "assigned"
    assert record.domain_assignment_id != record.security_assignment_id
    assert record.domain_reviewer_subject_digest != record.security_reviewer_subject_digest
    assert not record.content_inspection_opened
    assert not record.domain_review_completed and not record.security_review_completed
    assert not record.knowledge_approved and not record.retrieval_published
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and repeated.assignment_set_id == record.assignment_set_id
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewerAssignmentAdapter)
    assert adapter.call_count == 1
    assert authorizer.calls == [(review_request.organization_id, review_request.environment_id)]
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_reviewer_assignment_requested",
        "operational_knowledge_review_request_claimed_for_assignment",
        "operational_knowledge_reviewers_assigned",
    ]


@pytest.mark.asyncio
async def test_reviewer_assignment_accepts_development_identity_under_default_policy() -> None:
    service, _, review_request, policy, _, _, _ = await reviewer_assignment_fixture()
    actor = development_target_session_operator("subject.knowledge-review-coordinator")

    record = await assign_reviewers(service, review_request, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.requested_by == actor.subject_id


@pytest.mark.parametrize(
    "required_assurance_level",
    [AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED],
)
@pytest.mark.asyncio
async def test_reviewer_assignment_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, review_request, policy, authorizer, adapter, _ = await reviewer_assignment_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="assurance_required"):
        await assign_reviewers(
            service,
            review_request,
            policy,
            actor=development_target_session_operator("subject.knowledge-review-coordinator"),
        )

    assert authorizer.calls == []
    assert getattr(adapter, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_denies_non_human_identity() -> None:
    service, _, review_request, policy, authorizer, adapter, _ = await reviewer_assignment_fixture()
    actor = replace(
        development_target_session_operator("subject.knowledge-review-coordinator"),
        kind=SubjectKind.SERVICE,
    )

    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="human_required"):
        await assign_reviewers(service, review_request, policy, actor=actor)

    assert authorizer.calls == []
    assert getattr(adapter, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_atomically_rejects_concurrent_second_claim() -> None:
    adapter = BlockingReviewerAssignmentAdapter()
    service, _, review_request, policy, _, _, _ = await reviewer_assignment_fixture(adapter=adapter)
    first = asyncio.create_task(
        assign_reviewers(service, review_request, policy, key="assign-first")
    )
    await adapter.started.wait()
    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="idempotency_conflict"):
        await assign_reviewers(service, review_request, policy, key="assign-second")
    adapter.release.set()
    record = await first
    assert record.reviewer_assigned and adapter.call_count == 1


@pytest.mark.asyncio
async def test_reviewer_assignment_permission_denial_happens_before_claim() -> None:
    service, repository, review_request, policy, _, adapter, _ = await reviewer_assignment_fixture(
        permission_authorizer=RecordingReviewerAssignmentPermissionAuthorizer(deny=True)
    )
    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="permission_denied"):
        await assign_reviewers(service, review_request, policy)
    assert (
        await repository.get_claim_by_source(
            source_review_request_id=review_request.review_request_id
        )
        is None
    )
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewerAssignmentAdapter)
    assert adapter.call_count == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_uncertain_or_invalid_receipt_stays_claimed() -> None:
    uncertain = UncertainReviewerAssignmentAdapter()
    service, repository, review_request, policy, _, _, _ = await reviewer_assignment_fixture(
        adapter=uncertain
    )
    with pytest.raises(OperationalKnowledgeReviewerAssignmentUncertainError, match="uncertain"):
        await assign_reviewers(service, review_request, policy)
    assert uncertain.calls == 1
    assert await repository.get_claim_by_source(
        source_review_request_id=review_request.review_request_id
    )
    with pytest.raises(OperationalKnowledgeReviewerAssignmentError, match="already_claimed"):
        await assign_reviewers(service, review_request, policy)

    altered = AlteredReviewerAssignmentReceiptAdapter(clock=lambda: review_request.created_at)
    (
        altered_service,
        _,
        altered_request,
        altered_policy,
        _,
        _,
        _,
    ) = await reviewer_assignment_fixture(adapter=altered)
    with pytest.raises(
        OperationalKnowledgeReviewerAssignmentUncertainError, match="receipt_invalid"
    ):
        await assign_reviewers(altered_service, altered_request, altered_policy)


@pytest.mark.asyncio
async def test_reviewer_assignment_claim_audit_failure_stays_claimed() -> None:
    service, repository, review_request, policy, _, adapter, _ = await reviewer_assignment_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await assign_reviewers(service, review_request, policy)
    assert await repository.get_claim_by_source(
        source_review_request_id=review_request.review_request_id
    )
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewerAssignmentAdapter)
    assert adapter.call_count == 0


@pytest.mark.asyncio
async def test_reviewer_assignment_postgres_round_trip_excludes_identity_and_content() -> None:
    service, repository, review_request, policy, _, _, _ = await reviewer_assignment_fixture()
    record = await assign_reviewers(service, review_request, policy)
    claim = await repository.get_claim_by_source(
        source_review_request_id=review_request.review_request_id
    )
    assert claim is not None
    raw_claim = OperationalKnowledgeReviewerAssignmentService._normalize(asdict(claim))
    raw_record = OperationalKnowledgeReviewerAssignmentService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert (
        PostgreSQLOperationalKnowledgeReviewerAssignmentRepository._claim_to_domain(raw_claim)
        == claim
    )
    assert (
        PostgreSQLOperationalKnowledgeReviewerAssignmentRepository._record_to_domain(raw_record)
        == record
    )
    for hidden in (
        "draft_content",
        "evidence_content",
        "excerpt",
        "domain_reviewer_id",
        "security_reviewer_id",
        "reviewer_group",
        "directory_attributes",
        "idempotency_key",
    ):
        assert hidden not in raw_claim and hidden not in raw_record


def test_reviewer_assignment_api_forbids_identity_selection_and_returns_minimized_metadata(
    tmp_path: Path,
) -> None:
    service, _, review_request, policy, _, _, review_parts = asyncio.run(
        reviewer_assignment_fixture()
    )
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
    subject = target_session_operator("subject.knowledge-review-coordinator")
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.operational-knowledge-reviewer-assignment-input.v1",
        "source_review_request_id": review_request.review_request_id,
        "source_review_request_digest": review_request.canonical_digest,
        "assignment_policy_id": policy.policy_id,
        "assignment_policy_digest": policy.canonical_digest,
        "purpose": (
            "Assign distinct eligible domain and security reviewers without exposing identity."
        ),
        ACKNOWLEDGEMENT_FIELD: True,
    }
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
            operational_knowledge_reviewer_assignment_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/knowledge/operational-reviewer-assignments"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "assign-api-1"})
        forbidden = client.post(
            endpoint,
            json={**payload, "domain_reviewer_id": "subject.self-selected-reviewer"},
            headers={
                "Idempotency-Key": "assign-api-2",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "assign-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        assignment_set_id = created.json()["data"]["assignment_set_id"]
        read = client.get(f"{endpoint}/{assignment_set_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["knowledge_lifecycle"] == "reviewer_assigned"
    assert data["reviewer_assigned"] is True
    assert data["content_inspection_opened"] is False
    assert data["knowledge_approved"] is False
    assert data["retrieval_published"] is False
    for hidden in (
        "domain_reviewer_id",
        "security_reviewer_id",
        "reviewer_group",
        "directory_attributes",
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
    ):
        assert hidden not in data
