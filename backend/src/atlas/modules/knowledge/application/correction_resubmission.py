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
    KNOWLEDGE_CORRECTION_RESUBMISSION_CREATE,
    KNOWLEDGE_CORRECTION_RESUBMISSION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.knowledge.application.correction_resubmission_ports import (
    OperationalKnowledgeCorrectionAdapter,
    OperationalKnowledgeCorrectionError,
    OperationalKnowledgeCorrectionPermissionAuthorizer,
    OperationalKnowledgeCorrectionPolicySource,
    OperationalKnowledgeCorrectionRepository,
    OperationalKnowledgeCorrectionSource,
    OperationalKnowledgeCorrectionUncertainError,
)
from atlas.modules.knowledge.application.draft_review_request import (
    OperationalKnowledgeReviewRequestService,
)
from atlas.modules.knowledge.application.evidence_draft import (
    OperationalEvidenceKnowledgeDraftService,
)
from atlas.modules.knowledge.domain.correction_resubmission import (
    OPERATIONAL_KNOWLEDGE_CORRECTION_RESUBMITTED,
    TRACKS,
    OperationalKnowledgeCorrectionClaim,
    OperationalKnowledgeCorrectionInstruction,
    OperationalKnowledgeCorrectionPolicySnapshot,
    OperationalKnowledgeCorrectionReceipt,
    OperationalKnowledgeCorrectionRecord,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    AWAITING_REVIEWER,
    OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    DRAFT_OPERATIONAL_KNOWLEDGE_CREATED,
    OperationalEvidenceKnowledgeDraftRecord,
)
from atlas.modules.knowledge.domain.review_decision import (
    OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED,
    OperationalKnowledgeTrackReviewDecisionRecord,
)

CORRECTION_POLICY_SCHEMA = "atlas.operational-knowledge-correction-policy.v1"
CORRECTION_CLAIM_SCHEMA = "atlas.operational-knowledge-correction-claim.v1"
CORRECTION_RECORD_SCHEMA = "atlas.operational-knowledge-correction-resubmission.v1"

CorrectionSourceBundle = tuple[
    tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
    OperationalKnowledgeReviewRequestRecord,
    OperationalEvidenceKnowledgeDraftRecord,
]


