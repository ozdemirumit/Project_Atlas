from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from test_finding_presentation import finding_presentation_fixture, present_finding
from test_package_acquisition import CollectingAuditSink
from test_protected_content import development_domain_reviewer
from test_protected_inspection import domain_reviewer
from test_runtime_activation import FailSecondAuditSink

from atlas.api.review_decision_schemas import (
    OperationalKnowledgeTrackReviewDecisionData,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.review_decision_memory import (
    InMemoryOperationalKnowledgeTrackReviewDecisionPolicySource,
    InMemoryOperationalKnowledgeTrackReviewDecisionRepository,
)
from atlas.modules.knowledge.adapters.review_decision_postgres import (
    PostgreSQLOperationalKnowledgeTrackReviewDecisionRepository,
)
from atlas.modules.knowledge.adapters.review_decision_synthetic import (
    SyntheticOperationalKnowledgeTrackReviewDecisionAttestor,
    UnavailableOperationalKnowledgeTrackReviewDecisionAttestor,
)
from atlas.modules.knowledge.application.review_decision import (
    OperationalKnowledgeTrackReviewDecisionService,
    build_development_operational_knowledge_track_review_decision_policy,
)
from atlas.modules.knowledge.application.review_decision_ports import (
    OperationalKnowledgeTrackReviewDecisionError,
)
from atlas.modules.knowledge.domain.finding_presentation import (
    OperationalKnowledgeFindingPresentationRecord,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentRecord,
)
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionInstruction,
    OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
    OperationalKnowledgeTrackReviewDecisionReceipt,
    OperationalKnowledgeTrackReviewDecisionRecord,
)
from atlas.modules.knowledge.domain.review_finding import OperationalKnowledgeReviewFindingRecord


class RecordingReviewDecisionPermissionAuthorizer:
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
            raise OperationalKnowledgeTrackReviewDecisionError(
                "operational_knowledge_track_review_decision_permission_denied"
            )


class BlockingReviewDecisionAttestor(SyntheticOperationalKnowledgeTrackReviewDecisionAttestor):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def attest(
        self, instruction: OperationalKnowledgeTrackReviewDecisionInstruction
    ) -> OperationalKnowledgeTrackReviewDecisionReceipt:
        self.started.set()
        await self.release.wait()
        return await super().attest(instruction)


class AlteredReviewDecisionAttestor(SyntheticOperationalKnowledgeTrackReviewDecisionAttestor):
    async def attest(
        self, instruction: OperationalKnowledgeTrackReviewDecisionInstruction
    ) -> OperationalKnowledgeTrackReviewDecisionReceipt:
        receipt = await super().attest(instruction)
        altered = replace(receipt, disposition_code="review-disposition.changes-required")
        return replace(
            altered,
            canonical_digest=OperationalKnowledgeTrackReviewDecisionService._receipt_digest(
                altered
            ),
        )


async def review_decision_fixture(
    *,
    attestor: SyntheticOperationalKnowledgeTrackReviewDecisionAttestor | None = None,
    authorizer: RecordingReviewDecisionPermissionAuthorizer | None = None,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    clock_offset: timedelta = timedelta(),
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    OperationalKnowledgeTrackReviewDecisionService,
    InMemoryOperationalKnowledgeTrackReviewDecisionRepository,
    OperationalKnowledgeProtectedContentRecord,
    OperationalKnowledgeReviewFindingRecord,
    OperationalKnowledgeFindingPresentationRecord,
    str,
    OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
    SyntheticOperationalKnowledgeTrackReviewDecisionAttestor,
    RecordingReviewDecisionPermissionAuthorizer,
    CollectingAuditSink | FailSecondAuditSink,
]:
    (
        finding_service,
        _,
        content,
        finding,
        secret,
        finding_policy,
        *_,
    ) = await finding_presentation_fixture()
    presentation = await present_finding(finding_service, content, finding, secret, finding_policy)
    policy = build_development_operational_knowledge_track_review_decision_policy(
        organization_id=presentation.organization_id,
        environment_id=presentation.environment_id,
        issued_at=presentation.presented_at - timedelta(hours=1),
        expires_at=presentation.expires_at,
    )
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(
            policy,
            canonical_digest=OperationalKnowledgeTrackReviewDecisionService._digest(
                OperationalKnowledgeTrackReviewDecisionService._policy_payload(policy)
            ),
        )
    resolved_attestor = attestor or SyntheticOperationalKnowledgeTrackReviewDecisionAttestor()
    resolved_attestor._clock = lambda: presentation.presented_at + clock_offset
    repository = InMemoryOperationalKnowledgeTrackReviewDecisionRepository()
    permission_authorizer = authorizer or RecordingReviewDecisionPermissionAuthorizer()
    audit = audit_sink or CollectingAuditSink()
    service = OperationalKnowledgeTrackReviewDecisionService(
        repository=repository,
        source=finding_service,
        policy_source=InMemoryOperationalKnowledgeTrackReviewDecisionPolicySource((policy,)),
        permission_authorizer=permission_authorizer,
        attestor=resolved_attestor,
        audit_sink=audit,
        environment_id=presentation.environment_id,
        clock=lambda: presentation.presented_at + clock_offset,
    )
    return (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        resolved_attestor,
        permission_authorizer,
        audit,
    )


