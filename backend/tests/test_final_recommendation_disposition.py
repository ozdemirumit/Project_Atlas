from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_package_acquisition import CollectingAuditSink
from test_recommendation_review_decision import decide, review_decision_fixture
from test_runtime_activation import FailSecondAuditSink
from test_target_session import target_session_operator

from atlas.api.final_recommendation_disposition_schemas import (
    FinalRecommendationDispositionData,
    FinalRecommendationDispositionInput,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.adapters.final_disposition_memory import (
    InMemoryFinalRecommendationDispositionPolicySource,
    InMemoryFinalRecommendationDispositionRepository,
)
from atlas.modules.recommendations.adapters.final_disposition_postgres import (
    PostgreSQLFinalRecommendationDispositionRepository,
)
from atlas.modules.recommendations.adapters.final_disposition_synthetic import (
    SyntheticFinalRecommendationDispositionAttestor,
    UnavailableFinalRecommendationDispositionAttestor,
)
from atlas.modules.recommendations.application.final_disposition import (
    FinalRecommendationDispositionService,
    build_development_final_recommendation_disposition_policy,
)
from atlas.modules.recommendations.application.final_disposition_ports import (
    FinalRecommendationDispositionError,
    FinalRecommendationDispositionUncertainError,
)
from atlas.modules.recommendations.domain.final_disposition import (
    FINAL_ACCEPTED,
    FINAL_REJECTED,
    FinalRecommendationDispositionInstruction,
    FinalRecommendationDispositionPolicySnapshot,
    FinalRecommendationDispositionReceipt,
    FinalRecommendationDispositionRecord,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_decision import (
    RecommendationTrackReviewDecisionRecord,
)
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestRecord,
)


class RecordingFinalDispositionPermissionAuthorizer:
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
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_permission_denied"
            )


class StaticFinalDispositionSource:
    def __init__(
        self,
        *,
        decisions: tuple[RecommendationTrackReviewDecisionRecord, ...],
        request: RecommendationReviewRequestRecord,
        readiness: RecommendationReadinessAssessment,
        artifact: PromotedRecommendationArtifact,
    ) -> None:
        self.decisions = decisions
        self.request = request
        self.readiness = readiness
        self.artifact = artifact

    async def final_disposition_source(
        self, *, review_request_id: str
    ) -> tuple[
        tuple[RecommendationTrackReviewDecisionRecord, ...],
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
    ]:
        if review_request_id != self.request.review_request_id:
            raise FinalRecommendationDispositionError("source_not_found")
        return self.decisions, self.request, self.readiness, self.artifact


class BlockingFinalDispositionAttestor(SyntheticFinalRecommendationDispositionAttestor):
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def attest(
        self, instruction: FinalRecommendationDispositionInstruction
    ) -> FinalRecommendationDispositionReceipt:
        self.started.set()
        await self.release.wait()
        return await super().attest(instruction)


class DelayedFinalDispositionAttestor(SyntheticFinalRecommendationDispositionAttestor):
    async def attest(
        self, instruction: FinalRecommendationDispositionInstruction
    ) -> FinalRecommendationDispositionReceipt:
        receipt = await super().attest(instruction)
        delayed = replace(
            receipt,
            attested_at=receipt.attested_at + timedelta(minutes=2),
            canonical_digest="0" * 64,
        )
        return replace(
            delayed,
            canonical_digest=FinalRecommendationDispositionService._receipt_digest(delayed),
        )


