from __future__ import annotations

from dataclasses import replace

from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.recommendations.application.readiness_ports import (
    RecommendationReadinessError,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.readiness import (
    RecommendationReadinessAssessment,
    RecommendationReadinessInstruction,
    RecommendationReadinessReceipt,
)

READINESS_CHECKS = (
    "source.draft-and-current",
    "outcome.roles-consistent",
    "content.required-fields-present",
    "steps.conceptual-and-contiguous",
    "safety.risk-impact-recovery-present",
    "evidence.references-or-support-present",
    "authority.all-operational-flags-false",
)
READINESS_REASONS = (
    "source-not-draft",
    "outcome-role-mismatch",
    "required-content-missing",
    "conceptual-steps-invalid",
    "safety-detail-incomplete",
    "evidence-support-missing",
    "authority-boundary-invalid",
)


class SyntheticTrustedRecommendationReadinessEvaluator:
    evaluator_id = "recommendation-readiness-evaluator.synthetic"
    attestor_id = "subject.recommendation-readiness-attestor"

    async def evaluate(
        self,
        instruction: RecommendationReadinessInstruction,
        source: PromotedRecommendationArtifact,
        *,
        claim_id: str,
        policy_version: str,
        purpose: str,
        classification: str,
        browser_session_binding_digest: str,
    ) -> tuple[RecommendationReadinessReceipt, RecommendationReadinessAssessment]:
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        checks = self._checks(source)
        if tuple(checks) != instruction.required_check_ids:
            raise RecommendationReadinessError("recommendation_readiness_profile_invalid")
        reason_codes = tuple(reason for passed, reason in checks.values() if not passed)[
            : instruction.maximum_reason_count
        ]
        if any(reason not in instruction.allowed_reason_codes for reason in reason_codes):
            raise RecommendationReadinessError("recommendation_readiness_profile_invalid")
        passed_count = sum(passed for passed, _ in checks.values())
        evaluation_outcome = "ready" if passed_count == len(checks) else "blocked"
        source_binding_digest = digest(
            [
                source.canonical_digest,
                source.promotion_receipt_digest,
                source.source_binding_digest,
                source.promotion_policy_digest,
            ]
        )
        assessment = RecommendationReadinessAssessment(
            assessment_id=instruction.assessment_id,
            recommendation_id=instruction.recommendation_id,
            schema_version=instruction.assessment_schema,
            version=1,
            claim_id=claim_id,
            promotion_id=source.promotion_id,
            presentation_id=source.presentation_id,
            organization_id=instruction.organization_id,
            environment_id=instruction.environment_id,
            classification=classification,
            consumer_subject_digest=instruction.consumer_subject_digest,
            browser_session_binding_digest=browser_session_binding_digest,
            readiness_policy_id=instruction.policy_id,
            readiness_policy_digest=instruction.policy_digest,
            readiness_policy_version=policy_version,
            evaluator_id=self.evaluator_id,
            readiness_receipt_digest="0" * 64,
            readiness_authorization_digest=instruction.readiness_authorization_digest,
            source_artifact_digest=source.canonical_digest,
            source_binding_digest=source_binding_digest,
            source_outcome=source.outcome,
            option_count=len(source.options),
            preferred_count=sum(option.role == "preferred" for option in source.options),
            evaluation_outcome=evaluation_outcome,
            reason_codes=reason_codes,
            check_count=len(checks),
            passed_check_count=passed_count,
            state="ready_for_review" if evaluation_outcome == "ready" else "blocked",
            assessed_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            purpose=purpose,
            canonical_digest="0" * 64,
            recommendation_ready_for_review=evaluation_outcome == "ready",
        )
        assessment = replace(assessment, canonical_digest=digest(payload(assessment)))
        receipt = RecommendationReadinessReceipt(
            assessment_id=instruction.assessment_id,
            schema_version="atlas.recommendation-readiness-receipt.v1",
            version=1,
            evaluator_id=self.evaluator_id,
            attested_by=self.attestor_id,
            recommendation_id=instruction.recommendation_id,
            recommendation_digest=instruction.recommendation_digest,
            policy_digest=instruction.policy_digest,
            readiness_authorization_digest=instruction.readiness_authorization_digest,
            assessment_digest=assessment.canonical_digest,
            source_binding_digest=source_binding_digest,
            evaluation_outcome=evaluation_outcome,
            check_count=len(checks),
            passed_check_count=passed_count,
            reason_count=len(reason_codes),
            assessed_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            source_verified=True,
            outcome_preserved=True,
            deterministic_evaluation=True,
            no_model_used=True,
            no_network_used=True,
            no_operational_authority=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        assessment = replace(assessment, readiness_receipt_digest=receipt.canonical_digest)
        return receipt, assessment

    @staticmethod
    def _checks(
        source: PromotedRecommendationArtifact,
    ) -> dict[str, tuple[bool, str]]:
        roles_valid = (
            (
                source.outcome == "preferred"
                and sum(option.role == "preferred" for option in source.options) == 1
            )
            or (source.outcome == "tie" and all(option.role == "tied" for option in source.options))
            or (
                source.outcome == "no_support"
                and all(option.role == "unsupported" for option in source.options)
            )
        )
        content_present = bool(
            source.headline.strip()
            and source.safety_notice.strip()
            and source.purpose.strip()
            and all(
                option.title.strip()
                and option.intended_outcome.strip()
                and option.rationale.strip()
                and option.confidence.strip()
                and option.confidence_rationale.strip()
                for option in source.options
            )
        )
        steps_valid = all(
            tuple(step.order for step in option.steps) == tuple(range(1, len(option.steps) + 1))
            and all(
                step.conceptual_action.strip() and step.capability_class in {"C0", "C1"}
                for step in option.steps
            )
            for option in source.options
        )
        safety_complete = all(
            option.overall_risk.strip()
            and option.interruption_expected_mode.strip()
            and option.recovery_feasibility.strip()
            and option.work_maximum_minutes >= option.work_minimum_minutes
            and option.interruption_maximum_minutes >= option.interruption_minimum_minutes
            and option.recovery_maximum_minutes >= option.recovery_minimum_minutes
            for option in source.options
        )
        evidence_present = all(
            option.evidence_references or option.support_reasons for option in source.options
        )
        authority_valid = not any(
            (
                source.recommendation_ready_for_review,
                source.human_review_completed,
                source.recommendation_approved,
                source.workflow_created,
                source.itsm_record_created,
                source.execution_authorized,
                source.deployment_authorized,
                source.infrastructure_mutated,
            )
        )
        return {
            READINESS_CHECKS[0]: (
                source.state == "draft" and source.recommendation_promoted,
                READINESS_REASONS[0],
            ),
            READINESS_CHECKS[1]: (roles_valid, READINESS_REASONS[1]),
            READINESS_CHECKS[2]: (content_present, READINESS_REASONS[2]),
            READINESS_CHECKS[3]: (steps_valid, READINESS_REASONS[3]),
            READINESS_CHECKS[4]: (safety_complete, READINESS_REASONS[4]),
            READINESS_CHECKS[5]: (evidence_present, READINESS_REASONS[5]),
            READINESS_CHECKS[6]: (authority_valid, READINESS_REASONS[6]),
        }


class UnavailableTrustedRecommendationReadinessEvaluator:
    async def evaluate(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        raise RecommendationReadinessError("recommendation_readiness_evaluator_unavailable")