async def decide(
    service: OperationalKnowledgeTrackReviewDecisionService,
    content: OperationalKnowledgeProtectedContentRecord,
    finding: OperationalKnowledgeReviewFindingRecord,
    presentation: OperationalKnowledgeFindingPresentationRecord,
    secret: str,
    policy: OperationalKnowledgeTrackReviewDecisionPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    cookie_secret: str | None = None,
    disposition_code: str = "review-disposition.passed",
    idempotency_key: str = "knowledge-track-review-decision-001",
) -> OperationalKnowledgeTrackReviewDecisionRecord:
    grant = await service.create(
        actor=actor or domain_reviewer(),
        source_lease_id=content.source_lease_id,
        source_content_presentation_id=content.presentation_id,
        source_finding_packet_id=finding.finding_packet_id,
        source_finding_presentation_id=presentation.finding_presentation_id,
        source_finding_presentation_digest=presentation.canonical_digest,
        decision_policy_id=policy.policy_id,
        decision_policy_digest=policy.canonical_digest,
        disposition_code=disposition_code,
        basis_codes=("review-basis.technical-accuracy", "review-basis.evidence-quality"),
        purpose="Record the accountable domain review decision for this exact finding packet.",
        exact_findings_reviewed_acknowledged=True,
        human_track_decision_acknowledged=True,
        no_approval_or_operational_authority_acknowledged=True,
        browser_session_id="session_knowledge_inspection_001",
        lease_secrets={"review-track.domain": cookie_secret or secret},
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_track_review_decision",
    )
    return grant.record


@pytest.mark.asyncio
async def test_review_decision_is_immutable_minimized_and_idempotent() -> None:
    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        _,
        authorizer,
        audit,
    ) = await review_decision_fixture()
    record = await decide(service, content, finding, presentation, secret, policy)
    repeated = await decide(service, content, finding, presentation, secret, policy)
    replay = await service.get(
        actor=domain_reviewer(),
        source_lease_id=content.source_lease_id,
        source_content_presentation_id=content.presentation_id,
        source_finding_packet_id=finding.finding_packet_id,
        source_finding_presentation_id=presentation.finding_presentation_id,
        decision_id=record.decision_id,
        browser_session_id="session_knowledge_inspection_001",
        lease_secrets={"review-track.domain": secret},
        correlation_id="cor_knowledge_track_review_decision_read",
    )

    assert record.domain_review_completed and record.domain_review_passed
    assert not record.security_review_completed and not record.correction_required
    assert not record.knowledge_approved and not record.knowledge_published
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and replay.record.reused
    assert not replay.all_tracks_decided and not replay.all_tracks_passed
    assert not replay.any_correction_required
    assert await repository.get(decision_id=record.decision_id) == record
    raw = asdict(record)
    for forbidden in ("category_code", "severity_code", "summary", "detail", "findings"):
        assert forbidden not in raw
    public = OperationalKnowledgeTrackReviewDecisionData.from_grant(replay).model_dump()
    for hidden in (
        "decided_by_subject_digest",
        "browser_session_binding_digest",
        "source_finding_digest",
        "source_lease_digest",
        "basis_digest",
    ):
        assert hidden not in public
    assert len(authorizer.calls) == 3
    assert isinstance(audit, CollectingAuditSink)
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_track_review_decision_requested",
        "operational_knowledge_track_review_decision_claimed",
        "operational_knowledge_track_review_decided",
        "operational_knowledge_track_review_decision_read",
        "operational_knowledge_track_review_decision_read",
    ]


