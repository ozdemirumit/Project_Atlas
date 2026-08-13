from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from test_package_acquisition import CollectingAuditSink
from test_protected_content import development_domain_reviewer
from test_protected_inspection import domain_reviewer
from test_review_finding import (
    domain_finding,
    record_finding,
    review_finding_fixture,
)
from test_runtime_activation import FailSecondAuditSink

from atlas.api.finding_presentation_schemas import (
    OperationalKnowledgeFindingPresentationData,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.finding_presentation_memory import (
    InMemoryOperationalKnowledgeFindingPresentationPolicySource,
    InMemoryOperationalKnowledgeFindingPresentationRepository,
)
from atlas.modules.knowledge.adapters.finding_presentation_postgres import (
    PostgreSQLOperationalKnowledgeFindingPresentationRepository,
)
from atlas.modules.knowledge.adapters.finding_presentation_synthetic import (
    SyntheticOperationalKnowledgeFindingPresenter,
    UnavailableOperationalKnowledgeFindingPresenter,
)
from atlas.modules.knowledge.adapters.review_finding_synthetic import (
    SyntheticOperationalKnowledgeReviewFindingRecorder,
)
from atlas.modules.knowledge.application.finding_presentation import (
    OperationalKnowledgeFindingPresentationService,
    build_development_operational_knowledge_finding_presentation_policy,
)
from atlas.modules.knowledge.application.finding_presentation_ports import (
    OperationalKnowledgeFindingPresentationError,
)
from atlas.modules.knowledge.domain.finding_presentation import (
    OperationalKnowledgeFindingPresentationInstruction,
    OperationalKnowledgeFindingPresentationPolicySnapshot,
    OperationalKnowledgeFindingPresentationReceipt,
    OperationalKnowledgeFindingPresentationRecord,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentRecord,
)
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingRecord,
)


class RecordingFindingPresentationPermissionAuthorizer:
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
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_permission_denied"
            )


class BlockingFindingPresenter(SyntheticOperationalKnowledgeFindingPresenter):
    def __init__(self, *, recorder: SyntheticOperationalKnowledgeReviewFindingRecorder) -> None:
        super().__init__(recorder=recorder)
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def present(
        self, instruction: OperationalKnowledgeFindingPresentationInstruction
    ) -> OperationalKnowledgeFindingPresentationReceipt:
        self.started.set()
        await self.release.wait()
        return await super().present(instruction)


class AlteredFindingPresenter(SyntheticOperationalKnowledgeFindingPresenter):
    async def present(
        self, instruction: OperationalKnowledgeFindingPresentationInstruction
    ) -> OperationalKnowledgeFindingPresentationReceipt:
        self._clock = lambda: instruction.expires_at - timedelta(minutes=1)
        receipt = await super().present(instruction)
        altered = replace(receipt, finding_content_digest="f" * 64)
        return replace(
            altered,
            canonical_digest=OperationalKnowledgeFindingPresentationService._receipt_digest(
                altered
            ),
        )


