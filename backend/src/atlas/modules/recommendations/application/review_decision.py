from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.authorization.application.bootstrap import (
    RECOMMENDATION_TRACK_REVIEW_DECISION_CREATE,
    RECOMMENDATION_TRACK_REVIEW_DECISION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.recommendations.application.review_decision_ports import (
    RecommendationTrackReviewDecisionAttestor,
    RecommendationTrackReviewDecisionError,
    RecommendationTrackReviewDecisionPermissionAuthorizer,
    RecommendationTrackReviewDecisionPolicySource,
    RecommendationTrackReviewDecisionRepository,
    RecommendationTrackReviewDecisionSource,
    RecommendationTrackReviewDecisionUncertainError,
)
from atlas.modules.recommendations.domain.finding_presentation import (
    RECOMMENDATION_HUMAN_REVIEW_FINDING_PRESENTED,
    RecommendationFindingPresentationPolicySnapshot,
    RecommendationFindingPresentationRecord,
)
from atlas.modules.recommendations.domain.human_review_finding import (
    RecommendationHumanReviewFindingPolicySnapshot,
    RecommendationHumanReviewFindingRecord,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.protected_content import (
    RecommendationProtectedContentPolicySnapshot,
    RecommendationProtectedContentRecord,
)
from atlas.modules.recommendations.domain.protected_inspection import (
    RECOMMENDATION_PROTECTED_INSPECTION_LEASED,
    RecommendationProtectedInspectionPolicySnapshot,
    RecommendationProtectedInspectionRecord,
)
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_decision import (
    DISPOSITIONS,
    RECOMMENDATION_TRACK_REVIEW_DECIDED,
    RecommendationTrackDecisionBinding,
    RecommendationTrackReviewDecisionClaim,
    RecommendationTrackReviewDecisionGrant,
    RecommendationTrackReviewDecisionInstruction,
    RecommendationTrackReviewDecisionPolicySnapshot,
    RecommendationTrackReviewDecisionReceipt,
    RecommendationTrackReviewDecisionRecord,
)
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentRecord,
)

DECISION_POLICY_SCHEMA = "atlas.recommendation-track-review-decision-policy.v1"
DECISION_CLAIM_SCHEMA = "atlas.recommendation-track-review-decision-claim.v1"
DECISION_RECORD_SCHEMA = "atlas.recommendation-track-review-decision.v1"

ReviewDecisionSourceBundle = tuple[
    RecommendationFindingPresentationRecord,
    RecommendationHumanReviewFindingRecord,
    RecommendationProtectedContentRecord,
    RecommendationProtectedInspectionRecord,
    RecommendationProtectedInspectionPolicySnapshot,
    RecommendationReviewerAssignmentRecord,
    RecommendationReviewRequestRecord,
    RecommendationReadinessAssessment,
    PromotedRecommendationArtifact,
    RecommendationProtectedContentPolicySnapshot,
    RecommendationHumanReviewFindingPolicySnapshot,
    RecommendationFindingPresentationPolicySnapshot,
]


class RecommendationTrackReviewDecisionService:
    def __init__(
        self,
        *,
        repository: RecommendationTrackReviewDecisionRepository,
        source: RecommendationTrackReviewDecisionSource,
        policy_source: RecommendationTrackReviewDecisionPolicySource,
        permission_authorizer: RecommendationTrackReviewDecisionPermissionAuthorizer,
        attestor: RecommendationTrackReviewDecisionAttestor,
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
        recommendation_id: str,
        source_lease_id: str,
        source_content_presentation_id: str,
        source_finding_packet_id: str,
        source_finding_presentation_id: str,
        source_finding_presentation_digest: str,
        decision_policy_id: str,
        decision_policy_digest: str,
        disposition_code: str,
        basis_codes: tuple[str, ...],
        purpose: str,
        exact_findings_reviewed_acknowledged: bool,
        human_track_decision_acknowledged: bool,
        no_approval_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        idempotency_key: str,
        correlation_id: str,
    ) -> RecommendationTrackReviewDecisionGrant:
        purpose = purpose.strip()
        basis_codes = tuple(sorted(set(basis_codes)))
        if (
            not exact_findings_reviewed_acknowledged
            or not human_track_decision_acknowledged
            or not no_approval_or_operational_authority_acknowledged
            or disposition_code not in DISPOSITIONS
            or not basis_codes
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_request_invalid"
            )
        source, policy = await self._authorize(
            actor=actor,
            recommendation_id=recommendation_id,
            source_lease_id=source_lease_id,
            source_content_presentation_id=source_content_presentation_id,
            source_finding_packet_id=source_finding_packet_id,
            source_finding_presentation_id=source_finding_presentation_id,
            source_finding_presentation_digest=source_finding_presentation_digest,
            decision_policy_id=decision_policy_id,
            decision_policy_digest=decision_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
        )
        presentation, _finding, _content, _lease, inspection_policy, *_ = source
        allowed_basis = (
            frozenset(policy.technical_basis_codes)
            if presentation.track_code == "review-track.technical"
            else frozenset(policy.service_impact_basis_codes)
        )
        if len(basis_codes) > policy.maximum_basis_codes or any(
            code not in allowed_basis for code in basis_codes
        ):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_basis_invalid"
            )
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest(
            [inspection_policy.browser_binding_key_digest, browser_session_id]
        )
        basis_digest = self._digest(basis_codes)
        purpose_digest = self._digest(purpose)
        request_digest = self._digest(
            {
                "source_finding_presentation_id": presentation.finding_presentation_id,
                "source_finding_presentation_digest": presentation.canonical_digest,
                "decision_policy_id": policy.policy_id,
                "decision_policy_digest": policy.canonical_digest,
                "track_code": presentation.track_code,
                "disposition_code": disposition_code,
                "basis_digest": basis_digest,
                "purpose_digest": purpose_digest,
                "browser_session_binding_digest": browser_digest,
            }
        )
        idempotency_digest = self._digest([subject_digest, browser_digest, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=subject_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                source=source,
                policy=policy,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_digest=request_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        seed = self._digest(
            [
                presentation.finding_presentation_id,
                presentation.canonical_digest,
                policy.canonical_digest,
            ]
        )
        decision_id = f"recommendation-track-review-decision.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "recommendation_track_review_decision_requested",
            presentation.finding_presentation_id,
            (("track_code", presentation.track_code), ("disposition_code", disposition_code)),
        )
        claim = RecommendationTrackReviewDecisionClaim(
            claim_id=f"recommendation-track-review-decision-claim.{seed[:24]}",
            schema_version=DECISION_CLAIM_SCHEMA,
            version=1,
            source_finding_presentation_id=presentation.finding_presentation_id,
            source_finding_presentation_digest=presentation.canonical_digest,
            decision_id=decision_id,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            track_code=presentation.track_code,
            disposition_code=disposition_code,
            basis_digest=basis_digest,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            purpose_digest=purpose_digest,
            claimed_at=self._clock(),
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        if not await self._repository.claim(claim):
            prior = await self._repository.get_claim_by_source_presentation(
                source_finding_presentation_id=presentation.finding_presentation_id
            )
            if prior is None:
                raise RecommendationTrackReviewDecisionUncertainError(
                    "recommendation_track_review_decision_claim_uncertain"
                )
            return await self._reuse(
                prior,
                source=source,
                policy=policy,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_digest=request_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_track_review_decision_claimed",
            claim.claim_id,
            (("decision_id", decision_id),),
        )
        instruction = self._instruction(claim, presentation, source[6], policy, basis_codes)
        try:
            receipt = await self._attestor.attest(instruction)
            self._verify_receipt(instruction, receipt, policy)
        except RecommendationTrackReviewDecisionError:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_track_review_decision_failed",
                decision_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_track_review_decision_uncertain",
                decision_id,
                (("claim_persisted", "true"),),
            )
            raise RecommendationTrackReviewDecisionUncertainError(
                "recommendation_track_review_decision_outcome_uncertain"
            ) from error
        record = self._record(claim, presentation, source[6], policy, receipt, basis_codes, purpose)
        await self._audit(
            actor,
            correlation_id,
            "recommendation_track_review_decided",
            decision_id,
            (("track_code", record.track_code), ("disposition_code", record.disposition_code)),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_presentation(
                source_finding_presentation_id=presentation.finding_presentation_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise RecommendationTrackReviewDecisionUncertainError(
                    "recommendation_track_review_decision_persistence_uncertain"
                )
            record = replace(raced, reused=True)
        return await self._grant(record)

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        source_content_presentation_id: str,
        source_finding_packet_id: str,
        source_finding_presentation_id: str,
        decision_id: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
    ) -> RecommendationTrackReviewDecisionGrant:
        record = await self._repository.get(decision_id=decision_id)
        if (
            record is None
            or record.recommendation_id != recommendation_id
            or record.source_lease_id != source_lease_id
            or record.source_content_presentation_id != source_content_presentation_id
            or record.source_finding_packet_id != source_finding_packet_id
            or record.source_finding_presentation_id != source_finding_presentation_id
        ):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_not_found"
            )
        self._verify_record(record)
        await self._authorize(
            actor=actor,
            recommendation_id=recommendation_id,
            source_lease_id=source_lease_id,
            source_content_presentation_id=source_content_presentation_id,
            source_finding_packet_id=source_finding_packet_id,
            source_finding_presentation_id=source_finding_presentation_id,
            source_finding_presentation_digest=record.source_finding_presentation_digest,
            decision_policy_id=record.decision_policy_id,
            decision_policy_digest=record.decision_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
            allow_existing_decision=True,
        )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_track_review_decision_read",
            record.decision_id,
            (("track_code", record.track_code),),
            permission_id=RECOMMENDATION_TRACK_REVIEW_DECISION_READ,
        )
        return await self._grant(replace(record, reused=True))

    async def close(self) -> None:
        await self._repository.close()

    async def correction_resubmission_source(
        self, *, review_request_id: str
    ) -> tuple[
        tuple[RecommendationTrackReviewDecisionRecord, ...],
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
    ]:
        records = await self._repository.list_by_review_request(review_request_id=review_request_id)
        if len(records) != 2 or {record.track_code for record in records} != {
            "review-track.technical",
            "review-track.service-impact",
        }:
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_source_not_found"
            )
        ordered = tuple(sorted(records, key=lambda record: record.track_code))
        anchor = records[0]
        for record in ordered:
            self._verify_record(record)
            if (
                record.review_request_id != anchor.review_request_id
                or record.source_review_request_digest != anchor.source_review_request_digest
                or record.source_assignment_set_id != anchor.source_assignment_set_id
                or record.recommendation_id != anchor.recommendation_id
                or record.readiness_assessment_id != anchor.readiness_assessment_id
                or record.promotion_id != anchor.promotion_id
                or record.recommendation_artifact_digest != anchor.recommendation_artifact_digest
                or record.decision_policy_id != anchor.decision_policy_id
                or record.decision_policy_digest != anchor.decision_policy_digest
                or record.decision_policy_version != anchor.decision_policy_version
            ):
                raise RecommendationTrackReviewDecisionError(
                    "recommendation_track_review_decision_aggregate_integrity_failed"
                )
        try:
            source = await self._source.review_decision_source(
                finding_presentation_id=anchor.source_finding_presentation_id
            )
        except Exception as error:
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_source_not_found"
            ) from error
        assignment = source[5]
        request = source[6]
        readiness = source[7]
        artifact = source[8]
        if (
            request.review_request_id != anchor.review_request_id
            or request.canonical_digest != anchor.source_review_request_digest
            or assignment.assignment_set_id != anchor.source_assignment_set_id
            or readiness.assessment_id != anchor.readiness_assessment_id
            or artifact.recommendation_id != anchor.recommendation_id
            or artifact.promotion_id != anchor.promotion_id
            or artifact.canonical_digest != anchor.recommendation_artifact_digest
        ):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_source_invalid"
            )
        return ordered, request, readiness, artifact

    async def final_disposition_source(
        self, *, review_request_id: str
    ) -> tuple[
        tuple[RecommendationTrackReviewDecisionRecord, ...],
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
    ]:
        return await self.correction_resubmission_source(review_request_id=review_request_id)

    async def _authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        source_content_presentation_id: str,
        source_finding_packet_id: str,
        source_finding_presentation_id: str,
        source_finding_presentation_digest: str,
        decision_policy_id: str,
        decision_policy_digest: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
        allow_existing_decision: bool = False,
    ) -> tuple[ReviewDecisionSourceBundle, RecommendationTrackReviewDecisionPolicySnapshot]:
        self._require_enterprise_human(actor)
        try:
            source = await self._source.review_decision_source(
                finding_presentation_id=source_finding_presentation_id
            )
        except Exception as error:
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_source_not_found"
            ) from error
        presentation, finding, content, lease, inspection_policy, assignment, *_ = source
        policy = await self._policy_source.get_by_id(policy_id=decision_policy_id)
        if policy is None:
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_policy_not_found"
            )
        self._verify_policy(policy)
        self._require_assurance(actor, policy)
        now = self._clock()
        later_authority = (
            presentation.correction_created,
            presentation.recommendation_approved,
            presentation.workflow_created,
            presentation.itsm_record_created,
            presentation.execution_authorized,
            presentation.deployment_authorized,
            presentation.infrastructure_mutated,
        )
        if (
            presentation.finding_presentation_id != source_finding_presentation_id
            or presentation.recommendation_id != recommendation_id
            or presentation.canonical_digest != source_finding_presentation_digest
            or presentation.source_lease_id != source_lease_id
            or presentation.source_presentation_id != source_content_presentation_id
            or presentation.source_finding_packet_id != source_finding_packet_id
            or presentation.state != RECOMMENDATION_HUMAN_REVIEW_FINDING_PRESENTED
            or not presentation.human_findings_presented
            or any(later_authority)
            or lease.state != RECOMMENDATION_PROTECTED_INSPECTION_LEASED
            or now >= lease.expires_at
            or now >= content.expires_at
            or now >= finding.expires_at
            or now >= presentation.expires_at
            or policy.canonical_digest != decision_policy_digest
            or policy.organization_id != presentation.organization_id
            or policy.environment_id != presentation.environment_id
            or policy.required_source_schema != presentation.schema_version
            or policy.required_source_state != presentation.state
            or policy.subject_digest_salt_digest != inspection_policy.subject_digest_salt_digest
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_source_invalid"
            )
        self._require_scope(actor, presentation.organization_id, presentation.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        selected_assignment = next(
            (
                item
                for item in assignment.track_assignments
                if item[0] == presentation.track_code and item[4] == "assigned"
            ),
            None,
        )
        expected_assignee = selected_assignment[3] if selected_assignment is not None else None
        browser_digest = self._digest(
            [inspection_policy.browser_binding_key_digest, browser_session_id]
        )
        secret = lease_secrets.get(presentation.track_code)
        secret_digest = (
            self._digest([lease.inspection_policy_digest, "lease-secret", secret])
            if secret
            else None
        )
        if (
            subject_digest != lease.lease_holder_subject_digest
            or subject_digest != presentation.lease_holder_subject_digest
            or subject_digest != expected_assignee
            or browser_digest != lease.browser_session_binding_digest
            or browser_digest != presentation.browser_session_binding_digest
            or secret_digest != lease.lease_secret_digest
        ):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_source_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            correlation_id=correlation_id,
        )
        return source, policy

    async def _reuse(
        self,
        claim: RecommendationTrackReviewDecisionClaim,
        *,
        source: ReviewDecisionSourceBundle,
        policy: RecommendationTrackReviewDecisionPolicySnapshot,
        subject_digest: str,
        browser_digest: str,
        request_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> RecommendationTrackReviewDecisionGrant:
        del source, policy
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_idempotency_conflict"
            )
        self._verify_claim(claim)
        record = await self._repository.get(decision_id=claim.decision_id)
        if record is None:
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_already_claimed"
            )
        self._verify_record(record)
        await self._audit(
            actor,
            correlation_id,
            "recommendation_track_review_decision_read",
            record.decision_id,
            (("track_code", record.track_code),),
            permission_id=RECOMMENDATION_TRACK_REVIEW_DECISION_READ,
        )
        return await self._grant(replace(record, reused=True))

    async def _grant(
        self, record: RecommendationTrackReviewDecisionRecord
    ) -> RecommendationTrackReviewDecisionGrant:
        records = await self._repository.list_by_review_request(
            review_request_id=record.review_request_id
        )
        tracks: dict[str, RecommendationTrackReviewDecisionRecord] = {}
        for candidate in records:
            self._verify_record(candidate)
            if (
                candidate.source_assignment_set_id != record.source_assignment_set_id
                or candidate.recommendation_id != record.recommendation_id
                or candidate.readiness_assessment_id != record.readiness_assessment_id
                or candidate.promotion_id != record.promotion_id
                or candidate.recommendation_artifact_digest != record.recommendation_artifact_digest
                or candidate.source_review_request_digest != record.source_review_request_digest
                or candidate.decision_policy_digest != record.decision_policy_digest
            ):
                raise RecommendationTrackReviewDecisionError(
                    "recommendation_track_review_decision_aggregate_integrity_failed"
                )
            prior = tracks.get(candidate.track_code)
            if prior is not None and prior.decision_id != candidate.decision_id:
                raise RecommendationTrackReviewDecisionError(
                    "recommendation_track_review_decision_aggregate_integrity_failed"
                )
            tracks[candidate.track_code] = candidate
        all_decided = set(tracks) == {
            "review-track.technical",
            "review-track.service-impact",
        }
        any_correction = any(item.correction_required for item in tracks.values())
        all_passed = (
            all_decided
            and not any_correction
            and all(
                item.disposition_code == "review-disposition.passed" for item in tracks.values()
            )
        )
        return RecommendationTrackReviewDecisionGrant(
            record=record,
            all_tracks_decided=all_decided,
            all_tracks_passed=all_passed,
            any_correction_required=any_correction,
            track_decisions=tuple(
                RecommendationTrackDecisionBinding(
                    track_code=item.track_code,
                    decision_id=item.decision_id,
                    canonical_digest=item.canonical_digest,
                    disposition_code=item.disposition_code,
                )
                for item in sorted(tracks.values(), key=lambda value: value.track_code)
            ),
        )

    def _instruction(
        self,
        claim: RecommendationTrackReviewDecisionClaim,
        presentation: RecommendationFindingPresentationRecord,
        review_request: RecommendationReviewRequestRecord,
        policy: RecommendationTrackReviewDecisionPolicySnapshot,
        basis_codes: tuple[str, ...],
    ) -> RecommendationTrackReviewDecisionInstruction:
        return RecommendationTrackReviewDecisionInstruction(
            decision_id=claim.decision_id,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            source_finding_presentation_id=presentation.finding_presentation_id,
            source_finding_presentation_digest=presentation.canonical_digest,
            source_finding_packet_id=presentation.source_finding_packet_id,
            source_finding_digest=presentation.source_finding_digest,
            source_lease_id=presentation.source_lease_id,
            source_assignment_set_id=presentation.source_assignment_set_id,
            review_request_id=presentation.review_request_id,
            source_review_request_digest=review_request.canonical_digest,
            recommendation_id=presentation.recommendation_id,
            readiness_assessment_id=presentation.readiness_assessment_id,
            promotion_id=presentation.promotion_id,
            recommendation_artifact_digest=presentation.recommendation_artifact_digest,
            presented_content_digest=presentation.presented_content_digest,
            track_code=presentation.track_code,
            disposition_code=claim.disposition_code,
            basis_codes=basis_codes,
            decision_policy_digest=policy.canonical_digest,
            decided_by_subject_digest=claim.claimed_by_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            purpose_digest=claim.purpose_digest,
            decided_at=claim.claimed_at,
            expires_at=presentation.expires_at,
        )

    def _record(
        self,
        claim: RecommendationTrackReviewDecisionClaim,
        presentation: RecommendationFindingPresentationRecord,
        review_request: RecommendationReviewRequestRecord,
        policy: RecommendationTrackReviewDecisionPolicySnapshot,
        receipt: RecommendationTrackReviewDecisionReceipt,
        basis_codes: tuple[str, ...],
        purpose: str,
    ) -> RecommendationTrackReviewDecisionRecord:
        technical = presentation.track_code == "review-track.technical"
        passed = claim.disposition_code == "review-disposition.passed"
        record = RecommendationTrackReviewDecisionRecord(
            decision_id=claim.decision_id,
            schema_version=DECISION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_finding_presentation_id=presentation.finding_presentation_id,
            source_finding_presentation_digest=presentation.canonical_digest,
            source_finding_packet_id=presentation.source_finding_packet_id,
            source_finding_digest=presentation.source_finding_digest,
            source_lease_id=presentation.source_lease_id,
            source_lease_digest=presentation.source_lease_digest,
            source_content_presentation_id=presentation.source_presentation_id,
            source_assignment_set_id=presentation.source_assignment_set_id,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            review_request_id=presentation.review_request_id,
            source_review_request_digest=review_request.canonical_digest,
            recommendation_id=presentation.recommendation_id,
            readiness_assessment_id=presentation.readiness_assessment_id,
            promotion_id=presentation.promotion_id,
            recommendation_artifact_digest=presentation.recommendation_artifact_digest,
            presented_content_digest=presentation.presented_content_digest,
            classification=presentation.classification,
            source_outcome=presentation.source_outcome,
            option_count=presentation.option_count,
            preferred_count=presentation.preferred_count,
            access_policy_id=presentation.access_policy_id,
            retention_policy_id=presentation.retention_policy_id,
            encryption_profile_id=presentation.encryption_profile_id,
            track_code=presentation.track_code,
            disposition_code=claim.disposition_code,
            basis_codes=basis_codes,
            basis_digest=claim.basis_digest,
            decided_by_subject_digest=claim.claimed_by_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            decision_policy_id=policy.policy_id,
            decision_policy_digest=policy.canonical_digest,
            decision_policy_version=policy.policy_version,
            attestor_id=receipt.attestor_id,
            attestation_digest=receipt.canonical_digest,
            decided_at=receipt.attested_at,
            expires_at=presentation.expires_at,
            state=RECOMMENDATION_TRACK_REVIEW_DECIDED,
            purpose=purpose,
            canonical_digest="0" * 64,
            technical_review_completed=technical,
            service_impact_review_completed=not technical,
            technical_review_passed=technical and passed,
            service_impact_review_passed=(not technical) and passed,
            correction_required=not passed,
        )
        return replace(record, canonical_digest=self._digest(self._record_payload(record)))

    def _verify_receipt(
        self,
        instruction: RecommendationTrackReviewDecisionInstruction,
        receipt: RecommendationTrackReviewDecisionReceipt,
        policy: RecommendationTrackReviewDecisionPolicySnapshot,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.attestor_id != policy.required_attestor_id
            or receipt.attested_by != policy.required_attestor_subject_id
            or receipt.decision_id != instruction.decision_id
            or receipt.source_finding_presentation_id != instruction.source_finding_presentation_id
            or receipt.source_finding_presentation_digest
            != instruction.source_finding_presentation_digest
            or receipt.track_code != instruction.track_code
            or receipt.disposition_code != instruction.disposition_code
            or receipt.basis_digest != self._digest(instruction.basis_codes)
            or receipt.instruction_digest != self._digest(asdict(instruction))
            or not instruction.decided_at <= receipt.attested_at < instruction.expires_at
            or receipt.canonical_digest != self._receipt_digest(receipt)
        ):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_attestation_invalid"
            )

    @classmethod
    def _verify_policy(cls, policy: RecommendationTrackReviewDecisionPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._policy_payload(policy)):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: RecommendationTrackReviewDecisionClaim) -> None:
        if claim.canonical_digest != cls._digest(cls._claim_payload(claim)):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: RecommendationTrackReviewDecisionRecord) -> None:
        if record.canonical_digest != cls._digest(cls._record_payload(record)):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_record_integrity_failed"
            )

    @classmethod
    def _policy_payload(
        cls, policy: RecommendationTrackReviewDecisionPolicySnapshot
    ) -> dict[str, object]:
        payload = asdict(policy)
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _claim_payload(cls, claim: RecommendationTrackReviewDecisionClaim) -> dict[str, object]:
        payload = asdict(claim)
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: RecommendationTrackReviewDecisionRecord) -> dict[str, object]:
        payload = asdict(record)
        payload.pop("canonical_digest")
        payload.pop("reused")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: RecommendationTrackReviewDecisionReceipt) -> str:
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return cls._digest(payload)

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        return value

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(
                RecommendationTrackReviewDecisionService._normalize(payload),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_human_required"
            )

    @staticmethod
    def _require_assurance(
        actor: AuthenticatedSubject,
        policy: RecommendationTrackReviewDecisionPolicySnapshot,
    ) -> None:
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_assurance_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise RecommendationTrackReviewDecisionError(
                "recommendation_track_review_decision_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = RECOMMENDATION_TRACK_REVIEW_DECISION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendation.track-review-decision",
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
                resource_type="resource.recommendation.track-review-decisions",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def build_development_recommendation_track_review_decision_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> RecommendationTrackReviewDecisionPolicySnapshot:
    digest = RecommendationTrackReviewDecisionService._digest
    policy = RecommendationTrackReviewDecisionPolicySnapshot(
        policy_id="recommendation-track-review-decision-policy.development",
        schema_version=DECISION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.recommendation-finding-presentation.v1",
        required_source_state=RECOMMENDATION_HUMAN_REVIEW_FINDING_PRESENTED,
        required_attestor_id="recommendation-track-review-decision-attestor.synthetic",
        required_attestor_subject_id=("subject.recommendation-track-review-decision-attestor"),
        required_receipt_schema=("atlas.recommendation-track-review-decision-receipt.v1"),
        subject_digest_salt_digest=digest(["recommendation-reviewer-subject-salt.v1"]),
        maximum_authentication_age_minutes=15,
        allowed_dispositions=tuple(sorted(DISPOSITIONS)),
        technical_basis_codes=(
            "review-basis.recommendation-technical-correctness",
            "review-basis.evidence-grounding",
            "review-basis.action-safety",
            "review-basis.recovery-viability",
        ),
        service_impact_basis_codes=(
            "review-basis.service-impact-scope",
            "review-basis.interruption-duration",
            "review-basis.dependency-risk",
            "review-basis.business-continuity",
        ),
        maximum_basis_codes=4,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        signed_by="subject.recommendation-track-review-decision-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(RecommendationTrackReviewDecisionService._policy_payload(policy)),
    )
