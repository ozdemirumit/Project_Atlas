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
    RECOMMENDATION_FINAL_DISPOSITION_CREATE,
    RECOMMENDATION_FINAL_DISPOSITION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.recommendations.application.final_disposition_ports import (
    FinalRecommendationDispositionAttestor,
    FinalRecommendationDispositionError,
    FinalRecommendationDispositionPermissionAuthorizer,
    FinalRecommendationDispositionPolicySource,
    FinalRecommendationDispositionRepository,
    FinalRecommendationDispositionSource,
    FinalRecommendationDispositionUncertainError,
)
from atlas.modules.recommendations.domain.final_disposition import (
    FINAL_ACCEPTED,
    FINAL_ACCEPTED_STATE,
    FINAL_DISPOSITIONS,
    FINAL_REJECTED_STATE,
    TRACKS,
    FinalRecommendationDispositionClaim,
    FinalRecommendationDispositionInstruction,
    FinalRecommendationDispositionPolicySnapshot,
    FinalRecommendationDispositionReceipt,
    FinalRecommendationDispositionRecord,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_decision import (
    RECOMMENDATION_TRACK_REVIEW_DECIDED,
    RecommendationTrackReviewDecisionRecord,
)
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord

FINAL_DISPOSITION_POLICY_SCHEMA = "atlas.final-recommendation-disposition-policy.v1"
FINAL_DISPOSITION_CLAIM_SCHEMA = "atlas.final-recommendation-disposition-claim.v1"
FINAL_DISPOSITION_RECORD_SCHEMA = "atlas.final-recommendation-disposition.v1"


class FinalRecommendationDispositionService:
    def __init__(
        self,
        *,
        repository: FinalRecommendationDispositionRepository,
        source: FinalRecommendationDispositionSource,
        policy_source: FinalRecommendationDispositionPolicySource,
        permission_authorizer: FinalRecommendationDispositionPermissionAuthorizer,
        attestor: FinalRecommendationDispositionAttestor,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._attestor = attestor
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        review_request_id: str,
        review_request_digest: str,
        recommendation_id: str,
        recommendation_digest: str,
        decision_ids: tuple[str, str],
        decision_digests: tuple[str, str],
        disposition_code: str,
        basis_codes: tuple[str, ...],
        disposition_policy_id: str,
        disposition_policy_digest: str,
        purpose: str,
        immutable_generation_acknowledged: bool,
        recommendation_level_only_acknowledged: bool,
        handoff_eligibility_only_acknowledged: bool,
        no_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> FinalRecommendationDispositionRecord:
        self._require_enterprise_human(actor)
        purpose = purpose.strip()
        basis_codes = tuple(sorted(set(basis_codes)))
        if (
            disposition_code not in FINAL_DISPOSITIONS
            or not basis_codes
            or len(set(decision_ids)) != 2
            or len(set(decision_digests)) != 2
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    immutable_generation_acknowledged,
                    recommendation_level_only_acknowledged,
                    handoff_eligibility_only_acknowledged,
                    no_operational_authority_acknowledged,
                )
            )
        ):
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_request_invalid"
            )
        try:
            decisions, request, readiness, artifact = await self._source.final_disposition_source(
                review_request_id=review_request_id
            )
        except Exception as error:
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=disposition_policy_id)
        if policy is None:
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_policy_not_found"
            )
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
            review_request_id=review_request_id,
            review_request_digest=review_request_digest,
            recommendation_id=recommendation_id,
            recommendation_digest=recommendation_digest,
            decision_ids=decision_ids,
            decision_digests=decision_digests,
            disposition_code=disposition_code,
            basis_codes=basis_codes,
            disposition_policy_digest=disposition_policy_digest,
            now=now,
        )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            correlation_id=correlation_id,
        )
        approver_digest = self._digest(
            [policy.approver_subject_digest_salt_digest, actor.subject_id]
        )
        reviewer_digest = self._digest(
            [policy.reviewer_subject_digest_salt_digest, actor.subject_id]
        )
        consumer_digest = self._digest(
            [policy.source_consumer_subject_digest_salt_digest, actor.subject_id]
        )
        if (
            reviewer_digest in {decision.decided_by_subject_digest for decision in ordered}
            or consumer_digest == artifact.consumer_subject_digest
            or bool(set(actor.role_ids) & set(policy.forbidden_approver_role_ids))
            or actor.subject_id
            in {policy.signed_by, policy.required_attestor_subject_id, policy.required_attestor_id}
        ):
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_actor_separation_required"
            )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        decision_aggregate_digest = self._decision_aggregate_digest(ordered)
        basis_digest = self._digest(list(basis_codes))
        purpose_digest = self._digest(purpose)
        request_binding_digest = self._digest(
            {
                "review_request_id": review_request_id,
                "review_request_digest": review_request_digest,
                "recommendation_id": recommendation_id,
                "recommendation_digest": recommendation_digest,
                "decision_aggregate_digest": decision_aggregate_digest,
                "disposition_code": disposition_code,
                "basis_digest": basis_digest,
                "policy_digest": policy.canonical_digest,
                "purpose_digest": purpose_digest,
                "approver_subject_digest": approver_digest,
                "browser_session_binding_digest": browser_digest,
            }
        )
        idempotency_digest = self._digest(
            [approver_digest, review_request_id, browser_digest, idempotency_key]
        )
        existing = await self._repository.get_claim_by_review_request(
            review_request_id=review_request_id
        )
        if existing is not None:
            return await self._reuse(
                existing,
                approver_digest=approver_digest,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        seed = self._digest([review_request_id, request_binding_digest])[:24]
        disposition_id = f"final-recommendation-disposition.{seed}"
        await self._audit(
            actor,
            correlation_id,
            "final_recommendation_disposition_intent_recorded",
            review_request_id,
            (("disposition_code", disposition_code),),
        )
        claim = FinalRecommendationDispositionClaim(
            claim_id=f"final-recommendation-disposition-claim.{seed}",
            schema_version=FINAL_DISPOSITION_CLAIM_SCHEMA,
            version=1,
            review_request_id=review_request_id,
            disposition_id=disposition_id,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            claimed_by_subject_digest=approver_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_review_request(
                review_request_id=review_request_id
            )
            if concurrent is None:
                raise FinalRecommendationDispositionUncertainError(
                    "final_recommendation_disposition_claim_uncertain"
                )
            return await self._reuse(
                concurrent,
                approver_digest=approver_digest,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        try:
            await self._audit(
                actor,
                correlation_id,
                "final_recommendation_disposition_claimed",
                disposition_id,
                (("disposition_code", disposition_code),),
            )
        except Exception as error:
            await self._audit_uncertain(actor, correlation_id, disposition_id, disposition_code)
            raise FinalRecommendationDispositionUncertainError(
                "final_recommendation_disposition_outcome_uncertain"
            ) from error
        instruction = FinalRecommendationDispositionInstruction(
            disposition_id=disposition_id,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            review_request_id=review_request_id,
            review_request_digest=review_request_digest,
            recommendation_id=recommendation_id,
            recommendation_digest=recommendation_digest,
            promotion_id=artifact.promotion_id,
            readiness_assessment_id=readiness.assessment_id,
            assignment_set_id=ordered[0].source_assignment_set_id,
            decision_ids=(ordered[0].decision_id, ordered[1].decision_id),
            decision_digests=(ordered[0].canonical_digest, ordered[1].canonical_digest),
            decision_aggregate_digest=decision_aggregate_digest,
            approver_subject_digest=approver_digest,
            browser_session_binding_digest=browser_digest,
            disposition_code=disposition_code,
            basis_codes=basis_codes,
            basis_digest=basis_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            purpose_digest=purpose_digest,
            requested_at=now,
        )
        try:
            receipt = await self._attestor.attest(instruction)
            self._verify_receipt(receipt, instruction, policy)
            await self._audit(
                actor,
                correlation_id,
                "final_recommendation_disposition_attested",
                disposition_id,
                (("disposition_code", disposition_code),),
            )
        except Exception as error:
            await self._audit_uncertain(actor, correlation_id, disposition_id, disposition_code)
            raise FinalRecommendationDispositionUncertainError(
                "final_recommendation_disposition_outcome_uncertain"
            ) from error
        accepted = disposition_code == FINAL_ACCEPTED
        record = FinalRecommendationDispositionRecord(
            disposition_id=disposition_id,
            schema_version=FINAL_DISPOSITION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            review_request_id=review_request_id,
            review_request_digest=review_request_digest,
            recommendation_id=recommendation_id,
            recommendation_digest=recommendation_digest,
            promotion_id=artifact.promotion_id,
            readiness_assessment_id=readiness.assessment_id,
            assignment_set_id=ordered[0].source_assignment_set_id,
            decision_ids=(ordered[0].decision_id, ordered[1].decision_id),
            decision_digests=(ordered[0].canonical_digest, ordered[1].canonical_digest),
            decision_aggregate_digest=decision_aggregate_digest,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            classification=artifact.classification,
            disposition_code=disposition_code,
            basis_codes=basis_codes,
            basis_digest=basis_digest,
            approved_by_subject_digest=approver_digest,
            browser_session_binding_digest=browser_digest,
            disposition_policy_id=policy.policy_id,
            disposition_policy_digest=policy.canonical_digest,
            disposition_policy_version=policy.policy_version,
            attestor_id=receipt.attestor_id,
            attestation_digest=receipt.canonical_digest,
            resolved_at=receipt.attested_at,
            state=FINAL_ACCEPTED_STATE if accepted else FINAL_REJECTED_STATE,
            purpose=purpose,
            canonical_digest="0" * 64,
            recommendation_approved=accepted,
            workflow_handoff_eligible=accepted,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        try:
            added = await self._repository.add(record)
        except Exception as error:
            await self._audit_uncertain(actor, correlation_id, disposition_id, disposition_code)
            raise FinalRecommendationDispositionUncertainError(
                "final_recommendation_disposition_outcome_uncertain"
            ) from error
        if not added:
            raced = await self._repository.get_by_review_request(
                review_request_id=review_request_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                await self._audit_uncertain(actor, correlation_id, disposition_id, disposition_code)
                raise FinalRecommendationDispositionUncertainError(
                    "final_recommendation_disposition_persistence_uncertain"
                )
            return replace(raced, reused=True)
        try:
            await self._audit(
                actor,
                correlation_id,
                "final_recommendation_disposition_recorded",
                disposition_id,
                (("disposition_code", disposition_code),),
            )
        except Exception as error:
            await self._audit_uncertain(actor, correlation_id, disposition_id, disposition_code)
            raise FinalRecommendationDispositionUncertainError(
                "final_recommendation_disposition_outcome_uncertain"
            ) from error
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        disposition_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> FinalRecommendationDispositionRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(disposition_id=disposition_id)
        if record is None:
            raise FinalRecommendationDispositionError("final_recommendation_disposition_not_found")
        self._verify_record(record)
        policy = await self._policy_source.get_by_id(policy_id=record.disposition_policy_id)
        if (
            policy is None
            or policy.canonical_digest != record.disposition_policy_digest
            or not policy.issued_at <= self._clock() < policy.expires_at
        ):
            raise FinalRecommendationDispositionError("final_recommendation_disposition_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        if (
            self._digest([policy.approver_subject_digest_salt_digest, actor.subject_id])
            != record.approved_by_subject_digest
            or self._digest([policy.browser_binding_key_digest, browser_session_id])
            != record.browser_session_binding_digest
        ):
            raise FinalRecommendationDispositionError("final_recommendation_disposition_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        await self._audit(
            actor,
            correlation_id,
            "final_recommendation_disposition_read",
            record.disposition_id,
            (("disposition_code", record.disposition_code),),
            permission_id=RECOMMENDATION_FINAL_DISPOSITION_READ,
        )
        return replace(record, reused=True)

    async def close(self) -> None:
        await self._repository.close()

    def _verify_source(
        self,
        *,
        actor: AuthenticatedSubject,
        decisions: tuple[RecommendationTrackReviewDecisionRecord, ...],
        request: RecommendationReviewRequestRecord,
        readiness: RecommendationReadinessAssessment,
        artifact: PromotedRecommendationArtifact,
        policy: FinalRecommendationDispositionPolicySnapshot,
        review_request_id: str,
        review_request_digest: str,
        recommendation_id: str,
        recommendation_digest: str,
        decision_ids: tuple[str, str],
        decision_digests: tuple[str, str],
        disposition_code: str,
        basis_codes: tuple[str, ...],
        disposition_policy_digest: str,
        now: datetime,
    ) -> tuple[RecommendationTrackReviewDecisionRecord, ...]:
        ordered = tuple(sorted(decisions, key=lambda item: item.track_code))
        supplied = set(zip(decision_ids, decision_digests, strict=True))
        actual = {(item.decision_id, item.canonical_digest) for item in ordered}
        allowed_basis = (
            frozenset(policy.accepted_basis_codes)
            if disposition_code == FINAL_ACCEPTED
            else frozenset(policy.rejected_basis_codes)
        )
        if (
            len(ordered) != 2
            or {item.track_code for item in ordered} != TRACKS
            or supplied != actual
            or any(item.disposition_code != "review-disposition.passed" for item in ordered)
            or any(item.state != RECOMMENDATION_TRACK_REVIEW_DECIDED for item in ordered)
            or any(
                item.correction_required
                or item.correction_created
                or item.recommendation_approved
                or item.workflow_created
                or item.itsm_record_created
                or item.execution_authorized
                or item.deployment_authorized
                or item.infrastructure_mutated
                for item in ordered
            )
            or len(basis_codes) > policy.maximum_basis_codes
            or not set(basis_codes) <= allowed_basis
            or request.review_request_id != review_request_id
            or request.canonical_digest != review_request_digest
            or request.recommendation_id != artifact.recommendation_id
            or request.readiness_assessment_id != readiness.assessment_id
            or request.promotion_id != artifact.promotion_id
            or readiness.recommendation_id != artifact.recommendation_id
            or readiness.promotion_id != artifact.promotion_id
            or readiness.source_artifact_digest != artifact.canonical_digest
            or not readiness.recommendation_ready_for_review
            or artifact.recommendation_id != recommendation_id
            or artifact.canonical_digest != recommendation_digest
            or artifact.recommendation_approved
            or artifact.workflow_created
            or artifact.itsm_record_created
            or artifact.execution_authorized
            or artifact.deployment_authorized
            or artifact.infrastructure_mutated
            or any(item.review_request_id != request.review_request_id for item in ordered)
            or any(item.recommendation_id != artifact.recommendation_id for item in ordered)
            or any(item.readiness_assessment_id != readiness.assessment_id for item in ordered)
            or any(item.promotion_id != artifact.promotion_id for item in ordered)
            or any(
                item.recommendation_artifact_digest != artifact.canonical_digest for item in ordered
            )
            or any(
                item.source_assignment_set_id != ordered[0].source_assignment_set_id
                for item in ordered
            )
            or any(item.decision_policy_id != ordered[0].decision_policy_id for item in ordered)
            or any(
                item.decision_policy_digest != ordered[0].decision_policy_digest for item in ordered
            )
            or any(
                item.decision_policy_version != ordered[0].decision_policy_version
                for item in ordered
            )
            or policy.canonical_digest != disposition_policy_digest
            or policy.organization_id != request.organization_id
            or policy.environment_id != request.environment_id
            or any(item.schema_version != policy.required_decision_schema for item in ordered)
            or any(item.state != policy.required_decision_state for item in ordered)
            or request.schema_version != policy.required_request_schema
            or request.state != policy.required_request_state
            or readiness.schema_version != policy.required_readiness_schema
            or readiness.state != policy.required_readiness_state
            or artifact.schema_version != policy.required_promotion_schema
            or artifact.state != policy.required_promotion_state
            or not request.requested_at <= now < request.expires_at
            or not readiness.assessed_at <= now < readiness.expires_at
            or not artifact.promoted_at <= now < artifact.expires_at
            or any(not item.decided_at <= now < item.expires_at for item in ordered)
            or not policy.issued_at <= now < policy.expires_at
            or not actor.authenticated_at <= now
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_source_invalid"
            )
        self._require_scope(actor, request.organization_id, request.environment_id)
        return ordered

    async def _reuse(
        self,
        claim: FinalRecommendationDispositionClaim,
        *,
        approver_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> FinalRecommendationDispositionRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by_subject_digest != approver_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_idempotency_conflict"
            )
        record = await self._repository.get(disposition_id=claim.disposition_id)
        if record is None:
            raise FinalRecommendationDispositionUncertainError(
                "final_recommendation_disposition_claimed_outcome_uncertain"
            )
        self._verify_record(record)
        await self._audit(
            actor,
            correlation_id,
            "final_recommendation_disposition_read",
            record.disposition_id,
            (("disposition_code", record.disposition_code),),
            permission_id=RECOMMENDATION_FINAL_DISPOSITION_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _verify_receipt(
        cls,
        receipt: FinalRecommendationDispositionReceipt,
        instruction: FinalRecommendationDispositionInstruction,
        policy: FinalRecommendationDispositionPolicySnapshot,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.disposition_id != instruction.disposition_id
            or receipt.disposition_code != instruction.disposition_code
            or receipt.attestor_id != policy.required_attestor_id
            or receipt.attested_by != policy.required_attestor_subject_id
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or not instruction.requested_at
            <= receipt.attested_at
            <= instruction.requested_at
            + timedelta(seconds=policy.maximum_attestation_delay_seconds)
            or receipt.attested_at >= policy.expires_at
            or receipt.canonical_digest != cls._receipt_digest(receipt)
        ):
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_attestation_invalid"
            )

    @classmethod
    def _verify_policy(cls, policy: FinalRecommendationDispositionPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._payload(policy)):
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_policy_invalid"
            )

    @classmethod
    def _verify_claim(cls, claim: FinalRecommendationDispositionClaim) -> None:
        if claim.canonical_digest != cls._digest(cls._payload(claim)):
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: FinalRecommendationDispositionRecord) -> None:
        if record.canonical_digest != cls._digest(cls._payload(record)):
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_integrity_failed"
            )

    @classmethod
    def _receipt_digest(cls, receipt: FinalRecommendationDispositionReceipt) -> str:
        payload = cast(dict[str, object], asdict(receipt))
        payload.pop("canonical_digest", None)
        return cls._digest(payload)

    @staticmethod
    def _payload(
        value: FinalRecommendationDispositionPolicySnapshot
        | FinalRecommendationDispositionClaim
        | FinalRecommendationDispositionRecord,
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(value))
        payload.pop("canonical_digest", None)
        payload.pop("reused", None)
        return payload

    @classmethod
    def _decision_aggregate_digest(
        cls, decisions: tuple[RecommendationTrackReviewDecisionRecord, ...]
    ) -> str:
        return cls._digest(
            [
                [item.track_code, item.decision_id, item.canonical_digest, item.disposition_code]
                for item in decisions
            ]
        )

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: cls._normalize(item) for key, item in value.items()}
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
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_human_required"
            )

    @staticmethod
    def _require_assurance(
        actor: AuthenticatedSubject,
        policy: FinalRecommendationDispositionPolicySnapshot,
    ) -> None:
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_assurance_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise FinalRecommendationDispositionError(
                "final_recommendation_disposition_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = RECOMMENDATION_FINAL_DISPOSITION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendation.final-disposition",
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
                resource_type="resource.recommendation.final-dispositions",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )

    async def _audit_uncertain(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        disposition_id: str,
        disposition_code: str,
    ) -> None:
        try:
            await self._audit(
                actor,
                correlation_id,
                "final_recommendation_disposition_uncertain",
                disposition_id,
                (("disposition_code", disposition_code),),
            )
        except Exception:
            return


