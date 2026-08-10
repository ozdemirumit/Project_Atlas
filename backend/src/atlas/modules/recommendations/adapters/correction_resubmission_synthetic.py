from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime

from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.recommendations.application.correction_resubmission_ports import (
    RecommendationCorrectionError,
)
from atlas.modules.recommendations.domain.correction_resubmission import (
    RecommendationCorrectionInstruction,
    RecommendationCorrectionReceipt,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact


class SyntheticRecommendationCorrectionAdapter:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._artifacts: dict[str, PromotedRecommendationArtifact] = {}
        self.calls: list[RecommendationCorrectionInstruction] = []

    async def correct(
        self,
        instruction: RecommendationCorrectionInstruction,
        source: PromotedRecommendationArtifact,
    ) -> tuple[RecommendationCorrectionReceipt, PromotedRecommendationArtifact]:
        self.calls.append(instruction)
        now = self._clock()
        source_binding = self._digest(
            [
                source.canonical_digest,
                instruction.decision_aggregate_digest,
                instruction.correction_submission_digest,
            ]
        )
        artifact = replace(
            source,
            promotion_id=instruction.new_promotion_id,
            recommendation_id=instruction.new_recommendation_id,
            claim_id=instruction.correction_id,
            presentation_id=instruction.correction_submission_id,
            presentation_digest=instruction.correction_submission_digest,
            adjudication_id=(
                f"recommendation-correction-source.{instruction.correction_id.rsplit('.', 1)[-1]}"
            ),
            consumer_subject_digest=instruction.corrected_by_subject_digest,
            browser_session_binding_digest=instruction.browser_session_binding_digest,
            promotion_policy_id="recommendation-correction-policy.synthetic",
            promotion_policy_digest=instruction.correction_policy_digest,
            promotion_policy_version="policy-version.recommendation-correction-development-v1",
            promoter_id="recommendation-correction-adapter.synthetic",
            promotion_receipt_digest="0" * 64,
            promotion_authorization_digest=self._digest(
                [instruction.corrected_by_subject_digest, instruction.correction_policy_digest]
            ),
            source_binding_digest=source_binding,
            headline=f"Corrected: {source.headline}"[:500],
            promoted_at=now,
            expires_at=instruction.expires_at,
            byte_count=max(source.byte_count, len(source.headline.encode("utf-8")) + 11),
            canonical_digest="0" * 64,
            recommendation_ready_for_review=False,
            human_review_completed=False,
            recommendation_approved=False,
            workflow_created=False,
            itsm_record_created=False,
            execution_authorized=False,
            deployment_authorized=False,
            infrastructure_mutated=False,
            reused=False,
        )
        artifact_digest = self._artifact_digest(artifact)
        receipt = RecommendationCorrectionReceipt(
            correction_id=instruction.correction_id,
            schema_version="atlas.recommendation-correction-receipt.v1",
            version=1,
            adapter_id="recommendation-correction-adapter.synthetic",
            attested_by="subject.recommendation-correction-attestor",
            source_review_request_id=instruction.source_review_request_id,
            source_review_request_digest=instruction.source_review_request_digest,
            decision_aggregate_digest=instruction.decision_aggregate_digest,
            correction_submission_id=instruction.correction_submission_id,
            correction_submission_digest=instruction.correction_submission_digest,
            new_recommendation_id=instruction.new_recommendation_id,
            new_promotion_id=instruction.new_promotion_id,
            new_artifact_digest=artifact_digest,
            source_binding_digest=source_binding,
            corrected_at=now,
            expires_at=instruction.expires_at,
            source_verified=True,
            corrected_version_immutable=True,
            safe_content_verified=True,
            transient_buffers_erased=True,
            artifact_channel_closed=True,
            no_model_used=True,
            no_network_used=True,
            no_operational_authority=True,
            signature_verified=True,
            instruction_digest=self._digest(asdict(instruction)),
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=self._receipt_digest(receipt))
        artifact = replace(
            artifact,
            promotion_receipt_digest=receipt.canonical_digest,
            canonical_digest=artifact_digest,
        )
        self._artifacts[artifact.recommendation_id] = artifact
        return receipt, artifact

    async def get_artifact(
        self, *, recommendation_id: str
    ) -> PromotedRecommendationArtifact | None:
        return self._artifacts.get(recommendation_id)

    @staticmethod
    def _digest(value: object) -> str:
        return GovernedProtectedModelInvocationService._digest(value)

    @staticmethod
    def _artifact_digest(artifact: PromotedRecommendationArtifact) -> str:
        unsigned = replace(
            artifact,
            promotion_receipt_digest="0" * 64,
            canonical_digest="0" * 64,
        )
        return GovernedProtectedModelInvocationService._digest(
            GovernedProtectedModelInvocationService._payload(unsigned)
        )

    @classmethod
    def _receipt_digest(cls, receipt: RecommendationCorrectionReceipt) -> str:
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return cls._digest(payload)


class UnavailableRecommendationCorrectionAdapter:
    async def correct(
        self,
        instruction: RecommendationCorrectionInstruction,
        source: PromotedRecommendationArtifact,
    ) -> tuple[RecommendationCorrectionReceipt, PromotedRecommendationArtifact]:
        del instruction, source
        raise RecommendationCorrectionError("recommendation_correction_adapter_unavailable")

    async def get_artifact(
        self, *, recommendation_id: str
    ) -> PromotedRecommendationArtifact | None:
        del recommendation_id
        raise RecommendationCorrectionError(
            "recommendation_correction_artifact_provider_unavailable"
        )
