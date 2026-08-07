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
    KNOWLEDGE_FINDING_PRESENTATION_CREATE,
    KNOWLEDGE_FINDING_PRESENTATION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.application.finding_presentation_ports import (
    OperationalKnowledgeFindingPresentationError,
    OperationalKnowledgeFindingPresentationPermissionAuthorizer,
    OperationalKnowledgeFindingPresentationPolicySource,
    OperationalKnowledgeFindingPresentationRepository,
    OperationalKnowledgeFindingPresentationSource,
    OperationalKnowledgeFindingPresentationUncertainError,
    OperationalKnowledgeFindingPresenter,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.finding_presentation import (
    OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_PRESENTED,
    OperationalKnowledgeFindingPresentationClaim,
    OperationalKnowledgeFindingPresentationGrant,
    OperationalKnowledgeFindingPresentationInstruction,
    OperationalKnowledgeFindingPresentationPolicySnapshot,
    OperationalKnowledgeFindingPresentationReceipt,
    OperationalKnowledgeFindingPresentationRecord,
)
from atlas.modules.knowledge.domain.protected_content import (
    PROTECTED_CONTENT_PRESENTED,
    OperationalKnowledgeProtectedContentRecord,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OPERATIONAL_KNOWLEDGE_PROTECTED_INSPECTION_LEASED,
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeProtectedInspectionRecord,
)
from atlas.modules.knowledge.domain.review_finding import (
    OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_RECORDED,
    OperationalKnowledgeReviewFindingPolicySnapshot,
    OperationalKnowledgeReviewFindingRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OperationalKnowledgeReviewerAssignmentRecord,
)

FINDING_PRESENTATION_POLICY_SCHEMA = "atlas.operational-knowledge-finding-presentation-policy.v1"
FINDING_PRESENTATION_CLAIM_SCHEMA = "atlas.operational-knowledge-finding-presentation-claim.v1"
FINDING_PRESENTATION_RECORD_SCHEMA = "atlas.operational-knowledge-finding-presentation.v1"

FindingPresentationSourceBundle = tuple[
    OperationalKnowledgeReviewFindingRecord,
    OperationalKnowledgeProtectedContentRecord,
    OperationalKnowledgeProtectedInspectionRecord,
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentRecord,
    OperationalKnowledgeReviewRequestRecord,
    OperationalEvidenceKnowledgeDraftRecord,
    OperationalKnowledgeReviewFindingPolicySnapshot,
    OperationalKnowledgeFindingPresentationPolicySnapshot,
]


class OperationalKnowledgeFindingPresentationService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeFindingPresentationRepository,
        source: OperationalKnowledgeFindingPresentationSource,
        policy_source: OperationalKnowledgeFindingPresentationPolicySource,
        permission_authorizer: OperationalKnowledgeFindingPresentationPermissionAuthorizer,
        presenter: OperationalKnowledgeFindingPresenter,
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
        source_lease_id: str,
        source_content_presentation_id: str,
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
    ) -> OperationalKnowledgeFindingPresentationGrant:
        purpose = purpose.strip()
        if (
            not sensitive_findings_acknowledged
            or not finding_is_not_decision_acknowledged
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_request_invalid"
            )
        source = await self._authorize(
            actor=actor,
            source_lease_id=source_lease_id,
            source_content_presentation_id=source_content_presentation_id,
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
            _draft,
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
                "source_content_presentation_id": presentation.presentation_id,
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
        finding_presentation_id = f"operational-knowledge-finding-presentation.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_finding_presentation_requested",
            finding.finding_packet_id,
            (("track_code", finding.track_code),),
        )
        claim = OperationalKnowledgeFindingPresentationClaim(
            claim_id=f"operational-knowledge-finding-presentation-claim.{seed[:24]}",
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
                raise OperationalKnowledgeFindingPresentationUncertainError(
                    "operational_knowledge_finding_presentation_claim_uncertain"
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
            "operational_knowledge_finding_presentation_claimed",
            claim.claim_id,
            (("finding_presentation_id", finding_presentation_id),),
        )
        instruction = self._instruction(
            finding_presentation_id=finding_presentation_id,
            finding=finding,
            policy=policy,
            purpose=purpose,
        )
        try:
            receipt = await self._presenter.present(instruction)
            self._verify_receipt(instruction, receipt, policy, finding_policy)
        except OperationalKnowledgeFindingPresentationError:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_finding_presentation_failed",
                finding_presentation_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_finding_presentation_uncertain",
                finding_presentation_id,
                (("claim_persisted", "true"),),
            )
            raise OperationalKnowledgeFindingPresentationUncertainError(
                "operational_knowledge_finding_presentation_outcome_uncertain"
            ) from error
        record = self._record(claim, finding, policy, receipt)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_finding_presented",
            finding_presentation_id,
            (("finding_count", str(record.finding_count)), ("track_code", record.track_code)),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_finding(
                source_finding_packet_id=finding.finding_packet_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise OperationalKnowledgeFindingPresentationUncertainError(
                    "operational_knowledge_finding_presentation_persistence_uncertain"
                )
            record = replace(raced, reused=True)
        return OperationalKnowledgeFindingPresentationGrant(
            record=record, findings=receipt.findings
        )

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        source_lease_id: str,
        source_content_presentation_id: str,
        source_finding_packet_id: str,
        finding_presentation_id: str,
        browser_session_id: str,
        lease_secrets: Mapping[str, str],
        correlation_id: str,
    ) -> OperationalKnowledgeFindingPresentationGrant:
        record = await self._repository.get(finding_presentation_id=finding_presentation_id)
        if (
            record is None
            or record.source_lease_id != source_lease_id
            or record.source_content_presentation_id != source_content_presentation_id
            or record.source_finding_packet_id != source_finding_packet_id
        ):
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_not_found"
            )
        self._verify_record(record)
        source = await self._authorize(
            actor=actor,
            source_lease_id=source_lease_id,
            source_content_presentation_id=source_content_presentation_id,
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
            _draft,
            finding_policy,
            policy,
        ) = source
        instruction = self._instruction(
            finding_presentation_id=record.finding_presentation_id,
            finding=finding,
            policy=policy,
            purpose=record.purpose,
        )
        try:
            receipt = await self._presenter.present(instruction)
            self._verify_receipt(instruction, receipt, policy, finding_policy)
        except Exception as error:
            raise OperationalKnowledgeFindingPresentationUncertainError(
                "operational_knowledge_finding_presentation_replay_uncertain"
            ) from error
        if not self._receipt_matches_record(receipt, record):
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_replay_drift"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_finding_presentation_read",
            record.finding_presentation_id,
            (("track_code", record.track_code),),
            permission_id=KNOWLEDGE_FINDING_PRESENTATION_READ,
        )
        return OperationalKnowledgeFindingPresentationGrant(
            record=replace(record, reused=True), findings=receipt.findings
        )

    async def close(self) -> None:
        await self._repository.close()

    async def review_decision_source(
        self, *, finding_presentation_id: str
    ) -> tuple[
        OperationalKnowledgeFindingPresentationRecord,
        OperationalKnowledgeReviewFindingRecord,
        OperationalKnowledgeProtectedContentRecord,
        OperationalKnowledgeProtectedInspectionRecord,
        OperationalKnowledgeProtectedInspectionPolicySnapshot,
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
        OperationalKnowledgeReviewFindingPolicySnapshot,
        OperationalKnowledgeFindingPresentationPolicySnapshot,
    ]:
        record = await self._repository.get(finding_presentation_id=finding_presentation_id)
        if record is None:
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_not_found"
            )
        self._verify_record(record)
        try:
            source = await self._source.finding_presentation_source(
                finding_packet_id=record.source_finding_packet_id
            )
        except Exception as error:
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_lineage_invalid"
            ) from error
        finding, presentation, lease, _inspection_policy, assignment, review_request, draft, _ = (
            source
        )
        policy = await self._policy_source.get_by_id(policy_id=record.presentation_policy_id)
        if policy is None:
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_lineage_invalid"
            )
        self._verify_policy(policy)
        if (
            record.source_finding_packet_id != finding.finding_packet_id
            or record.source_finding_digest != finding.canonical_digest
            or record.source_lease_id != lease.lease_id
            or record.source_lease_digest != lease.canonical_digest
            or record.source_content_presentation_id != presentation.presentation_id
            or record.source_content_presentation_digest != presentation.canonical_digest
            or record.source_assignment_set_id != assignment.assignment_set_id
            or record.review_request_id != review_request.review_request_id
            or record.source_draft_id != draft.draft_id
            or record.source_draft_digest != draft.canonical_digest
            or record.track_code != finding.track_code
            or record.presentation_policy_digest != policy.canonical_digest
            or record.organization_id != finding.organization_id
            or record.environment_id != finding.environment_id
        ):
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_lineage_invalid"
            )
        return (record, *source, policy)

    async def _authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        source_lease_id: str,
        source_content_presentation_id: str,
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
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_source_not_found"
            ) from error
        finding, presentation, lease, inspection_policy, assignment, *_ = source
        policy = await self._policy_source.get_by_id(policy_id=presentation_policy_id)
        if policy is None:
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        later_authority = (
            finding.domain_review_completed,
            finding.security_review_completed,
            finding.correction_created,
            finding.knowledge_approved,
            finding.knowledge_published,
            finding.chunks_created,
            finding.embeddings_created,
            finding.retrieval_published,
            finding.model_context_available,
            finding.graph_updated,
            finding.scheduled,
            finding.workflow_continued,
            finding.execution_authorized,
            finding.deployment_approved,
            finding.infrastructure_mutation_performed,
        )
        if (
            finding.finding_packet_id != source_finding_packet_id
            or finding.canonical_digest != source_finding_digest
            or finding.source_lease_id != source_lease_id
            or finding.source_presentation_id != source_content_presentation_id
            or finding.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_RECORDED
            or not finding.finding_recorded
            or any(later_authority)
            or presentation.instance_state != PROTECTED_CONTENT_PRESENTED
            or lease.instance_state != OPERATIONAL_KNOWLEDGE_PROTECTED_INSPECTION_LEASED
            or now >= lease.expires_at
            or now >= presentation.expires_at
            or now >= finding.expires_at
            or policy.canonical_digest != presentation_policy_digest
            or policy.organization_id != finding.organization_id
            or policy.environment_id != finding.environment_id
            or policy.required_source_schema != finding.schema_version
            or policy.required_source_state != finding.instance_state
            or policy.subject_digest_salt_digest != inspection_policy.subject_digest_salt_digest
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_source_invalid"
            )
        self._require_scope(actor, finding.organization_id, finding.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        expected_assignee = (
            assignment.domain_reviewer_subject_digest
            if finding.track_code == "review-track.domain"
            else assignment.security_reviewer_subject_digest
        )
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
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_source_not_found"
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
        claim: OperationalKnowledgeFindingPresentationClaim,
        *,
        source: FindingPresentationSourceBundle,
        subject_digest: str,
        browser_digest: str,
        request_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgeFindingPresentationGrant:
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_idempotency_conflict"
            )
        self._verify_claim(claim)
        record = await self._repository.get(finding_presentation_id=claim.finding_presentation_id)
        if record is None:
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_already_claimed"
            )
        self._verify_record(record)
        (
            finding,
            _presentation,
            _lease,
            _inspection_policy,
            _assignment,
            _review_request,
            _draft,
            finding_policy,
            policy,
        ) = source
        instruction = self._instruction(
            finding_presentation_id=record.finding_presentation_id,
            finding=finding,
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
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_replay_drift"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_finding_presentation_read",
            record.finding_presentation_id,
            (("track_code", record.track_code),),
            permission_id=KNOWLEDGE_FINDING_PRESENTATION_READ,
        )
        return OperationalKnowledgeFindingPresentationGrant(
            record=replace(record, reused=True), findings=receipt.findings
        )

    @staticmethod
    def _instruction(
        *,
        finding_presentation_id: str,
        finding: OperationalKnowledgeReviewFindingRecord,
        policy: OperationalKnowledgeFindingPresentationPolicySnapshot,
        purpose: str,
    ) -> OperationalKnowledgeFindingPresentationInstruction:
        return OperationalKnowledgeFindingPresentationInstruction(
            finding_presentation_id=finding_presentation_id,
            organization_id=finding.organization_id,
            environment_id=finding.environment_id,
            source_finding_packet_id=finding.finding_packet_id,
            source_finding_digest=finding.canonical_digest,
            source_finding_artifact_id=finding.finding_artifact_id,
            source_lease_id=finding.source_lease_id,
            source_lease_digest=finding.source_lease_digest,
            source_content_presentation_id=finding.source_presentation_id,
            source_content_presentation_digest=finding.source_presentation_digest,
            source_assignment_set_id=finding.source_assignment_set_id,
            track_code=finding.track_code,
            lease_holder_subject_digest=finding.lease_holder_subject_digest,
            browser_session_binding_digest=finding.browser_session_binding_digest,
            source_draft_id=finding.source_draft_id,
            source_draft_digest=finding.source_draft_digest,
            knowledge_item_id=finding.knowledge_item_id,
            draft_version_id=finding.draft_version_id,
            classification=finding.classification,
            access_policy_id=finding.access_policy_id,
            retention_policy_id=finding.retention_policy_id,
            encryption_profile_id=finding.encryption_profile_id,
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
        instruction: OperationalKnowledgeFindingPresentationInstruction,
        receipt: OperationalKnowledgeFindingPresentationReceipt,
        policy: OperationalKnowledgeFindingPresentationPolicySnapshot,
        finding_policy: OperationalKnowledgeReviewFindingPolicySnapshot,
    ) -> None:
        now = self._clock()
        categories = (
            finding_policy.domain_category_codes
            if instruction.track_code == "review-track.domain"
            else finding_policy.security_category_codes
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
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_receipt_invalid"
            )

    def _record(
        self,
        claim: OperationalKnowledgeFindingPresentationClaim,
        finding: OperationalKnowledgeReviewFindingRecord,
        policy: OperationalKnowledgeFindingPresentationPolicySnapshot,
        receipt: OperationalKnowledgeFindingPresentationReceipt,
    ) -> OperationalKnowledgeFindingPresentationRecord:
        record = OperationalKnowledgeFindingPresentationRecord(
            finding_presentation_id=receipt.finding_presentation_id,
            schema_version=FINDING_PRESENTATION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_finding_packet_id=finding.finding_packet_id,
            source_finding_digest=finding.canonical_digest,
            source_lease_id=finding.source_lease_id,
            source_lease_digest=finding.source_lease_digest,
            source_content_presentation_id=finding.source_presentation_id,
            source_content_presentation_digest=finding.source_presentation_digest,
            source_assignment_set_id=finding.source_assignment_set_id,
            organization_id=finding.organization_id,
            environment_id=finding.environment_id,
            review_request_id=finding.review_request_id,
            source_draft_id=finding.source_draft_id,
            source_draft_digest=finding.source_draft_digest,
            knowledge_item_id=finding.knowledge_item_id,
            draft_version_id=finding.draft_version_id,
            title=finding.title,
            classification=finding.classification,
            access_policy_id=finding.access_policy_id,
            retention_policy_id=finding.retention_policy_id,
            encryption_profile_id=finding.encryption_profile_id,
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
            instance_state=OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_PRESENTED,
            purpose=claim.purpose,
            canonical_digest="0" * 64,
            domain_finding_recorded=finding.domain_finding_recorded,
            security_finding_recorded=finding.security_finding_recorded,
        )
        return replace(record, canonical_digest=self._digest(self._record_payload(record)))

    @staticmethod
    def _receipt_matches_record(
        receipt: OperationalKnowledgeFindingPresentationReceipt,
        record: OperationalKnowledgeFindingPresentationRecord,
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
    def _verify_policy(cls, policy: OperationalKnowledgeFindingPresentationPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._policy_payload(policy)):
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: OperationalKnowledgeFindingPresentationClaim) -> None:
        if claim.canonical_digest != cls._digest(cls._claim_payload(claim)):
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: OperationalKnowledgeFindingPresentationRecord) -> None:
        if record.canonical_digest != cls._digest(cls._record_payload(record)):
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_record_integrity_failed"
            )

    @classmethod
    def _policy_payload(
        cls, policy: OperationalKnowledgeFindingPresentationPolicySnapshot
    ) -> dict[str, object]:
        payload = asdict(policy)
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _claim_payload(
        cls, claim: OperationalKnowledgeFindingPresentationClaim
    ) -> dict[str, object]:
        payload = asdict(claim)
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(
        cls, record: OperationalKnowledgeFindingPresentationRecord
    ) -> dict[str, object]:
        payload = asdict(record)
        payload.pop("canonical_digest")
        payload.pop("reused")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: OperationalKnowledgeFindingPresentationReceipt) -> str:
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
                OperationalKnowledgeFindingPresentationService._normalize(payload),
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
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeFindingPresentationError(
                "operational_knowledge_finding_presentation_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = KNOWLEDGE_FINDING_PRESENTATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-finding-presentation",
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
                resource_type="resource.knowledge.operational-finding-presentations",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def build_development_operational_knowledge_finding_presentation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeFindingPresentationPolicySnapshot:
    digest = OperationalKnowledgeFindingPresentationService._digest
    policy = OperationalKnowledgeFindingPresentationPolicySnapshot(
        policy_id="operational-knowledge-finding-presentation-policy.development",
        schema_version=FINDING_PRESENTATION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.operational-knowledge-review-finding.v1",
        required_source_state=OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_RECORDED,
        required_presenter_id="operational-knowledge-finding-presenter.synthetic",
        required_presenter_attestor_id="subject.operational-knowledge-finding-presenter-attestor",
        required_receipt_schema="atlas.operational-knowledge-finding-presentation-receipt.v1",
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        maximum_authentication_age_minutes=15,
        maximum_findings=20,
        maximum_packet_bytes=32768,
        permitted_media_type="media-type.application-json",
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.operational-knowledge-finding-presentation-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(
            OperationalKnowledgeFindingPresentationService._policy_payload(policy)
        ),
    )