@pytest.mark.asyncio
async def test_review_decision_accepts_development_identity_under_default_policy() -> None:
    service, _, content, finding, presentation, secret, policy, *_ = await review_decision_fixture()

    record = await decide(
        service,
        content,
        finding,
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
async def test_review_decision_enforces_explicit_step_up_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        attestor,
        authorizer,
        _,
    ) = await review_decision_fixture(required_assurance_level=required_assurance_level)

    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="source_invalid"):
        await decide(
            service,
            content,
            finding,
            presentation,
            secret,
            policy,
            actor=development_domain_reviewer(),
        )

    assert authorizer.calls == []
    assert not attestor.calls
    assert (
        await repository.get_claim_by_source_presentation(
            source_finding_presentation_id=presentation.finding_presentation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_review_decision_rejects_non_human_identity() -> None:
    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        attestor,
        authorizer,
        _,
    ) = await review_decision_fixture()
    actor = replace(development_domain_reviewer(), kind=SubjectKind.SERVICE)

    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="human_required"):
        await decide(service, content, finding, presentation, secret, policy, actor=actor)

    assert authorizer.calls == []
    assert not attestor.calls
    assert (
        await repository.get_claim_by_source_presentation(
            source_finding_presentation_id=presentation.finding_presentation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_changes_required_is_not_correction_or_approval() -> None:
    service, _, content, finding, presentation, secret, policy, *_ = await review_decision_fixture()
    record = await decide(
        service,
        content,
        finding,
        presentation,
        secret,
        policy,
        disposition_code="review-disposition.changes-required",
    )
    assert record.domain_review_completed and not record.domain_review_passed
    assert record.correction_required and not record.correction_created
    assert not record.knowledge_approved and not record.retrieval_published


@pytest.mark.asyncio
async def test_matching_domain_and_security_passes_only_establish_review_readiness() -> None:
    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        *_,
    ) = await review_decision_fixture()
    domain = await decide(service, content, finding, presentation, secret, policy)
    security_basis = (
        "review-basis.access-control",
        "review-basis.policy-compliance",
    )
    security = replace(
        domain,
        decision_id="decision.synthetic-security-review",
        claim_id="claim.synthetic-security-review",
        source_finding_presentation_id="finding-presentation.synthetic-security-review",
        source_finding_presentation_digest=service._digest(
            "finding-presentation.synthetic-security-review"
        ),
        track_code="review-track.security",
        basis_codes=security_basis,
        basis_digest=service._digest(security_basis),
        domain_review_completed=False,
        security_review_completed=True,
        domain_review_passed=False,
        security_review_passed=True,
        canonical_digest="0" * 64,
    )
    security = replace(
        security,
        canonical_digest=service._digest(service._record_payload(security)),
    )

    assert await repository.add(security)
    grant = await service._grant(security)

    assert grant.all_tracks_decided and grant.all_tracks_passed
    assert not grant.any_correction_required
    assert not grant.record.knowledge_approved
    assert not grant.record.knowledge_published
    assert not grant.record.retrieval_published
    assert not grant.record.execution_authorized
    assert not grant.record.infrastructure_mutation_performed


@pytest.mark.asyncio
async def test_review_decision_rejects_wrong_authority_before_claim() -> None:
    denied = RecordingReviewDecisionPermissionAuthorizer(deny=True)
    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        attestor,
        *_,
    ) = await review_decision_fixture(authorizer=denied)
    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="permission_denied"):
        await decide(service, content, finding, presentation, secret, policy)
    assert not attestor.calls

    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        attestor,
        *_,
    ) = await review_decision_fixture()
    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="source_not_found"):
        await decide(
            service,
            content,
            finding,
            presentation,
            secret,
            policy,
            cookie_secret="wrong-cookie-secret",
        )
    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="source_not_found"):
        await decide(
            service,
            content,
            finding,
            presentation,
            secret,
            policy,
            actor=replace(domain_reviewer(), subject_id="subject.synthetic-unassigned-reviewer"),
        )
    assert not attestor.calls
    assert (
        await repository.get_claim_by_source_presentation(
            source_finding_presentation_id=presentation.finding_presentation_id
        )
        is None
    )

    (
        service,
        _,
        content,
        finding,
        presentation,
        secret,
        policy,
        attestor,
        *_,
    ) = await review_decision_fixture(clock_offset=timedelta(minutes=11))
    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="source_invalid"):
        await decide(service, content, finding, presentation, secret, policy)
    assert not attestor.calls


