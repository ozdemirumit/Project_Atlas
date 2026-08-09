from __future__ import annotations

from dataclasses import replace

from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    ProtectedPresentedRecommendation,
    ProtectedRecommendationPresentationRecord,
)
from atlas.modules.recommendations.application.promotion_ports import (
    RecommendationPromotionError,
)
from atlas.modules.recommendations.domain.promotion import (
    PromotedRecommendationArtifact,
    RecommendationPromotionInstruction,
    RecommendationPromotionReceipt,
)


class SyntheticTrustedRecommendationPromoter:
    promoter_id = "recommendation-promoter.synthetic"
    attestor_id = "subject.recommendation-promoter-attestor"

    async def promote(
        self,
        instruction: RecommendationPromotionInstruction,
        presentation_record: ProtectedRecommendationPresentationRecord,
        presentation: ProtectedPresentedRecommendation,
        *,
        claim_id: str,
        policy_version: str,
        purpose: str,
        classification: str,
        browser_session_binding_digest: str,
    ) -> tuple[RecommendationPromotionReceipt, PromotedRecommendationArtifact]:
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        source_binding_digest = digest(
            [
                presentation_record.canonical_digest,
                presentation.canonical_digest,
                presentation_record.adjudication_digest,
                presentation_record.source_binding_digest,
            ]
        )
        artifact = PromotedRecommendationArtifact(
            promotion_id=instruction.promotion_id,
            recommendation_id=instruction.recommendation_id,
            schema_version=instruction.artifact_schema,
            version=1,
            claim_id=claim_id,
            presentation_id=instruction.presentation_id,
            presentation_digest=instruction.presentation_digest,
            adjudication_id=presentation_record.adjudication_id,
            organization_id=instruction.organization_id,
            environment_id=instruction.environment_id,
            classification=classification,
            consumer_subject_digest=instruction.consumer_subject_digest,
            browser_session_binding_digest=browser_session_binding_digest,
            promotion_policy_id=instruction.policy_id,
            promotion_policy_digest=instruction.policy_digest,
            promotion_policy_version=policy_version,
            promoter_id=self.promoter_id,
            promotion_receipt_digest="0" * 64,
            promotion_authorization_digest=instruction.promotion_authorization_digest,
            source_binding_digest=source_binding_digest,
            outcome=presentation.outcome,
            headline=presentation.headline,
            safety_notice=(
                "Decision support draft only. Promotion is not review readiness, approval, "
                "workflow creation, execution authorization, or infrastructure mutation."
            ),
            options=presentation.options,
            evidence_needs=presentation.evidence_needs,
            state="draft",
            promoted_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            purpose=purpose,
            byte_count=presentation.byte_count,
            canonical_digest="0" * 64,
        )
        artifact = replace(artifact, canonical_digest=digest(payload(artifact)))
        receipt = RecommendationPromotionReceipt(
            promotion_id=instruction.promotion_id,
            schema_version="atlas.recommendation-promotion-receipt.v1",
            version=1,
            promoter_id=self.promoter_id,
            attested_by=self.attestor_id,
            presentation_id=instruction.presentation_id,
            presentation_digest=instruction.presentation_digest,
            policy_digest=instruction.policy_digest,
            promotion_authorization_digest=instruction.promotion_authorization_digest,
            artifact_digest=artifact.canonical_digest,
            source_binding_digest=source_binding_digest,
            outcome=artifact.outcome,
            option_count=len(artifact.options),
            preferred_count=sum(option.role == "preferred" for option in artifact.options),
            byte_count=artifact.byte_count,
            promoted_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            source_verified=True,
            outcome_preserved=True,
            safe_content_verified=True,
            no_model_used=True,
            no_network_used=True,
            no_operational_authority=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        artifact = replace(
            artifact,
            promotion_receipt_digest=receipt.canonical_digest,
        )
        return receipt, artifact


class UnavailableTrustedRecommendationPromoter:
    async def promote(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        raise RecommendationPromotionError("recommendation_promoter_unavailable")
