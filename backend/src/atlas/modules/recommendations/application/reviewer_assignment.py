from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE,
    RECOMMENDATION_REVIEWER_ASSIGNMENT_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.recommendations.application.review_request import (
    GovernedRecommendationReviewRequestService,
)
from atlas.modules.recommendations.application.review_request_ports import (
    RecommendationReviewRequestError,
)
from atlas.modules.recommendations.application.reviewer_assignment_ports import (
    RecommendationReviewerAssignmentError,
    RecommendationReviewerAssignmentPermissionAuthorizer,
    RecommendationReviewerAssignmentPolicySource,
    RecommendationReviewerAssignmentRepository,
    RecommendationReviewerAssignmentUncertainError,
    TrustedRecommendationReviewerAssignmentAdapter,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestRecord,
    RecommendationReviewRequestResult,
)
from atlas.modules.recommendations.domain.reviewer_assignment import (
    SERVICE_IMPACT_TRACK,
    TECHNICAL_TRACK,
    RecommendationReviewerAssignmentClaim,
    RecommendationReviewerAssignmentInstruction,
    RecommendationReviewerAssignmentManifest,
    RecommendationReviewerAssignmentPolicySnapshot,
    RecommendationReviewerAssignmentReceipt,
    RecommendationReviewerAssignmentRecord,
    RecommendationReviewerAssignmentResult,
)

POLICY_SCHEMA = "atlas.recommendation-reviewer-assignment-policy.v1"
CLAIM_SCHEMA = "atlas.recommendation-reviewer-assignment-claim.v1"
ASSIGNMENT_SCHEMA = "atlas.recommendation-reviewer-assignment.v1"
RECEIPT_SCHEMA = "atlas.recommendation-reviewer-assignment-receipt.v1"


