from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from test_package_acquisition import CollectingAuditSink
from test_recommendation_finding_presentation import present_findings, presentation_fixture
from test_runtime_activation import FailSecondAuditSink
from test_target_session import target_session_operator

from atlas.api.recommendation_review_decision_schemas import (
    RecommendationTrackReviewDecisionData,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.adapters.review_decision_memory import (
    InMemoryRecommendationTrackReviewDecisionPolicySource,
    InMemoryRecommendationTrackReviewDecisionRepository,
)
from atlas.modules.recommendations.adapters.review_decision_postgres import (
    PostgreSQLRecommendationTrackReviewDecisionRepository,
)
from atlas.modules.recommendations.adapters.review_decision_synthetic import (
    SyntheticRecommendationTrackReviewDecisionAttestor,
    UnavailableRecommendationTrackReviewDecisionAttestor,
)
from atlas.modules.recommendations.application.review_decision import (
    RecommendationTrackReviewDecisionService,
    build_development_recommendation_track_review_decision_policy,
)
from atlas.modules.recommendations.application.review_decision_ports import (
    RecommendationTrackReviewDecisionError,
)
from atlas.modules.recommendations.domain.finding_presentation import (
    RecommendationFindingPresentationRecord,
)
from atlas.modules.recommendations.domain.human_review_finding import (
    RecommendationHumanReviewFindingRecord,
)
from atlas.modules.recommendations.domain.protected_content import (
    RecommendationProtectedContentRecord,
)
from atlas.modules.recommendations.domain.review_decision import (
    RecommendationTrackReviewDecisionInstruction,
    RecommendationTrackReviewDecisionPolicySnapshot,
    RecommendationTrackReviewDecisionReceipt,
    RecommendationTrackReviewDecisionRecord,
)


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
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_permission_denied"
            )


class BlockingReviewDecisionAttestor(SyntheticRecommendationTrackReviewDecisionAttestor):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def attest(
        self, instruction: RecommendationTrackReviewDecisionInstruction
    ) -> RecommendationTrackReviewDecisionReceipt:
        self.started.set()
        await self.release.wait()
        return await super().attest(instruction)


class AlteredReviewDecisionAttestor(SyntheticRecommendationTrackReviewDecisionAttestor):
    async def attest(
        self, instruction: RecommendationTrackReviewDecisionInstruction
    ) -> RecommendationTrackReviewDecisionReceipt:
        receipt = await super().attest(instruction)
        altered = replace(receipt, disposition_code="review-disposition.changes-required")
        return replace(
            altered,
            canonical_digest=RecommendationTrackReviewDecisionService._receipt_digest(altered),
        )