async def finding_presentation_fixture(
    *,
    presenter_factory: type[SyntheticOperationalKnowledgeFindingPresenter] | None = None,
    authorizer: RecordingFindingPresentationPermissionAuthorizer | None = None,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    clock_offset: timedelta = timedelta(),
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    OperationalKnowledgeFindingPresentationService,
    InMemoryOperationalKnowledgeFindingPresentationRepository,
    OperationalKnowledgeProtectedContentRecord,
    OperationalKnowledgeReviewFindingRecord,
    str,
    OperationalKnowledgeFindingPresentationPolicySnapshot,
    SyntheticOperationalKnowledgeFindingPresenter,
    RecordingFindingPresentationPermissionAuthorizer,
    CollectingAuditSink | FailSecondAuditSink,
]:
    recorder = SyntheticOperationalKnowledgeReviewFindingRecorder()
    review_service, _, content, secret, finding_policy, *_ = await review_finding_fixture(
        recorder=recorder
    )
    recorder._clock = lambda: content.presented_at
    finding = await record_finding(review_service, content, secret, finding_policy)
    policy = build_development_operational_knowledge_finding_presentation_policy(
        organization_id=finding.organization_id,
        environment_id=finding.environment_id,
        issued_at=finding.created_at - timedelta(hours=1),
        expires_at=finding.expires_at,
    )
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(
            policy,
            canonical_digest=OperationalKnowledgeFindingPresentationService._digest(
                OperationalKnowledgeFindingPresentationService._policy_payload(policy)
            ),
        )
    presenter_type = presenter_factory or SyntheticOperationalKnowledgeFindingPresenter
    presenter = presenter_type(recorder=recorder)
    presenter._clock = lambda: finding.created_at + clock_offset
    repository = InMemoryOperationalKnowledgeFindingPresentationRepository()
    permission_authorizer = authorizer or RecordingFindingPresentationPermissionAuthorizer()
    audit = audit_sink or CollectingAuditSink()
    service = OperationalKnowledgeFindingPresentationService(
        repository=repository,
        source=review_service,
        policy_source=InMemoryOperationalKnowledgeFindingPresentationPolicySource((policy,)),
        permission_authorizer=permission_authorizer,
        presenter=presenter,
        audit_sink=audit,
        environment_id=finding.environment_id,
        clock=lambda: finding.created_at + clock_offset,
    )
    return (
        service,
        repository,
        content,
        finding,
        secret,
        policy,
        presenter,
        permission_authorizer,
        audit,
    )


async def present_finding(
    service: OperationalKnowledgeFindingPresentationService,
    content: OperationalKnowledgeProtectedContentRecord,
    finding: OperationalKnowledgeReviewFindingRecord,
    secret: str,
    policy: OperationalKnowledgeFindingPresentationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    cookie_secret: str | None = None,
    idempotency_key: str = "knowledge-finding-presentation-001",
) -> OperationalKnowledgeFindingPresentationRecord:
    grant = await service.create(
        actor=actor or domain_reviewer(),
        source_lease_id=content.source_lease_id,
        source_content_presentation_id=content.presentation_id,
        source_finding_packet_id=finding.finding_packet_id,
        source_finding_digest=finding.canonical_digest,
        presentation_policy_id=policy.policy_id,
        presentation_policy_digest=policy.canonical_digest,
        purpose="Inspect the exact sealed findings before recording a track decision.",
        sensitive_findings_acknowledged=True,
        finding_is_not_decision_acknowledged=True,
        browser_session_id="session_knowledge_inspection_001",
        lease_secrets={"review-track.domain": cookie_secret or secret},
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_finding_presentation",
    )
    assert grant.findings == domain_finding()
    return grant.record


@pytest.mark.asyncio
async def test_finding_presentation_is_exact_metadata_only_and_replayable() -> None:
    (
        service,
        repository,
        content,
        finding,
        secret,
        policy,
        _,
        authorizer,
        audit,
    ) = await finding_presentation_fixture()
    record = await present_finding(service, content, finding, secret, policy)
    repeated = await present_finding(service, content, finding, secret, policy)
    replay = await service.get(
        actor=domain_reviewer(),
        source_lease_id=content.source_lease_id,
        source_content_presentation_id=content.presentation_id,
        source_finding_packet_id=finding.finding_packet_id,
        finding_presentation_id=record.finding_presentation_id,
        browser_session_id="session_knowledge_inspection_001",
        lease_secrets={"review-track.domain": secret},
        correlation_id="cor_knowledge_finding_presentation_replay",
    )

    assert record.finding_presented and record.domain_finding_recorded
    assert not record.domain_review_completed and not record.knowledge_approved
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and replay.record.reused
    assert replay.findings == domain_finding()
    persisted = await repository.get(finding_presentation_id=record.finding_presentation_id)
    assert persisted == record
    raw = asdict(record)
    assert "summary" not in raw and "detail" not in raw
    public = OperationalKnowledgeFindingPresentationData.from_grant(replay).model_dump()
    assert public["findings"][0]["summary"] == domain_finding()[0].summary
    for hidden in (
        "source_finding_artifact_id",
        "lease_holder_subject_digest",
        "browser_session_binding_digest",
        "source_cleanup_digest",
        "presentation_cleanup_digest",
    ):
        assert hidden not in public
    assert len(authorizer.calls) == 3
    assert isinstance(audit, CollectingAuditSink)
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_finding_presentation_requested",
        "operational_knowledge_finding_presentation_claimed",
        "operational_knowledge_finding_presented",
        "operational_knowledge_finding_presentation_read",
        "operational_knowledge_finding_presentation_read",
    ]


