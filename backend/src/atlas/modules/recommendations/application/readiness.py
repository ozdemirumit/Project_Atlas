from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_READINESS_CREATE,
    RECOMMENDATION_READINESS_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.recommendations.adapters.readiness_synthetic import (
    READINESS_CHECKS,
    READINESS_REASONS,
)
from atlas.modules.recommendations.application.promotion import (
    GovernedRecommendationPromotionService,
)
from atlas.modules.recommendations.application.promotion_ports import (
    RecommendationPromotionError,
)
from atlas.modules.recommendations.application.readiness_ports import (
    RecommendationReadinessError,
    RecommendationReadinessPermissionAuthorizer,
    RecommendationReadinessPolicySource,
    RecommendationReadinessPromotionSource,
    RecommendationReadinessRepository,
    RecommendationReadinessUncertainError,
    TrustedRecommendationReadinessEvaluator,
)
from atlas.modules.recommendations.domain.promotion import (
    PromotedRecommendationArtifact,
    RecommendationPromotionResult,
)
from atlas.modules.recommendations.domain.readiness import (
    RecommendationReadinessAssessment,
    RecommendationReadinessClaim,
    RecommendationReadinessInstruction,
    RecommendationReadinessManifest,
    RecommendationReadinessPolicySnapshot,
    RecommendationReadinessReceipt,
    RecommendationReadinessResult,
)

POLICY_SCHEMA = "atlas.recommendation-readiness-policy.v1"
CLAIM_SCHEMA = "atlas.recommendation-readiness-claim.v1"
ASSESSMENT_SCHEMA = "atlas.recommendation-readiness-assessment.v1"