async def final_disposition_fixture(
    *,
    attestor: SyntheticFinalRecommendationDispositionAttestor
    | UnavailableFinalRecommendationDispositionAttestor
    | None = None,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
) -> tuple[
    FinalRecommendationDispositionService,
    InMemoryFinalRecommendationDispositionRepository,
    tuple[RecommendationTrackReviewDecisionRecord, ...],
    RecommendationReviewRequestRecord,
    RecommendationReadinessAssessment,
    PromotedRecommendationArtifact,
    FinalRecommendationDispositionPolicySnapshot,
    AuthenticatedSubject,
    RecordingFinalDispositionPermissionAuthorizer,
    CollectingAuditSink | FailSecondAuditSink,
]:
    (
        decision_service,
        decision_repository,
        content,
        finding,
        presentation,
        secret,
        decision_policy,
        *_,
    ) = await review_decision_fixture()
    technical = await decide(
        decision_service,
        content,
        finding,
        presentation,
        secret,
        decision_policy,
    )
    service_basis = (
        "review-basis.service-impact-scope",
        "review-basis.business-continuity",
    )
    service_impact = replace(
        technical,
        decision_id="decision.synthetic-service-impact-final-review",
        claim_id="claim.synthetic-service-impact-final-review",
        source_finding_presentation_id="finding-presentation.synthetic-service-impact-final",
        source_finding_presentation_digest=decision_service._digest(
            "finding-presentation.synthetic-service-impact-final"
        ),
        track_code="review-track.service-impact",
        basis_codes=service_basis,
        basis_digest=decision_service._digest(service_basis),
        decided_by_subject_digest=decision_service._digest(
            [decision_policy.subject_digest_salt_digest, "subject.synthetic-service-reviewer"]
        ),
        technical_review_completed=False,
        service_impact_review_completed=True,
        technical_review_passed=False,
        service_impact_review_passed=True,
        canonical_digest="0" * 64,
    )
    service_impact = replace(
        service_impact,
        canonical_digest=decision_service._digest(decision_service._record_payload(service_impact)),
    )
    assert await decision_repository.add(service_impact)
    decisions, request, readiness, artifact = await decision_service.final_disposition_source(
        review_request_id=technical.review_request_id
    )
    actor = replace(
        target_session_operator("subject.enterprise-final-recommendation-approver"),
        organization_id=request.organization_id,
        authenticated_at=technical.decided_at,
    )
    policy = build_development_final_recommendation_disposition_policy(
        organization_id=request.organization_id,
        environment_id=request.environment_id,
        issued_at=technical.decided_at - timedelta(hours=1),
        expires_at=technical.decided_at + timedelta(hours=1),
    )
    repository = InMemoryFinalRecommendationDispositionRepository()
    permission = RecordingFinalDispositionPermissionAuthorizer()
    audit = audit_sink or CollectingAuditSink()
    service = FinalRecommendationDispositionService(
        repository=repository,
        source=StaticFinalDispositionSource(
            decisions=decisions,
            request=request,
            readiness=readiness,
            artifact=artifact,
        ),
        policy_source=InMemoryFinalRecommendationDispositionPolicySource((policy,)),
        permission_authorizer=permission,
        attestor=attestor or SyntheticFinalRecommendationDispositionAttestor(),
        audit_sink=audit,
        environment_id=request.environment_id,
        clock=lambda: technical.decided_at,
    )
    return (
        service,
        repository,
        decisions,
        request,
        readiness,
        artifact,
        policy,
        actor,
        permission,
        audit,
    )


async def dispose(
    service: FinalRecommendationDispositionService,
    decisions: tuple[RecommendationTrackReviewDecisionRecord, ...],
    request: RecommendationReviewRequestRecord,
    artifact: PromotedRecommendationArtifact,
    policy: FinalRecommendationDispositionPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    disposition_code: str = FINAL_ACCEPTED,
    idempotency_key: str = "final-recommendation-disposition-001",
) -> FinalRecommendationDispositionRecord:
    basis_codes = (
        ("recommendation-final-basis.review-evidence-sufficient",)
        if disposition_code == FINAL_ACCEPTED
        else ("recommendation-final-basis.risk-not-acceptable",)
    )
    return await service.create(
        actor=actor,
        review_request_id=request.review_request_id,
        review_request_digest=request.canonical_digest,
        recommendation_id=artifact.recommendation_id,
        recommendation_digest=artifact.canonical_digest,
        decision_ids=(decisions[0].decision_id, decisions[1].decision_id),
        decision_digests=(decisions[0].canonical_digest, decisions[1].canonical_digest),
        disposition_code=disposition_code,
        basis_codes=basis_codes,
        disposition_policy_id=policy.policy_id,
        disposition_policy_digest=policy.canonical_digest,
        purpose=(
            "Record the accountable final recommendation disposition for this review generation."
        ),
        immutable_generation_acknowledged=True,
        recommendation_level_only_acknowledged=True,
        handoff_eligibility_only_acknowledged=True,
        no_operational_authority_acknowledged=True,
        browser_session_id="session_final_recommendation_disposition_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_final_recommendation_disposition",
    )


