from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from test_package_acquisition import CollectingAuditSink
from test_protected_content import (
    development_domain_reviewer,
    present_content,
    protected_content_fixture,
)
from test_protected_inspection import domain_reviewer
from test_runtime_activation import FailSecondAuditSink

from atlas.api.review_finding_schemas import OperationalKnowledgeReviewFindingData
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.review_finding_memory import (
    InMemoryOperationalKnowledgeReviewFindingPolicySource,
    InMemoryOperationalKnowledgeReviewFindingRepository,
)
from atlas.modules.knowledge.adapters.review_finding_postgres import (
    PostgreSQLOperationalKnowledgeReviewFindingRepository,
)
from atlas.modules.knowledge.adapters.review_finding_synthetic import (
    SyntheticOperationalKnowledgeReviewFindingRecorder,
    UnavailableOperationalKnowledgeReviewFindingRecorder,
)
from atlas.modules.knowledge.application.review_finding import (
    OperationalKnowledgeReviewFindingService,
    build_development_operational_knowledge_review_finding_policy,
)
from atlas.modules.knowledge.application.review_finding_ports import (
    OperationalKnowledgeReviewFindingError,
    OperationalKnowledgeReviewFindingRecorder,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentRecord,
)
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingInstruction,
    OperationalKnowledgeReviewFindingItem,
    OperationalKnowledgeReviewFindingPolicySnapshot,
    OperationalKnowledgeReviewFindingReceipt,
    OperationalKnowledgeReviewFindingRecord,
)


class RecordingReviewFindingPermissionAuthorizer:
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
            raise OperationalKnowledgeReviewFindingError(
                "operational_knowledge_review_finding_permission_denied"
            )


class BlockingReviewFindingRecorder(SyntheticOperationalKnowledgeReviewFindingRecorder):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def record(
        self, instruction: OperationalKnowledgeReviewFindingInstruction
    ) -> OperationalKnowledgeReviewFindingReceipt:
        self.started.set()
        await self.release.wait()
        self._clock = lambda: instruction.expires_at - timedelta(minutes=1)
        return await super().record(instruction)


class AlteredReviewFindingRecorder(SyntheticOperationalKnowledgeReviewFindingRecorder):
    async def record(
        self, instruction: OperationalKnowledgeReviewFindingInstruction
    ) -> OperationalKnowledgeReviewFindingReceipt:
        self._clock = lambda: instruction.expires_at - timedelta(minutes=1)
        receipt = await super().record(instruction)
        altered = replace(receipt, track_code="review-track.security")
        return replace(
            altered,
            canonical_digest=OperationalKnowledgeReviewFindingService._receipt_digest(altered),
        )


async def review_finding_fixture(
    *,
    recorder: OperationalKnowledgeReviewFindingRecorder | None = None,
    authorizer: RecordingReviewFindingPermissionAuthorizer | None = None,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    clock_offset: timedelta = timedelta(),
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    OperationalKnowledgeReviewFindingService,
    InMemoryOperationalKnowledgeReviewFindingRepository,
    OperationalKnowledgeProtectedContentRecord,
    str,
    OperationalKnowledgeReviewFindingPolicySnapshot,
    RecordingReviewFindingPermissionAuthorizer,
    CollectingAuditSink | FailSecondAuditSink,
]:
    content_service, _, lease, secret, content_policy, *_ = await protected_content_fixture()
    presentation = await present_content(content_service, lease, secret, content_policy)
    policy = build_development_operational_knowledge_review_finding_policy(
        organization_id=presentation.record.organization_id,
        environment_id=presentation.record.environment_id,
        issued_at=presentation.record.presented_at,
        expires_at=presentation.record.expires_at,
    )
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(
            policy,
            canonical_digest=OperationalKnowledgeReviewFindingService._digest(
                OperationalKnowledgeReviewFindingService._policy_payload(policy)
            ),
        )
    repository = InMemoryOperationalKnowledgeReviewFindingRepository()
    permission_authorizer = authorizer or RecordingReviewFindingPermissionAuthorizer()
    audit = audit_sink or CollectingAuditSink()
    service = OperationalKnowledgeReviewFindingService(
        repository=repository,
        source=content_service,
        policy_source=InMemoryOperationalKnowledgeReviewFindingPolicySource((policy,)),
        permission_authorizer=permission_authorizer,
        recorder=recorder
        or SyntheticOperationalKnowledgeReviewFindingRecorder(
            clock=lambda: presentation.record.presented_at + clock_offset
        ),
        audit_sink=audit,
        environment_id=presentation.record.environment_id,
        clock=lambda: presentation.record.presented_at + clock_offset,
    )
    return (
        service,
        repository,
        presentation.record,
        secret,
        policy,
        permission_authorizer,
        audit,
    )


