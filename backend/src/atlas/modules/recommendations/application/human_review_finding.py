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
    RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
    RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.recommendations.application.human_review_finding_ports import (
    RecommendationHumanReviewFindingError,
    RecommendationHumanReviewFindingPermissionAuthorizer,
    RecommendationHumanReviewFindingPolicySource,
    RecommendationHumanReviewFindingRecorder,
    RecommendationHumanReviewFindingRepository,
    RecommendationHumanReviewFindingSource,
    RecommendationHumanReviewFindingUncertainError,
)
from atlas.modules.recommendations.domain.human_review_finding import (
    RECOMMENDATION_HUMAN_REVIEW_FINDING_RECORDED,
    RecommendationHumanReviewFindingClaim,
    RecommendationHumanReviewFindingInstruction,
    RecommendationHumanReviewFindingItem,
    RecommendationHumanReviewFindingPolicySnapshot,
    RecommendationHumanReviewFindingReceipt,
    RecommendationHumanReviewFindingRecord,
)
from atlas.modules.recommendations.domain.promotion import PromotedRecommendationArtifact
from atlas.modules.recommendations.domain.protected_content import (
    RECOMMENDATION_PROTECTED_CONTENT_PRESENTED,
    RecommendationProtectedContentPolicySnapshot,
    RecommendationProtectedContentRecord,
)
from atlas.modules.recommendations.domain.protected_inspection import (
    RECOMMENDATION_PROTECTED_INSPECTION_LEASED,
    RecommendationProtectedInspectionPolicySnapshot,
    RecommendationProtectedInspectionRecord,
)
from atlas.modules.recommendations.domain.readiness import RecommendationReadinessAssessment
from atlas.modules.recommendations.domain.review_request import RecommendationReviewRequestRecord
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentRecord,
)

FINDING_POLICY_SCHEMA = "atlas.recommendation-human-review-finding-policy.v1"
FINDING_CLAIM_SCHEMA = "atlas.recommendation-human-review-finding-claim.v1"
FINDING_RECORD_SCHEMA = "atlas.recommendation-human-review-finding.v1"


