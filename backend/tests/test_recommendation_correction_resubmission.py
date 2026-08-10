from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_package_acquisition import CollectingAuditSink
from test_recommendation_review_decision import (
    decide,
    review_decision_fixture,
)
from test_target_session import target_session_operator

from atlas.api.recommendation_correction_resubmission_schemas import (
    RecommendationCorrectionInput,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.adapters.correction_resubmission_memory import (
    InMemoryRecommendationCorrectionPolicySource,
    InMemoryRecommendationCorrectionRepository,
)
from atlas.modules.recommendations.adapters.correction_resubmission_postgres import (
    PostgreSQLRecommendationCorrectionRepository,
)
from atlas.modules.recommendations.adapters.correction_resubmission_synthetic import (
    SyntheticRecommendationCorrectionAdapter,
)
from atlas.modules.recommendations.application.correction_resubmission import (
    RecommendationCorrectionService,
    build_development_recommendation_correction_policy,
)
from atlas.modules.recommendations.application.correction_resubmission_ports import (
    RecommendationCorrectionError,
)
from atlas.modules.recommendations.domain.correction_resubmission import (
    RecommendationCorrectionPolicySnapshot,
    RecommendationCorrectionRecord,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.review_decision import (
    RecommendationTrackReviewDecisionRecord,
)


class RecordingCorrectionPermissionAuthorizer:
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
            raise RecommendationCorrectionError("recommendation_correction_permission_denied")


async def correction_fixture() -> tuple[
    RecommendationCorrectionService,
    InMemoryRecommendationCorrectionRepository,
    tuple[RecommendationTrackReviewDecisionRecord, ...],
    PromotedRecommendationArtifact,
    RecommendationCorrectionPolicySnapshot,
    AuthenticatedSubject,
    SyntheticRecommendationCorrectionAdapter,
    RecordingCorrectionPermissionAuthorizer,
    CollectingAuditSink,
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
        disposition_code="review-disposition.changes-required",
    )
    basis = ("review-basis.service-impact-scope", "review-basis.business-continuity")
    service_impact = replace(
        technical,
        decision_id="decision.synthetic-service-impact-correction-review",
        claim_id="claim.synthetic-service-impact-correction-review",
        source_finding_presentation_id="finding-presentation.synthetic-service-impact-correction",
        source_finding_presentation_digest=decision_service._digest(
            "finding-presentation.synthetic-service-impact-correction"
        ),
        track_code="review-track.service-impact",
        disposition_code="review-disposition.passed",
        basis_codes=basis,
        basis_digest=decision_service._digest(basis),
        decided_by_subject_digest=decision_service._digest(
            [decision_policy.subject_digest_salt_digest, "subject.synthetic-service-reviewer"]
        ),
        technical_review_completed=False,
        service_impact_review_completed=True,
        technical_review_passed=False,
        service_impact_review_passed=True,
        correction_required=False,
        canonical_digest="0" * 64,
    )
    service_impact = replace(
        service_impact,
        canonical_digest=decision_service._digest(decision_service._record_payload(service_impact)),
    )
    assert await decision_repository.add(service_impact)
    decisions, request, _, artifact = await decision_service.correction_resubmission_source(
        review_request_id=technical.review_request_id
    )
    actor = replace(
        target_session_operator("subject.knowledge-retrieval-consumer"),
        organization_id=request.organization_id,
        authenticated_at=technical.decided_at,
    )
    policy = build_development_recommendation_correction_policy(
        organization_id=request.organization_id,
        environment_id=request.environment_id,
        issued_at=technical.decided_at - timedelta(hours=1),
        expires_at=technical.decided_at + timedelta(hours=1),
    )
    assert artifact.consumer_subject_digest == RecommendationCorrectionService._digest(
        [policy.source_consumer_subject_digest_salt_digest, actor.subject_id]
    )
    repository = InMemoryRecommendationCorrectionRepository()
    adapter = SyntheticRecommendationCorrectionAdapter(clock=lambda: technical.decided_at)
    permission = RecordingCorrectionPermissionAuthorizer()
    audit = CollectingAuditSink()
    service = RecommendationCorrectionService(
        repository=repository,
        source=decision_service,
        policy_source=InMemoryRecommendationCorrectionPolicySource((policy,)),
        permission_authorizer=permission,
        adapter=adapter,
        audit_sink=audit,
        environment_id=request.environment_id,
        clock=lambda: technical.decided_at,
    )
    return service, repository, decisions, artifact, policy, actor, adapter, permission, audit


async def correct(
    service: RecommendationCorrectionService,
    decisions: tuple[RecommendationTrackReviewDecisionRecord, ...],
    artifact: PromotedRecommendationArtifact,
    policy: RecommendationCorrectionPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "recommendation-correction-001",
) -> RecommendationCorrectionRecord:
    source = decisions[0]
    return await service.create(
        actor=actor,
        source_review_request_id=source.review_request_id,
        source_review_request_digest=source.source_review_request_digest,
        source_recommendation_id=artifact.recommendation_id,
        source_recommendation_digest=artifact.canonical_digest,
        source_decision_ids=(decisions[0].decision_id, decisions[1].decision_id),
        source_decision_digests=(
            decisions[0].canonical_digest,
            decisions[1].canonical_digest,
        ),
        correction_submission_id="recommendation-correction-submission.synthetic-001",
        correction_submission_digest=RecommendationCorrectionService._digest(
            "opaque-correction-submission-001"
        ),
        correction_policy_id=policy.policy_id,
        correction_policy_digest=policy.canonical_digest,
        purpose="Create a corrected immutable recommendation version for fresh readiness review.",
        exact_change_requirements_addressed_acknowledged=True,
        new_immutable_version_acknowledged=True,
        fresh_readiness_required_acknowledged=True,
        no_later_authority_acknowledged=True,
        browser_session_id="session_recommendation_correction_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_recommendation_correction",
    )


@pytest.mark.asyncio
async def test_correction_creates_new_promoted_version_and_resets_authority() -> None:
    (
        service,
        repository,
        decisions,
        artifact,
        policy,
        actor,
        adapter,
        permission,
        audit,
    ) = await correction_fixture()
    record = await correct(service, decisions, artifact, policy, actor)
    repeated = await correct(service, decisions, artifact, policy, actor)
    corrected = await service.get_corrected_promotion(
        actor=actor,
        recommendation_id=record.new_recommendation_id,
        browser_session_id="session_recommendation_correction_001",
        correlation_id="cor_recommendation_correction_readiness_source",
    )

    assert record.correction_created and record.recommendation_promoted
    assert record.state == "recommendation_correction_resubmitted"
    assert not record.readiness_assessed and not record.review_requested
    assert not record.reviewer_assigned and not record.human_findings_recorded
    assert not record.final_disposition_recorded and not record.recommendation_approved
    assert not record.workflow_created and not record.execution_authorized
    assert not record.infrastructure_mutated and repeated.reused
    assert corrected.artifact.recommendation_id != artifact.recommendation_id
    assert corrected.artifact.canonical_digest == record.new_artifact_digest
    assert not corrected.artifact.recommendation_ready_for_review
    assert await repository.get_by_source_request(
        source_review_request_id=record.source_review_request_id
    )
    assert len(adapter.calls) == 1
    assert len(permission.calls) == 3
    assert [item.result_code for item in audit.records] == [
        "recommendation_correction_intent_recorded",
        "recommendation_correction_claimed",
        "recommendation_correction_resubmitted",
        "recommendation_correction_read",
    ]


@pytest.mark.asyncio
async def test_correction_rejects_wrong_owner_and_conflicting_replay() -> None:
    (
        service,
        repository,
        decisions,
        artifact,
        policy,
        actor,
        adapter,
        *_,
    ) = await correction_fixture()
    wrong = replace(actor, subject_id="subject.unrelated-recommendation-consumer")
    with pytest.raises(RecommendationCorrectionError, match="source_invalid"):
        await correct(service, decisions, artifact, policy, wrong)
    assert not adapter.calls
    assert (
        await repository.get_claim_by_source_request(
            source_review_request_id=decisions[0].review_request_id
        )
        is None
    )

    await correct(service, decisions, artifact, policy, actor)
    with pytest.raises(RecommendationCorrectionError, match="idempotency_conflict"):
        await correct(
            service,
            decisions,
            artifact,
            policy,
            actor,
            idempotency_key="recommendation-correction-conflict-002",
        )


def test_correction_schema_and_postgres_mapping_exclude_protected_content() -> None:
    fields = RecommendationCorrectionInput.model_fields
    for forbidden in (
        "corrected_content",
        "patch",
        "findings",
        "options",
        "artifact_location",
        "reviewer_id",
        "approval",
        "command",
    ):
        assert forbidden not in fields
    with pytest.raises(ValidationError):
        RecommendationCorrectionInput.model_validate(
            {
                "source_review_request_digest": "a" * 64,
                "source_recommendation_id": "recommendation.source",
                "source_recommendation_digest": "b" * 64,
                "source_decision_ids": ("decision.one", "decision.two"),
                "source_decision_digests": ("c" * 64, "d" * 64),
                "correction_submission_id": "correction-submission.one",
                "correction_submission_digest": "e" * 64,
                "correction_policy_id": "correction-policy.one",
                "correction_policy_digest": "f" * 64,
                "purpose": "Correct the exact recommendation through the trusted boundary.",
                "acknowledged_exact_change_requirements_addressed": True,
                "acknowledged_new_immutable_recommendation_version": True,
                "acknowledged_fresh_readiness_required": True,
                "acknowledged_no_review_approval_or_operational_authority": True,
                "corrected_content": "must never enter the ordinary API",
            }
        )
    assert PostgreSQLRecommendationCorrectionRepository._record_to_domain is not None