@pytest.mark.asyncio
async def test_accepted_disposition_is_minimized_immutable_and_idempotent() -> None:
    (
        service,
        repository,
        decisions,
        request,
        _,
        artifact,
        policy,
        actor,
        permission,
        audit,
    ) = await final_disposition_fixture()

    record = await dispose(service, decisions, request, artifact, policy, actor)
    repeated = await dispose(service, decisions, request, artifact, policy, actor)
    replayed = await service.get(
        actor=actor,
        disposition_id=record.disposition_id,
        browser_session_id="session_final_recommendation_disposition_001",
        correlation_id="cor_final_recommendation_disposition_read",
    )

    assert record.final_disposition_recorded and record.recommendation_approved
    assert record.workflow_handoff_eligible
    assert not record.workflow_created and not record.itsm_record_created
    assert not record.change_approved and not record.execution_authorized
    assert not record.deployment_authorized and not record.infrastructure_mutated
    assert repeated.reused and replayed.reused
    assert (
        await repository.get_by_review_request(review_request_id=request.review_request_id)
        == record
    )
    public = FinalRecommendationDispositionData.from_domain(record).model_dump()
    assert "approved_by_subject_digest" not in public
    assert "browser_session_binding_digest" not in public
    for forbidden in (
        "recommendation_content",
        "findings",
        "artifact_location",
        "command",
        "credential",
    ):
        assert forbidden not in asdict(record)
        assert forbidden not in public
    assert len(permission.calls) == 3
    assert [item.result_code for item in audit.records] == [
        "final_recommendation_disposition_intent_recorded",
        "final_recommendation_disposition_claimed",
        "final_recommendation_disposition_attested",
        "final_recommendation_disposition_recorded",
        "final_recommendation_disposition_read",
        "final_recommendation_disposition_read",
    ]


@pytest.mark.asyncio
async def test_rejected_disposition_never_creates_approval_or_handoff_authority() -> None:
    (
        service,
        _,
        decisions,
        request,
        _,
        artifact,
        policy,
        actor,
        *_,
    ) = await final_disposition_fixture()

    record = await dispose(
        service,
        decisions,
        request,
        artifact,
        policy,
        actor,
        disposition_code=FINAL_REJECTED,
    )

    assert record.state == "recommendation_final_rejected"
    assert record.final_disposition_recorded
    assert not record.recommendation_approved
    assert not record.workflow_handoff_eligible
    assert not record.workflow_created and not record.itsm_record_created
    assert not record.change_approved and not record.infrastructure_mutated


@pytest.mark.asyncio
async def test_source_generation_and_actor_separation_fail_before_claim() -> None:
    (
        service,
        repository,
        decisions,
        request,
        _,
        artifact,
        policy,
        actor,
        *_,
    ) = await final_disposition_fixture()
    source = service._source
    assert isinstance(source, StaticFinalDispositionSource)

    source.decisions = (
        decisions[0],
        replace(decisions[1], decision_policy_version="policy-version.conflicting"),
    )
    with pytest.raises(FinalRecommendationDispositionError, match="source_invalid"):
        await dispose(service, source.decisions, request, artifact, policy, actor)
    assert (
        await repository.get_claim_by_review_request(review_request_id=request.review_request_id)
        is None
    )

    source.decisions = decisions
    expired = replace(
        decisions[1],
        decided_at=decisions[1].decided_at - timedelta(minutes=2),
        expires_at=decisions[1].decided_at - timedelta(minutes=1),
    )
    source.decisions = (decisions[0], expired)
    with pytest.raises(FinalRecommendationDispositionError, match="source_invalid"):
        await dispose(service, source.decisions, request, artifact, policy, actor)

    source.decisions = decisions
    future_actor = replace(actor, authenticated_at=decisions[0].decided_at + timedelta(seconds=1))
    with pytest.raises(FinalRecommendationDispositionError, match="source_invalid"):
        await dispose(service, decisions, request, artifact, policy, future_actor)

    reviewer = replace(actor, subject_id="subject.synthetic-technical-reviewer")
    with pytest.raises(FinalRecommendationDispositionError, match="separation_required"):
        await dispose(service, decisions, request, artifact, policy, reviewer)
    consumer = replace(actor, subject_id="subject.knowledge-retrieval-consumer")
    with pytest.raises(FinalRecommendationDispositionError, match="separation_required"):
        await dispose(service, decisions, request, artifact, policy, consumer)
    break_glass = replace(actor, role_ids=("role.break-glass",))
    with pytest.raises(FinalRecommendationDispositionError, match="separation_required"):
        await dispose(service, decisions, request, artifact, policy, break_glass)
    assert (
        await repository.get_claim_by_review_request(review_request_id=request.review_request_id)
        is None
    )