class RecommendationHumanReviewFindingService:
    def __init__(
        self,
        *,
        repository: RecommendationHumanReviewFindingRepository,
        source: RecommendationHumanReviewFindingSource,
        policy_source: RecommendationHumanReviewFindingPolicySource,
        permission_authorizer: RecommendationHumanReviewFindingPermissionAuthorizer,
        recorder: RecommendationHumanReviewFindingRecorder,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._recorder = recorder
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        source_presentation_id: str,
        source_presentation_digest: str,
        finding_policy_id: str,
        finding_policy_digest: str,
        findings: tuple[RecommendationHumanReviewFindingItem, ...],
        purpose: str,
        evidence_review_acknowledged: bool,
        finding_is_not_decision_acknowledged: bool,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        idempotency_key: str,
        correlation_id: str,
    ) -> RecommendationHumanReviewFindingRecord:
        purpose = purpose.strip()
        if (
            not evidence_review_acknowledged
            or not finding_is_not_decision_acknowledged
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_request_invalid"
            )
        (
            presentation,
            lease,
            inspection_policy,
            _assignment,
            _review_request,
            _assessment,
            _artifact,
            _content_policy,
            policy,
        ) = await self._authorize(
            actor=actor,
            recommendation_id=recommendation_id,
            source_lease_id=source_lease_id,
            source_presentation_id=source_presentation_id,
            source_presentation_digest=source_presentation_digest,
            finding_policy_id=finding_policy_id,
            finding_policy_digest=finding_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
        )
        normalized_findings = self._validate_findings(findings, presentation.track_code, policy)
        findings_payload = self._finding_items_payload(normalized_findings)
        encoded = json.dumps(
            findings_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        if len(encoded) > policy.maximum_packet_bytes:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_packet_too_large"
            )
        findings_digest = sha256(encoded).hexdigest()
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest(
            [inspection_policy.browser_binding_key_digest, browser_session_id]
        )
        request_digest = self._digest(
            {
                "source_lease_id": lease.lease_id,
                "source_presentation_id": presentation.presentation_id,
                "source_presentation_digest": presentation.canonical_digest,
                "finding_policy_id": policy.policy_id,
                "finding_policy_digest": policy.canonical_digest,
                "findings_digest": findings_digest,
                "finding_count": len(normalized_findings),
                "purpose": purpose,
                "track_code": presentation.track_code,
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
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_digest=request_digest,
                idempotency_digest=idempotency_digest,
            )
        seed = self._digest(
            [presentation.presentation_id, presentation.canonical_digest, policy.canonical_digest]
        )
        finding_packet_id = f"recommendation-human-review-finding.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "recommendation_human_review_finding_requested",
            presentation.presentation_id,
            (
                ("track_code", presentation.track_code),
                ("finding_count", str(len(normalized_findings))),
            ),
        )
        claim = RecommendationHumanReviewFindingClaim(
            claim_id=f"recommendation-human-review-finding-claim.{seed[:24]}",
            schema_version=FINDING_CLAIM_SCHEMA,
            version=1,
            source_presentation_id=presentation.presentation_id,
            source_presentation_digest=presentation.canonical_digest,
            finding_packet_id=finding_packet_id,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            track_code=presentation.track_code,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            purpose=purpose,
            claimed_at=self._clock(),
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        if not await self._repository.claim(claim):
            prior = await self._repository.get_claim_by_source_presentation(
                source_presentation_id=presentation.presentation_id
            )
            if prior is None:
                raise RecommendationHumanReviewFindingUncertainError(
                    "recommendation_human_review_finding_claim_uncertain"
                )
            return await self._reuse(
                prior,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_digest=request_digest,
                idempotency_digest=idempotency_digest,
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_human_review_finding_claimed",
            claim.claim_id,
            (("finding_packet_id", finding_packet_id),),
        )
        instruction = self._instruction(
            finding_packet_id,
            presentation,
            lease,
            normalized_findings,
            policy,
            purpose,
        )
        try:
            receipt = await self._recorder.record(instruction)
            self._verify_receipt(instruction, receipt, policy)
        except RecommendationHumanReviewFindingError:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_human_review_finding_failed",
                finding_packet_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_human_review_finding_uncertain",
                finding_packet_id,
                (("claim_persisted", "true"),),
            )
            raise RecommendationHumanReviewFindingUncertainError(
                "recommendation_human_review_finding_outcome_uncertain"
            ) from error
        record = self._record(claim, presentation, policy, receipt)
        await self._audit(
            actor,
            correlation_id,
            "recommendation_human_review_finding_recorded",
            finding_packet_id,
            (
                ("track_code", record.track_code),
                ("finding_count", str(record.finding_count)),
            ),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_presentation(
                source_presentation_id=presentation.presentation_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise RecommendationHumanReviewFindingUncertainError(
                    "recommendation_human_review_finding_persistence_uncertain"
                )
            record = replace(raced, reused=True)
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        source_presentation_id: str,
        finding_packet_id: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
    ) -> RecommendationHumanReviewFindingRecord:
        record = await self._repository.get(finding_packet_id=finding_packet_id)
        if (
            record is None
            or record.source_lease_id != source_lease_id
            or record.source_presentation_id != source_presentation_id
        ):
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_record_not_found"
            )
        self._verify_record(record)
        await self._authorize(
            actor=actor,
            recommendation_id=recommendation_id,
            source_lease_id=source_lease_id,
            source_presentation_id=source_presentation_id,
            source_presentation_digest=record.source_presentation_digest,
            finding_policy_id=record.finding_policy_id,
            finding_policy_digest=record.finding_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
        )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_human_review_finding_read",
            record.finding_packet_id,
            (("track_code", record.track_code),),
            permission_id=RECOMMENDATION_HUMAN_REVIEW_FINDING_READ,
        )
        return replace(record, reused=True)

    async def close(self) -> None:
        await self._repository.close()

    async def finding_presentation_source(
        self, *, finding_packet_id: str
    ) -> tuple[
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
    ]:
        record = await self._repository.get(finding_packet_id=finding_packet_id)
        if record is None:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_record_not_found"
            )
        self._verify_record(record)
        try:
            (
                presentation,
                lease,
                inspection_policy,
                assignment,
                review_request,
                assessment,
                artifact,
                content_policy,
            ) = await self._source.human_review_finding_source(
                presentation_id=record.source_presentation_id
            )
        except Exception as error:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_lineage_invalid"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=record.finding_policy_id)
        if policy is None:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_lineage_invalid"
            )
        self._verify_policy(policy)
        if (
            record.source_presentation_digest != presentation.canonical_digest
            or record.source_lease_id != lease.lease_id
            or record.source_lease_digest != lease.canonical_digest
            or record.source_assignment_set_id != assignment.assignment_set_id
            or record.review_request_id != review_request.review_request_id
            or record.recommendation_id != artifact.recommendation_id
            or record.readiness_assessment_id != assessment.assessment_id
            or record.promotion_id != artifact.promotion_id
            or record.recommendation_artifact_digest != artifact.canonical_digest
            or record.track_code != presentation.track_code
            or record.lease_holder_subject_digest != lease.lease_holder_subject_digest
            or record.browser_session_binding_digest != lease.browser_session_binding_digest
            or record.presented_content_digest != presentation.presented_content_digest
            or record.finding_policy_digest != policy.canonical_digest
            or presentation.presentation_policy_digest != content_policy.canonical_digest
            or record.organization_id != presentation.organization_id
            or record.environment_id != presentation.environment_id
        ):
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_lineage_invalid"
            )
        return (
            record,
            presentation,
            lease,
            inspection_policy,
            assignment,
            review_request,
            assessment,
            artifact,
            content_policy,
            policy,
        )

    async def _authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        source_presentation_id: str,
        source_presentation_digest: str,
        finding_policy_id: str,
        finding_policy_digest: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
    ) -> tuple[
        RecommendationProtectedContentRecord,
        RecommendationProtectedInspectionRecord,
        RecommendationProtectedInspectionPolicySnapshot,
        RecommendationReviewerAssignmentRecord,
        RecommendationReviewRequestRecord,
        RecommendationReadinessAssessment,
        PromotedRecommendationArtifact,
        RecommendationProtectedContentPolicySnapshot,
        RecommendationHumanReviewFindingPolicySnapshot,
    ]:
        self._require_enterprise_human(actor)
        try:
            (
                presentation,
                lease,
                inspection_policy,
                assignment,
                review_request,
                assessment,
                artifact,
                content_policy,
            ) = await self._source.human_review_finding_source(
                presentation_id=source_presentation_id
            )
        except Exception as error:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=finding_policy_id)
        if policy is None:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        later_authority = (
            presentation.human_findings_recorded,
            presentation.human_review_completed,
            presentation.recommendation_approved,
            presentation.workflow_created,
            presentation.itsm_record_created,
            presentation.execution_authorized,
            presentation.deployment_authorized,
            presentation.infrastructure_mutated,
        )
        if (
            presentation.presentation_id != source_presentation_id
            or presentation.recommendation_id != recommendation_id
            or presentation.canonical_digest != source_presentation_digest
            or presentation.source_lease_id != source_lease_id
            or presentation.state != RECOMMENDATION_PROTECTED_CONTENT_PRESENTED
            or not presentation.content_disclosed
            or presentation.protected_content_bytes_returned <= 0
            or any(later_authority)
            or lease.lease_id != source_lease_id
            or lease.state != RECOMMENDATION_PROTECTED_INSPECTION_LEASED
            or presentation.track_code != lease.track_code
            or presentation.source_assignment_set_id != assignment.assignment_set_id
            or presentation.recommendation_id != artifact.recommendation_id
            or presentation.review_request_id != review_request.review_request_id
            or presentation.readiness_assessment_id != assessment.assessment_id
            or presentation.promotion_id != artifact.promotion_id
            or presentation.recommendation_artifact_digest != artifact.canonical_digest
            or presentation.presentation_policy_digest != content_policy.canonical_digest
            or now >= lease.expires_at
            or now >= presentation.expires_at
            or policy.canonical_digest != finding_policy_digest
            or policy.organization_id != presentation.organization_id
            or policy.environment_id != presentation.environment_id
            or policy.required_source_schema != presentation.schema_version
            or policy.required_source_state != presentation.state
            or policy.subject_digest_salt_digest != inspection_policy.subject_digest_salt_digest
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_source_invalid"
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
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_source_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            correlation_id=correlation_id,
        )
        return (
            presentation,
            lease,
            inspection_policy,
            assignment,
            review_request,
            assessment,
            artifact,
            content_policy,
            policy,
        )

    async def _reuse(
        self,
        claim: RecommendationHumanReviewFindingClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_digest: str,
        idempotency_digest: str,
    ) -> RecommendationHumanReviewFindingRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_idempotency_conflict"
            )
        record = await self._repository.get(finding_packet_id=claim.finding_packet_id)
        if record is None:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_already_claimed"
            )
        self._verify_record(record)
        return replace(record, reused=True)

    @classmethod
    def _validate_findings(
        cls,
        findings: tuple[RecommendationHumanReviewFindingItem, ...],
        track_code: str,
        policy: RecommendationHumanReviewFindingPolicySnapshot,
    ) -> tuple[RecommendationHumanReviewFindingItem, ...]:
        if not 1 <= len(findings) <= policy.maximum_findings:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_items_invalid"
            )
        allowed_categories = (
            frozenset(policy.technical_category_codes)
            if track_code == "review-track.technical"
            else frozenset(policy.service_impact_category_codes)
        )
        allowed_severities = frozenset(policy.severity_codes)
        normalized: list[RecommendationHumanReviewFindingItem] = []
        for item in findings:
            candidate = RecommendationHumanReviewFindingItem(
                category_code=item.category_code,
                severity_code=item.severity_code,
                summary=item.summary.strip(),
                detail=item.detail.strip(),
            )
            if (
                candidate.category_code not in allowed_categories
                or candidate.severity_code not in allowed_severities
                or len(candidate.summary) > policy.maximum_summary_characters
                or len(candidate.detail) > policy.maximum_detail_characters
            ):
                raise RecommendationHumanReviewFindingError(
                    "recommendation_human_review_finding_items_invalid"
                )
            normalized.append(candidate)
        return tuple(normalized)

    @staticmethod
    def _finding_items_payload(
        findings: tuple[RecommendationHumanReviewFindingItem, ...],
    ) -> list[dict[str, str]]:
        return [
            {
                "category_code": item.category_code,
                "severity_code": item.severity_code,
                "summary": item.summary,
                "detail": item.detail,
            }
            for item in findings
        ]

    @staticmethod
    def _instruction(
        finding_packet_id: str,
        presentation: RecommendationProtectedContentRecord,
        lease: RecommendationProtectedInspectionRecord,
        findings: tuple[RecommendationHumanReviewFindingItem, ...],
        policy: RecommendationHumanReviewFindingPolicySnapshot,
        purpose: str,
    ) -> RecommendationHumanReviewFindingInstruction:
        return RecommendationHumanReviewFindingInstruction(
            finding_packet_id=finding_packet_id,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            source_lease_id=lease.lease_id,
            source_lease_digest=lease.canonical_digest,
            source_presentation_id=presentation.presentation_id,
            source_presentation_digest=presentation.canonical_digest,
            source_assignment_set_id=presentation.source_assignment_set_id,
            recommendation_id=presentation.recommendation_id,
            review_request_id=presentation.review_request_id,
            readiness_assessment_id=presentation.readiness_assessment_id,
            promotion_id=presentation.promotion_id,
            recommendation_artifact_digest=presentation.recommendation_artifact_digest,
            presented_content_digest=presentation.presented_content_digest,
            track_code=presentation.track_code,
            lease_holder_subject_digest=presentation.lease_holder_subject_digest,
            browser_session_binding_digest=presentation.browser_session_binding_digest,
            classification=presentation.classification,
            finding_store_id=policy.finding_store_id,
            access_policy_id=policy.access_policy_id,
            retention_policy_id=policy.retention_policy_id,
            encryption_profile_id=policy.encryption_profile_id,
            finding_policy_digest=policy.canonical_digest,
            purpose=purpose,
            findings=findings,
            maximum_packet_bytes=policy.maximum_packet_bytes,
            expires_at=presentation.expires_at,
        )

    @classmethod
    def _verify_receipt(
        cls,
        instruction: RecommendationHumanReviewFindingInstruction,
        receipt: RecommendationHumanReviewFindingReceipt,
        policy: RecommendationHumanReviewFindingPolicySnapshot,
    ) -> None:
        categories = sorted({item.category_code for item in instruction.findings})
        severities = sorted({item.severity_code for item in instruction.findings})
        if (
            cls._receipt_digest(receipt) != receipt.canonical_digest
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.recorder_id != policy.required_recorder_id
            or receipt.attested_by != policy.required_recorder_attestor_id
            or receipt.finding_packet_id != instruction.finding_packet_id
            or receipt.source_presentation_id != instruction.source_presentation_id
            or receipt.source_presentation_digest != instruction.source_presentation_digest
            or receipt.track_code != instruction.track_code
            or receipt.finding_count != len(instruction.findings)
            or not 1 <= receipt.finding_bytes <= policy.maximum_packet_bytes
            or receipt.lineage_digest
            != cls._digest(
                [
                    instruction.source_lease_digest,
                    instruction.source_presentation_digest,
                    instruction.recommendation_artifact_digest,
                    instruction.presented_content_digest,
                ]
            )
            or receipt.category_catalog_digest != cls._digest(categories)
            or receipt.severity_catalog_digest != cls._digest(severities)
            or receipt.access_digest
            != cls._digest([instruction.classification, instruction.access_policy_id, "inherited"])
            or receipt.retention_digest
            != cls._digest([instruction.retention_policy_id, "inherited"])
            or receipt.encryption_digest
            != cls._digest([instruction.encryption_profile_id, "encrypted"])
            or receipt.cleanup_digest
            != cls._digest([instruction.finding_packet_id, "buffers-erased", "channel-closed"])
            or receipt.expires_at != instruction.expires_at
        ):
            raise RecommendationHumanReviewFindingUncertainError(
                "recommendation_human_review_finding_receipt_invalid"
            )

    @staticmethod
    def _record(
        claim: RecommendationHumanReviewFindingClaim,
        presentation: RecommendationProtectedContentRecord,
        policy: RecommendationHumanReviewFindingPolicySnapshot,
        receipt: RecommendationHumanReviewFindingReceipt,
    ) -> RecommendationHumanReviewFindingRecord:
        record = RecommendationHumanReviewFindingRecord(
            finding_packet_id=receipt.finding_packet_id,
            schema_version=FINDING_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_lease_id=presentation.source_lease_id,
            source_lease_digest=presentation.source_lease_digest,
            source_presentation_id=presentation.presentation_id,
            source_presentation_digest=presentation.canonical_digest,
            source_assignment_set_id=presentation.source_assignment_set_id,
            recommendation_id=presentation.recommendation_id,
            review_request_id=presentation.review_request_id,
            readiness_assessment_id=presentation.readiness_assessment_id,
            promotion_id=presentation.promotion_id,
            recommendation_artifact_digest=presentation.recommendation_artifact_digest,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            classification=presentation.classification,
            source_outcome=presentation.source_outcome,
            option_count=presentation.option_count,
            preferred_count=presentation.preferred_count,
            track_code=presentation.track_code,
            lease_holder_subject_digest=presentation.lease_holder_subject_digest,
            browser_session_binding_digest=presentation.browser_session_binding_digest,
            presented_content_digest=presentation.presented_content_digest,
            finding_artifact_id=receipt.finding_artifact_id,
            finding_count=receipt.finding_count,
            finding_bytes=receipt.finding_bytes,
            finding_content_digest=receipt.finding_content_digest,
            finding_metadata_digest=receipt.finding_metadata_digest,
            lineage_digest=receipt.lineage_digest,
            category_catalog_digest=receipt.category_catalog_digest,
            severity_catalog_digest=receipt.severity_catalog_digest,
            access_digest=receipt.access_digest,
            retention_digest=receipt.retention_digest,
            encryption_digest=receipt.encryption_digest,
            cleanup_digest=receipt.cleanup_digest,
            finding_policy_id=policy.policy_id,
            finding_policy_digest=policy.canonical_digest,
            finding_policy_version=policy.policy_version,
            recorder_id=receipt.recorder_id,
            created_at=receipt.created_at,
            expires_at=receipt.expires_at,
            state=RECOMMENDATION_HUMAN_REVIEW_FINDING_RECORDED,
            purpose=claim.purpose,
            technical_finding_recorded=presentation.track_code == "review-track.technical",
            service_impact_finding_recorded=(
                presentation.track_code == "review-track.service-impact"
            ),
            canonical_digest="0" * 64,
        )
        return replace(
            record,
            canonical_digest=RecommendationHumanReviewFindingService._digest(
                RecommendationHumanReviewFindingService._record_payload(record)
            ),
        )

    @classmethod
    def _verify_policy(cls, policy: RecommendationHumanReviewFindingPolicySnapshot) -> None:
        if cls._digest(cls._policy_payload(policy)) != policy.canonical_digest:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: RecommendationHumanReviewFindingClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: RecommendationHumanReviewFindingRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_record_integrity_failed"
            )

    @classmethod
    def _policy_payload(
        cls, policy: RecommendationHumanReviewFindingPolicySnapshot
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(policy))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _claim_payload(cls, claim: RecommendationHumanReviewFindingClaim) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: RecommendationHumanReviewFindingRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: RecommendationHumanReviewFindingReceipt) -> str:
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

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise RecommendationHumanReviewFindingError(
                "recommendation_human_review_finding_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = RECOMMENDATION_HUMAN_REVIEW_FINDING_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendations.human-review-finding",
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
                resource_type="resource.recommendations.human-review-findings",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def build_development_recommendation_human_review_finding_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> RecommendationHumanReviewFindingPolicySnapshot:
    digest = RecommendationHumanReviewFindingService._digest
    policy = RecommendationHumanReviewFindingPolicySnapshot(
        policy_id="recommendation-human-review-finding-policy.development",
        schema_version=FINDING_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.recommendation-protected-content-presentation.v1",
        required_source_state=RECOMMENDATION_PROTECTED_CONTENT_PRESENTED,
        required_recorder_id="recommendation-human-review-finding-recorder.synthetic",
        required_recorder_attestor_id=(
            "subject.recommendation-human-review-finding-recorder-attestor"
        ),
        required_receipt_schema="atlas.recommendation-human-review-finding-receipt.v1",
        subject_digest_salt_digest=digest(["recommendation-reviewer-subject-salt.v1"]),
        finding_store_id="finding-store.recommendation-review.development",
        access_policy_id="access-policy.recommendation-review-findings",
        retention_policy_id="retention-policy.recommendation-review-findings",
        encryption_profile_id="encryption-profile.recommendation-review-findings",
        maximum_authentication_age_minutes=15,
        maximum_findings=20,
        maximum_summary_characters=200,
        maximum_detail_characters=4000,
        maximum_packet_bytes=32768,
        technical_category_codes=(
            "finding-category.technical-accuracy",
            "finding-category.operational-safety",
            "finding-category.evidence-conflict",
            "finding-category.recovery-feasibility",
            "finding-category.implementation-assumption",
            "finding-category.technical-unknown",
        ),
        service_impact_category_codes=(
            "finding-category.affected-service",
            "finding-category.interruption-estimate",
            "finding-category.business-impact",
            "finding-category.communication-gap",
            "finding-category.recovery-objective",
            "finding-category.dependency-uncertainty",
        ),
        severity_codes=(
            "finding-severity.observation",
            "finding-severity.minor",
            "finding-severity.material",
            "finding-severity.critical",
        ),
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.recommendation-human-review-finding-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(RecommendationHumanReviewFindingService._policy_payload(policy)),
    )
