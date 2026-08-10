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
    RECOMMENDATION_REVIEW_REQUEST_CREATE,
    RECOMMENDATION_REVIEW_REQUEST_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.recommendations.application.readiness import (
    GovernedRecommendationReadinessService,
)
from atlas.modules.recommendations.application.readiness_ports import (
    RecommendationReadinessError,
)
from atlas.modules.recommendations.application.review_request_ports import (
    RecommendationReviewRequestError,
    RecommendationReviewRequestPermissionAuthorizer,
    RecommendationReviewRequestPolicySource,
    RecommendationReviewRequestRepository,
    RecommendationReviewRequestUncertainError,
    TrustedRecommendationReviewRequestOrchestrator,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.readiness import (
    RecommendationReadinessAssessment,
    RecommendationReadinessResult,
)
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestClaim,
    RecommendationReviewRequestInstruction,
    RecommendationReviewRequestManifest,
    RecommendationReviewRequestPolicySnapshot,
    RecommendationReviewRequestReceipt,
    RecommendationReviewRequestRecord,
    RecommendationReviewRequestResult,
)

POLICY_SCHEMA = "atlas.recommendation-review-request-policy.v1"
CLAIM_SCHEMA = "atlas.recommendation-review-request-claim.v1"
REQUEST_SCHEMA = "atlas.recommendation-review-request.v1"
RECEIPT_SCHEMA = "atlas.recommendation-review-request-receipt.v1"