def domain_finding() -> tuple[OperationalKnowledgeReviewFindingItem, ...]:
    return (
        OperationalKnowledgeReviewFindingItem(
            category_code="finding-category.accuracy",
            severity_code="finding-severity.material",
            summary="The stated controller count conflicts with the collected inventory.",
            detail=(
                "The presented evidence reports one controller while inventory evidence "
                "reports two."
            ),
        ),
    )


async def record_finding(
    service: OperationalKnowledgeReviewFindingService,
    presentation: OperationalKnowledgeProtectedContentRecord,
    secret: str,
    policy: OperationalKnowledgeReviewFindingPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    findings: tuple[OperationalKnowledgeReviewFindingItem, ...] | None = None,
    idempotency_key: str = "knowledge-review-finding-001",
) -> OperationalKnowledgeReviewFindingRecord:
    return await service.create(
        actor=actor or domain_reviewer(),
        source_lease_id=presentation.source_lease_id,
        source_presentation_id=presentation.presentation_id,
        source_presentation_digest=presentation.canonical_digest,
        finding_policy_id=policy.policy_id,
        finding_policy_digest=policy.canonical_digest,
        findings=findings or domain_finding(),
        purpose="Record a bounded domain finding without creating a review decision.",
        evidence_review_acknowledged=True,
        finding_is_not_decision_acknowledged=True,
        browser_session_id="session_knowledge_inspection_001",
        lease_secrets={"review-track.domain": secret},
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_review_finding",
    )


@pytest.mark.asyncio
async def test_review_finding_is_immutable_metadata_only_and_idempotent() -> None:
    (
        service,
        repository,
        presentation,
        secret,
        policy,
        authorizer,
        audit,
    ) = await review_finding_fixture()
    record = await record_finding(service, presentation, secret, policy)
    repeated = await record_finding(service, presentation, secret, policy)

    assert record.finding_recorded and record.domain_finding_recorded
    assert not record.security_finding_recorded
    assert not record.domain_review_completed
    assert not record.knowledge_approved
    assert not record.execution_authorized
    assert repeated.reused
    assert repeated.canonical_digest == record.canonical_digest
    persisted = await repository.get(finding_packet_id=record.finding_packet_id)
    assert persisted == record
    assert "summary" not in asdict(record)
    assert "detail" not in asdict(record)
    public = OperationalKnowledgeReviewFindingData.from_record(record).model_dump()
    assert "finding_artifact_id" not in public
    assert "lease_holder_subject_digest" not in public
    assert "browser_session_binding_digest" not in public
    assert len(authorizer.calls) == 2
    assert isinstance(audit, CollectingAuditSink)
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_review_finding_requested",
        "operational_knowledge_review_finding_claimed",
        "operational_knowledge_review_finding_recorded",
    ]