@pytest.mark.asyncio
async def test_finding_presentation_accepts_development_identity_under_default_policy() -> None:
    service, _, content, finding, secret, policy, *_ = await finding_presentation_fixture()

    record = await present_finding(
        service,
        content,
        finding,
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
async def test_finding_presentation_enforces_explicit_step_up_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    (
        service,
        repository,
        content,
        finding,
        secret,
        policy,
        presenter,
        authorizer,
        _,
    ) = await finding_presentation_fixture(required_assurance_level=required_assurance_level)

    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="source_invalid"):
        await present_finding(
            service,
            content,
            finding,
            secret,
            policy,
            actor=development_domain_reviewer(),
        )

    assert authorizer.calls == []
    assert not presenter.calls
    assert (
        await repository.get_claim_by_source_finding(
            source_finding_packet_id=finding.finding_packet_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_finding_presentation_rejects_non_human_identity() -> None:
    (
        service,
        repository,
        content,
        finding,
        secret,
        policy,
        presenter,
        authorizer,
        _,
    ) = await finding_presentation_fixture()
    actor = replace(development_domain_reviewer(), kind=SubjectKind.SERVICE)

    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="human_required"):
        await present_finding(service, content, finding, secret, policy, actor=actor)

    assert authorizer.calls == []
    assert not presenter.calls
    assert (
        await repository.get_claim_by_source_finding(
            source_finding_packet_id=finding.finding_packet_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_finding_presentation_rejects_invalid_authority_before_claim() -> None:
    denied_authorizer = RecordingFindingPresentationPermissionAuthorizer(deny=True)
    (
        service,
        repository,
        content,
        finding,
        secret,
        policy,
        presenter,
        *_,
    ) = await finding_presentation_fixture(authorizer=denied_authorizer)
    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="permission_denied"):
        await present_finding(service, content, finding, secret, policy)
    assert not presenter.calls

    (
        service,
        repository,
        content,
        finding,
        secret,
        policy,
        presenter,
        *_,
    ) = await finding_presentation_fixture()
    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="source_not_found"):
        await present_finding(
            service, content, finding, secret, policy, cookie_secret="wrong-cookie-secret"
        )
    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="source_not_found"):
        await present_finding(
            service,
            content,
            finding,
            secret,
            policy,
            actor=replace(domain_reviewer(), subject_id="subject.synthetic-unassigned-reviewer"),
        )
    assert not presenter.calls
    assert (
        await repository.get_claim_by_source_finding(
            source_finding_packet_id=finding.finding_packet_id
        )
        is None
    )

    (
        service,
        repository,
        content,
        finding,
        secret,
        policy,
        presenter,
        *_,
    ) = await finding_presentation_fixture(clock_offset=timedelta(minutes=11))
    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="source_invalid"):
        await present_finding(service, content, finding, secret, policy)
    assert not presenter.calls


