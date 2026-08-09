from __future__ import annotations

from dataclasses import asdict, replace
from datetime import timedelta

from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.recommendations.application.reviewer_assignment_ports import (
    RecommendationReviewerAssignmentError,
)
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord
from atlas.modules.recommendations.domain.reviewer_assignment import (
    ASSIGNED,
    RecommendationReviewerAssignmentInstruction,
    RecommendationReviewerAssignmentReceipt,
)


class SyntheticTrustedRecommendationReviewerAssignmentAdapter:
    adapter_id = "recommendation-reviewer-assignment-adapter.synthetic"
    attestor_id = "subject.recommendation-reviewer-assignment-attestor"

    async def assign(
        self,
        instruction: RecommendationReviewerAssignmentInstruction,
        source: RecommendationReviewRequestRecord,
    ) -> RecommendationReviewerAssignmentReceipt:
        del source
        digest = GovernedProtectedModelInvocationService._digest
        seed = digest(
            [
                instruction.assignment_set_id,
                instruction.review_request_digest,
                instruction.policy_digest,
            ]
        )
        reviewers = (
            digest(
                [
                    instruction.subject_digest_salt_digest,
                    "subject.synthetic-technical-reviewer",
                ]
            ),
            digest(
                [
                    instruction.subject_digest_salt_digest,
                    "subject.synthetic-service-impact-reviewer",
                ]
            ),
        )
        if any(item in instruction.exclusion_subject_digests for item in reviewers):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_no_eligible_reviewer"
            )
        track_assignments = tuple(
            (
                track,
                queue,
                f"recommendation-review-assignment.{index}.{seed[:24]}",
                reviewers[index],
                ASSIGNED,
            )
            for index, (track, queue) in enumerate(
                zip(instruction.track_codes, instruction.queue_ids, strict=True)
            )
        )
        routing_digest = digest(
            [
                instruction.track_codes,
                instruction.queue_ids,
                instruction.routing_profile_digest,
            ]
        )
        receipt = RecommendationReviewerAssignmentReceipt(
            assignment_set_id=instruction.assignment_set_id,
            schema_version="atlas.recommendation-reviewer-assignment-receipt.v1",
            version=1,
            adapter_id=self.adapter_id,
            attested_by=self.attestor_id,
            review_request_id=instruction.review_request_id,
            review_request_digest=instruction.review_request_digest,
            assignment_digest=digest([seed, track_assignments]),
            routing_digest=routing_digest,
            eligibility_digest=digest(
                [instruction.directory_source_digest, instruction.eligibility_profile_digests]
            ),
            separation_digest=digest(
                [
                    instruction.separation_profile_digest,
                    instruction.exclusion_subject_digests,
                    reviewers,
                ]
            ),
            artifact_digest=digest([seed, "encrypted-identity-references"]),
            track_assignments=track_assignments,
            created_at=instruction.requested_at,
            expires_at=min(
                instruction.expires_at,
                instruction.requested_at + timedelta(minutes=instruction.assignment_ttl_minutes),
            ),
            directory_snapshot_current=True,
            eligibility_verified=True,
            excluded_actors_verified=True,
            distinct_reviewers_verified=True,
            immutable_assignments_confirmed=True,
            encrypted_identity_references=True,
            transient_identity_buffers_erased=True,
            directory_channel_closed=True,
            no_content_opened=True,
            no_model_used=True,
            no_operational_authority=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=digest(payload))


class UnavailableTrustedRecommendationReviewerAssignmentAdapter:
    async def assign(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        raise RecommendationReviewerAssignmentError(
            "recommendation_reviewer_assignment_adapter_unavailable"
        )