@pytest.mark.asyncio
async def test_basis_and_idempotency_conflicts_are_fail_closed() -> None:
    (
        service,
        repository,
        decisions,
        request,
        _,
        artifact,
        policy,
        actor,
        *_,
    ) = await final_disposition_fixture()
    with pytest.raises(FinalRecommendationDispositionError, match="source_invalid"):
        await service.create(
            actor=actor,
            review_request_id=request.review_request_id,
            review_request_digest=request.canonical_digest,
            recommendation_id=artifact.recommendation_id,
            recommendation_digest=artifact.canonical_digest,
            decision_ids=(decisions[0].decision_id, decisions[1].decision_id),
            decision_digests=(decisions[0].canonical_digest, decisions[1].canonical_digest),
            disposition_code=FINAL_ACCEPTED,
            basis_codes=("recommendation-final-basis.risk-not-acceptable",),
            disposition_policy_id=policy.policy_id,
            disposition_policy_digest=policy.canonical_digest,
            purpose="Reject incompatible final disposition basis before any claim is created.",
            immutable_generation_acknowledged=True,
            recommendation_level_only_acknowledged=True,
            handoff_eligibility_only_acknowledged=True,
            no_operational_authority_acknowledged=True,
            browser_session_id="session_final_recommendation_disposition_001",
            idempotency_key="final-recommendation-disposition-invalid-basis",
            correlation_id="cor_final_recommendation_disposition_invalid_basis",
        )
    assert (
        await repository.get_claim_by_review_request(review_request_id=request.review_request_id)
        is None
    )

    await dispose(service, decisions, request, artifact, policy, actor)
    with pytest.raises(FinalRecommendationDispositionError, match="idempotency_conflict"):
        await dispose(
            service,
            decisions,
            request,
            artifact,
            policy,
            actor,
            disposition_code=FINAL_REJECTED,
        )


@pytest.mark.asyncio
async def test_unavailable_attestor_preserves_claim_and_makes_retry_uncertain() -> None:
    (
        service,
        repository,
        decisions,
        request,
        _,
        artifact,
        policy,
        actor,
        *_,
    ) = await final_disposition_fixture(
        attestor=UnavailableFinalRecommendationDispositionAttestor()
    )

    with pytest.raises(
        FinalRecommendationDispositionUncertainError,
        match="outcome_uncertain",
    ):
        await dispose(service, decisions, request, artifact, policy, actor)
    claim = await repository.get_claim_by_review_request(
        review_request_id=request.review_request_id
    )
    assert claim is not None
    assert await repository.get(disposition_id=claim.disposition_id) is None

    with pytest.raises(
        FinalRecommendationDispositionUncertainError,
        match="claimed_outcome_uncertain",
    ):
        await dispose(service, decisions, request, artifact, policy, actor)