@pytest.mark.asyncio
async def test_finding_presentation_claim_survives_presenter_and_audit_failure() -> None:
    service, repository, content, finding, secret, policy, *_ = await finding_presentation_fixture()
    service._presenter = UnavailableOperationalKnowledgeFindingPresenter()
    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="unavailable"):
        await present_finding(service, content, finding, secret, policy)
    assert (
        await repository.get_claim_by_source_finding(
            source_finding_packet_id=finding.finding_packet_id
        )
        is not None
    )
    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="already_claimed"):
        await present_finding(service, content, finding, secret, policy)

    failing_audit = FailSecondAuditSink()
    (
        service,
        repository,
        content,
        finding,
        secret,
        policy,
        presenter,
        *_,
    ) = await finding_presentation_fixture(audit_sink=failing_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await present_finding(service, content, finding, secret, policy)
    assert not presenter.calls
    assert (
        await repository.get_claim_by_source_finding(
            source_finding_packet_id=finding.finding_packet_id
        )
        is not None
    )


@pytest.mark.asyncio
async def test_finding_presentation_rejects_receipt_drift_and_preserves_claim() -> None:
    service, repository, content, finding, secret, policy, *_ = await finding_presentation_fixture(
        presenter_factory=AlteredFindingPresenter
    )
    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="receipt_invalid"):
        await present_finding(service, content, finding, secret, policy)
    assert (
        await repository.get_claim_by_source_finding(
            source_finding_packet_id=finding.finding_packet_id
        )
        is not None
    )


@pytest.mark.asyncio
async def test_finding_presentation_atomically_rejects_concurrent_second_claim() -> None:
    recorder = SyntheticOperationalKnowledgeReviewFindingRecorder()
    review_service, _, content, secret, finding_policy, *_ = await review_finding_fixture(
        recorder=recorder
    )
    recorder._clock = lambda: content.presented_at
    finding = await record_finding(review_service, content, secret, finding_policy)
    policy = build_development_operational_knowledge_finding_presentation_policy(
        organization_id=finding.organization_id,
        environment_id=finding.environment_id,
        issued_at=finding.created_at - timedelta(hours=1),
        expires_at=finding.expires_at,
    )
    presenter = BlockingFindingPresenter(recorder=recorder)
    presenter._clock = lambda: finding.created_at
    service = OperationalKnowledgeFindingPresentationService(
        repository=InMemoryOperationalKnowledgeFindingPresentationRepository(),
        source=review_service,
        policy_source=InMemoryOperationalKnowledgeFindingPresentationPolicySource((policy,)),
        permission_authorizer=RecordingFindingPresentationPermissionAuthorizer(),
        presenter=presenter,
        audit_sink=CollectingAuditSink(),
        environment_id=finding.environment_id,
        clock=lambda: finding.created_at,
    )
    first = asyncio.create_task(present_finding(service, content, finding, secret, policy))
    await presenter.started.wait()
    with pytest.raises(OperationalKnowledgeFindingPresentationError, match="idempotency_conflict"):
        await present_finding(
            service,
            content,
            finding,
            secret,
            policy,
            idempotency_key="knowledge-finding-presentation-002",
        )
    presenter.release.set()
    record = await first
    assert record.finding_presented


@pytest.mark.asyncio
async def test_finding_presentation_postgres_mapping_contains_no_finding_text() -> None:
    service, repository, content, finding, secret, policy, *_ = await finding_presentation_fixture()
    record = await present_finding(service, content, finding, secret, policy)
    claim = await repository.get_claim_by_source_finding(
        source_finding_packet_id=finding.finding_packet_id
    )
    assert claim is not None
    raw_claim = OperationalKnowledgeFindingPresentationService._normalize(asdict(claim))
    raw_record = OperationalKnowledgeFindingPresentationService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert (
        PostgreSQLOperationalKnowledgeFindingPresentationRepository._claim_to_domain(raw_claim)
        == claim
    )
    assert (
        PostgreSQLOperationalKnowledgeFindingPresentationRepository._record_to_domain(raw_record)
        == record
    )
    assert "summary" not in raw_record and "detail" not in raw_record