class GovernedRecommendationReadinessService:
    def __init__(
        self,
        *,
        repository: RecommendationReadinessRepository,
        promotion_source: RecommendationReadinessPromotionSource,
        policy_source: RecommendationReadinessPolicySource,
        permission_authorizer: RecommendationReadinessPermissionAuthorizer,
        evaluator: TrustedRecommendationReadinessEvaluator,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._promotion_source = promotion_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._evaluator = evaluator
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        recommendation_digest: str,
        readiness_policy_id: str,
        readiness_policy_digest: str,
        purpose: str,
        readiness_is_not_review_acknowledged: bool,
        blocked_requires_new_version_acknowledged: bool,
        no_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> RecommendationReadinessResult:
        self._require_human(actor)
        if not all(
            (
                readiness_is_not_review_acknowledged,
                blocked_requires_new_version_acknowledged,
                no_operational_authority_acknowledged,
            )
        ):
            raise RecommendationReadinessError("recommendation_readiness_acknowledgement_required")
        now = self._clock()
        policy = await self._policy_source.get_by_id(policy_id=readiness_policy_id)
        self._verify_policy(policy, readiness_policy_digest, actor, self._environment_id, now)
        assert policy is not None
        self._require_policy_assurance(actor, policy)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            correlation_id=correlation_id,
        )
        source = await self._read_source(
            actor, recommendation_id, browser_session_id, correlation_id
        )
        self._verify_source(source, policy, recommendation_digest, purpose, now)
        artifact = source.artifact
        subject_digest = self._digest([actor.subject_id, actor.organization_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        idempotency_digest = self._digest([subject_digest, idempotency_key])
        request_digest = self._digest(
            [
                recommendation_id,
                recommendation_digest,
                policy.canonical_digest,
                purpose,
                readiness_is_not_review_acknowledged,
                blocked_requires_new_version_acknowledged,
                no_operational_authority_acknowledged,
            ]
        )
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=subject_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                subject_digest,
                idempotency_digest,
                browser_digest,
                request_digest,
                actor,
                browser_session_id,
                correlation_id,
            )
        assessment_id = f"recommendation-readiness.{uuid4().hex}"
        claim = RecommendationReadinessClaim(
            claim_id=f"claim.recommendation-readiness.{uuid4().hex}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            assessment_id=assessment_id,
            recommendation_id=recommendation_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._claim_digest(claim))
        await self._audit(
            actor,
            correlation_id,
            "recommendation_readiness_intent_recorded",
            recommendation_id,
        )
        if not await self._repository.claim(claim):
            collision = await self._repository.get_claim_by_idempotency(
                claimed_by_subject_digest=subject_digest,
                idempotency_digest=idempotency_digest,
            )
            if collision is None:
                raise RecommendationReadinessError("recommendation_readiness_already_claimed")
            return await self._reuse(
                collision,
                subject_digest,
                idempotency_digest,
                browser_digest,
                request_digest,
                actor,
                browser_session_id,
                correlation_id,
            )
        await self._audit(actor, correlation_id, "recommendation_readiness_claimed", assessment_id)
        try:
            source = await self._read_source(
                actor, recommendation_id, browser_session_id, correlation_id
            )
            self._verify_source(source, policy, recommendation_digest, purpose, now)
            artifact = source.artifact
            authorization_digest = self._digest(
                [
                    artifact.promotion_authorization_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    artifact.canonical_digest,
                ]
            )
            expires_at = min(
                artifact.expires_at,
                policy.expires_at,
                now + timedelta(minutes=policy.retention_minutes),
            )
            instruction = RecommendationReadinessInstruction(
                assessment_id=assessment_id,
                recommendation_id=recommendation_id,
                recommendation_digest=artifact.canonical_digest,
                promotion_id=artifact.promotion_id,
                organization_id=artifact.organization_id,
                environment_id=artifact.environment_id,
                consumer_subject_digest=artifact.consumer_subject_digest,
                readiness_authorization_digest=authorization_digest,
                policy_id=policy.policy_id,
                policy_digest=policy.canonical_digest,
                assessment_schema=policy.assessment_schema,
                required_check_ids=policy.required_check_ids,
                allowed_reason_codes=policy.allowed_reason_codes,
                maximum_reason_count=policy.maximum_reason_count,
                readiness_profile_digest=policy.readiness_profile_digest,
                prohibited_content_profile_digest=policy.prohibited_content_profile_digest,
                requested_at=now,
                expires_at=expires_at,
            )
            receipt, assessment = await self._evaluator.evaluate(
                instruction,
                artifact,
                claim_id=claim.claim_id,
                policy_version=policy.policy_version,
                purpose=purpose,
                classification=artifact.classification,
                browser_session_binding_digest=browser_digest,
            )
            self._verify_output(receipt, assessment, instruction, policy, artifact, claim)
            await self._repository.save(assessment)
            await self._audit(
                actor,
                correlation_id,
                "recommendation_readiness_completed",
                assessment_id,
            )
        except RecommendationReadinessError:
            raise
        except RecommendationPromotionError as error:
            raise RecommendationReadinessError("recommendation_readiness_source_invalid") from error
        except Exception as error:
            raise RecommendationReadinessUncertainError(
                "recommendation_readiness_persistence_uncertain"
            ) from error
        return RecommendationReadinessResult(
            assessment=assessment, manifest=self._manifest(assessment)
        )

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        assessment_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationReadinessResult:
        self._require_human(actor)
        assessment = await self._repository.get(assessment_id=assessment_id)
        if assessment is None:
            raise RecommendationReadinessError("recommendation_readiness_not_found")
        self._require_scope(actor, assessment.organization_id, assessment.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=assessment.readiness_policy_id)
        now = self._clock()
        if (
            policy is None
            or assessment.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or assessment.canonical_digest != self._assessment_digest(assessment)
            or now >= assessment.expires_at
            or policy.canonical_digest != assessment.readiness_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
        ):
            raise RecommendationReadinessError("recommendation_readiness_not_found")
        self._require_policy_assurance(actor, policy)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=assessment.organization_id,
            environment_id=assessment.environment_id,
            correlation_id=correlation_id,
        )
        source = await self._read_source(
            actor, assessment.recommendation_id, browser_session_id, correlation_id
        )
        self._verify_source(
            source, policy, assessment.source_artifact_digest, assessment.purpose, now
        )
        artifact = source.artifact
        if (
            artifact.promotion_id != assessment.promotion_id
            or artifact.presentation_id != assessment.presentation_id
            or artifact.outcome != assessment.source_outcome
            or len(artifact.options) != assessment.option_count
            or sum(option.role == "preferred" for option in artifact.options)
            != assessment.preferred_count
        ):
            raise RecommendationReadinessError("recommendation_readiness_integrity_failed")
        await self._audit(
            actor,
            correlation_id,
            "recommendation_readiness_read",
            assessment_id,
            permission_id=RECOMMENDATION_READINESS_READ,
        )
        reused = replace(assessment, reused=True)
        return RecommendationReadinessResult(assessment=reused, manifest=self._manifest(assessment))

    async def close(self) -> None:
        await self._repository.close()

    async def protected_content_source(
        self, *, assessment_id: str
    ) -> tuple[RecommendationReadinessAssessment, PromotedRecommendationArtifact]:
        assessment = await self._repository.get(assessment_id=assessment_id)
        if assessment is None or assessment.canonical_digest != self._assessment_digest(assessment):
            raise RecommendationReadinessError("recommendation_readiness_not_found")
        policy = await self._policy_source.get_by_id(policy_id=assessment.readiness_policy_id)
        if (
            policy is None
            or policy.canonical_digest != assessment.readiness_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
        ):
            raise RecommendationReadinessError("recommendation_readiness_not_found")
        artifact = await self._promotion_source.protected_content_source(
            recommendation_id=assessment.recommendation_id
        )
        if (
            artifact.promotion_id != assessment.promotion_id
            or artifact.canonical_digest != assessment.source_artifact_digest
            or artifact.outcome != assessment.source_outcome
            or len(artifact.options) != assessment.option_count
        ):
            raise RecommendationReadinessError("recommendation_readiness_integrity_failed")
        return assessment, artifact

    async def _read_source(
        self,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationPromotionResult:
        try:
            return await self._promotion_source.get(
                actor=actor,
                recommendation_id=recommendation_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
        except RecommendationPromotionError as error:
            raise RecommendationReadinessError("recommendation_readiness_source_invalid") from error

    @classmethod
    def _verify_policy(
        cls,
        policy: RecommendationReadinessPolicySnapshot | None,
        expected_digest: str,
        actor: AuthenticatedSubject,
        environment_id: str,
        now: datetime,
    ) -> None:
        if (
            policy is None
            or policy.canonical_digest != expected_digest
            or policy.canonical_digest != cls._digest(cls._payload(policy))
            or policy.schema_version != POLICY_SCHEMA
            or policy.assessment_schema != ASSESSMENT_SCHEMA
            or policy.organization_id != actor.organization_id
            or policy.environment_id != environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise RecommendationReadinessError("recommendation_readiness_policy_invalid")

    @classmethod
    def _verify_source(
        cls,
        source: RecommendationPromotionResult,
        policy: RecommendationReadinessPolicySnapshot,
        expected_digest: str,
        purpose: str,
        now: datetime,
    ) -> None:
        artifact = source.artifact
        if (
            artifact.canonical_digest != expected_digest
            or artifact.canonical_digest
            != GovernedRecommendationPromotionService._artifact_digest(artifact)
            or artifact.schema_version != policy.required_source_schema
            or artifact.state != policy.required_source_state
            or artifact.purpose != purpose
            or artifact.outcome not in policy.allowed_outcomes
            or len(artifact.options) > policy.maximum_option_count
            or now >= artifact.expires_at
            or not artifact.recommendation_promoted
            or artifact.recommendation_ready_for_review
            or artifact.human_review_completed
            or artifact.recommendation_approved
            or artifact.workflow_created
            or artifact.itsm_record_created
            or artifact.execution_authorized
            or artifact.deployment_authorized
            or artifact.infrastructure_mutated
        ):
            raise RecommendationReadinessError("recommendation_readiness_source_invalid")

    @classmethod
    def _verify_output(
        cls,
        receipt: RecommendationReadinessReceipt,
        assessment: RecommendationReadinessAssessment,
        instruction: RecommendationReadinessInstruction,
        policy: RecommendationReadinessPolicySnapshot,
        source: PromotedRecommendationArtifact,
        claim: RecommendationReadinessClaim,
    ) -> None:
        expected_source_binding = cls._digest(
            [
                source.canonical_digest,
                source.promotion_receipt_digest,
                source.source_binding_digest,
                source.promotion_policy_digest,
            ]
        )
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.evaluator_id != policy.required_evaluator_id
            or receipt.attested_by != policy.required_evaluator_attestor_id
            or receipt.assessment_id != instruction.assessment_id
            or receipt.recommendation_id != instruction.recommendation_id
            or receipt.recommendation_digest != instruction.recommendation_digest
            or receipt.policy_digest != policy.canonical_digest
            or receipt.readiness_authorization_digest != instruction.readiness_authorization_digest
            or receipt.assessment_digest != assessment.canonical_digest
            or receipt.source_binding_digest != expected_source_binding
            or receipt.evaluation_outcome != assessment.evaluation_outcome
            or receipt.check_count != assessment.check_count
            or receipt.passed_check_count != assessment.passed_check_count
            or receipt.reason_count != len(assessment.reason_codes)
            or receipt.assessed_at != instruction.requested_at
            or receipt.expires_at != instruction.expires_at
            or assessment.assessment_id != instruction.assessment_id
            or assessment.recommendation_id != instruction.recommendation_id
            or assessment.claim_id != claim.claim_id
            or assessment.promotion_id != source.promotion_id
            or assessment.presentation_id != source.presentation_id
            or assessment.schema_version != policy.assessment_schema
            or assessment.organization_id != instruction.organization_id
            or assessment.environment_id != instruction.environment_id
            or assessment.classification != source.classification
            or assessment.consumer_subject_digest != instruction.consumer_subject_digest
            or assessment.browser_session_binding_digest != claim.browser_session_binding_digest
            or assessment.readiness_policy_id != policy.policy_id
            or assessment.readiness_policy_digest != policy.canonical_digest
            or assessment.readiness_policy_version != policy.policy_version
            or assessment.evaluator_id != policy.required_evaluator_id
            or assessment.readiness_receipt_digest != receipt.canonical_digest
            or assessment.readiness_authorization_digest
            != instruction.readiness_authorization_digest
            or assessment.source_artifact_digest != source.canonical_digest
            or assessment.source_binding_digest != expected_source_binding
            or assessment.source_outcome != source.outcome
            or assessment.option_count != len(source.options)
            or assessment.preferred_count
            != sum(option.role == "preferred" for option in source.options)
            or any(reason not in policy.allowed_reason_codes for reason in assessment.reason_codes)
            or assessment.check_count != len(policy.required_check_ids)
            or assessment.assessed_at != instruction.requested_at
            or assessment.expires_at != instruction.expires_at
            or assessment.purpose != source.purpose
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or assessment.canonical_digest != cls._assessment_digest(assessment)
        ):
            raise RecommendationReadinessError("recommendation_readiness_receipt_invalid")

    async def _reuse(
        self,
        claim: RecommendationReadinessClaim,
        subject_digest: str,
        idempotency_digest: str,
        browser_digest: str,
        request_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationReadinessResult:
        if (
            claim.canonical_digest != self._claim_digest(claim)
            or claim.claimed_by_subject_digest != subject_digest
            or claim.idempotency_digest != idempotency_digest
            or claim.organization_id != actor.organization_id
            or claim.environment_id != self._environment_id
        ):
            raise RecommendationReadinessError("recommendation_readiness_integrity_failed")
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise RecommendationReadinessError("recommendation_readiness_idempotency_conflict")
        return await self.get(
            actor=actor,
            assessment_id=claim.assessment_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise RecommendationReadinessError("recommendation_readiness_human_required")

    @staticmethod
    def _require_policy_assurance(
        actor: AuthenticatedSubject, policy: RecommendationReadinessPolicySnapshot
    ) -> None:
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise RecommendationReadinessError("recommendation_readiness_policy_assurance_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise RecommendationReadinessError("recommendation_readiness_not_found")

    @staticmethod
    def _manifest(
        assessment: RecommendationReadinessAssessment,
    ) -> RecommendationReadinessManifest:
        return RecommendationReadinessManifest(
            assessment_id=assessment.assessment_id,
            recommendation_id=assessment.recommendation_id,
            promotion_id=assessment.promotion_id,
            source_outcome=assessment.source_outcome,
            option_count=assessment.option_count,
            preferred_count=assessment.preferred_count,
            evaluation_outcome=assessment.evaluation_outcome,
            reason_codes=assessment.reason_codes,
            check_count=assessment.check_count,
            passed_check_count=assessment.passed_check_count,
            state=assessment.state,
            assessed_at=assessment.assessed_at,
            expires_at=assessment.expires_at,
            recommendation_ready_for_review=assessment.recommendation_ready_for_review,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = RECOMMENDATION_READINESS_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendation.review-readiness",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.recommendation.review-readiness",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    _digest = staticmethod(GovernedProtectedModelInvocationService._digest)
    _payload = staticmethod(GovernedProtectedModelInvocationService._payload)

    @classmethod
    def _claim_digest(cls, claim: RecommendationReadinessClaim) -> str:
        return cls._digest(cls._payload(replace(claim, canonical_digest="0" * 64)))

    @classmethod
    def _assessment_digest(cls, assessment: RecommendationReadinessAssessment) -> str:
        unsigned = replace(
            assessment,
            readiness_receipt_digest="0" * 64,
            canonical_digest="0" * 64,
        )
        return cls._digest(cls._payload(unsigned))


def build_development_recommendation_readiness_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> RecommendationReadinessPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = RecommendationReadinessPolicySnapshot(
        policy_id="recommendation-readiness-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.recommendation-readiness-development-v1",
        required_source_schema="atlas.promoted-recommendation-artifact.v1",
        required_source_state="draft",
        required_evaluator_id="recommendation-readiness-evaluator.synthetic",
        required_evaluator_attestor_id="subject.recommendation-readiness-attestor",
        required_receipt_schema="atlas.recommendation-readiness-receipt.v1",
        assessment_schema=ASSESSMENT_SCHEMA,
        allowed_outcomes=("preferred", "tie", "no_support"),
        required_check_ids=READINESS_CHECKS,
        allowed_reason_codes=READINESS_REASONS,
        maximum_option_count=5,
        maximum_reason_count=len(READINESS_REASONS),
        retention_minutes=10,
        browser_binding_key_digest=digest(["recommendation-readiness-browser-key"]),
        readiness_profile_digest=digest(["recommendation-readiness-profile.v1"]),
        prohibited_content_profile_digest=digest(
            ["prohibited-content.no-protected-identifiers-review-authority-v1"]
        ),
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