async def review_decision_fixture(
    *,
    attestor: SyntheticRecommendationTrackReviewDecisionAttestor | None = None,
    authorizer: RecordingReviewDecisionPermissionAuthorizer | None = None,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    clock_offset: timedelta = timedelta(),
) -> tuple[
    RecommendationTrackReviewDecisionService,
    InMemoryRecommendationTrackReviewDecisionRepository,
    RecommendationProtectedContentRecord,
    RecommendationHumanReviewFindingRecord,
    RecommendationFindingPresentationRecord,
    str,
    RecommendationTrackReviewDecisionPolicySnapshot,
    SyntheticRecommendationTrackReviewDecisionAttestor,
    RecordingReviewDecisionPermissionAuthorizer,
    CollectingAuditSink | FailSecondAuditSink,
]:
    (
        finding_service,
        _,
        _,
        _,
        assignment,
        lease,
        content_grant,
        finding,
        finding_policy,
        actor,
    ) = await presentation_fixture()
    presentation_grant = await present_findings(
        finding_service,
        assignment,
        lease,
        content_grant,
        finding,
        finding_policy,
        actor,
    )
    content = content_grant.record
    presentation = presentation_grant.record
    secret = str(lease.lease_secret)
    policy = build_development_recommendation_track_review_decision_policy(
        organization_id=presentation.organization_id,
        environment_id=presentation.environment_id,
        issued_at=presentation.presented_at - timedelta(hours=1),
        expires_at=presentation.expires_at,
    )
    resolved_attestor = attestor or SyntheticRecommendationTrackReviewDecisionAttestor()
    resolved_attestor._clock = lambda: presentation.presented_at + clock_offset
    repository = InMemoryRecommendationTrackReviewDecisionRepository()
    permission_authorizer = authorizer or RecordingReviewDecisionPermissionAuthorizer()
    audit = audit_sink or CollectingAuditSink()
    service = RecommendationTrackReviewDecisionService(
        repository=repository,
        source=finding_service,
        policy_source=InMemoryRecommendationTrackReviewDecisionPolicySource((policy,)),
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


def technical_reviewer(
    presentation: RecommendationFindingPresentationRecord,
) -> AuthenticatedSubject:
    return replace(
        target_session_operator("subject.synthetic-technical-reviewer"),
        organization_id=presentation.organization_id,
        authenticated_at=presentation.presented_at,
    )


async def decide(
    service: RecommendationTrackReviewDecisionService,
    content: RecommendationProtectedContentRecord,
    finding: RecommendationHumanReviewFindingRecord,
    presentation: RecommendationFindingPresentationRecord,
    secret: str,
    policy: RecommendationTrackReviewDecisionPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    cookie_secret: str | None = None,
    disposition_code: str = "review-disposition.passed",
    idempotency_key: str = "recommendation-track-review-decision-001",
) -> RecommendationTrackReviewDecisionRecord:
    grant = await service.create(
        actor=actor or technical_reviewer(presentation),
        recommendation_id=presentation.recommendation_id,
        source_lease_id=content.source_lease_id,
        source_content_presentation_id=content.presentation_id,
        source_finding_packet_id=finding.finding_packet_id,
        source_finding_presentation_id=presentation.finding_presentation_id,
        source_finding_presentation_digest=presentation.canonical_digest,
        decision_policy_id=policy.policy_id,
        decision_policy_digest=policy.canonical_digest,
        disposition_code=disposition_code,
        basis_codes=(
            "review-basis.recommendation-technical-correctness",
            "review-basis.evidence-grounding",
        ),
        purpose="Record the accountable technical review decision for this exact finding packet.",
        exact_findings_reviewed_acknowledged=True,
        human_track_decision_acknowledged=True,
        no_approval_or_operational_authority_acknowledged=True,
        browser_session_id="session_recommendation_inspection_001",
        lease_secrets={"review-track.technical": cookie_secret or secret},
        idempotency_key=idempotency_key,
        correlation_id="cor_recommendation_track_review_decision",
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
        actor=technical_reviewer(presentation),
        recommendation_id=presentation.recommendation_id,
        source_lease_id=content.source_lease_id,
        source_content_presentation_id=content.presentation_id,
        source_finding_packet_id=finding.finding_packet_id,
        source_finding_presentation_id=presentation.finding_presentation_id,
        decision_id=record.decision_id,
        browser_session_id="session_recommendation_inspection_001",
        lease_secrets={"review-track.technical": secret},
        correlation_id="cor_recommendation_track_review_decision_read",
    )

    assert record.technical_review_completed and record.technical_review_passed
    assert not record.service_impact_review_completed and not record.correction_required
    assert not record.recommendation_approved and not record.workflow_created
    assert not record.execution_authorized and not record.infrastructure_mutated
    assert repeated.reused and replay.record.reused
    assert not replay.all_tracks_decided and not replay.all_tracks_passed
    assert not replay.any_correction_required
    assert await repository.get(decision_id=record.decision_id) == record
    raw = asdict(record)
    for forbidden in ("category_code", "severity_code", "summary", "detail", "findings"):
        assert forbidden not in raw
    public = RecommendationTrackReviewDecisionData.from_grant(replay).model_dump()
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
        "recommendation_track_review_decision_requested",
        "recommendation_track_review_decision_claimed",
        "recommendation_track_review_decided",
        "recommendation_track_review_decision_read",
        "recommendation_track_review_decision_read",
    ]


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
    assert record.technical_review_completed and not record.technical_review_passed
    assert record.correction_required and not record.correction_created
    assert not record.recommendation_approved and not record.itsm_record_created


