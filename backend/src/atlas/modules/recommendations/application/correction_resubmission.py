from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_CORRECTION_RESUBMISSION_CREATE,
    RECOMMENDATION_CORRECTION_RESUBMISSION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.recommendations.application.correction_resubmission_ports import (
    RecommendationCorrectionAdapter,
    RecommendationCorrectionError,
    RecommendationCorrectionPermissionAuthorizer,
    RecommendationCorrectionPolicySource,
    RecommendationCorrectionRepository,
    RecommendationCorrectionSource,
    RecommendationCorrectionUncertainError,
)
from atlas.modules.recommendations.application.promotion import (
    GovernedRecommendationPromotionService,
)
from atlas.modules.recommendations.domain.correction_resubmission import (
    CHANGES_REQUIRED,
    RECOMMENDATION_CORRECTION_RESUBMITTED,
    TRACKS,
    RecommendationCorrectionClaim,
    RecommendationCorrectionInstruction,
    RecommendationCorrectionPolicySnapshot,
    RecommendationCorrectionReceipt,
    RecommendationCorrectionRecord,
)
from atlas.modules.recommendations.domain.promotion import (
    PromotedRecommendationArtifact,
    RecommendationPromotionManifest,
    RecommendationPromotionResult,
)
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_decision import (
    RECOMMENDATION_TRACK_REVIEW_DECIDED,
    RecommendationTrackReviewDecisionRecord,
)
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord

CORRECTION_POLICY_SCHEMA = "atlas.recommendation-correction-policy.v1"
CORRECTION_CLAIM_SCHEMA = "atlas.recommendation-correction-claim.v1"
CORRECTION_RECORD_SCHEMA = "atlas.recommendation-correction-resubmission.v1"


