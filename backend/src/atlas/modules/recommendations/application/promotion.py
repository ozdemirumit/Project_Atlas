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
from atlas.modules.ai.application.protected_recommendation_presentation import (
    GovernedProtectedRecommendationPresentationService,
)
from atlas.modules.ai.application.protected_recommendation_presentation_ports import (
    ProtectedRecommendationPresentationError,
)
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    ProtectedRecommendationPresentationResult,
)
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_PROMOTION_CREATE,
    RECOMMENDATION_PROMOTION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.recommendations.application.promotion_ports import (
    RecommendationPromotionError,
    RecommendationPromotionPermissionAuthorizer,
    RecommendationPromotionPolicySource,
    RecommendationPromotionRepository,
    RecommendationPromotionUncertainError,
    TrustedRecommendationPromoter,
)
from atlas.modules.recommendations.domain.promotion import (
    PromotedRecommendationArtifact,
    RecommendationPromotionClaim,
    RecommendationPromotionInstruction,
    RecommendationPromotionManifest,
    RecommendationPromotionPolicySnapshot,
    RecommendationPromotionReceipt,
    RecommendationPromotionResult,
)

POLICY_SCHEMA = "atlas.recommendation-promotion-policy.v1"
CLAIM_SCHEMA = "atlas.recommendation-promotion-claim.v1"
ARTIFACT_SCHEMA = "atlas.promoted-recommendation-artifact.v1"


