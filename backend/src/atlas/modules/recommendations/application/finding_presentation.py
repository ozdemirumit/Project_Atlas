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
    RECOMMENDATION_FINDING_PRESENTATION_CREATE,
    RECOMMENDATION_FINDING_PRESENTATION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.recommendations.application.finding_presentation_ports import (
    RecommendationFindingPresentationError,
    RecommendationFindingPresentationPermissionAuthorizer,
    RecommendationFindingPresentationPolicySource,
    RecommendationFindingPresentationRepository,
    RecommendationFindingPresentationSource,
    RecommendationFindingPresentationUncertainError,
    RecommendationFindingPresenter,
)
from atlas.modules.recommendations.domain.finding_presentation import (
    RECOMMENDATION_HUMAN_REVIEW_FINDING_PRESENTED,
    RecommendationFindingPresentationClaim,
    RecommendationFindingPresentationGrant,
    RecommendationFindingPresentationInstruction,
    RecommendationFindingPresentationPolicySnapshot,
    RecommendationFindingPresentationReceipt,
    RecommendationFindingPresentationRecord,
)
from atlas.modules.recommendations.domain.human_review_finding import (
    RECOMMENDATION_HUMAN_REVIEW_FINDING_RECORDED,
    RecommendationHumanReviewFindingPolicySnapshot,
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
from atlas.modules.recommendations.domain.review_request import (
    RecommendationReviewRequestRecord,
)
from atlas.modules.recommendations.domain.reviewer_assignment import (
    RecommendationReviewerAssignmentRecord,
)

FINDING_PRESENTATION_POLICY_SCHEMA = "atlas.recommendation-finding-presentation-policy.v1"
FINDING_PRESENTATION_CLAIM_SCHEMA = "atlas.recommendation-finding-presentation-claim.v1"
FINDING_PRESENTATION_RECORD_SCHEMA = "atlas.recommendation-finding-presentation.v1"

FindingPresentationSourceBundle = tuple[
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


class RecommendationFindingPresentationService:
    def __init__(
        self,
        *,
        repository: RecommendationFindingPresentationRepository,
        source: RecommendationFindingPresentationSource,
        policy_source: RecommendationFindingPresentationPolicySource,
        permission_authorizer: RecommendationFindingPresentationPermissionAuthorizer,
        presenter: RecommendationFindingPresenter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._presenter = presenter
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
        source_finding_packet_id: str,
        source_finding_digest: str,
        presentation_policy_id: str,
        presentation_policy_digest: str,
        purpose: str,
        sensitive_findings_acknowledged: bool,
        finding_is_not_decision_acknowledged: bool,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        idempotency_key: str,
        correlation_id: str,
    ) -> RecommendationFindingPresentationGrant:
        purpose = purpose.strip()
        if (
            not sensitive_findings_acknowledged
            or not finding_is_not_decision_acknowledged
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_request_invalid"
            )
        source = await self._authorize(
            actor=actor,
            recommendation_id=recommendation_id,
            source_lease_id=source_lease_id,
            source_presentation_id=source_presentation_id,
            source_finding_packet_id=source_finding_packet_id,
            source_finding_digest=source_finding_digest,
            presentation_policy_id=presentation_policy_id,
            presentation_policy_digest=presentation_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
        )
        (
            finding,
            presentation,
            lease,
            inspection_policy,
            _assignment,
            _review_request,
            _assessment,
            _artifact,
            _content_policy,
            finding_policy,
            policy,
        ) = source
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest(
            [inspection_policy.browser_binding_key_digest, browser_session_id]
        )
        request_digest = self._digest(
            {
                "source_lease_id": lease.lease_id,
                "source_presentation_id": presentation.presentation_id,
                "source_finding_packet_id": finding.finding_packet_id,
                "source_finding_digest": finding.canonical_digest,
                "presentation_policy_id": policy.policy_id,
                "presentation_policy_digest": policy.canonical_digest,
                "purpose": purpose,
                "track_code": finding.track_code,
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
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_digest=request_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        seed = self._digest(
            [finding.finding_packet_id, finding.canonical_digest, policy.canonical_digest]
        )
        finding_presentation_id = f"recommendation-finding-presentation.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "recommendation_finding_presentation_requested",
            finding.finding_packet_id,
            (("track_code", finding.track_code),),
        )
        claim = RecommendationFindingPresentationClaim(
            claim_id=f"recommendation-finding-presentation-claim.{seed[:24]}",
            schema_version=FINDING_PRESENTATION_CLAIM_SCHEMA,
            version=1,
            source_finding_packet_id=finding.finding_packet_id,
            source_finding_digest=finding.canonical_digest,
            finding_presentation_id=finding_presentation_id,
            organization_id=finding.organization_id,
            environment_id=finding.environment_id,
            track_code=finding.track_code,
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
            prior = await self._repository.get_claim_by_source_finding(
                source_finding_packet_id=finding.finding_packet_id
            )
            if prior is None:
                raise RecommendationFindingPresentationUncertainError(
                    "recommendation_finding_presentation_claim_uncertain"
                )
            return await self._reuse(
                prior,
                source=source,
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
            "recommendation_finding_presentation_claimed",
            claim.claim_id,
            (("finding_presentation_id", finding_presentation_id),),
        )
        instruction = self._instruction(
            finding_presentation_id=finding_presentation_id,
            finding=finding,
            finding_policy=finding_policy,
            policy=policy,
            purpose=purpose,
        )
        try:
            receipt = await self._presenter.present(instruction)
            self._verify_receipt(instruction, receipt, policy, finding_policy)
        except RecommendationFindingPresentationError:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_finding_presentation_failed",
                finding_presentation_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "recommendation_finding_presentation_uncertain",
                finding_presentation_id,
                (("claim_persisted", "true"),),
            )
            raise RecommendationFindingPresentationUncertainError(
                "recommendation_finding_presentation_outcome_uncertain"
            ) from error
        record = self._record(claim, finding, finding_policy, policy, receipt)
        await self._audit(
            actor,
            correlation_id,
            "recommendation_human_review_finding_presented",
            finding_presentation_id,
            (("finding_count", str(record.finding_count)), ("track_code", record.track_code)),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_finding(
                source_finding_packet_id=finding.finding_packet_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise RecommendationFindingPresentationUncertainError(
                    "recommendation_finding_presentation_persistence_uncertain"
                )
            record = replace(raced, reused=True)
        return RecommendationFindingPresentationGrant(record=record, findings=receipt.findings)

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        source_presentation_id: str,
        source_finding_packet_id: str,
        finding_presentation_id: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
    ) -> RecommendationFindingPresentationGrant:
        record = await self._repository.get(finding_presentation_id=finding_presentation_id)
        if (
            record is None
            or record.recommendation_id != recommendation_id
            or record.source_lease_id != source_lease_id
            or record.source_presentation_id != source_presentation_id
            or record.source_finding_packet_id != source_finding_packet_id
        ):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_not_found"
            )
        self._verify_record(record)
        source = await self._authorize(
            actor=actor,
            recommendation_id=recommendation_id,
            source_lease_id=source_lease_id,
            source_presentation_id=source_presentation_id,
            source_finding_packet_id=source_finding_packet_id,
            source_finding_digest=record.source_finding_digest,
            presentation_policy_id=record.presentation_policy_id,
            presentation_policy_digest=record.presentation_policy_digest,
            browser_session_id=browser_session_id,
            lease_secrets=lease_secrets,
            correlation_id=correlation_id,
        )
        (
            finding,
            _presentation,
            _lease,
            _inspection_policy,
            _assignment,
            _review_request,
            _assessment,
            _artifact,
            _content_policy,
            finding_policy,
            policy,
        ) = source
        instruction = self._instruction(
            finding_presentation_id=record.finding_presentation_id,
            finding=finding,
            finding_policy=finding_policy,
            policy=policy,
            purpose=record.purpose,
        )
        try:
            receipt = await self._presenter.present(instruction)
            self._verify_receipt(instruction, receipt, policy, finding_policy)
        except Exception as error:
            raise RecommendationFindingPresentationUncertainError(
                "recommendation_finding_presentation_replay_uncertain"
            ) from error
        if not self._receipt_matches_record(receipt, record):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_replay_drift"
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_finding_presentation_read",
            record.finding_presentation_id,
            (("track_code", record.track_code),),
            permission_id=RECOMMENDATION_FINDING_PRESENTATION_READ,
        )
        return RecommendationFindingPresentationGrant(
            record=replace(record, reused=True), findings=receipt.findings
        )

    async def close(self) -> None:
        await self._repository.close()

    async def review_decision_source(
        self, *, finding_presentation_id: str
    ) -> tuple[
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
    ]:
        record = await self._repository.get(finding_presentation_id=finding_presentation_id)
        if record is None:
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_not_found"
            )
        self._verify_record(record)
        try:
            source = await self._source.finding_presentation_source(
                finding_packet_id=record.source_finding_packet_id
            )
        except Exception as error:
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_lineage_invalid"
            ) from error
        (
            finding,
            presentation,
            lease,
            _inspection_policy,
            assignment,
            review_request,
            assessment,
            artifact,
            content_policy,
            _finding_policy,
        ) = source
        policy = await self._policy_source.get_by_id(policy_id=record.presentation_policy_id)
        if policy is None:
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_lineage_invalid"
            )
        self._verify_policy(policy)
        if (
            record.source_finding_packet_id != finding.finding_packet_id
            or record.source_finding_digest != finding.canonical_digest
            or record.source_lease_id != lease.lease_id
            or record.source_lease_digest != lease.canonical_digest
            or record.source_presentation_id != presentation.presentation_id
            or record.source_presentation_digest != presentation.canonical_digest
            or record.source_assignment_set_id != assignment.assignment_set_id
            or record.review_request_id != review_request.review_request_id
            or record.recommendation_id != artifact.recommendation_id
            or record.readiness_assessment_id != assessment.assessment_id
            or record.promotion_id != artifact.promotion_id
            or record.recommendation_artifact_digest != artifact.canonical_digest
            or record.presented_content_digest != presentation.presented_content_digest
            or record.track_code != finding.track_code
            or record.presentation_policy_digest != policy.canonical_digest
            or presentation.presentation_policy_digest != content_policy.canonical_digest
            or record.organization_id != finding.organization_id
            or record.environment_id != finding.environment_id
        ):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_lineage_invalid"
            )
        return (record, *source, policy)

    async def _authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        recommendation_id: str,
        source_lease_id: str,
        source_presentation_id: str,
        source_finding_packet_id: str,
        source_finding_digest: str,
        presentation_policy_id: str,
        presentation_policy_digest: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
    ) -> FindingPresentationSourceBundle:
        self._require_enterprise_human(actor)
        try:
            source = await self._source.finding_presentation_source(
                finding_packet_id=source_finding_packet_id
            )
        except Exception as error:
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_source_not_found"
            ) from error
        finding, presentation, lease, inspection_policy, assignment, *_ = source
        policy = await self._policy_source.get_by_id(policy_id=presentation_policy_id)
        if policy is None:
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        later_authority = (
            finding.human_review_completed,
            finding.correction_created,
            finding.recommendation_approved,
            finding.workflow_created,
            finding.itsm_record_created,
            finding.execution_authorized,
            finding.deployment_authorized,
            finding.infrastructure_mutated,
        )
        if (
            finding.finding_packet_id != source_finding_packet_id
            or finding.recommendation_id != recommendation_id
            or finding.canonical_digest != source_finding_digest
            or finding.source_lease_id != source_lease_id
            or finding.source_presentation_id != source_presentation_id
            or finding.state != RECOMMENDATION_HUMAN_REVIEW_FINDING_RECORDED
            or not finding.human_findings_recorded
            or any(later_authority)
            or presentation.state != RECOMMENDATION_PROTECTED_CONTENT_PRESENTED
            or lease.state != RECOMMENDATION_PROTECTED_INSPECTION_LEASED
            or now >= lease.expires_at
            or now >= presentation.expires_at
            or now >= finding.expires_at
            or policy.canonical_digest != presentation_policy_digest
            or policy.organization_id != finding.organization_id
            or policy.environment_id != finding.environment_id
            or policy.required_source_schema != finding.schema_version
            or policy.required_source_state != finding.state
            or policy.subject_digest_salt_digest != inspection_policy.subject_digest_salt_digest
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_source_invalid"
            )
        self._require_scope(actor, finding.organization_id, finding.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        selected_assignment = next(
            (
                item
                for item in assignment.track_assignments
                if item[0] == finding.track_code and item[4] == "assigned"
            ),
            None,
        )
        expected_assignee = selected_assignment[3] if selected_assignment is not None else None
        browser_digest = self._digest(
            [inspection_policy.browser_binding_key_digest, browser_session_id]
        )
        secret = lease_secrets.get(finding.track_code)
        secret_digest = (
            self._digest([lease.inspection_policy_digest, "lease-secret", secret])
            if secret
            else None
        )
        if (
            subject_digest != lease.lease_holder_subject_digest
            or subject_digest != finding.lease_holder_subject_digest
            or subject_digest != expected_assignee
            or browser_digest != lease.browser_session_binding_digest
            or browser_digest != finding.browser_session_binding_digest
            or secret_digest != lease.lease_secret_digest
        ):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_source_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=finding.organization_id,
            environment_id=finding.environment_id,
            correlation_id=correlation_id,
        )
        return (*source, policy)

    async def _reuse(
        self,
        claim: RecommendationFindingPresentationClaim,
        *,
        source: FindingPresentationSourceBundle,
        subject_digest: str,
        browser_digest: str,
        request_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> RecommendationFindingPresentationGrant:
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_idempotency_conflict"
            )
        self._verify_claim(claim)
        record = await self._repository.get(finding_presentation_id=claim.finding_presentation_id)
        if record is None:
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_already_claimed"
            )
        self._verify_record(record)
        (
            finding,
            _presentation,
            _lease,
            _inspection_policy,
            _assignment,
            _review_request,
            _assessment,
            _artifact,
            _content_policy,
            finding_policy,
            policy,
        ) = source
        instruction = self._instruction(
            finding_presentation_id=record.finding_presentation_id,
            finding=finding,
            finding_policy=finding_policy,
            policy=policy,
            purpose=record.purpose,
        )
        receipt = await self._presenter.present(instruction)
        self._verify_receipt(
            instruction,
            receipt,
            policy,
            finding_policy,
        )
        if not self._receipt_matches_record(receipt, record):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_replay_drift"
            )
        await self._audit(
            actor,
            correlation_id,
            "recommendation_finding_presentation_read",
            record.finding_presentation_id,
            (("track_code", record.track_code),),
            permission_id=RECOMMENDATION_FINDING_PRESENTATION_READ,
        )
        return RecommendationFindingPresentationGrant(
            record=replace(record, reused=True), findings=receipt.findings
        )

    @staticmethod
    def _instruction(
        *,
        finding_presentation_id: str,
        finding: RecommendationHumanReviewFindingRecord,
        finding_policy: RecommendationHumanReviewFindingPolicySnapshot,
        policy: RecommendationFindingPresentationPolicySnapshot,
        purpose: str,
    ) -> RecommendationFindingPresentationInstruction:
        return RecommendationFindingPresentationInstruction(
            finding_presentation_id=finding_presentation_id,
            organization_id=finding.organization_id,
            environment_id=finding.environment_id,
            source_finding_packet_id=finding.finding_packet_id,
            source_finding_digest=finding.canonical_digest,
            source_finding_artifact_id=finding.finding_artifact_id,
            source_lease_id=finding.source_lease_id,
            source_lease_digest=finding.source_lease_digest,
            source_presentation_id=finding.source_presentation_id,
            source_presentation_digest=finding.source_presentation_digest,
            source_assignment_set_id=finding.source_assignment_set_id,
            track_code=finding.track_code,
            lease_holder_subject_digest=finding.lease_holder_subject_digest,
            browser_session_binding_digest=finding.browser_session_binding_digest,
            recommendation_id=finding.recommendation_id,
            review_request_id=finding.review_request_id,
            readiness_assessment_id=finding.readiness_assessment_id,
            promotion_id=finding.promotion_id,
            recommendation_artifact_digest=finding.recommendation_artifact_digest,
            presented_content_digest=finding.presented_content_digest,
            classification=finding.classification,
            access_policy_id=finding_policy.access_policy_id,
            retention_policy_id=finding_policy.retention_policy_id,
            encryption_profile_id=finding_policy.encryption_profile_id,
            expected_finding_count=finding.finding_count,
            expected_finding_bytes=finding.finding_bytes,
            expected_content_digest=finding.finding_content_digest,
            expected_metadata_digest=finding.finding_metadata_digest,
            expected_lineage_digest=finding.lineage_digest,
            expected_category_catalog_digest=finding.category_catalog_digest,
            expected_severity_catalog_digest=finding.severity_catalog_digest,
            expected_access_digest=finding.access_digest,
            expected_retention_digest=finding.retention_digest,
            expected_encryption_digest=finding.encryption_digest,
            expected_source_cleanup_digest=finding.cleanup_digest,
            presentation_policy_digest=policy.canonical_digest,
            purpose=purpose,
            maximum_findings=policy.maximum_findings,
            maximum_packet_bytes=policy.maximum_packet_bytes,
            expires_at=finding.expires_at,
        )

    def _verify_receipt(
        self,
        instruction: RecommendationFindingPresentationInstruction,
        receipt: RecommendationFindingPresentationReceipt,
        policy: RecommendationFindingPresentationPolicySnapshot,
        finding_policy: RecommendationHumanReviewFindingPolicySnapshot,
    ) -> None:
        now = self._clock()
        categories = (
            finding_policy.technical_category_codes
            if instruction.track_code == "review-track.technical"
            else finding_policy.service_impact_category_codes
        )
        if (
            receipt.finding_presentation_id != instruction.finding_presentation_id
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.presenter_id != policy.required_presenter_id
            or receipt.attested_by != policy.required_presenter_attestor_id
            or receipt.source_finding_packet_id != instruction.source_finding_packet_id
            or receipt.source_finding_digest != instruction.source_finding_digest
            or receipt.track_code != instruction.track_code
            or receipt.media_type != policy.permitted_media_type
            or receipt.finding_count != instruction.expected_finding_count
            or receipt.finding_bytes != instruction.expected_finding_bytes
            or receipt.finding_content_digest != instruction.expected_content_digest
            or receipt.finding_metadata_digest != instruction.expected_metadata_digest
            or receipt.lineage_digest != instruction.expected_lineage_digest
            or receipt.category_catalog_digest != instruction.expected_category_catalog_digest
            or receipt.severity_catalog_digest != instruction.expected_severity_catalog_digest
            or receipt.access_digest != instruction.expected_access_digest
            or receipt.retention_digest != instruction.expected_retention_digest
            or receipt.encryption_digest != instruction.expected_encryption_digest
            or receipt.source_cleanup_digest != instruction.expected_source_cleanup_digest
            or receipt.presented_at > now
            or now >= receipt.expires_at
            or receipt.expires_at != instruction.expires_at
            or not all(
                item.category_code in categories
                and item.severity_code in finding_policy.severity_codes
                for item in receipt.findings
            )
            or receipt.canonical_digest != self._receipt_digest(receipt)
        ):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_receipt_invalid"
            )

    def _record(
        self,
        claim: RecommendationFindingPresentationClaim,
        finding: RecommendationHumanReviewFindingRecord,
        finding_policy: RecommendationHumanReviewFindingPolicySnapshot,
        policy: RecommendationFindingPresentationPolicySnapshot,
        receipt: RecommendationFindingPresentationReceipt,
    ) -> RecommendationFindingPresentationRecord:
        record = RecommendationFindingPresentationRecord(
            finding_presentation_id=receipt.finding_presentation_id,
            schema_version=FINDING_PRESENTATION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_finding_packet_id=finding.finding_packet_id,
            source_finding_digest=finding.canonical_digest,
            source_lease_id=finding.source_lease_id,
            source_lease_digest=finding.source_lease_digest,
            source_presentation_id=finding.source_presentation_id,
            source_presentation_digest=finding.source_presentation_digest,
            source_assignment_set_id=finding.source_assignment_set_id,
            recommendation_id=finding.recommendation_id,
            readiness_assessment_id=finding.readiness_assessment_id,
            promotion_id=finding.promotion_id,
            recommendation_artifact_digest=finding.recommendation_artifact_digest,
            presented_content_digest=finding.presented_content_digest,
            organization_id=finding.organization_id,
            environment_id=finding.environment_id,
            review_request_id=finding.review_request_id,
            classification=finding.classification,
            source_outcome=finding.source_outcome,
            option_count=finding.option_count,
            preferred_count=finding.preferred_count,
            access_policy_id=finding_policy.access_policy_id,
            retention_policy_id=finding_policy.retention_policy_id,
            encryption_profile_id=finding_policy.encryption_profile_id,
            track_code=finding.track_code,
            lease_holder_subject_digest=finding.lease_holder_subject_digest,
            browser_session_binding_digest=finding.browser_session_binding_digest,
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
            source_cleanup_digest=receipt.source_cleanup_digest,
            presentation_cleanup_digest=receipt.presentation_cleanup_digest,
            presentation_policy_id=policy.policy_id,
            presentation_policy_digest=policy.canonical_digest,
            presentation_policy_version=policy.policy_version,
            presenter_id=receipt.presenter_id,
            presented_at=receipt.presented_at,
            expires_at=receipt.expires_at,
            state=RECOMMENDATION_HUMAN_REVIEW_FINDING_PRESENTED,
            purpose=claim.purpose,
            canonical_digest="0" * 64,
            technical_finding_recorded=finding.technical_finding_recorded,
            service_impact_finding_recorded=finding.service_impact_finding_recorded,
            technical_findings_presented=finding.technical_finding_recorded,
            service_impact_findings_presented=finding.service_impact_finding_recorded,
        )
        return replace(record, canonical_digest=self._digest(self._record_payload(record)))

    @staticmethod
    def _receipt_matches_record(
        receipt: RecommendationFindingPresentationReceipt,
        record: RecommendationFindingPresentationRecord,
    ) -> bool:
        return (
            receipt.finding_count == record.finding_count
            and receipt.finding_bytes == record.finding_bytes
            and receipt.finding_content_digest == record.finding_content_digest
            and receipt.finding_metadata_digest == record.finding_metadata_digest
            and receipt.lineage_digest == record.lineage_digest
            and receipt.category_catalog_digest == record.category_catalog_digest
            and receipt.severity_catalog_digest == record.severity_catalog_digest
            and receipt.access_digest == record.access_digest
            and receipt.retention_digest == record.retention_digest
            and receipt.encryption_digest == record.encryption_digest
            and receipt.source_cleanup_digest == record.source_cleanup_digest
            and receipt.presentation_cleanup_digest == record.presentation_cleanup_digest
        )

    @classmethod
    def _verify_policy(cls, policy: RecommendationFindingPresentationPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._policy_payload(policy)):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: RecommendationFindingPresentationClaim) -> None:
        if claim.canonical_digest != cls._digest(cls._claim_payload(claim)):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: RecommendationFindingPresentationRecord) -> None:
        if record.canonical_digest != cls._digest(cls._record_payload(record)):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_record_integrity_failed"
            )

    @classmethod
    def _policy_payload(
        cls, policy: RecommendationFindingPresentationPolicySnapshot
    ) -> dict[str, object]:
        payload = asdict(policy)
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _claim_payload(cls, claim: RecommendationFindingPresentationClaim) -> dict[str, object]:
        payload = asdict(claim)
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: RecommendationFindingPresentationRecord) -> dict[str, object]:
        payload = asdict(record)
        payload.pop("canonical_digest")
        payload.pop("reused")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: RecommendationFindingPresentationReceipt) -> str:
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
                RecommendationFindingPresentationService._normalize(payload),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest()

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = RECOMMENDATION_FINDING_PRESENTATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.recommendations.finding-presentation",
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
                resource_type="resource.recommendations.finding-presentations",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def build_development_recommendation_finding_presentation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> RecommendationFindingPresentationPolicySnapshot:
    digest = RecommendationFindingPresentationService._digest
    policy = RecommendationFindingPresentationPolicySnapshot(
        policy_id="recommendation-finding-presentation-policy.development",
        schema_version=FINDING_PRESENTATION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.recommendation-human-review-finding.v1",
        required_source_state=RECOMMENDATION_HUMAN_REVIEW_FINDING_RECORDED,
        required_presenter_id="recommendation-finding-presenter.synthetic",
        required_presenter_attestor_id="subject.recommendation-finding-presenter-attestor",
        required_receipt_schema="atlas.recommendation-finding-presentation-receipt.v1",
        subject_digest_salt_digest=digest(["recommendation-reviewer-subject-salt.v1"]),
        maximum_authentication_age_minutes=15,
        maximum_findings=20,
        maximum_packet_bytes=32768,
        permitted_media_type="media-type.application-json",
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.recommendation-finding-presentation-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(RecommendationFindingPresentationService._policy_payload(policy)),
    )
