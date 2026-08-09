from __future__ import annotations

from dataclasses import replace

from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.recommendations.application.review_request_ports import (
    RecommendationReviewRequestError,
)
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestInstruction,
    RecommendationReviewRequestReceipt,
    RecommendationReviewRequestRecord,
)


class SyntheticTrustedRecommendationReviewRequestOrchestrator:
    adapter_id = "recommendation-review-request-orchestrator.synthetic"
    attestor_id = "subject.recommendation-review-request-attestor"

    async def orchestrate(
        self,
        instruction: RecommendationReviewRequestInstruction,
        source: RecommendationReadinessAssessment,
        *,
        claim_id: str,
        policy_version: str,
        purpose: str,
        classification: str,
        browser_session_binding_digest: str,
    ) -> tuple[RecommendationReviewRequestReceipt, RecommendationReviewRequestRecord]:
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        track_statuses = tuple((track, "awaiting_reviewer") for track in instruction.track_codes)
        routing_digest = digest(
            [
                instruction.track_codes,
                instruction.queue_ids,
                instruction.routing_profile,
                instruction.sla_class,
                instruction.routing_profile_digest,
            ]
        )
        manifest_digest = digest(
            [
                instruction.review_request_id,
                instruction.recommendation_id,
                instruction.readiness_assessment_id,
                track_statuses,
                routing_digest,
                instruction.policy_digest,
            ]
        )
        source_binding_digest = digest(
            [
                source.canonical_digest,
                source.readiness_receipt_digest,
                source.source_artifact_digest,
                source.source_binding_digest,
                source.readiness_policy_digest,
            ]
        )
        record = RecommendationReviewRequestRecord(
            review_request_id=instruction.review_request_id,
            recommendation_id=instruction.recommendation_id,
            schema_version=instruction.request_schema,
            version=1,
            claim_id=claim_id,
            readiness_assessment_id=instruction.readiness_assessment_id,
            promotion_id=source.promotion_id,
            presentation_id=source.presentation_id,
            organization_id=instruction.organization_id,
            environment_id=instruction.environment_id,
            classification=classification,
            requester_subject_digest=instruction.requester_subject_digest,
            browser_session_binding_digest=browser_session_binding_digest,
            review_request_policy_id=instruction.policy_id,
            review_request_policy_digest=instruction.policy_digest,
            review_request_policy_version=policy_version,
            orchestrator_id=self.adapter_id,
            review_request_receipt_digest="0" * 64,
            review_request_authorization_digest=(instruction.review_request_authorization_digest),
            source_assessment_digest=source.canonical_digest,
            source_recommendation_digest=source.source_artifact_digest,
            source_binding_digest=source_binding_digest,
            source_outcome=source.source_outcome,
            option_count=source.option_count,
            preferred_count=source.preferred_count,
            track_codes=instruction.track_codes,
            queue_ids=instruction.queue_ids,
            track_statuses=track_statuses,
            routing_profile=instruction.routing_profile,
            sla_class=instruction.sla_class,
            manifest_digest=manifest_digest,
            state="review_requested",
            requested_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            purpose=purpose,
            canonical_digest="0" * 64,
            review_requested=True,
        )
        record = replace(record, canonical_digest=digest(payload(record)))
        receipt = RecommendationReviewRequestReceipt(
            review_request_id=instruction.review_request_id,
            schema_version="atlas.recommendation-review-request-receipt.v1",
            version=1,
            adapter_id=self.adapter_id,
            attested_by=self.attestor_id,
            recommendation_id=instruction.recommendation_id,
            recommendation_digest=instruction.recommendation_digest,
            readiness_assessment_id=instruction.readiness_assessment_id,
            readiness_assessment_digest=instruction.readiness_assessment_digest,
            policy_digest=instruction.policy_digest,
            review_request_authorization_digest=(instruction.review_request_authorization_digest),
            request_digest=record.canonical_digest,
            manifest_digest=manifest_digest,
            routing_digest=routing_digest,
            track_count=len(instruction.track_codes),
            requested_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            source_verified=True,
            routing_policy_preserved=True,
            immutable_manifest_confirmed=True,
            deterministic_orchestration=True,
            no_model_used=True,
            no_network_used=True,
            no_reviewer_assigned=True,
            no_operational_authority=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        record = replace(record, review_request_receipt_digest=receipt.canonical_digest)
        return receipt, record


class UnavailableTrustedRecommendationReviewRequestOrchestrator:
    async def orchestrate(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        raise RecommendationReviewRequestError(
            "recommendation_review_request_orchestrator_unavailable"
        )