@pytest.mark.asyncio
async def test_concurrent_request_cannot_replace_an_in_flight_claim() -> None:
    attestor = BlockingFinalDispositionAttestor()
    (
        service,
        repository,
        decisions,
        request,
        _,
        artifact,
        policy,
        actor,
        *_,
    ) = await final_disposition_fixture(attestor=attestor)
    first = asyncio.create_task(dispose(service, decisions, request, artifact, policy, actor))
    await attestor.started.wait()

    with pytest.raises(
        FinalRecommendationDispositionUncertainError,
        match="claimed_outcome_uncertain",
    ):
        await dispose(service, decisions, request, artifact, policy, actor)
    claim = await repository.get_claim_by_review_request(
        review_request_id=request.review_request_id
    )
    assert claim is not None

    attestor.release.set()
    record = await first
    repeated = await dispose(service, decisions, request, artifact, policy, actor)

    assert repeated.disposition_id == record.disposition_id
    assert repeated.reused
    assert await repository.get(disposition_id=claim.disposition_id) == record


@pytest.mark.asyncio
async def test_required_post_claim_audit_failure_keeps_an_uncertain_claim() -> None:
    audit = FailSecondAuditSink()
    (
        service,
        repository,
        decisions,
        request,
        _,
        artifact,
        policy,
        actor,
        *_,
    ) = await final_disposition_fixture(audit_sink=audit)

    with pytest.raises(
        FinalRecommendationDispositionUncertainError,
        match="outcome_uncertain",
    ):
        await dispose(service, decisions, request, artifact, policy, actor)

    claim = await repository.get_claim_by_review_request(
        review_request_id=request.review_request_id
    )
    assert claim is not None
    assert await repository.get(disposition_id=claim.disposition_id) is None


@pytest.mark.asyncio
async def test_delayed_but_signed_attestation_is_rejected_after_claim() -> None:
    (
        service,
        repository,
        decisions,
        request,
        _,
        artifact,
        policy,
        actor,
        *_,
    ) = await final_disposition_fixture(attestor=DelayedFinalDispositionAttestor())

    with pytest.raises(
        FinalRecommendationDispositionUncertainError,
        match="outcome_uncertain",
    ):
        await dispose(service, decisions, request, artifact, policy, actor)

    claim = await repository.get_claim_by_review_request(
        review_request_id=request.review_request_id
    )
    assert claim is not None
    assert await repository.get(disposition_id=claim.disposition_id) is None


def test_input_forbids_content_authority_and_free_form_extensions() -> None:
    base = {
        "review_request_digest": "a" * 64,
        "recommendation_id": "recommendation.synthetic",
        "recommendation_digest": "b" * 64,
        "decision_ids": ("decision.technical", "decision.service-impact"),
        "decision_digests": ("c" * 64, "d" * 64),
        "disposition_code": FINAL_ACCEPTED,
        "basis_codes": ("recommendation-final-basis.review-evidence-sufficient",),
        "disposition_policy_id": "final-recommendation-disposition-policy.synthetic",
        "disposition_policy_digest": "e" * 64,
        "purpose": "Record a bounded final recommendation disposition for this generation.",
        "acknowledged_immutable_review_generation": True,
        "acknowledged_recommendation_level_decision_only": True,
        "acknowledged_handoff_eligibility_only": True,
        "acknowledged_no_workflow_itsm_change_or_operational_authority": True,
    }
    for field in (
        "recommendation_content",
        "findings",
        "artifact_location",
        "workflow_created",
        "approved_by",
    ):
        with pytest.raises(ValidationError):
            FinalRecommendationDispositionInput.model_validate({**base, field: "forbidden"})


@pytest.mark.asyncio
async def test_postgres_payload_round_trip_preserves_only_structured_metadata() -> None:
    (
        service,
        _,
        decisions,
        request,
        _,
        artifact,
        policy,
        actor,
        *_,
    ) = await final_disposition_fixture()
    record = await dispose(service, decisions, request, artifact, policy, actor)
    raw = FinalRecommendationDispositionService._normalize(asdict(record))
    assert isinstance(raw, dict)

    restored = PostgreSQLFinalRecommendationDispositionRepository._record_to_domain(raw)

    assert restored == record
    serialized = str(raw).lower()
    for forbidden in ("recommendation_content", "findings", "artifact_location", "command"):
        assert forbidden not in serialized