class OperationalKnowledgeCorrectionService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeCorrectionRepository,
        source: OperationalKnowledgeCorrectionSource,
        policy_source: OperationalKnowledgeCorrectionPolicySource,
        permission_authorizer: OperationalKnowledgeCorrectionPermissionAuthorizer,
        adapter: OperationalKnowledgeCorrectionAdapter,
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
        source_decision_ids: tuple[str, str],
        source_decision_digests: tuple[str, str],
        correction_submission_id: str,
        correction_submission_digest: str,
        correction_policy_id: str,
        correction_policy_digest: str,
        purpose: str,
        exact_change_requirements_addressed_acknowledged: bool,
        new_immutable_generation_acknowledged: bool,
        no_later_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeCorrectionRecord:
        self._require_human(actor)
        purpose = purpose.strip()
        if (
            not exact_change_requirements_addressed_acknowledged
            or not new_immutable_generation_acknowledged
            or not no_later_authority_acknowledged
            or len(set(source_decision_ids)) != 2
            or len(set(source_decision_digests)) != 2
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_request_invalid"
            )
        try:
            source = await self._source.correction_resubmission_source(
                review_request_id=source_review_request_id
            )
        except Exception as error:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=correction_policy_id)
        if policy is None:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_policy_not_found"
            )
        self._verify_policy(policy)
        self._require_policy_assurance(actor, policy)
        decisions, request, draft = source
        now = self._clock()
        ordered = self._verify_source(
            actor=actor,
            decisions=decisions,
            request=request,
            draft=draft,
            policy=policy,
            source_review_request_digest=source_review_request_digest,
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
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if subject_digest in {decision.decided_by_subject_digest for decision in ordered}:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_actor_separation_required"
            )
        decision_aggregate_digest = self._decision_aggregate_digest(ordered)
        purpose_digest = self._digest(purpose)
        request_binding_digest = self._digest(
            {
                "source_review_request_id": request.review_request_id,
                "source_review_request_digest": request.canonical_digest,
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
                request_binding_digest=request_binding_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        seed = self._digest(
            [request.review_request_id, request.canonical_digest, policy.canonical_digest]
        )
        correction_id = f"operational-knowledge-correction.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_correction_requested",
            request.review_request_id,
            (("knowledge_item_id", request.knowledge_item_id),),
        )
        claim = OperationalKnowledgeCorrectionClaim(
            claim_id=f"operational-knowledge-correction-claim.{seed[:24]}",
            schema_version=CORRECTION_CLAIM_SCHEMA,
            version=1,
            source_review_request_id=request.review_request_id,
            source_review_request_digest=request.canonical_digest,
            correction_id=correction_id,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            decision_aggregate_digest=decision_aggregate_digest,
            correction_submission_digest=correction_submission_digest,
            claimed_by_subject_digest=subject_digest,
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
                raise OperationalKnowledgeCorrectionUncertainError(
                    "operational_knowledge_correction_claim_uncertain"
                )
            return await self._reuse(
                prior,
                subject_digest=subject_digest,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                idempotency_digest=idempotency_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_correction_claimed",
            claim.claim_id,
            (("correction_id", correction_id),),
        )
        instruction = self._instruction(
            claim,
            ordered,
            request,
            draft,
            policy,
            correction_submission_id,
            correction_submission_digest,
        )
        try:
            receipt = await self._adapter.correct_and_resubmit(instruction)
            self._verify_receipt(instruction, receipt, policy)
        except OperationalKnowledgeCorrectionError:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_correction_failed",
                correction_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_correction_uncertain",
                correction_id,
                (("claim_persisted", "true"),),
            )
            raise OperationalKnowledgeCorrectionUncertainError(
                "operational_knowledge_correction_outcome_uncertain"
            ) from error
        record = self._record(
            claim,
            ordered,
            request,
            draft,
            policy,
            receipt,
            correction_submission_id,
            purpose,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_correction_resubmitted",
            record.correction_id,
            (("new_review_request_id", record.new_review_request_id),),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_request(
                source_review_request_id=request.review_request_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise OperationalKnowledgeCorrectionUncertainError(
                    "operational_knowledge_correction_persistence_uncertain"
                )
            return replace(raced, reused=True)
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        correction_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeCorrectionRecord:
        self._require_human(actor)
        record = await self._repository.get(correction_id=correction_id)
        if record is None:
            raise OperationalKnowledgeCorrectionError("operational_knowledge_correction_not_found")
        self._verify_record(record)
        policy = await self._policy_source.get_by_id(policy_id=record.correction_policy_id)
        if policy is None or policy.canonical_digest != record.correction_policy_digest:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_policy_not_found"
            )
        self._verify_policy(policy)
        self._require_policy_assurance(actor, policy)
        self._require_scope(actor, record.organization_id, record.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            subject_digest != record.corrected_by_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise OperationalKnowledgeCorrectionError("operational_knowledge_correction_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_correction_read",
            record.correction_id,
            (),
            permission_id=KNOWLEDGE_CORRECTION_RESUBMISSION_READ,
        )
        return replace(record, reused=True)

    async def close(self) -> None:
        await self._repository.close()

    async def reviewer_assignment_source(
        self, *, review_request_id: str, organization_id: str, environment_id: str
    ) -> tuple[OperationalKnowledgeReviewRequestRecord, frozenset[str]]:
        review_request, draft = await self.protected_content_lineage(
            review_request_id=review_request_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        return review_request, frozenset((draft.curated_by,))

    async def protected_content_lineage(
        self, *, review_request_id: str, organization_id: str, environment_id: str
    ) -> tuple[
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]:
        record = await self._repository.get_by_new_review_request(
            new_review_request_id=review_request_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if record is None:
            raise OperationalKnowledgeCorrectionError("operational_knowledge_correction_not_found")
        self._verify_record(record)
        (
            _decisions,
            source_request,
            source_draft,
        ) = await self._source.correction_resubmission_source(
            review_request_id=record.source_review_request_id
        )
        if (
            source_request.canonical_digest != record.source_review_request_digest
            or source_draft.canonical_digest != record.source_draft_digest
        ):
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_lineage_invalid"
            )
        draft = self._corrected_draft(record, source_draft)
        request = self._resubmitted_request(record, source_request, draft)
        return request, draft

    @classmethod
    def _corrected_draft(
        cls,
        correction: OperationalKnowledgeCorrectionRecord,
        source: OperationalEvidenceKnowledgeDraftRecord,
    ) -> OperationalEvidenceKnowledgeDraftRecord:
        record = replace(
            source,
            draft_id=correction.new_draft_id,
            claim_id=correction.claim_id,
            draft_version_id=correction.new_draft_version_id,
            draft_artifact_id=correction.new_draft_artifact_id,
            draft_schema_version=correction.new_draft_schema_version,
            draft_content_digest=correction.new_draft_content_digest,
            draft_metadata_digest=correction.new_draft_metadata_digest,
            provenance_digest=correction.new_provenance_digest,
            draft_item_count=correction.new_draft_item_count,
            draft_bytes=correction.new_draft_bytes,
            created_at=correction.created_at,
            purpose=correction.purpose,
            canonical_digest="0" * 64,
            reused=False,
        )
        return replace(
            record,
            canonical_digest=OperationalEvidenceKnowledgeDraftService._digest(
                OperationalEvidenceKnowledgeDraftService._record_payload(record)
            ),
        )

    @classmethod
    def _resubmitted_request(
        cls,
        correction: OperationalKnowledgeCorrectionRecord,
        source: OperationalKnowledgeReviewRequestRecord,
        draft: OperationalEvidenceKnowledgeDraftRecord,
    ) -> OperationalKnowledgeReviewRequestRecord:
        record = replace(
            source,
            review_request_id=correction.new_review_request_id,
            claim_id=correction.claim_id,
            source_draft_id=draft.draft_id,
            source_draft_digest=draft.canonical_digest,
            draft_version_id=draft.draft_version_id,
            draft_content_digest=draft.draft_content_digest,
            draft_metadata_digest=draft.draft_metadata_digest,
            provenance_digest=draft.provenance_digest,
            manifest_id=correction.new_manifest_id,
            manifest_artifact_id=correction.new_manifest_artifact_id,
            manifest_schema_version=correction.new_manifest_schema_version,
            manifest_digest=correction.new_manifest_digest,
            routing_digest=correction.new_routing_digest,
            governance_digest=correction.new_governance_digest,
            artifact_digest=correction.new_artifact_digest,
            domain_track_code=correction.domain_track_code,
            security_track_code=correction.security_track_code,
            domain_queue_id=correction.domain_queue_id,
            security_queue_id=correction.security_queue_id,
            assignment_strategy=correction.assignment_strategy,
            sla_class=correction.sla_class,
            domain_status=correction.domain_status,
            security_status=correction.security_status,
            manifest_bytes=correction.manifest_bytes,
            created_at=correction.created_at,
            requested_by=draft.curated_by,
            purpose=correction.purpose,
            canonical_digest="0" * 64,
            reviewer_assigned=False,
            content_inspection_opened=False,
            domain_review_completed=False,
            security_review_completed=False,
            correction_created=False,
            knowledge_approved=False,
            knowledge_published=False,
            chunks_created=False,
            embeddings_created=False,
            retrieval_published=False,
            model_context_available=False,
            graph_updated=False,
            scheduled=False,
            workflow_continued=False,
            execution_authorized=False,
            deployment_approved=False,
            infrastructure_mutation_performed=False,
            reused=False,
        )
        return replace(
            record,
            canonical_digest=OperationalKnowledgeReviewRequestService._digest(
                OperationalKnowledgeReviewRequestService._record_payload(record)
            ),
        )

    def _verify_source(
        self,
        *,
        actor: AuthenticatedSubject,
        decisions: tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        request: OperationalKnowledgeReviewRequestRecord,
        draft: OperationalEvidenceKnowledgeDraftRecord,
        policy: OperationalKnowledgeCorrectionPolicySnapshot,
        source_review_request_digest: str,
        source_decision_ids: tuple[str, str],
        source_decision_digests: tuple[str, str],
        correction_policy_digest: str,
        now: datetime,
    ) -> tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...]:
        ordered = tuple(sorted(decisions, key=lambda item: item.track_code))
        decision_later_authority = any(
            any(
                (
                    item.correction_created,
                    item.knowledge_approved,
                    item.knowledge_published,
                    item.retrieval_published,
                    item.model_context_available,
                    item.workflow_continued,
                    item.execution_authorized,
                    item.deployment_approved,
                    item.infrastructure_mutation_performed,
                )
            )
            for item in ordered
        )
        request_later_authority = any(
            (
                request.correction_created,
                request.knowledge_approved,
                request.knowledge_published,
                request.retrieval_published,
                request.model_context_available,
                request.workflow_continued,
                request.execution_authorized,
                request.deployment_approved,
                request.infrastructure_mutation_performed,
            )
        )
        supplied = set(zip(source_decision_ids, source_decision_digests, strict=True))
        actual = {(item.decision_id, item.canonical_digest) for item in ordered}
        if (
            len(ordered) != 2
            or {item.track_code for item in ordered} != TRACKS
            or supplied != actual
            or request.review_request_id == ""
            or request.canonical_digest != source_review_request_digest
            or request.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED
            or draft.instance_state != DRAFT_OPERATIONAL_KNOWLEDGE_CREATED
            or request.source_draft_id != draft.draft_id
            or request.source_draft_digest != draft.canonical_digest
            or request.knowledge_item_id != draft.knowledge_item_id
            or request.draft_version_id != draft.draft_version_id
            or any(item.review_request_id != request.review_request_id for item in ordered)
            or any(item.source_draft_id != draft.draft_id for item in ordered)
            or any(item.source_draft_digest != draft.canonical_digest for item in ordered)
            or any(item.knowledge_item_id != draft.knowledge_item_id for item in ordered)
            or any(
                item.instance_state != OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED
                for item in ordered
            )
            or not all(
                item.domain_review_completed or item.security_review_completed for item in ordered
            )
            or not any(item.correction_required for item in ordered)
            or decision_later_authority
            or request_later_authority
            or policy.canonical_digest != correction_policy_digest
            or policy.organization_id != request.organization_id
            or policy.environment_id != request.environment_id
            or policy.required_decision_schema != ordered[0].schema_version
            or any(item.schema_version != policy.required_decision_schema for item in ordered)
            or any(item.instance_state != policy.required_decision_state for item in ordered)
            or policy.required_request_schema != request.schema_version
            or policy.required_request_state != request.instance_state
            or policy.required_draft_schema != draft.schema_version
            or policy.required_draft_state != draft.instance_state
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_source_invalid"
            )
        self._require_scope(actor, request.organization_id, request.environment_id)
        if actor.subject_id != draft.curated_by:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_source_not_found"
            )
        if actor.subject_id in {policy.signed_by, policy.required_adapter_attestor_id}:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_actor_separation_required"
            )
        return ordered

    async def _reuse(
        self,
        claim: OperationalKnowledgeCorrectionClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgeCorrectionRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_idempotency_conflict"
            )
        record = await self._repository.get(correction_id=claim.correction_id)
        if record is None:
            raise OperationalKnowledgeCorrectionUncertainError(
                "operational_knowledge_correction_claimed_outcome_uncertain"
            )
        self._verify_record(record)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_correction_read",
            record.correction_id,
            (("reused", "true"),),
            permission_id=KNOWLEDGE_CORRECTION_RESUBMISSION_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _instruction(
        cls,
        claim: OperationalKnowledgeCorrectionClaim,
        decisions: tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        request: OperationalKnowledgeReviewRequestRecord,
        draft: OperationalEvidenceKnowledgeDraftRecord,
        policy: OperationalKnowledgeCorrectionPolicySnapshot,
        correction_submission_id: str,
        correction_submission_digest: str,
    ) -> OperationalKnowledgeCorrectionInstruction:
        seed = claim.correction_id.rsplit(".", 1)[-1]
        return OperationalKnowledgeCorrectionInstruction(
            correction_id=claim.correction_id,
            source_review_request_id=request.review_request_id,
            source_review_request_digest=request.canonical_digest,
            source_draft_id=draft.draft_id,
            source_draft_digest=draft.canonical_digest,
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
            knowledge_item_id=request.knowledge_item_id,
            prior_draft_version_id=request.draft_version_id,
            title=request.title,
            draft_domain=request.draft_domain,
            content_type=request.content_type,
            language=request.language,
            classification=request.classification,
            access_policy_id=request.access_policy_id,
            access_policy_digest=request.access_policy_digest,
            retention_policy_id=request.retention_policy_id,
            retention_policy_digest=request.retention_policy_digest,
            encryption_profile_id=request.encryption_profile_id,
            encryption_profile_digest=request.encryption_profile_digest,
            new_draft_id=f"operational-evidence-knowledge-draft.correction-{seed}",
            new_draft_version_id=f"knowledge-draft-version.correction-{seed}",
            new_review_request_id=f"operational-knowledge-review-request.correction-{seed}",
            review_generation=2,
            domain_track_code=policy.domain_track_code,
            security_track_code=policy.security_track_code,
            domain_queue_id=policy.domain_queue_id,
            security_queue_id=policy.security_queue_id,
            assignment_strategy=policy.assignment_strategy,
            sla_class=policy.sla_class,
            maximum_draft_items=policy.maximum_draft_items,
            maximum_draft_bytes=policy.maximum_draft_bytes,
            maximum_manifest_bytes=policy.maximum_manifest_bytes,
            corrected_by_subject_digest=claim.claimed_by_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            correction_policy_digest=policy.canonical_digest,
        )

    @classmethod
    def _verify_receipt(
        cls,
        instruction: OperationalKnowledgeCorrectionInstruction,
        receipt: OperationalKnowledgeCorrectionReceipt,
        policy: OperationalKnowledgeCorrectionPolicySnapshot,
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
            or receipt.new_draft_id != instruction.new_draft_id
            or receipt.new_draft_version_id != instruction.new_draft_version_id
            or receipt.new_review_request_id != instruction.new_review_request_id
            or receipt.domain_status != AWAITING_REVIEWER
            or receipt.security_status != AWAITING_REVIEWER
            or receipt.new_draft_item_count > policy.maximum_draft_items
            or receipt.new_draft_bytes > policy.maximum_draft_bytes
            or receipt.manifest_bytes > policy.maximum_manifest_bytes
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or cls._receipt_digest(receipt) != receipt.canonical_digest
        ):
            raise OperationalKnowledgeCorrectionUncertainError(
                "operational_knowledge_correction_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: OperationalKnowledgeCorrectionClaim,
        decisions: tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        request: OperationalKnowledgeReviewRequestRecord,
        draft: OperationalEvidenceKnowledgeDraftRecord,
        policy: OperationalKnowledgeCorrectionPolicySnapshot,
        receipt: OperationalKnowledgeCorrectionReceipt,
        correction_submission_id: str,
        purpose: str,
    ) -> OperationalKnowledgeCorrectionRecord:
        record = OperationalKnowledgeCorrectionRecord(
            correction_id=claim.correction_id,
            schema_version=CORRECTION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_review_request_id=request.review_request_id,
            source_review_request_digest=request.canonical_digest,
            source_draft_id=draft.draft_id,
            source_draft_digest=draft.canonical_digest,
            source_decision_ids=cast(
                tuple[str, str], tuple(item.decision_id for item in decisions)
            ),
            source_decision_digests=cast(
                tuple[str, str], tuple(item.canonical_digest for item in decisions)
            ),
            decision_aggregate_digest=claim.decision_aggregate_digest,
            organization_id=request.organization_id,
            environment_id=request.environment_id,
            knowledge_item_id=request.knowledge_item_id,
            prior_draft_version_id=request.draft_version_id,
            title=request.title,
            classification=request.classification,
            access_policy_id=request.access_policy_id,
            access_policy_digest=request.access_policy_digest,
            retention_policy_id=request.retention_policy_id,
            retention_policy_digest=request.retention_policy_digest,
            encryption_profile_id=request.encryption_profile_id,
            encryption_profile_digest=request.encryption_profile_digest,
            correction_submission_id=correction_submission_id,
            correction_submission_digest=claim.correction_submission_digest,
            corrected_by_subject_digest=claim.claimed_by_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            correction_policy_id=policy.policy_id,
            correction_policy_digest=policy.canonical_digest,
            correction_policy_version=policy.policy_version,
            adapter_id=receipt.adapter_id,
            attestation_digest=receipt.canonical_digest,
            new_draft_id=receipt.new_draft_id,
            new_draft_version_id=receipt.new_draft_version_id,
            new_draft_artifact_id=receipt.new_draft_artifact_id,
            new_draft_schema_version=receipt.new_draft_schema_version,
            new_draft_content_digest=receipt.new_draft_content_digest,
            new_draft_metadata_digest=receipt.new_draft_metadata_digest,
            new_provenance_digest=receipt.new_provenance_digest,
            new_draft_item_count=receipt.new_draft_item_count,
            new_draft_bytes=receipt.new_draft_bytes,
            new_review_request_id=receipt.new_review_request_id,
            new_manifest_id=receipt.new_manifest_id,
            new_manifest_artifact_id=receipt.new_manifest_artifact_id,
            new_manifest_schema_version=receipt.new_manifest_schema_version,
            new_manifest_digest=receipt.new_manifest_digest,
            new_routing_digest=receipt.new_routing_digest,
            new_governance_digest=receipt.new_governance_digest,
            new_artifact_digest=receipt.new_artifact_digest,
            domain_track_code=policy.domain_track_code,
            security_track_code=policy.security_track_code,
            domain_queue_id=policy.domain_queue_id,
            security_queue_id=policy.security_queue_id,
            assignment_strategy=policy.assignment_strategy,
            sla_class=policy.sla_class,
            domain_status=receipt.domain_status,
            security_status=receipt.security_status,
            review_generation=2,
            manifest_bytes=receipt.manifest_bytes,
            created_at=receipt.created_at,
            instance_state=OPERATIONAL_KNOWLEDGE_CORRECTION_RESUBMITTED,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._record_payload(record)))

    @classmethod
    def _decision_aggregate_digest(
        cls, decisions: tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...]
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
    def _verify_policy(cls, policy: OperationalKnowledgeCorrectionPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: OperationalKnowledgeCorrectionClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: OperationalKnowledgeCorrectionRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_record_integrity_failed"
            )

    @classmethod
    def _claim_payload(cls, claim: OperationalKnowledgeCorrectionClaim) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: OperationalKnowledgeCorrectionRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: OperationalKnowledgeCorrectionReceipt) -> str:
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
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_human_required"
            )

    @staticmethod
    def _require_policy_assurance(
        actor: AuthenticatedSubject, policy: OperationalKnowledgeCorrectionPolicySnapshot
    ) -> None:
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_assurance_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = KNOWLEDGE_CORRECTION_RESUBMISSION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-correction-resubmission",
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
                resource_type="resource.knowledge.operational-corrections",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def build_development_operational_knowledge_correction_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> OperationalKnowledgeCorrectionPolicySnapshot:
    digest = OperationalKnowledgeCorrectionService._digest
    policy = OperationalKnowledgeCorrectionPolicySnapshot(
        policy_id="operational-knowledge-correction-policy.development",
        schema_version=CORRECTION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.operational-knowledge-correction-development-v1",
        required_decision_schema="atlas.operational-knowledge-track-review-decision.v1",
        required_decision_state=OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED,
        required_request_schema="atlas.operational-knowledge-review-request.v1",
        required_request_state=OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
        required_draft_schema="atlas.operational-evidence-knowledge-draft.v1",
        required_draft_state=DRAFT_OPERATIONAL_KNOWLEDGE_CREATED,
        required_adapter_id="operational-knowledge-correction-adapter.synthetic",
        required_adapter_attestor_id="subject.operational-knowledge-correction-attestor",
        required_receipt_schema="atlas.operational-knowledge-correction-receipt.v1",
        domain_track_code="review-track.domain",
        security_track_code="review-track.security",
        domain_queue_id="review-queue.operational-domain",
        security_queue_id="review-queue.operational-security",
        assignment_strategy="assignment-strategy.independent-tracks",
        sla_class="sla-class.operational-knowledge-standard",
        maximum_authentication_age_minutes=15,
        maximum_draft_items=1000,
        maximum_draft_bytes=1_048_576,
        maximum_manifest_bytes=262_144,
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        browser_binding_key_digest=digest(
            ["operational-knowledge-correction", organization_id, "browser-binding"]
        ),
        required_assurance_level=required_assurance_level,
        signed_by="subject.operational-knowledge-correction-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return replace(
        policy, canonical_digest=digest(OperationalKnowledgeCorrectionService._normalize(payload))
    )