def build_development_final_recommendation_disposition_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> FinalRecommendationDispositionPolicySnapshot:
    digest = FinalRecommendationDispositionService._digest
    policy = FinalRecommendationDispositionPolicySnapshot(
        policy_id="final-recommendation-disposition-policy.development",
        schema_version=FINAL_DISPOSITION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.final-recommendation-disposition-development-v1",
        required_decision_schema="atlas.recommendation-track-review-decision.v1",
        required_decision_state=RECOMMENDATION_TRACK_REVIEW_DECIDED,
        required_request_schema="atlas.recommendation-review-request.v1",
        required_request_state="review_requested",
        required_readiness_schema="atlas.recommendation-readiness-assessment.v1",
        required_readiness_state="ready_for_review",
        required_promotion_schema="atlas.promoted-recommendation-artifact.v1",
        required_promotion_state="draft",
        allowed_dispositions=tuple(sorted(FINAL_DISPOSITIONS)),
        accepted_basis_codes=(
            "recommendation-final-basis.review-evidence-sufficient",
            "recommendation-final-basis.service-impact-understood",
            "recommendation-final-basis.governance-scope-accepted",
        ),
        rejected_basis_codes=(
            "recommendation-final-basis.evidence-insufficient",
            "recommendation-final-basis.risk-not-acceptable",
            "recommendation-final-basis.governance-scope-rejected",
        ),
        forbidden_approver_role_ids=(
            "role.ai-operator",
            "role.break-glass",
            "role.recovery",
            "role.shared-operator",
        ),
        maximum_basis_codes=3,
        maximum_authentication_age_minutes=15,
        maximum_attestation_delay_seconds=60,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        source_consumer_subject_digest_salt_digest=digest(
            [organization_id, environment_id, "review-salt-v1"]
        ),
        approver_subject_digest_salt_digest=digest(
            ["final-recommendation-approver-subject-salt.v1"]
        ),
        reviewer_subject_digest_salt_digest=digest(["recommendation-reviewer-subject-salt.v1"]),
        browser_binding_key_digest=digest(["final-recommendation-browser-key.v1"]),
        required_attestor_id="final-recommendation-disposition-attestor.synthetic",
        required_attestor_subject_id="subject.final-recommendation-disposition-attestor",
        required_receipt_schema="atlas.final-recommendation-disposition-receipt.v1",
        signed_by="subject.final-recommendation-disposition-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(FinalRecommendationDispositionService._payload(policy))
    )