@pytest.mark.asyncio
async def test_matching_technical_and_service_impact_passes_only_establish_review_readiness() -> (
    None
):
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
    technical = await decide(service, content, finding, presentation, secret, policy)
    service_impact_basis = (
        "review-basis.service-impact-scope",
        "review-basis.business-continuity",
    )
    service_impact = replace(
        technical,
        decision_id="decision.synthetic-service-impact-review",
        claim_id="claim.synthetic-service-impact-review",
        source_finding_presentation_id="finding-presentation.synthetic-service-impact-review",
        source_finding_presentation_digest=service._digest(
            "finding-presentation.synthetic-service-impact-review"
        ),
        track_code="review-track.service-impact",
        basis_codes=service_impact_basis,
        basis_digest=service._digest(service_impact_basis),
        technical_review_completed=False,
        service_impact_review_completed=True,
        technical_review_passed=False,
        service_impact_review_passed=True,
        canonical_digest="0" * 64,
    )
    service_impact = replace(
        service_impact,
        canonical_digest=service._digest(service._record_payload(service_impact)),
    )

    assert await repository.add(service_impact)
    grant = await service._grant(service_impact)

    assert grant.all_tracks_decided and grant.all_tracks_passed
    assert not grant.any_correction_required
    assert not grant.record.recommendation_approved
    assert not grant.record.workflow_created
    assert not grant.record.itsm_record_created
    assert not grant.record.execution_authorized
    assert not grant.record.infrastructure_mutated


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
    with pytest.raises(RecommendationTrackReviewDecisionError, match="permission_denied"):
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
    with pytest.raises(RecommendationTrackReviewDecisionError, match="source_not_found"):
        await decide(
            service,
            content,
            finding,
            presentation,
            secret,
            policy,
            cookie_secret="wrong-cookie-secret",
        )
    with pytest.raises(RecommendationTrackReviewDecisionError, match="source_not_found"):
        await decide(
            service,
            content,
            finding,
            presentation,
            secret,
            policy,
            actor=replace(
                technical_reviewer(presentation),
                subject_id="subject.synthetic-unassigned-reviewer",
            ),
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
    with pytest.raises(RecommendationTrackReviewDecisionError, match="source_invalid"):
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
    service._attestor = UnavailableRecommendationTrackReviewDecisionAttestor()
    with pytest.raises(RecommendationTrackReviewDecisionError, match="unavailable"):
        await decide(service, content, finding, presentation, secret, policy)
    assert (
        await repository.get_claim_by_source_presentation(
            source_finding_presentation_id=presentation.finding_presentation_id
        )
        is not None
    )
    with pytest.raises(RecommendationTrackReviewDecisionError, match="already_claimed"):
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
    with pytest.raises(RecommendationTrackReviewDecisionError, match="attestation_invalid"):
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
    with pytest.raises(RecommendationTrackReviewDecisionError, match="idempotency_conflict"):
        await decide(
            service,
            content,
            finding,
            presentation,
            secret,
            policy,
            disposition_code="review-disposition.changes-required",
            idempotency_key="recommendation-track-review-decision-002",
        )
    attestor.release.set()
    record = await first
    assert record.technical_review_passed


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
    raw_claim = RecommendationTrackReviewDecisionService._normalize(asdict(claim))
    raw_record = RecommendationTrackReviewDecisionService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert (
        PostgreSQLRecommendationTrackReviewDecisionRepository._claim_to_domain(raw_claim) == claim
    )
    assert (
        PostgreSQLRecommendationTrackReviewDecisionRepository._record_to_domain(raw_record)
        == record
    )
    serialized = str(raw_record)
    for forbidden in ("category_code", "severity_code", "summary", "detail"):
        assert forbidden not in serialized