class GovernedRecommendationReviewRequestService:
    def __init__(
        self,
        *,
        repository: RecommendationReviewRequestRepository,
        readiness_source: GovernedRecommendationReadinessService,
        policy_source: RecommendationReviewRequestPolicySource,
        permission_authorizer: RecommendationReviewRequestPermissionAuthorizer,
        orchestrator: TrustedRecommendationReviewRequestOrchestrator,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._readiness_source = readiness_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._orchestrator = orchestrator
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        recommendation_digest: str,
        readiness_assessment_id: str,
        readiness_assessment_digest: str,
        review_request_policy_id: str,
        review_request_policy_digest: str,
        purpose: str,
        request_is_not_assignment_or_review_acknowledged: bool,
        routing_is_policy_owned_acknowledged: bool,
        no_approval_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> RecommendationReviewRequestResult:
        self._require_human(actor)
        if not all(
            (
                request_is_not_assignment_or_review_acknowledged,
                routing_is_policy_owned_acknowledged,
                no_approval_or_operational_authority_acknowledged,
            )
        ):
            raise RecommendationReviewRequestError(
                "recommendation_review_request_acknowledgement_required"
            )
        now = self._clock()
        policy = await self._policy_source.get_by_id(policy_id=review_request_policy_id)
        self._verify_policy(policy, review_request_policy_digest, actor, self._environment_id, now)
        assert policy is not None
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            correlation_id=correlation_id,
        )
        source = await self._read_source(
            actor, readiness_assessment_id, browser_session_id, correlation_id
        )
        self._verify_source(
            source,
            policy,
            recommendation_id,
            recommendation_digest,
            readiness_assessment_digest,
            purpose,
            now,
        )
        assessment = source.assessment
        subject_digest = self._digest([actor.subject_id, actor.organization_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        idempotency_digest = self._digest([subject_digest, idempotency_key])
        request_digest = self._digest(
            [
                recommendation_id,
                recommendation_digest,
                readiness_assessment_id,
                readiness_assessment_digest,
                policy.canonical_digest,
                purpose,
                request_is_not_assignment_or_review_acknowledged,
                routing_is_policy_owned_acknowledged,
                no_approval_or_operational_authority_acknowledged,
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
        review_request_id = f"recommendation-review-request.{uuid4().hex}"
        claim = RecommendationReviewRequestClaim(
            claim_id=f"claim.recommendation-review-request.{uuid4().hex}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            review_request_id=review_request_id,
            recommendation_id=recommendation_id,
            readiness_assessment_id=readiness_assessment_id,
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
            "recommendation_review_request_intent_recorded",
            readiness_assessment_id,
        )
        if not await self._repository.claim(claim):
            collision = await self._repository.get_claim_by_idempotency(
                claimed_by_subject_digest=subject_digest,
                idempotency_digest=idempotency_digest,
            )
            if collision is None:
                raise RecommendationReviewRequestError(
                    "recommendation_review_request_already_claimed"
                )
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
        await self._audit(
            actor,
            correlation_id,
            "recommendation_review_request_claimed",
            review_request_id,
        )
        try:
            source = await self._read_source(
                actor, readiness_assessment_id, browser_session_id, correlation_id
            )
            self._verify_source(
                source,
                policy,
                recommendation_id,
                recommendation_digest,
                readiness_assessment_digest,
                purpose,
                now,
            )
            assessment = source.assessment
            authorization_digest = self._digest(
                [
                    assessment.readiness_authorization_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    assessment.canonical_digest,
                ]
            )
            expires_at = min(
                assessment.expires_at,
                policy.expires_at,
                now + timedelta(minutes=policy.retention_minutes),
            )
            instruction = RecommendationReviewRequestInstruction(
                review_request_id=review_request_id,
                recommendation_id=recommendation_id,
                recommendation_digest=recommendation_digest,
                readiness_assessment_id=readiness_assessment_id,
                readiness_assessment_digest=assessment.canonical_digest,
                promotion_id=assessment.promotion_id,
                organization_id=assessment.organization_id,
                environment_id=assessment.environment_id,
                requester_subject_digest=subject_digest,
                review_request_authorization_digest=authorization_digest,
                policy_id=policy.policy_id,
                policy_digest=policy.canonical_digest,
                request_schema=policy.request_schema,
                track_codes=policy.track_codes,
                queue_ids=policy.queue_ids,
                routing_profile=policy.routing_profile,
                sla_class=policy.sla_class,
                routing_profile_digest=policy.routing_profile_digest,
                no_authority_profile_digest=policy.no_authority_profile_digest,
                requested_at=now,
                expires_at=expires_at,
            )
            receipt, record = await self._orchestrator.orchestrate(
                instruction,
                assessment,
                claim_id=claim.claim_id,
                policy_version=policy.policy_version,
                purpose=purpose,
                classification=assessment.classification,
                browser_session_binding_digest=browser_digest,
            )
            self._verify_output(receipt, record, instruction, policy, assessment, claim)
            await self._audit(
                actor,
                correlation_id,
                "recommendation_review_request_completed",
                review_request_id,
            )
            await self._repository.save(record)
        except RecommendationReviewRequestError:
            raise
        except Exception as error:
            raise RecommendationReviewRequestUncertainError(
                "recommendation_review_request_persistence_uncertain"
            ) from error
        return RecommendationReviewRequestResult(record=record, manifest=self._manifest(record))

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        review_request_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationReviewRequestResult:
        self._require_human(actor)
        record = await self._repository.get(review_request_id=review_request_id)
        if record is None:
            raise RecommendationReviewRequestError("recommendation_review_request_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.review_request_policy_id)
        now = self._clock()
        if (
            policy is None
            or record.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or record.canonical_digest != self._record_digest(record)
            or now >= record.expires_at
            or policy.canonical_digest != record.review_request_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
        ):
            raise RecommendationReviewRequestError("recommendation_review_request_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        source = await self._read_source(
            actor,
            record.readiness_assessment_id,
            browser_session_id,
            correlation_id,
        )
        self._verify_source(
            source,
            policy,
            record.recommendation_id,
            record.source_recommendation_digest,
            record.source_assessment_digest,
            record.purpose,
            now,
        )
        assessment = source.assessment
        expected_binding = self._source_binding_digest(assessment)
        if (
            assessment.promotion_id != record.promotion_id
            or assessment.presentation_id != record.presentation_id
            or assessment.source_outcome != record.source_outcome
            or assessment.option_count != record.option_count
            or assessment.preferred_count != record.preferred_count
            or expected_binding != record.source_binding_digest
            or policy.track_codes != record.track_codes
            or policy.queue_ids != record.queue_ids
            or policy.routing_profile != record.routing_profile
            or policy.sla_class != record.sla_class
        ):
            raise RecommendationReviewRequestError("recommendation_review_request_integrity_failed")
        await self._audit(
            actor,
            correlation_id,
            "recommendation_review_request_read",
            review_request_id,
            permission_id=RECOMMENDATION_REVIEW_REQUEST_READ,
        )
        reused = replace(record, reused=True)
        return RecommendationReviewRequestResult(record=reused, manifest=self._manifest(record))

    async def close(self) -> None:
        await self._repository.close()

    async def protected_content_source(
        self, *, review_request_id: str
    ) -> tuple[
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
    ]:
        record = await self._repository.get(review_request_id=review_request_id)
        if record is None or record.canonical_digest != self._record_digest(record):
            raise RecommendationReviewRequestError("recommendation_review_request_not_found")
        policy = await self._policy_source.get_by_id(policy_id=record.review_request_policy_id)
        if (
            policy is None
            or policy.canonical_digest != record.review_request_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
        ):
            raise RecommendationReviewRequestError("recommendation_review_request_not_found")
        assessment, artifact = await self._readiness_source.protected_content_source(
            assessment_id=record.readiness_assessment_id
        )
        if (
            assessment.canonical_digest != record.source_assessment_digest
            or assessment.recommendation_id != record.recommendation_id
            or artifact.canonical_digest != record.source_recommendation_digest
            or artifact.promotion_id != record.promotion_id
            or artifact.outcome != record.source_outcome
            or len(artifact.options) != record.option_count
        ):
            raise RecommendationReviewRequestError("recommendation_review_request_integrity_failed")
        return record, assessment, artifact

    async def _read_source(
        self,
        actor: AuthenticatedSubject,
        assessment_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationReadinessResult:
        try:
            return await self._readiness_source.get(
                actor=actor,
                assessment_id=assessment_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
        except RecommendationReadinessError as error:
            raise RecommendationReviewRequestError(
                "recommendation_review_request_source_invalid"
            ) from error

    @classmethod
    def _verify_policy(
        cls,
        policy: RecommendationReviewRequestPolicySnapshot | None,
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
            or policy.request_schema != REQUEST_SCHEMA
            or policy.required_receipt_schema != RECEIPT_SCHEMA
            or policy.organization_id != actor.organization_id
            or policy.environment_id != environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise RecommendationReviewRequestError("recommendation_review_request_policy_invalid")

    @classmethod
    def _verify_source(
        cls,
        source: RecommendationReadinessResult,
        policy: RecommendationReviewRequestPolicySnapshot,
        recommendation_id: str,
        recommendation_digest: str,
        assessment_digest: str,
        purpose: str,
        now: datetime,
    ) -> None:
        assessment = source.assessment
        if (
            assessment.recommendation_id != recommendation_id
            or assessment.source_artifact_digest != recommendation_digest
            or assessment.canonical_digest != assessment_digest
            or assessment.canonical_digest
            != GovernedRecommendationReadinessService._assessment_digest(assessment)
            or assessment.schema_version != policy.required_source_schema
            or assessment.state != policy.required_source_state
            or assessment.evaluation_outcome != policy.required_source_outcome
            or assessment.source_outcome not in policy.allowed_source_outcomes
            or assessment.purpose != purpose
            or now >= assessment.expires_at
            or not assessment.recommendation_ready_for_review
            or assessment.human_review_completed
            or assessment.recommendation_approved
            or assessment.workflow_created
            or assessment.itsm_record_created
            or assessment.execution_authorized
            or assessment.deployment_authorized
            or assessment.infrastructure_mutated
        ):
            raise RecommendationReviewRequestError("recommendation_review_request_source_invalid")

    @classmethod
    def _verify_output(
        cls,
        receipt: RecommendationReviewRequestReceipt,
        record: RecommendationReviewRequestRecord,
        instruction: RecommendationReviewRequestInstruction,
        policy: RecommendationReviewRequestPolicySnapshot,
        source: RecommendationReadinessAssessment,
        claim: RecommendationReviewRequestClaim,
    ) -> None:
        expected_binding = cls._source_binding_digest(source)
        expected_routing = cls._digest(
            [
                policy.track_codes,
                policy.queue_ids,
                policy.routing_profile,
                policy.sla_class,
                policy.routing_profile_digest,
            ]
        )
        expected_manifest = cls._digest(
            [
                instruction.review_request_id,
                instruction.recommendation_id,
                instruction.readiness_assessment_id,
                tuple((track, "awaiting_reviewer") for track in policy.track_codes),
                expected_routing,
                policy.canonical_digest,
            ]
        )
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.adapter_id != policy.required_adapter_id
            or receipt.attested_by != policy.required_adapter_attestor_id
            or receipt.review_request_id != instruction.review_request_id
            or receipt.recommendation_id != instruction.recommendation_id
            or receipt.recommendation_digest != instruction.recommendation_digest
            or receipt.readiness_assessment_id != instruction.readiness_assessment_id
            or receipt.readiness_assessment_digest != instruction.readiness_assessment_digest
            or receipt.policy_digest != policy.canonical_digest
            or receipt.review_request_authorization_digest
            != instruction.review_request_authorization_digest
            or receipt.request_digest != record.canonical_digest
            or receipt.manifest_digest != expected_manifest
            or receipt.routing_digest != expected_routing
            or receipt.track_count != len(policy.track_codes)
            or receipt.requested_at != instruction.requested_at
            or receipt.expires_at != instruction.expires_at
            or record.review_request_id != instruction.review_request_id
            or record.recommendation_id != instruction.recommendation_id
            or record.claim_id != claim.claim_id
            or record.readiness_assessment_id != source.assessment_id
            or record.promotion_id != source.promotion_id
            or record.presentation_id != source.presentation_id
            or record.schema_version != policy.request_schema
            or record.organization_id != instruction.organization_id
            or record.environment_id != instruction.environment_id
            or record.classification != source.classification
            or record.requester_subject_digest != instruction.requester_subject_digest
            or record.browser_session_binding_digest != claim.browser_session_binding_digest
            or record.review_request_policy_id != policy.policy_id
            or record.review_request_policy_digest != policy.canonical_digest
            or record.review_request_policy_version != policy.policy_version
            or record.orchestrator_id != policy.required_adapter_id
            or record.review_request_receipt_digest != receipt.canonical_digest
            or record.review_request_authorization_digest
            != instruction.review_request_authorization_digest
            or record.source_assessment_digest != source.canonical_digest
            or record.source_recommendation_digest != source.source_artifact_digest
            or record.source_binding_digest != expected_binding
            or record.source_outcome != source.source_outcome
            or record.option_count != source.option_count
            or record.preferred_count != source.preferred_count
            or record.track_codes != policy.track_codes
            or record.queue_ids != policy.queue_ids
            or record.track_statuses
            != tuple((track, "awaiting_reviewer") for track in policy.track_codes)
            or record.routing_profile != policy.routing_profile
            or record.sla_class != policy.sla_class
            or record.manifest_digest != expected_manifest
            or record.requested_at != instruction.requested_at
            or record.expires_at != instruction.expires_at
            or record.purpose != source.purpose
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or record.canonical_digest != cls._record_digest(record)
        ):
            raise RecommendationReviewRequestError("recommendation_review_request_receipt_invalid")

    async def _reuse(
        self,
        claim: RecommendationReviewRequestClaim,
        subject_digest: str,
        idempotency_digest: str,
        browser_digest: str,
        request_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationReviewRequestResult:
        if (
            claim.canonical_digest != self._claim_digest(claim)
            or claim.claimed_by_subject_digest != subject_digest
            or claim.idempotency_digest != idempotency_digest
            or claim.organization_id != actor.organization_id
            or claim.environment_id != self._environment_id
        ):
            raise RecommendationReviewRequestError("recommendation_review_request_integrity_failed")
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise RecommendationReviewRequestError(
                "recommendation_review_request_idempotency_conflict"
            )
        return await self.get(
            actor=actor,
            review_request_id=claim.review_request_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise RecommendationReviewRequestError(
                "recommendation_review_request_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise RecommendationReviewRequestError("recommendation_review_request_not_found")

    @staticmethod
    def _manifest(
        record: RecommendationReviewRequestRecord,
    ) -> RecommendationReviewRequestManifest:
        return RecommendationReviewRequestManifest(
            review_request_id=record.review_request_id,
            recommendation_id=record.recommendation_id,
            readiness_assessment_id=record.readiness_assessment_id,
            promotion_id=record.promotion_id,
            source_outcome=record.source_outcome,
            option_count=record.option_count,
            preferred_count=record.preferred_count,
            track_codes=record.track_codes,
            queue_ids=record.queue_ids,
            track_statuses=record.track_statuses,
            routing_profile=record.routing_profile,
            sla_class=record.sla_class,
            state=record.state,
            requested_at=record.requested_at,
            expires_at=record.expires_at,
            review_requested=record.review_requested,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = RECOMMENDATION_REVIEW_REQUEST_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendation.human-review-request",
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
                resource_type="resource.recommendation.human-review-request",
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
    def _claim_digest(cls, claim: RecommendationReviewRequestClaim) -> str:
        return cls._digest(cls._payload(replace(claim, canonical_digest="0" * 64)))

    @classmethod
    def _record_digest(cls, record: RecommendationReviewRequestRecord) -> str:
        unsigned = replace(
            record,
            review_request_receipt_digest="0" * 64,
            canonical_digest="0" * 64,
        )
        return cls._digest(cls._payload(unsigned))

    @classmethod
    def _source_binding_digest(cls, assessment: RecommendationReadinessAssessment) -> str:
        return cls._digest(
            [
                assessment.canonical_digest,
                assessment.readiness_receipt_digest,
                assessment.source_artifact_digest,
                assessment.source_binding_digest,
                assessment.readiness_policy_digest,
            ]
        )


def build_development_recommendation_review_request_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> RecommendationReviewRequestPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = RecommendationReviewRequestPolicySnapshot(
        policy_id="recommendation-review-request-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.recommendation-review-request-development-v1",
        required_source_schema="atlas.recommendation-readiness-assessment.v1",
        required_source_state="ready_for_review",
        required_source_outcome="ready",
        required_adapter_id="recommendation-review-request-orchestrator.synthetic",
        required_adapter_attestor_id=("subject.recommendation-review-request-attestor"),
        required_receipt_schema=RECEIPT_SCHEMA,
        request_schema=REQUEST_SCHEMA,
        allowed_source_outcomes=("preferred", "tie", "no_support"),
        track_codes=("review-track.technical", "review-track.service-impact"),
        queue_ids=(
            "review-queue.recommendation-technical",
            "review-queue.recommendation-service-impact",
        ),
        routing_profile="routing-profile.recommendation-human-review-v1",
        sla_class="sla.recommendation-review.standard",
        maximum_track_count=4,
        retention_minutes=10,
        browser_binding_key_digest=digest(["recommendation-review-request-browser-key"]),
        routing_profile_digest=digest(["recommendation-review-request-routing-profile.v1"]),
        no_authority_profile_digest=digest(
            ["no-assignment-review-approval-workflow-execution-authority-v1"]
        ),
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