class GovernedRecommendationReviewerAssignmentService:
    def __init__(
        self,
        *,
        repository: RecommendationReviewerAssignmentRepository,
        review_request_source: GovernedRecommendationReviewRequestService,
        policy_source: RecommendationReviewerAssignmentPolicySource,
        permission_authorizer: RecommendationReviewerAssignmentPermissionAuthorizer,
        adapter: TrustedRecommendationReviewerAssignmentAdapter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._review_request_source = review_request_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._adapter = adapter
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        review_request_id: str,
        review_request_digest: str,
        assignment_policy_id: str,
        assignment_policy_digest: str,
        purpose: str,
        caller_cannot_select_reviewers_acknowledged: bool,
        distinct_reviewers_required_acknowledged: bool,
        no_inspection_decision_or_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> RecommendationReviewerAssignmentResult:
        self._require_human(actor)
        if not all(
            (
                caller_cannot_select_reviewers_acknowledged,
                distinct_reviewers_required_acknowledged,
                no_inspection_decision_or_authority_acknowledged,
            )
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_acknowledgement_required"
            )
        now = self._clock()
        policy = await self._policy_source.get_by_id(policy_id=assignment_policy_id)
        self._verify_policy(policy, assignment_policy_digest, actor, self._environment_id, now)
        assert policy is not None
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            permission_id=RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE,
            correlation_id=correlation_id,
        )
        source = await self._read_source(
            actor, review_request_id, browser_session_id, correlation_id
        )
        self._verify_source(source, policy, recommendation_id, review_request_digest, purpose, now)
        source_record = self._source_record(source)
        actor_digest = self._subject_digest(actor.subject_id, actor.organization_id)
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        idempotency_digest = self._digest([actor_digest, idempotency_key])
        request_binding_digest = self._digest(
            [
                review_request_id,
                recommendation_id,
                review_request_digest,
                policy.canonical_digest,
                purpose,
                caller_cannot_select_reviewers_acknowledged,
                distinct_reviewers_required_acknowledged,
                no_inspection_decision_or_authority_acknowledged,
            ]
        )
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=actor_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                actor_digest,
                idempotency_digest,
                browser_digest,
                request_binding_digest,
                actor,
                browser_session_id,
                correlation_id,
            )
        assignment_set_id = f"recommendation-reviewer-assignment.{uuid4().hex}"
        claim = RecommendationReviewerAssignmentClaim(
            claim_id=f"claim.recommendation-reviewer-assignment.{uuid4().hex}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            assignment_set_id=assignment_set_id,
            review_request_id=review_request_id,
            review_request_digest=source_record.canonical_digest,
            claimed_by_subject_digest=actor_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
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
            "recommendation_reviewer_assignment_intent_recorded",
            review_request_id,
        )
        if not await self._repository.claim(claim):
            collision = await self._repository.get_claim_by_idempotency(
                claimed_by_subject_digest=actor_digest,
                idempotency_digest=idempotency_digest,
            )
            if collision is None:
                raise RecommendationReviewerAssignmentError(
                    "recommendation_reviewer_assignment_already_claimed"
                )
            return await self._reuse(
                collision,
                actor_digest,
                idempotency_digest,
                browser_digest,
                request_binding_digest,
                actor,
                browser_session_id,
                correlation_id,
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_reviewer_assignment_claimed",
            assignment_set_id,
        )
        try:
            source = await self._read_source(
                actor, review_request_id, browser_session_id, correlation_id
            )
            self._verify_source(
                source, policy, recommendation_id, review_request_digest, purpose, now
            )
            source_record = self._source_record(source)
            exclusions = tuple(
                sorted(
                    {
                        source_record.requester_subject_digest,
                        actor_digest,
                        self._subject_digest(policy.signed_by, actor.organization_id),
                        self._subject_digest(
                            policy.required_adapter_attestor_id, actor.organization_id
                        ),
                    }
                )
            )
            expires_at = min(
                source_record.expires_at,
                policy.expires_at,
                now + timedelta(minutes=policy.retention_minutes),
            )
            instruction = RecommendationReviewerAssignmentInstruction(
                assignment_set_id=assignment_set_id,
                review_request_id=source_record.review_request_id,
                review_request_digest=source_record.canonical_digest,
                recommendation_id=source_record.recommendation_id,
                readiness_assessment_id=source_record.readiness_assessment_id,
                promotion_id=source_record.promotion_id,
                organization_id=source_record.organization_id,
                environment_id=source_record.environment_id,
                policy_id=policy.policy_id,
                policy_digest=policy.canonical_digest,
                assignment_schema=policy.assignment_schema,
                track_codes=policy.track_codes,
                queue_ids=policy.queue_ids,
                manifest_digest=source_record.manifest_digest,
                directory_source_id=policy.directory_source_id,
                directory_source_digest=policy.directory_source_digest,
                eligibility_profile_digests=policy.eligibility_profile_digests,
                subject_digest_salt_digest=policy.subject_digest_salt_digest,
                routing_profile_digest=policy.routing_profile_digest,
                separation_profile_digest=policy.separation_profile_digest,
                exclusion_subject_digests=exclusions,
                assignment_ttl_minutes=policy.assignment_ttl_minutes,
                requested_at=now,
                expires_at=expires_at,
            )
            receipt = await self._adapter.assign(instruction, source_record)
            self._verify_receipt(receipt, instruction, policy, exclusions)
            record = self._record(
                receipt,
                instruction,
                source_record,
                policy,
                claim,
                browser_digest,
                purpose,
            )
            self._verify_record(record, receipt, instruction, source_record, policy, claim)
            await self._audit(
                actor,
                correlation_id,
                "recommendation_reviewers_assigned",
                assignment_set_id,
            )
            await self._repository.save(record)
        except RecommendationReviewerAssignmentError:
            raise
        except Exception as error:
            raise RecommendationReviewerAssignmentUncertainError(
                "recommendation_reviewer_assignment_persistence_uncertain"
            ) from error
        return RecommendationReviewerAssignmentResult(
            record=record, manifest=self._manifest(record)
        )

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        assignment_set_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationReviewerAssignmentResult:
        self._require_human(actor)
        record = await self._repository.get(assignment_set_id=assignment_set_id)
        if record is None:
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.assignment_policy_id)
        now = self._clock()
        if (
            policy is None
            or record.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or record.canonical_digest != self._record_digest(record)
            or now >= record.expires_at
            or policy.canonical_digest != record.assignment_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            permission_id=RECOMMENDATION_REVIEWER_ASSIGNMENT_READ,
            correlation_id=correlation_id,
        )
        source = await self._read_source(
            actor, record.review_request_id, browser_session_id, correlation_id
        )
        self._verify_source(
            source,
            policy,
            record.recommendation_id,
            record.source_review_request_digest,
            record.purpose,
            now,
        )
        source_record = self._source_record(source)
        if (
            source_record.recommendation_id != record.recommendation_id
            or source_record.readiness_assessment_id != record.readiness_assessment_id
            or source_record.promotion_id != record.promotion_id
            or source_record.source_outcome != record.source_outcome
            or source_record.option_count != record.option_count
            or source_record.preferred_count != record.preferred_count
            or self._source_binding_digest(source_record) != record.source_binding_digest
            or policy.track_codes != tuple(item[0] for item in record.track_assignments)
            or policy.queue_ids != tuple(item[1] for item in record.track_assignments)
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_integrity_failed"
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_reviewer_assignment_read",
            assignment_set_id,
            permission_id=RECOMMENDATION_REVIEWER_ASSIGNMENT_READ,
        )
        reused = replace(record, reused=True)
        return RecommendationReviewerAssignmentResult(
            record=reused, manifest=self._manifest(record)
        )

    async def close(self) -> None:
        await self._repository.close()

    async def protected_inspection_source(
        self, *, assignment_set_id: str
    ) -> tuple[
        RecommendationReviewerAssignmentRecord,
        RecommendationReviewerAssignmentPolicySnapshot,
    ]:
        record = await self._repository.get(assignment_set_id=assignment_set_id)
        if record is None:
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_not_found"
            )
        if record.canonical_digest != self._record_digest(record):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_integrity_failed"
            )
        policy = await self._policy_source.get_by_id(policy_id=record.assignment_policy_id)
        if (
            policy is None
            or policy.canonical_digest != record.assignment_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_policy_invalid"
            )
        return record, policy

    async def protected_content_source(
        self, *, assignment_set_id: str
    ) -> tuple[
        RecommendationReviewerAssignmentRecord,
        RecommendationReviewerAssignmentPolicySnapshot,
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
    ]:
        record, policy = await self.protected_inspection_source(assignment_set_id=assignment_set_id)
        (
            review_request,
            assessment,
            artifact,
        ) = await self._review_request_source.protected_content_source(
            review_request_id=record.review_request_id
        )
        if (
            review_request.canonical_digest != record.source_review_request_digest
            or review_request.recommendation_id != record.recommendation_id
            or review_request.readiness_assessment_id != record.readiness_assessment_id
            or review_request.promotion_id != record.promotion_id
            or artifact.canonical_digest != review_request.source_recommendation_digest
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_integrity_failed"
            )
        return record, policy, review_request, assessment, artifact

    async def _read_source(
        self,
        actor: AuthenticatedSubject,
        review_request_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationReviewRequestResult:
        try:
            return await self._review_request_source.get(
                actor=actor,
                review_request_id=review_request_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
        except RecommendationReviewRequestError as error:
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_source_invalid"
            ) from error

    @staticmethod
    def _source_record(
        source: RecommendationReviewRequestResult,
    ) -> RecommendationReviewRequestRecord:
        return replace(source.record, reused=False)

    @classmethod
    def _verify_policy(
        cls,
        policy: RecommendationReviewerAssignmentPolicySnapshot | None,
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
            or policy.assignment_schema != ASSIGNMENT_SCHEMA
            or policy.required_receipt_schema != RECEIPT_SCHEMA
            or policy.organization_id != actor.organization_id
            or policy.environment_id != environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_policy_invalid"
            )

    @classmethod
    def _verify_source(
        cls,
        source: RecommendationReviewRequestResult,
        policy: RecommendationReviewerAssignmentPolicySnapshot,
        expected_recommendation_id: str,
        expected_digest: str,
        purpose: str,
        now: datetime,
    ) -> None:
        record = cls._source_record(source)
        if (
            record.recommendation_id != expected_recommendation_id
            or record.canonical_digest != expected_digest
            or record.canonical_digest
            != GovernedRecommendationReviewRequestService._record_digest(record)
            or record.schema_version != policy.required_source_schema
            or record.state != policy.required_source_state
            or record.track_codes != policy.track_codes
            or record.queue_ids != policy.queue_ids
            or record.track_statuses
            != tuple((track, "awaiting_reviewer") for track in policy.track_codes)
            or record.purpose != purpose
            or now < record.requested_at
            or now - record.requested_at > timedelta(minutes=policy.maximum_source_age_minutes)
            or now >= record.expires_at
            or not record.review_requested
            or any(
                (
                    record.reviewer_assigned,
                    record.content_inspection_opened,
                    record.human_review_completed,
                    record.recommendation_approved,
                    record.workflow_created,
                    record.itsm_record_created,
                    record.execution_authorized,
                    record.deployment_authorized,
                    record.infrastructure_mutated,
                )
            )
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_source_invalid"
            )

    @classmethod
    def _verify_receipt(
        cls,
        receipt: RecommendationReviewerAssignmentReceipt,
        instruction: RecommendationReviewerAssignmentInstruction,
        policy: RecommendationReviewerAssignmentPolicySnapshot,
        exclusions: tuple[str, ...],
    ) -> None:
        tracks = tuple(item[0] for item in receipt.track_assignments)
        queues = tuple(item[1] for item in receipt.track_assignments)
        reviewers = tuple(item[3] for item in receipt.track_assignments)
        expected_routing = cls._digest(
            [policy.track_codes, policy.queue_ids, policy.routing_profile_digest]
        )
        expected_eligibility = cls._digest(
            [policy.directory_source_digest, policy.eligibility_profile_digests]
        )
        expected_separation = cls._digest([policy.separation_profile_digest, exclusions, reviewers])
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.adapter_id != policy.required_adapter_id
            or receipt.attested_by != policy.required_adapter_attestor_id
            or receipt.assignment_set_id != instruction.assignment_set_id
            or receipt.review_request_id != instruction.review_request_id
            or receipt.review_request_digest != instruction.review_request_digest
            or tracks != policy.track_codes
            or queues != policy.queue_ids
            or any(item in exclusions for item in reviewers)
            or len(set(reviewers)) != 2
            or receipt.routing_digest != expected_routing
            or receipt.eligibility_digest != expected_eligibility
            or receipt.separation_digest != expected_separation
            or receipt.created_at != instruction.requested_at
            or receipt.expires_at > instruction.expires_at
            or receipt.canonical_digest != cls._digest(payload)
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        receipt: RecommendationReviewerAssignmentReceipt,
        instruction: RecommendationReviewerAssignmentInstruction,
        source: RecommendationReviewRequestRecord,
        policy: RecommendationReviewerAssignmentPolicySnapshot,
        claim: RecommendationReviewerAssignmentClaim,
        browser_digest: str,
        purpose: str,
    ) -> RecommendationReviewerAssignmentRecord:
        record = RecommendationReviewerAssignmentRecord(
            assignment_set_id=instruction.assignment_set_id,
            schema_version=policy.assignment_schema,
            version=1,
            claim_id=claim.claim_id,
            review_request_id=source.review_request_id,
            recommendation_id=source.recommendation_id,
            readiness_assessment_id=source.readiness_assessment_id,
            promotion_id=source.promotion_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            classification=source.classification,
            assignment_policy_id=policy.policy_id,
            assignment_policy_digest=policy.canonical_digest,
            assignment_policy_version=policy.policy_version,
            assignment_adapter_id=receipt.adapter_id,
            assignment_receipt_digest=receipt.canonical_digest,
            requester_subject_digest=source.requester_subject_digest,
            browser_session_binding_digest=browser_digest,
            source_review_request_digest=source.canonical_digest,
            source_binding_digest=cls._source_binding_digest(source),
            source_outcome=source.source_outcome,
            option_count=source.option_count,
            preferred_count=source.preferred_count,
            track_assignments=receipt.track_assignments,
            assignment_digest=receipt.assignment_digest,
            routing_digest=receipt.routing_digest,
            eligibility_digest=receipt.eligibility_digest,
            separation_digest=receipt.separation_digest,
            artifact_digest=receipt.artifact_digest,
            manifest_digest=source.manifest_digest,
            state="reviewers_assigned",
            assigned_at=receipt.created_at,
            expires_at=receipt.expires_at,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._record_digest(record))

    @classmethod
    def _verify_record(
        cls,
        record: RecommendationReviewerAssignmentRecord,
        receipt: RecommendationReviewerAssignmentReceipt,
        instruction: RecommendationReviewerAssignmentInstruction,
        source: RecommendationReviewRequestRecord,
        policy: RecommendationReviewerAssignmentPolicySnapshot,
        claim: RecommendationReviewerAssignmentClaim,
    ) -> None:
        if (
            record.claim_id != claim.claim_id
            or record.assignment_set_id != instruction.assignment_set_id
            or record.review_request_id != source.review_request_id
            or record.source_review_request_digest != source.canonical_digest
            or record.assignment_policy_digest != policy.canonical_digest
            or record.assignment_receipt_digest != receipt.canonical_digest
            or record.track_assignments != receipt.track_assignments
            or record.canonical_digest != cls._record_digest(record)
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_receipt_invalid"
            )

    async def _reuse(
        self,
        claim: RecommendationReviewerAssignmentClaim,
        actor_digest: str,
        idempotency_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationReviewerAssignmentResult:
        if (
            claim.canonical_digest != self._claim_digest(claim)
            or claim.claimed_by_subject_digest != actor_digest
            or claim.idempotency_digest != idempotency_digest
            or claim.organization_id != actor.organization_id
            or claim.environment_id != self._environment_id
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_integrity_failed"
            )
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
        ):
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_idempotency_conflict"
            )
        return await self.get(
            actor=actor,
            assignment_set_id=claim.assignment_set_id,
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
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise RecommendationReviewerAssignmentError(
                "recommendation_reviewer_assignment_not_found"
            )

    @staticmethod
    def _manifest(
        record: RecommendationReviewerAssignmentRecord,
    ) -> RecommendationReviewerAssignmentManifest:
        return RecommendationReviewerAssignmentManifest(
            assignment_set_id=record.assignment_set_id,
            review_request_id=record.review_request_id,
            recommendation_id=record.recommendation_id,
            track_assignments=record.track_assignments,
            state=record.state,
            assigned_at=record.assigned_at,
            expires_at=record.expires_at,
            reviewer_assigned=record.reviewer_assigned,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = RECOMMENDATION_REVIEWER_ASSIGNMENT_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendation.reviewer-assignment",
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
                resource_type="resource.recommendation.reviewer-assignment",
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
    def _claim_digest(cls, claim: RecommendationReviewerAssignmentClaim) -> str:
        return cls._digest(cls._payload(replace(claim, canonical_digest="0" * 64)))

    @classmethod
    def _record_digest(cls, record: RecommendationReviewerAssignmentRecord) -> str:
        return cls._digest(
            cls._payload(
                replace(
                    record,
                    assignment_receipt_digest="0" * 64,
                    canonical_digest="0" * 64,
                )
            )
        )

    @classmethod
    def _source_binding_digest(cls, source: RecommendationReviewRequestRecord) -> str:
        return cls._digest(
            [
                source.canonical_digest,
                source.review_request_receipt_digest,
                source.source_assessment_digest,
                source.source_recommendation_digest,
                source.source_binding_digest,
                source.review_request_policy_digest,
                source.manifest_digest,
            ]
        )

    @classmethod
    def _subject_digest(cls, subject_id: str, organization_id: str) -> str:
        return cls._digest([subject_id, organization_id])


def build_development_recommendation_reviewer_assignment_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> RecommendationReviewerAssignmentPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = RecommendationReviewerAssignmentPolicySnapshot(
        policy_id="recommendation-reviewer-assignment-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.recommendation-reviewer-assignment-development-v1",
        required_source_schema="atlas.recommendation-review-request.v1",
        required_source_state="review_requested",
        required_adapter_id="recommendation-reviewer-assignment-adapter.synthetic",
        required_adapter_attestor_id="subject.recommendation-reviewer-assignment-attestor",
        required_receipt_schema=RECEIPT_SCHEMA,
        assignment_schema=ASSIGNMENT_SCHEMA,
        track_codes=(TECHNICAL_TRACK, SERVICE_IMPACT_TRACK),
        queue_ids=(
            "review-queue.recommendation-technical",
            "review-queue.recommendation-service-impact",
        ),
        directory_source_id="directory.recommendation-reviewers.synthetic",
        directory_source_digest=digest(["directory.recommendation-reviewers.synthetic.v1"]),
        eligibility_profile_digests=(
            digest(["eligibility.recommendation-technical.v1"]),
            digest(["eligibility.recommendation-service-impact.v1"]),
        ),
        subject_digest_salt_digest=digest(["recommendation-reviewer-subject-salt.v1"]),
        routing_profile_digest=digest(["recommendation-reviewer-routing.v1"]),
        separation_profile_digest=digest(["recommendation-reviewer-separation.v1"]),
        maximum_source_age_minutes=30,
        assignment_ttl_minutes=10,
        retention_minutes=10,
        browser_binding_key_digest=digest(["recommendation-reviewer-assignment-browser-key"]),
        signed_by="subject.recommendation-reviewer-assignment-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