@pytest.mark.asyncio
async def test_review_decision_claim_survives_attestor_and_audit_failure() -> None:
    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        *_,
    ) = await review_decision_fixture()
    service._attestor = UnavailableOperationalKnowledgeTrackReviewDecisionAttestor()
    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="unavailable"):
        await decide(service, content, finding, presentation, secret, policy)
    assert (
        await repository.get_claim_by_source_presentation(
            source_finding_presentation_id=presentation.finding_presentation_id
        )
        is not None
    )
    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="already_claimed"):
        await decide(service, content, finding, presentation, secret, policy)

    failing_audit = FailSecondAuditSink()
    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        attestor,
        *_,
    ) = await review_decision_fixture(audit_sink=failing_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await decide(service, content, finding, presentation, secret, policy)
    assert not attestor.calls
    assert (
        await repository.get_claim_by_source_presentation(
            source_finding_presentation_id=presentation.finding_presentation_id
        )
        is not None
    )


@pytest.mark.asyncio
async def test_review_decision_rejects_attestation_drift() -> None:
    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        *_,
    ) = await review_decision_fixture(attestor=AlteredReviewDecisionAttestor())
    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="attestation_invalid"):
        await decide(service, content, finding, presentation, secret, policy)
    assert (
        await repository.get_claim_by_source_presentation(
            source_finding_presentation_id=presentation.finding_presentation_id
        )
        is not None
    )


@pytest.mark.asyncio
async def test_review_decision_atomically_rejects_conflicting_second_decision() -> None:
    attestor = BlockingReviewDecisionAttestor()
    service, _, content, finding, presentation, secret, policy, *_ = await review_decision_fixture(
        attestor=attestor
    )
    first = asyncio.create_task(decide(service, content, finding, presentation, secret, policy))
    await attestor.started.wait()
    with pytest.raises(OperationalKnowledgeTrackReviewDecisionError, match="idempotency_conflict"):
        await decide(
            service,
            content,
            finding,
            presentation,
            secret,
            policy,
            disposition_code="review-disposition.changes-required",
            idempotency_key="knowledge-track-review-decision-002",
        )
    attestor.release.set()
    record = await first
    assert record.domain_review_passed


@pytest.mark.asyncio
async def test_review_decision_postgres_mapping_contains_no_finding_text() -> None:
    (
        service,
        repository,
        content,
        finding,
        presentation,
        secret,
        policy,
        *_,
    ) = await review_decision_fixture()
    record = await decide(service, content, finding, presentation, secret, policy)
    claim = await repository.get_claim_by_source_presentation(
        source_finding_presentation_id=presentation.finding_presentation_id
    )
    assert claim is not None
    raw_claim = OperationalKnowledgeTrackReviewDecisionService._normalize(asdict(claim))
    raw_record = OperationalKnowledgeTrackReviewDecisionService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert (
        PostgreSQLOperationalKnowledgeTrackReviewDecisionRepository._claim_to_domain(raw_claim)
        == claim
    )
    assert (
        PostgreSQLOperationalKnowledgeTrackReviewDecisionRepository._record_to_domain(raw_record)
        == record
    )
    serialized = str(raw_record)
    for forbidden in ("category_code", "severity_code", "summary", "detail"):
        assert forbidden not in serialized