@pytest.mark.asyncio
async def test_review_finding_accepts_development_identity_under_default_policy() -> None:
    service, _, presentation, secret, policy, *_ = await review_finding_fixture()

    record = await record_finding(
        service,
        presentation,
        secret,
        policy,
        actor=development_domain_reviewer(),
    )

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.track_code == "review-track.domain"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required_assurance_level",
    (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED),
)
async def test_review_finding_enforces_explicit_step_up_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, repository, presentation, secret, policy, authorizer, _ = await review_finding_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(OperationalKnowledgeReviewFindingError, match="source_invalid"):
        await record_finding(
            service,
            presentation,
            secret,
            policy,
            actor=development_domain_reviewer(),
        )

    assert authorizer.calls == []
    assert (
        await repository.get_claim_by_source_presentation(
            source_presentation_id=presentation.presentation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_review_finding_rejects_non_human_identity() -> None:
    (
        service,
        repository,
        presentation,
        secret,
        policy,
        authorizer,
        _,
    ) = await review_finding_fixture()
    actor = replace(development_domain_reviewer(), kind=SubjectKind.SERVICE)

    with pytest.raises(OperationalKnowledgeReviewFindingError, match="human_required"):
        await record_finding(service, presentation, secret, policy, actor=actor)

    assert authorizer.calls == []
    assert (
        await repository.get_claim_by_source_presentation(
            source_presentation_id=presentation.presentation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_review_finding_rejects_wrong_track_category_before_claim() -> None:
    service, repository, presentation, secret, policy, *_ = await review_finding_fixture()
    security_item = OperationalKnowledgeReviewFindingItem(
        category_code="finding-category.malware",
        severity_code="finding-severity.critical",
        summary="A security-only category must not enter the domain review track.",
        detail="Track category allowlists prevent the finding from crossing reviewer duties.",
    )

    with pytest.raises(OperationalKnowledgeReviewFindingError, match="items_invalid"):
        await record_finding(service, presentation, secret, policy, findings=(security_item,))
    assert (
        await repository.get_claim_by_source_presentation(
            source_presentation_id=presentation.presentation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_review_finding_permission_denial_happens_before_claim() -> None:
    authorizer = RecordingReviewFindingPermissionAuthorizer(deny=True)
    service, repository, presentation, secret, policy, *_ = await review_finding_fixture(
        authorizer=authorizer
    )
    with pytest.raises(OperationalKnowledgeReviewFindingError, match="permission_denied"):
        await record_finding(service, presentation, secret, policy)
    assert (
        await repository.get_claim_by_source_presentation(
            source_presentation_id=presentation.presentation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_review_finding_rejects_wrong_cookie_assignee_and_expiry_before_claim() -> None:
    service, repository, presentation, secret, policy, *_ = await review_finding_fixture()
    with pytest.raises(OperationalKnowledgeReviewFindingError, match="source_not_found"):
        await service.create(
            actor=domain_reviewer(),
            source_lease_id=presentation.source_lease_id,
            source_presentation_id=presentation.presentation_id,
            source_presentation_digest=presentation.canonical_digest,
            finding_policy_id=policy.policy_id,
            finding_policy_digest=policy.canonical_digest,
            findings=domain_finding(),
            purpose="Record a bounded domain finding without creating a review decision.",
            evidence_review_acknowledged=True,
            finding_is_not_decision_acknowledged=True,
            browser_session_id="session_knowledge_inspection_001",
            lease_secrets={"review-track.domain": "wrong-lease-secret"},
            idempotency_key="knowledge-review-finding-wrong-cookie",
            correlation_id="cor_knowledge_review_finding_wrong_cookie",
        )
    with pytest.raises(OperationalKnowledgeReviewFindingError, match="source_not_found"):
        await service.create(
            actor=replace(domain_reviewer(), subject_id="subject.synthetic-unassigned-reviewer"),
            source_lease_id=presentation.source_lease_id,
            source_presentation_id=presentation.presentation_id,
            source_presentation_digest=presentation.canonical_digest,
            finding_policy_id=policy.policy_id,
            finding_policy_digest=policy.canonical_digest,
            findings=domain_finding(),
            purpose="Record a bounded domain finding without creating a review decision.",
            evidence_review_acknowledged=True,
            finding_is_not_decision_acknowledged=True,
            browser_session_id="session_knowledge_inspection_001",
            lease_secrets={"review-track.domain": secret},
            idempotency_key="knowledge-review-finding-wrong-assignee",
            correlation_id="cor_knowledge_review_finding_wrong_assignee",
        )
    assert (
        await repository.get_claim_by_source_presentation(
            source_presentation_id=presentation.presentation_id
        )
        is None
    )

    (
        expired_service,
        expired_repository,
        expired_presentation,
        expired_secret,
        expired_policy,
        *_,
    ) = await review_finding_fixture(clock_offset=timedelta(minutes=11))
    with pytest.raises(OperationalKnowledgeReviewFindingError, match="source_invalid"):
        await record_finding(expired_service, expired_presentation, expired_secret, expired_policy)
    assert (
        await expired_repository.get_claim_by_source_presentation(
            source_presentation_id=expired_presentation.presentation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_failed_first_review_finding_stays_claimed() -> None:
    service, repository, presentation, secret, policy, *_, audit = await review_finding_fixture(
        recorder=UnavailableOperationalKnowledgeReviewFindingRecorder()
    )
    with pytest.raises(OperationalKnowledgeReviewFindingError, match="recorder_unavailable"):
        await record_finding(service, presentation, secret, policy)
    assert (
        await repository.get_claim_by_source_presentation(
            source_presentation_id=presentation.presentation_id
        )
        is not None
    )
    with pytest.raises(OperationalKnowledgeReviewFindingError, match="already_claimed"):
        await record_finding(service, presentation, secret, policy)
    assert isinstance(audit, CollectingAuditSink)
    assert audit.records[-1].result_code == "operational_knowledge_review_finding_failed"


@pytest.mark.asyncio
async def test_review_finding_rejects_altered_receipt_and_preserves_claim() -> None:
    service, repository, presentation, secret, policy, *_ = await review_finding_fixture(
        recorder=AlteredReviewFindingRecorder()
    )
    with pytest.raises(OperationalKnowledgeReviewFindingError, match="receipt_invalid"):
        await record_finding(service, presentation, secret, policy)
    assert (
        await repository.get_claim_by_source_presentation(
            source_presentation_id=presentation.presentation_id
        )
        is not None
    )
    assert (
        await repository.get_by_source_presentation(
            source_presentation_id=presentation.presentation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_review_finding_audit_failure_preserves_claim_and_blocks_recorder() -> None:
    audit = FailSecondAuditSink()
    recorder = SyntheticOperationalKnowledgeReviewFindingRecorder()
    service, repository, presentation, secret, policy, *_ = await review_finding_fixture(
        recorder=recorder, audit_sink=audit
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await record_finding(service, presentation, secret, policy)
    assert (
        await repository.get_claim_by_source_presentation(
            source_presentation_id=presentation.presentation_id
        )
        is not None
    )
    assert recorder.calls == []


@pytest.mark.asyncio
async def test_review_finding_atomically_rejects_concurrent_second_claim() -> None:
    recorder = BlockingReviewFindingRecorder()
    service, repository, presentation, secret, policy, *_ = await review_finding_fixture(
        recorder=recorder
    )
    first = asyncio.create_task(record_finding(service, presentation, secret, policy))
    await recorder.started.wait()
    with pytest.raises(OperationalKnowledgeReviewFindingError, match="idempotency_conflict"):
        await record_finding(
            service,
            presentation,
            secret,
            policy,
            idempotency_key="knowledge-review-finding-002",
        )
    recorder.release.set()
    record = await first
    assert await repository.get(finding_packet_id=record.finding_packet_id) == record


@pytest.mark.asyncio
async def test_review_finding_postgres_mapping_contains_no_finding_text() -> None:
    service, repository, presentation, secret, policy, *_ = await review_finding_fixture()
    record = await record_finding(service, presentation, secret, policy)
    claim = await repository.get_claim_by_source_presentation(
        source_presentation_id=presentation.presentation_id
    )
    assert claim is not None
    raw_claim = OperationalKnowledgeReviewFindingService._normalize(asdict(claim))
    raw_record = OperationalKnowledgeReviewFindingService._normalize(asdict(record))
    assert isinstance(raw_claim, dict)
    assert isinstance(raw_record, dict)
    assert (
        PostgreSQLOperationalKnowledgeReviewFindingRepository._claim_to_domain(raw_claim) == claim
    )
    assert (
        PostgreSQLOperationalKnowledgeReviewFindingRepository._record_to_domain(raw_record)
        == record
    )
    assert "summary" not in raw_record and "detail" not in raw_record