class RecommendationCorrectionService:
    def __init__(
        self,
        *,
        repository: RecommendationCorrectionRepository,
        source: RecommendationCorrectionSource,
        policy_source: RecommendationCorrectionPolicySource,
        permission_authorizer: RecommendationCorrectionPermissionAuthorizer,
        adapter: RecommendationCorrectionAdapter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
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
        source_review_request_id: str,
        source_review_request_digest: str,
        source_recommendation_id: str,
        source_recommendation_digest: str,
        source_decision_ids: tuple[str, str],
        source_decision_digests: tuple[str, str],
        correction_submission_id: str,
        correction_submission_digest: str,
        correction_policy_id: str,
        correction_policy_digest: str,
        purpose: str,
        exact_change_requirements_addressed_acknowledged: bool,
        new_immutable_version_acknowledged: bool,
        fresh_readiness_required_acknowledged: bool,
        no_later_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> RecommendationCorrectionRecord:
        self._require_enterprise_human(actor)
        purpose = purpose.strip()
        if (
            not all(
                (
                    exact_change_requirements_addressed_acknowledged,
                    new_immutable_version_acknowledged,
                    fresh_readiness_required_acknowledged,
                    no_later_authority_acknowledged,
                )
            )
            or len(set(source_decision_ids)) != 2
            or len(set(source_decision_digests)) != 2
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise RecommendationCorrectionError("recommendation_correction_request_invalid")
        try:
            (
                decisions,
                request,
                readiness,
                artifact,
            ) = await self._source.correction_resubmission_source(
                review_request_id=source_review_request_id
            )
        except Exception as error:
            raise RecommendationCorrectionError(
                "recommendation_correction_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=correction_policy_id)
        if policy is None:
            raise RecommendationCorrectionError("recommendation_correction_policy_not_found")
        self._verify_policy(policy)
        self._require_assurance(actor, policy)
        now = self._clock()
        ordered = self._verify_source(
            actor=actor,
            decisions=decisions,
            request=request,
            readiness=readiness,
            artifact=artifact,
            policy=policy,
            source_review_request_id=source_review_request_id,
            source_review_request_digest=source_review_request_digest,
            source_recommendation_id=source_recommendation_id,
            source_recommendation_digest=source_recommendation_digest,
            source_decision_ids=source_decision_ids,
            source_decision_digests=source_decision_digests,
            correction_policy_digest=correction_policy_digest,
            now=now,
        )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            correlation_id=correlation_id,
        )
        owner_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        reviewer_digest = self._digest(
            [policy.reviewer_subject_digest_salt_digest, actor.subject_id]
        )
        if reviewer_digest in {decision.decided_by_subject_digest for decision in ordered}:
            raise RecommendationCorrectionError(
                "recommendation_correction_actor_separation_required"
            )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        decision_aggregate_digest = self._decision_aggregate_digest(ordered)
        purpose_digest = self._digest(purpose)
        request_binding_digest = self._digest(
            {
                "source_review_request_id": request.review_request_id,
                "source_review_request_digest": request.canonical_digest,
                "source_recommendation_id": artifact.recommendation_id,
                "source_recommendation_digest": artifact.canonical_digest,
                "source_decision_ids": [item.decision_id for item in ordered],
                "source_decision_digests": [item.canonical_digest for item in ordered],
                "decision_aggregate_digest": decision_aggregate_digest,
                "correction_submission_id": correction_submission_id,
                "correction_submission_digest": correction_submission_digest,
                "correction_policy_id": policy.policy_id,
                "correction_policy_digest": policy.canonical_digest,
                "purpose_digest": purpose_digest,
                "browser_session_binding_digest": browser_digest,
            }
        )
        idempotency_digest = self._digest([owner_digest, browser_digest, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=owner_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                subject_digest=owner_digest,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        seed = self._digest(
            [
                request.review_request_id,
                decision_aggregate_digest,
                correction_submission_digest,
                policy.canonical_digest,
            ]
        )[:24]
        correction_id = f"recommendation-correction.{seed}"
        await self._audit(
            actor,
            correlation_id,
            "recommendation_correction_intent_recorded",
            request.review_request_id,
        )
        claim = RecommendationCorrectionClaim(
            claim_id=f"recommendation-correction-claim.{seed}",
            schema_version=CORRECTION_CLAIM_SCHEMA,
            version=1,
            source_review_request_id=request.review_request_id,
            source_review_request_digest=request.canonical_digest,
            correction_id=correction_id,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            decision_aggregate_digest=decision_aggregate_digest,
            correction_submission_digest=correction_submission_digest,
            claimed_by_subject_digest=owner_digest,
            browser_session_binding_digest=browser_digest,
            purpose_digest=purpose_digest,
            claimed_at=now,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        if not await self._repository.claim(claim):
            prior = await self._repository.get_claim_by_source_request(
                source_review_request_id=request.review_request_id
            )
            if prior is None:
                raise RecommendationCorrectionUncertainError(
                    "recommendation_correction_claim_uncertain"
                )
            return await self._reuse(
                prior,
                subject_digest=owner_digest,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_correction_claimed",
            claim.claim_id,
        )
        instruction = self._instruction(
            claim,
            ordered,
            request,
            readiness,
            artifact,
            policy,
            correction_submission_id,
            correction_submission_digest,
        )
        try:
            receipt, corrected = await self._adapter.correct(instruction, artifact)
            self._verify_output(instruction, receipt, corrected, policy, artifact)
        except RecommendationCorrectionError:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_correction_failed",
                correction_id,
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_correction_uncertain",
                correction_id,
            )
            raise RecommendationCorrectionUncertainError(
                "recommendation_correction_outcome_uncertain"
            ) from error
        record = self._record(
            claim,
            ordered,
            request,
            readiness,
            artifact,
            policy,
            receipt,
            correction_submission_id,
            purpose,
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_request(
                source_review_request_id=request.review_request_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise RecommendationCorrectionUncertainError(
                    "recommendation_correction_persistence_uncertain"
                )
            return replace(raced, reused=True)
        await self._audit(
            actor,
            correlation_id,
            "recommendation_correction_resubmitted",
            record.correction_id,
        )
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        correction_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationCorrectionRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(correction_id=correction_id)
        if record is None:
            raise RecommendationCorrectionError("recommendation_correction_not_found")
        await self._authorize_record(actor, record, browser_session_id, correlation_id)
        await self._audit(
            actor,
            correlation_id,
            "recommendation_correction_read",
            record.correction_id,
            permission_id=RECOMMENDATION_CORRECTION_RESUBMISSION_READ,
        )
        return replace(record, reused=True)

    async def get_corrected_promotion(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> RecommendationPromotionResult:
        self._require_enterprise_human(actor)
        record = await self._repository.get_by_new_recommendation(
            new_recommendation_id=recommendation_id
        )
        if record is None:
            raise RecommendationCorrectionError("recommendation_correction_not_found")
        await self._authorize_record(actor, record, browser_session_id, correlation_id)
        artifact = await self._read_corrected_artifact(record)
        return RecommendationPromotionResult(artifact=artifact, manifest=self._manifest(artifact))

    async def protected_corrected_promotion(
        self, *, recommendation_id: str
    ) -> PromotedRecommendationArtifact:
        record = await self._repository.get_by_new_recommendation(
            new_recommendation_id=recommendation_id
        )
        if record is None:
            raise RecommendationCorrectionError("recommendation_correction_not_found")
        self._verify_record(record)
        return await self._read_corrected_artifact(record)

    async def close(self) -> None:
        await self._repository.close()

    async def _authorize_record(
        self,
        actor: AuthenticatedSubject,
        record: RecommendationCorrectionRecord,
        browser_session_id: str,
        correlation_id: str,
    ) -> None:
        self._verify_record(record)
        policy = await self._policy_source.get_by_id(policy_id=record.correction_policy_id)
        if policy is None or policy.canonical_digest != record.correction_policy_digest:
            raise RecommendationCorrectionError("recommendation_correction_not_found")
        self._verify_policy(policy)
        self._require_scope(actor, record.organization_id, record.environment_id)
        if (
            self._digest([policy.subject_digest_salt_digest, actor.subject_id])
            != record.corrected_by_subject_digest
            or self._digest([policy.browser_binding_key_digest, browser_session_id])
            != record.browser_session_binding_digest
        ):
            raise RecommendationCorrectionError("recommendation_correction_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )

    def _verify_source(
        self,
        *,
        actor: AuthenticatedSubject,
        decisions: tuple[RecommendationTrackReviewDecisionRecord, ...],
        request: RecommendationReviewRequestRecord,
        readiness: RecommendationReadinessAssessment,
        artifact: PromotedRecommendationArtifact,
        policy: RecommendationCorrectionPolicySnapshot,
        source_review_request_id: str,
        source_review_request_digest: str,
        source_recommendation_id: str,
        source_recommendation_digest: str,
        source_decision_ids: tuple[str, str],
        source_decision_digests: tuple[str, str],
        correction_policy_digest: str,
        now: datetime,
    ) -> tuple[RecommendationTrackReviewDecisionRecord, ...]:
        ordered = tuple(sorted(decisions, key=lambda item: item.track_code))
        supplied = set(zip(source_decision_ids, source_decision_digests, strict=True))
        actual = {(item.decision_id, item.canonical_digest) for item in ordered}
        later_authority = any(
            any(
                (
                    item.correction_created,
                    item.recommendation_approved,
                    item.workflow_created,
                    item.itsm_record_created,
                    item.execution_authorized,
                    item.deployment_authorized,
                    item.infrastructure_mutated,
                )
            )
            for item in ordered
        )
        if (
            len(ordered) != 2
            or {item.track_code for item in ordered} != TRACKS
            or supplied != actual
            or not any(item.disposition_code == CHANGES_REQUIRED for item in ordered)
            or any(item.state != RECOMMENDATION_TRACK_REVIEW_DECIDED for item in ordered)
            or later_authority
            or request.review_request_id != source_review_request_id
            or request.canonical_digest != source_review_request_digest
            or request.schema_version != policy.required_request_schema
            or request.state != policy.required_request_state
            or request.recommendation_id != artifact.recommendation_id
            or request.readiness_assessment_id != readiness.assessment_id
            or request.promotion_id != artifact.promotion_id
            or readiness.recommendation_id != artifact.recommendation_id
            or readiness.promotion_id != artifact.promotion_id
            or readiness.source_artifact_digest != artifact.canonical_digest
            or artifact.recommendation_id != source_recommendation_id
            or artifact.canonical_digest != source_recommendation_digest
            or artifact.schema_version != policy.required_promotion_schema
            or artifact.state != policy.required_promotion_state
            or artifact.consumer_subject_digest
            != self._digest([policy.source_consumer_subject_digest_salt_digest, actor.subject_id])
            or any(item.review_request_id != request.review_request_id for item in ordered)
            or any(item.recommendation_id != artifact.recommendation_id for item in ordered)
            or any(item.readiness_assessment_id != readiness.assessment_id for item in ordered)
            or any(item.promotion_id != artifact.promotion_id for item in ordered)
            or any(
                item.recommendation_artifact_digest != artifact.canonical_digest for item in ordered
            )
            or any(item.schema_version != policy.required_decision_schema for item in ordered)
            or any(item.state != policy.required_decision_state for item in ordered)
            or policy.canonical_digest != correction_policy_digest
            or policy.organization_id != request.organization_id
            or policy.environment_id != request.environment_id
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise RecommendationCorrectionError("recommendation_correction_source_invalid")
        self._require_scope(actor, request.organization_id, request.environment_id)
        if actor.subject_id in {policy.signed_by, policy.required_adapter_attestor_id}:
            raise RecommendationCorrectionError(
                "recommendation_correction_actor_separation_required"
            )
        return ordered

    async def _reuse(
        self,
        claim: RecommendationCorrectionClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> RecommendationCorrectionRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise RecommendationCorrectionError("recommendation_correction_idempotency_conflict")
        record = await self._repository.get(correction_id=claim.correction_id)
        if record is None:
            raise RecommendationCorrectionUncertainError(
                "recommendation_correction_claimed_outcome_uncertain"
            )
        self._verify_record(record)
        await self._audit(
            actor,
            correlation_id,
            "recommendation_correction_read",
            record.correction_id,
            permission_id=RECOMMENDATION_CORRECTION_RESUBMISSION_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _instruction(
        cls,
        claim: RecommendationCorrectionClaim,
        decisions: tuple[RecommendationTrackReviewDecisionRecord, ...],
        request: RecommendationReviewRequestRecord,
        readiness: RecommendationReadinessAssessment,
        artifact: PromotedRecommendationArtifact,
        policy: RecommendationCorrectionPolicySnapshot,
        correction_submission_id: str,
        correction_submission_digest: str,
    ) -> RecommendationCorrectionInstruction:
        seed = claim.correction_id.rsplit(".", 1)[-1]
        return RecommendationCorrectionInstruction(
            correction_id=claim.correction_id,
            source_review_request_id=request.review_request_id,
            source_review_request_digest=request.canonical_digest,
            source_recommendation_id=artifact.recommendation_id,
            source_recommendation_digest=artifact.canonical_digest,
            source_promotion_id=artifact.promotion_id,
            source_readiness_assessment_id=readiness.assessment_id,
            source_assignment_set_id=decisions[0].source_assignment_set_id,
            source_decision_ids=cast(
                tuple[str, str], tuple(item.decision_id for item in decisions)
            ),
            source_decision_digests=cast(
                tuple[str, str], tuple(item.canonical_digest for item in decisions)
            ),
            decision_aggregate_digest=claim.decision_aggregate_digest,
            correction_submission_id=correction_submission_id,
            correction_submission_digest=correction_submission_digest,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            new_recommendation_id=f"recommendation.corrected-{seed}",
            new_promotion_id=f"recommendation-promotion.correction-{seed}",
            corrected_by_subject_digest=claim.claimed_by_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            correction_policy_digest=policy.canonical_digest,
            requested_at=claim.claimed_at,
            expires_at=min(
                policy.expires_at, claim.claimed_at + timedelta(minutes=policy.retention_minutes)
            ),
        )

    @classmethod
    def _verify_output(
        cls,
        instruction: RecommendationCorrectionInstruction,
        receipt: RecommendationCorrectionReceipt,
        artifact: PromotedRecommendationArtifact,
        policy: RecommendationCorrectionPolicySnapshot,
        source: PromotedRecommendationArtifact,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.adapter_id != policy.required_adapter_id
            or receipt.attested_by != policy.required_adapter_attestor_id
            or receipt.correction_id != instruction.correction_id
            or receipt.source_review_request_id != instruction.source_review_request_id
            or receipt.source_review_request_digest != instruction.source_review_request_digest
            or receipt.decision_aggregate_digest != instruction.decision_aggregate_digest
            or receipt.correction_submission_id != instruction.correction_submission_id
            or receipt.correction_submission_digest != instruction.correction_submission_digest
            or receipt.new_recommendation_id != instruction.new_recommendation_id
            or receipt.new_promotion_id != instruction.new_promotion_id
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or receipt.canonical_digest != cls._receipt_digest(receipt)
            or artifact.recommendation_id != instruction.new_recommendation_id
            or artifact.promotion_id != instruction.new_promotion_id
            or artifact.canonical_digest != receipt.new_artifact_digest
            or artifact.canonical_digest
            != GovernedRecommendationPromotionService._artifact_digest(artifact)
            or artifact.source_binding_digest != receipt.source_binding_digest
            or artifact.organization_id != source.organization_id
            or artifact.environment_id != source.environment_id
            or artifact.classification != source.classification
            or artifact.consumer_subject_digest != instruction.corrected_by_subject_digest
            or artifact.browser_session_binding_digest != instruction.browser_session_binding_digest
            or artifact.state != policy.required_promotion_state
            or artifact.recommendation_ready_for_review
            or artifact.human_review_completed
            or artifact.recommendation_approved
            or artifact.workflow_created
            or artifact.itsm_record_created
            or artifact.execution_authorized
            or artifact.deployment_authorized
            or artifact.infrastructure_mutated
        ):
            raise RecommendationCorrectionUncertainError(
                "recommendation_correction_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: RecommendationCorrectionClaim,
        decisions: tuple[RecommendationTrackReviewDecisionRecord, ...],
        request: RecommendationReviewRequestRecord,
        readiness: RecommendationReadinessAssessment,
        source: PromotedRecommendationArtifact,
        policy: RecommendationCorrectionPolicySnapshot,
        receipt: RecommendationCorrectionReceipt,
        correction_submission_id: str,
        purpose: str,
    ) -> RecommendationCorrectionRecord:
        record = RecommendationCorrectionRecord(
            correction_id=claim.correction_id,
            schema_version=CORRECTION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_review_request_id=request.review_request_id,
            source_review_request_digest=request.canonical_digest,
            source_recommendation_id=source.recommendation_id,
            source_recommendation_digest=source.canonical_digest,
            source_promotion_id=source.promotion_id,
            source_readiness_assessment_id=readiness.assessment_id,
            source_assignment_set_id=decisions[0].source_assignment_set_id,
            source_decision_ids=cast(
                tuple[str, str], tuple(item.decision_id for item in decisions)
            ),
            source_decision_digests=cast(
                tuple[str, str], tuple(item.canonical_digest for item in decisions)
            ),
            decision_aggregate_digest=claim.decision_aggregate_digest,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            classification=request.classification,
            corrected_by_subject_digest=claim.claimed_by_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            correction_submission_id=correction_submission_id,
            correction_submission_digest=claim.correction_submission_digest,
            correction_policy_id=policy.policy_id,
            correction_policy_digest=policy.canonical_digest,
            correction_policy_version=policy.policy_version,
            adapter_id=receipt.adapter_id,
            attestation_digest=receipt.canonical_digest,
            new_recommendation_id=receipt.new_recommendation_id,
            new_promotion_id=receipt.new_promotion_id,
            new_artifact_digest=receipt.new_artifact_digest,
            source_binding_digest=receipt.source_binding_digest,
            created_at=receipt.corrected_at,
            expires_at=receipt.expires_at,
            state=RECOMMENDATION_CORRECTION_RESUBMITTED,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._record_payload(record)))

    async def _read_corrected_artifact(
        self, record: RecommendationCorrectionRecord
    ) -> PromotedRecommendationArtifact:
        try:
            artifact = await self._adapter.get_artifact(
                recommendation_id=record.new_recommendation_id
            )
        except RecommendationCorrectionError:
            raise
        except Exception as error:
            raise RecommendationCorrectionUncertainError(
                "recommendation_correction_artifact_uncertain"
            ) from error
        if (
            artifact is None
            or artifact.recommendation_id != record.new_recommendation_id
            or artifact.promotion_id != record.new_promotion_id
            or artifact.canonical_digest != record.new_artifact_digest
            or artifact.canonical_digest
            != GovernedRecommendationPromotionService._artifact_digest(artifact)
            or artifact.source_binding_digest != record.source_binding_digest
        ):
            raise RecommendationCorrectionError(
                "recommendation_correction_artifact_integrity_failed"
            )
        return artifact

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

    @classmethod
    def _decision_aggregate_digest(
        cls, decisions: tuple[RecommendationTrackReviewDecisionRecord, ...]
    ) -> str:
        return cls._digest(
            [
                {
                    "track_code": item.track_code,
                    "decision_id": item.decision_id,
                    "canonical_digest": item.canonical_digest,
                    "disposition_code": item.disposition_code,
                }
                for item in decisions
            ]
        )

    @classmethod
    def _verify_policy(cls, policy: RecommendationCorrectionPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise RecommendationCorrectionError("recommendation_correction_policy_integrity_failed")

    @classmethod
    def _verify_claim(cls, claim: RecommendationCorrectionClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise RecommendationCorrectionError("recommendation_correction_claim_integrity_failed")

    @classmethod
    def _verify_record(cls, record: RecommendationCorrectionRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise RecommendationCorrectionError("recommendation_correction_record_integrity_failed")

    @classmethod
    def _claim_payload(cls, claim: RecommendationCorrectionClaim) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: RecommendationCorrectionRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        payload.pop("canonical_digest")
        payload.pop("reused")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: RecommendationCorrectionReceipt) -> str:
        payload = cast(dict[str, object], asdict(receipt))
        payload.pop("canonical_digest")
        return cls._digest(cls._normalize(payload))

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @classmethod
    def _digest(cls, payload: object) -> str:
        return sha256(
            json.dumps(
                cls._normalize(payload),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise RecommendationCorrectionError("recommendation_correction_human_required")

    @staticmethod
    def _require_assurance(
        actor: AuthenticatedSubject,
        policy: RecommendationCorrectionPolicySnapshot,
    ) -> None:
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise RecommendationCorrectionError("recommendation_correction_assurance_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise RecommendationCorrectionError("recommendation_correction_source_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = RECOMMENDATION_CORRECTION_RESUBMISSION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendation.correction-resubmission",
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
                resource_type="resource.recommendation.corrections",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )


def build_development_recommendation_correction_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> RecommendationCorrectionPolicySnapshot:
    digest = RecommendationCorrectionService._digest
    policy = RecommendationCorrectionPolicySnapshot(
        policy_id="recommendation-correction-policy.development",
        schema_version=CORRECTION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.recommendation-correction-development-v1",
        required_decision_schema="atlas.recommendation-track-review-decision.v1",
        required_decision_state=RECOMMENDATION_TRACK_REVIEW_DECIDED,
        required_request_schema="atlas.recommendation-review-request.v1",
        required_request_state="review_requested",
        required_promotion_schema="atlas.promoted-recommendation-artifact.v1",
        required_promotion_state="draft",
        required_adapter_id="recommendation-correction-adapter.synthetic",
        required_adapter_attestor_id="subject.recommendation-correction-attestor",
        required_receipt_schema="atlas.recommendation-correction-receipt.v1",
        technical_track_code="review-track.technical",
        service_impact_track_code="review-track.service-impact",
        source_consumer_subject_digest_salt_digest=digest(
            [organization_id, environment_id, "review-salt-v1"]
        ),
        subject_digest_salt_digest=digest(["recommendation-correction-owner-salt.v1"]),
        reviewer_subject_digest_salt_digest=digest(["recommendation-reviewer-subject-salt.v1"]),
        browser_binding_key_digest=digest(["recommendation-correction-browser-key.v1"]),
        maximum_authentication_age_minutes=15,
        retention_minutes=10,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        signed_by="subject.recommendation-correction-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy, canonical_digest=digest(RecommendationCorrectionService._normalize(payload))
    )