class GovernedRecommendationPromotionService:
    def __init__(
        self,
        *,
        repository: RecommendationPromotionRepository,
        presentation_source: GovernedProtectedRecommendationPresentationService,
        policy_source: RecommendationPromotionPolicySource,
        permission_authorizer: RecommendationPromotionPermissionAuthorizer,
        promoter: TrustedRecommendationPromoter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._presentation_source = presentation_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._promoter = promoter
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        presentation_id: str,
        presentation_digest: str,
        promotion_policy_id: str,
        promotion_policy_digest: str,
        purpose: str,
        draft_only_acknowledged: bool,
        no_review_or_approval_acknowledged: bool,
        no_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> RecommendationPromotionResult:
        self._require_human(actor)
        if not all(
            (
                draft_only_acknowledged,
                no_review_or_approval_acknowledged,
                no_operational_authority_acknowledged,
            )
        ):
            raise RecommendationPromotionError("recommendation_promotion_acknowledgement_required")
        now = self._clock()
        policy = await self._policy_source.get_by_id(policy_id=promotion_policy_id)
        self._verify_policy(
            policy,
            promotion_policy_digest,
            actor,
            self._environment_id,
            now,
        )
        assert policy is not None
        self._require_policy_assurance(actor, policy)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            correlation_id=correlation_id,
        )
        source = await self._read_source(actor, presentation_id, browser_session_id, correlation_id)
        self._verify_source(source, policy, presentation_digest, purpose, now)
        subject_digest = self._digest([actor.subject_id, actor.organization_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        idempotency_digest = self._digest([subject_digest, idempotency_key])
        request_digest = self._digest(
            [
                presentation_id,
                presentation_digest,
                policy.canonical_digest,
                purpose,
                draft_only_acknowledged,
                no_review_or_approval_acknowledged,
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
        promotion_id = f"recommendation-promotion.{uuid4().hex}"
        recommendation_id = f"recommendation.promoted.{uuid4().hex}"
        claim = RecommendationPromotionClaim(
            claim_id=f"claim.recommendation-promotion.{uuid4().hex}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            promotion_id=promotion_id,
            recommendation_id=recommendation_id,
            presentation_id=presentation_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor, correlation_id, "recommendation_promotion_intent_recorded", presentation_id
        )
        if not await self._repository.claim(claim):
            collision = await self._repository.get_claim_by_idempotency(
                claimed_by_subject_digest=subject_digest,
                idempotency_digest=idempotency_digest,
            )
            if collision is None:
                raise RecommendationPromotionError("recommendation_promotion_already_claimed")
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
        await self._audit(actor, correlation_id, "recommendation_promotion_claimed", promotion_id)
        try:
            source = await self._read_source(
                actor, presentation_id, browser_session_id, correlation_id
            )
            self._verify_source(source, policy, presentation_digest, purpose, now)
            authorization_digest = self._digest(
                [
                    source.record.presentation_authorization_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    source.recommendation.canonical_digest,
                ]
            )
            expires_at = min(
                source.record.expires_at,
                source.recommendation.expires_at,
                policy.expires_at,
                now + timedelta(minutes=policy.retention_minutes),
            )
            instruction = RecommendationPromotionInstruction(
                promotion_id=promotion_id,
                recommendation_id=recommendation_id,
                presentation_id=presentation_id,
                presentation_digest=source.record.canonical_digest,
                recommendation_digest=source.recommendation.canonical_digest,
                organization_id=source.record.organization_id,
                environment_id=source.record.environment_id,
                consumer_subject_digest=source.record.consumer_subject_digest,
                promotion_authorization_digest=authorization_digest,
                policy_id=policy.policy_id,
                policy_digest=policy.canonical_digest,
                artifact_schema=policy.artifact_schema,
                maximum_option_count=policy.maximum_option_count,
                maximum_output_bytes=policy.maximum_output_bytes,
                promotion_profile_digest=policy.promotion_profile_digest,
                prohibited_content_profile_digest=policy.prohibited_content_profile_digest,
                requested_at=now,
                expires_at=expires_at,
            )
            receipt, artifact = await self._promoter.promote(
                instruction,
                source.record,
                source.recommendation,
                claim_id=claim.claim_id,
                policy_version=policy.policy_version,
                purpose=purpose,
                classification=source.record.classification,
                browser_session_binding_digest=browser_digest,
            )
            self._verify_output(receipt, artifact, instruction, policy, source, claim)
            await self._repository.save(artifact)
            await self._audit(
                actor, correlation_id, "recommendation_promotion_completed", recommendation_id
            )
        except RecommendationPromotionError:
            raise
        except ProtectedRecommendationPresentationError as error:
            raise RecommendationPromotionError("recommendation_promotion_source_invalid") from error
        except Exception as error:
            raise RecommendationPromotionUncertainError(
                "recommendation_promotion_persistence_uncertain"
            ) from error
        return RecommendationPromotionResult(artifact=artifact, manifest=self._manifest(artifact))

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationPromotionResult:
        self._require_human(actor)
        artifact = await self._repository.get(recommendation_id=recommendation_id)
        if artifact is None:
            raise RecommendationPromotionError("recommendation_promotion_not_found")
        self._require_scope(actor, artifact.organization_id, artifact.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=artifact.promotion_policy_id)
        now = self._clock()
        if (
            policy is None
            or artifact.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or artifact.canonical_digest != self._artifact_digest(artifact)
            or now >= artifact.expires_at
            or policy.canonical_digest != artifact.promotion_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
        ):
            raise RecommendationPromotionError("recommendation_promotion_not_found")
        self._require_policy_assurance(actor, policy)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=artifact.organization_id,
            environment_id=artifact.environment_id,
            correlation_id=correlation_id,
        )
        source = await self._read_source(
            actor, artifact.presentation_id, browser_session_id, correlation_id
        )
        self._verify_source(source, policy, artifact.presentation_digest, artifact.purpose, now)
        if (
            source.record.outcome != artifact.outcome
            or source.recommendation.options != artifact.options
            or source.recommendation.evidence_needs != artifact.evidence_needs
            or source.recommendation.byte_count != artifact.byte_count
        ):
            raise RecommendationPromotionError("recommendation_promotion_integrity_failed")
        await self._audit(
            actor,
            correlation_id,
            "recommendation_promotion_read",
            recommendation_id,
            permission_id=RECOMMENDATION_PROMOTION_READ,
        )
        reused = replace(artifact, reused=True)
        return RecommendationPromotionResult(artifact=reused, manifest=self._manifest(artifact))

    async def close(self) -> None:
        await self._repository.close()

    async def protected_content_source(
        self, *, recommendation_id: str
    ) -> PromotedRecommendationArtifact:
        artifact = await self._repository.get(recommendation_id=recommendation_id)
        if artifact is None or artifact.canonical_digest != self._artifact_digest(artifact):
            raise RecommendationPromotionError("recommendation_promotion_not_found")
        policy = await self._policy_source.get_by_id(policy_id=artifact.promotion_policy_id)
        if (
            policy is None
            or policy.canonical_digest != artifact.promotion_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
        ):
            raise RecommendationPromotionError("recommendation_promotion_not_found")
        return artifact

    async def _read_source(
        self,
        actor: AuthenticatedSubject,
        presentation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedRecommendationPresentationResult:
        try:
            return await self._presentation_source.get(
                actor=actor,
                presentation_id=presentation_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
        except ProtectedRecommendationPresentationError as error:
            raise RecommendationPromotionError("recommendation_promotion_source_invalid") from error

    @classmethod
    def _verify_policy(
        cls,
        policy: RecommendationPromotionPolicySnapshot | None,
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
            or policy.artifact_schema != ARTIFACT_SCHEMA
            or policy.organization_id != actor.organization_id
            or policy.environment_id != environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise RecommendationPromotionError("recommendation_promotion_policy_invalid")

    @classmethod
    def _verify_source(
        cls,
        source: ProtectedRecommendationPresentationResult,
        policy: RecommendationPromotionPolicySnapshot,
        expected_digest: str,
        purpose: str,
        now: datetime,
    ) -> None:
        record = source.record
        recommendation = source.recommendation
        if (
            record.canonical_digest != expected_digest
            or record.canonical_digest != cls._digest(cls._payload(record))
            or record.schema_version != policy.required_presentation_schema
            or record.instance_state != policy.required_presentation_state
            or record.purpose != purpose
            or now >= record.expires_at
            or record.recommendation_digest != recommendation.canonical_digest
            or len(recommendation.options) > policy.maximum_option_count
            or recommendation.byte_count > policy.maximum_output_bytes
            or not record.recommendation_presented
            or record.recommendation_ready_for_review
            or record.recommendation_approved
            or record.workflow_created
            or record.execution_authorized
            or record.deployment_authorized
            or record.infrastructure_mutated
        ):
            raise RecommendationPromotionError("recommendation_promotion_source_invalid")

    @classmethod
    def _verify_output(
        cls,
        receipt: RecommendationPromotionReceipt,
        artifact: PromotedRecommendationArtifact,
        instruction: RecommendationPromotionInstruction,
        policy: RecommendationPromotionPolicySnapshot,
        source: ProtectedRecommendationPresentationResult,
        claim: RecommendationPromotionClaim,
    ) -> None:
        expected_source_binding_digest = cls._digest(
            [
                source.record.canonical_digest,
                source.recommendation.canonical_digest,
                source.record.adjudication_digest,
                source.record.source_binding_digest,
            ]
        )
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.promoter_id != policy.required_promoter_id
            or receipt.attested_by != policy.required_promoter_attestor_id
            or receipt.promotion_id != instruction.promotion_id
            or receipt.presentation_id != instruction.presentation_id
            or receipt.presentation_digest != instruction.presentation_digest
            or receipt.policy_digest != policy.canonical_digest
            or receipt.promotion_authorization_digest != instruction.promotion_authorization_digest
            or receipt.artifact_digest != artifact.canonical_digest
            or receipt.source_binding_digest != expected_source_binding_digest
            or receipt.outcome != artifact.outcome
            or receipt.option_count != len(artifact.options)
            or receipt.preferred_count
            != sum(option.role == "preferred" for option in artifact.options)
            or receipt.byte_count != artifact.byte_count
            or receipt.promoted_at != instruction.requested_at
            or receipt.expires_at != instruction.expires_at
            or artifact.promotion_id != instruction.promotion_id
            or artifact.recommendation_id != instruction.recommendation_id
            or artifact.claim_id != claim.claim_id
            or artifact.presentation_id != instruction.presentation_id
            or artifact.schema_version != policy.artifact_schema
            or artifact.presentation_digest != source.record.canonical_digest
            or artifact.adjudication_id != source.record.adjudication_id
            or artifact.organization_id != instruction.organization_id
            or artifact.environment_id != instruction.environment_id
            or artifact.classification != source.record.classification
            or artifact.consumer_subject_digest != instruction.consumer_subject_digest
            or artifact.browser_session_binding_digest != claim.browser_session_binding_digest
            or artifact.promotion_policy_id != policy.policy_id
            or artifact.promotion_policy_digest != policy.canonical_digest
            or artifact.promotion_policy_version != policy.policy_version
            or artifact.promoter_id != policy.required_promoter_id
            or artifact.promotion_receipt_digest != receipt.canonical_digest
            or artifact.promotion_authorization_digest != instruction.promotion_authorization_digest
            or artifact.source_binding_digest != expected_source_binding_digest
            or artifact.outcome != source.recommendation.outcome
            or artifact.headline != source.recommendation.headline
            or artifact.options != source.recommendation.options
            or artifact.evidence_needs != source.recommendation.evidence_needs
            or artifact.promoted_at != instruction.requested_at
            or artifact.expires_at != instruction.expires_at
            or artifact.purpose != source.record.purpose
            or artifact.byte_count != source.recommendation.byte_count
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or artifact.canonical_digest != cls._artifact_digest(artifact)
        ):
            raise RecommendationPromotionError("recommendation_promotion_receipt_invalid")

    async def _reuse(
        self,
        claim: RecommendationPromotionClaim,
        subject_digest: str,
        idempotency_digest: str,
        browser_digest: str,
        request_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationPromotionResult:
        if (
            claim.canonical_digest != self._claim_digest(claim)
            or claim.claimed_by_subject_digest != subject_digest
            or claim.idempotency_digest != idempotency_digest
            or claim.organization_id != actor.organization_id
            or claim.environment_id != self._environment_id
        ):
            raise RecommendationPromotionError("recommendation_promotion_integrity_failed")
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise RecommendationPromotionError("recommendation_promotion_idempotency_conflict")
        return await self.get(
            actor=actor,
            recommendation_id=claim.recommendation_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise RecommendationPromotionError("recommendation_promotion_human_required")

    @staticmethod
    def _require_policy_assurance(
        actor: AuthenticatedSubject, policy: RecommendationPromotionPolicySnapshot
    ) -> None:
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise RecommendationPromotionError("recommendation_promotion_policy_assurance_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise RecommendationPromotionError("recommendation_promotion_not_found")

    @staticmethod
    def _manifest(artifact: PromotedRecommendationArtifact) -> RecommendationPromotionManifest:
        return RecommendationPromotionManifest(
            promotion_id=artifact.promotion_id,
            recommendation_id=artifact.recommendation_id,
            presentation_id=artifact.presentation_id,
            adjudication_id=artifact.adjudication_id,
            outcome=artifact.outcome,
            option_count=len(artifact.options),
            preferred_count=sum(option.role == "preferred" for option in artifact.options),
            state=artifact.state,
            source_binding_digest=artifact.source_binding_digest,
            promoted_at=artifact.promoted_at,
            expires_at=artifact.expires_at,
            safety_notice=artifact.safety_notice,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = RECOMMENDATION_PROMOTION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendation.promotion",
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
                resource_type="resource.recommendation.promotion",
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
    def _artifact_digest(cls, artifact: PromotedRecommendationArtifact) -> str:
        unsigned = replace(
            artifact,
            promotion_receipt_digest="0" * 64,
            canonical_digest="0" * 64,
        )
        return cls._digest(cls._payload(unsigned))

    @classmethod
    def _claim_digest(cls, claim: RecommendationPromotionClaim) -> str:
        return cls._digest(cls._payload(replace(claim, canonical_digest="0" * 64)))


def build_development_recommendation_promotion_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> RecommendationPromotionPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = RecommendationPromotionPolicySnapshot(
        policy_id="recommendation-promotion-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.recommendation-promotion-development-v1",
        required_presentation_schema="atlas.protected-recommendation-presentation.v1",
        required_presentation_state="protected_recommendation_presented",
        required_promoter_id="recommendation-promoter.synthetic",
        required_promoter_attestor_id="subject.recommendation-promoter-attestor",
        required_receipt_schema="atlas.recommendation-promotion-receipt.v1",
        artifact_schema=ARTIFACT_SCHEMA,
        maximum_option_count=5,
        maximum_output_bytes=65_536,
        retention_minutes=10,
        browser_binding_key_digest=digest(["recommendation-promotion-browser-key"]),
        promotion_profile_digest=digest(["promotion-profile.safe-draft-v1"]),
        prohibited_content_profile_digest=digest(
            ["prohibited-content.no-identifiers-tools-operations-v1"]
        ),
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
