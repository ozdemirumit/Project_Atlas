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
    KNOWLEDGE_DRAFT_REVIEW_REQUEST_CREATE,
    KNOWLEDGE_DRAFT_REVIEW_REQUEST_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.knowledge.application.draft_review_request_ports import (
    OperationalKnowledgeReviewRequestAdapter,
    OperationalKnowledgeReviewRequestError,
    OperationalKnowledgeReviewRequestPermissionAuthorizer,
    OperationalKnowledgeReviewRequestPolicySource,
    OperationalKnowledgeReviewRequestRepository,
    OperationalKnowledgeReviewRequestSource,
    OperationalKnowledgeReviewRequestUncertainError,
)
from atlas.modules.knowledge.application.reviewer_assignment_ports import (
    OperationalKnowledgeReviewerAssignmentSource,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    AWAITING_REVIEWER,
    OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
    OperationalKnowledgeReviewRequestClaim,
    OperationalKnowledgeReviewRequestInstruction,
    OperationalKnowledgeReviewRequestPolicySnapshot,
    OperationalKnowledgeReviewRequestReceipt,
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    DRAFT_OPERATIONAL_KNOWLEDGE_CREATED,
    OperationalEvidenceKnowledgeDraftRecord,
)

REVIEW_REQUEST_POLICY_SCHEMA = "atlas.operational-knowledge-review-request-policy.v1"
REVIEW_REQUEST_CLAIM_SCHEMA = "atlas.operational-knowledge-review-request-claim.v1"
REVIEW_REQUEST_RECORD_SCHEMA = "atlas.operational-knowledge-review-request.v1"


class OperationalKnowledgeReviewRequestService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeReviewRequestRepository,
        source: OperationalKnowledgeReviewRequestSource,
        policy_source: OperationalKnowledgeReviewRequestPolicySource,
        permission_authorizer: OperationalKnowledgeReviewRequestPermissionAuthorizer,
        adapter: OperationalKnowledgeReviewRequestAdapter,
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
        self._resubmission_source: OperationalKnowledgeReviewerAssignmentSource | None = None

    def set_resubmission_source(self, source: OperationalKnowledgeReviewerAssignmentSource) -> None:
        self._resubmission_source = source

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_draft_id: str,
        source_draft_digest: str,
        orchestration_policy_id: str,
        orchestration_policy_digest: str,
        purpose: str,
        review_request_only_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeReviewRequestRecord:
        self._require_human(actor)
        if not review_request_only_acknowledged:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_invalid"
            )
        request_binding_digest = self._digest(
            {
                "source_draft_id": source_draft_id,
                "source_draft_digest": source_draft_digest,
                "orchestration_policy_id": orchestration_policy_id,
                "orchestration_policy_digest": orchestration_policy_digest,
                "purpose": purpose,
            }
        )
        idempotency_digest = self._digest([actor.subject_id, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by=actor.subject_id, idempotency_digest=idempotency_digest
        )
        if existing is not None:
            return await self._reuse(existing, actor, request_binding_digest, idempotency_digest)
        try:
            source = await self._source.review_request_source(
                draft_id=source_draft_id,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
        except Exception as error:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=orchestration_policy_id)
        if policy is None:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_policy_not_found"
            )
        self._verify_snapshot(policy)
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_assurance_required"
            )
        now = self._clock()
        self._verify_source(
            source=source,
            policy=policy,
            source_digest=source_draft_digest,
            policy_digest=orchestration_policy_digest,
            now=now,
        )
        self._require_scope(actor, source.organization_id, source.environment_id)
        if actor.subject_id in {policy.signed_by, policy.required_adapter_attestor_id}:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            correlation_id=correlation_id,
        )
        seed = self._digest([source.draft_id, source.canonical_digest, policy.canonical_digest])
        review_request_id = f"operational-knowledge-review-request.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_review_requested",
            source.draft_id,
            (("knowledge_item_id", source.knowledge_item_id),),
        )
        claim = OperationalKnowledgeReviewRequestClaim(
            claim_id=f"operational-knowledge-review-request-claim.{seed[:24]}",
            schema_version=REVIEW_REQUEST_CLAIM_SCHEMA,
            version=1,
            source_draft_id=source.draft_id,
            source_draft_digest=source.canonical_digest,
            review_request_id=review_request_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            claimed_by=actor.subject_id,
            purpose=purpose,
            claimed_at=now,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        if not await self._repository.claim(claim):
            prior = await self._repository.get_claim_by_source(source_draft_id=source.draft_id)
            if prior is None:
                raise OperationalKnowledgeReviewRequestUncertainError(
                    "operational_knowledge_review_request_claim_uncertain"
                )
            return await self._reuse(prior, actor, request_binding_digest, idempotency_digest)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_review_source_claimed",
            claim.claim_id,
            (("review_request_id", review_request_id),),
        )
        instruction = self._instruction(review_request_id, source, policy)
        try:
            receipt = await self._adapter.create_review_request(instruction)
        except OperationalKnowledgeReviewRequestError as error:
            await self._audit(
                actor,
                correlation_id,
                (
                    "operational_knowledge_review_request_uncertain"
                    if isinstance(error, OperationalKnowledgeReviewRequestUncertainError)
                    else "operational_knowledge_review_request_failed"
                ),
                review_request_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_review_request_uncertain",
                review_request_id,
                (("claim_persisted", "true"),),
            )
            raise OperationalKnowledgeReviewRequestUncertainError(
                "operational_knowledge_review_request_outcome_uncertain"
            ) from error
        try:
            self._verify_receipt(instruction, receipt, policy)
        except OperationalKnowledgeReviewRequestUncertainError:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_review_request_uncertain",
                review_request_id,
                (("claim_persisted", "true"),),
            )
            raise
        record = self._record(claim, source, policy, receipt, actor, purpose)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_review_request_created",
            record.review_request_id,
            (("state", record.instance_state),),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source(source_draft_id=source.draft_id)
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise OperationalKnowledgeReviewRequestUncertainError(
                    "operational_knowledge_review_request_persistence_uncertain"
                )
            return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, review_request_id: str, correlation_id: str
    ) -> OperationalKnowledgeReviewRequestRecord:
        self._require_human(actor)
        record = await self._repository.get(review_request_id=review_request_id)
        if record is None:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_record_not_found"
            )
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_review_request_read",
            record.review_request_id,
            (),
            permission_id=KNOWLEDGE_DRAFT_REVIEW_REQUEST_READ,
        )
        return record

    async def close(self) -> None:
        await self._repository.close()

    async def reviewer_assignment_source(
        self, *, review_request_id: str
    ) -> tuple[OperationalKnowledgeReviewRequestRecord, frozenset[str]]:
        record = await self._repository.get(review_request_id=review_request_id)
        if record is None:
            if self._resubmission_source is not None:
                return await self._resubmission_source.reviewer_assignment_source(
                    review_request_id=review_request_id
                )
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_record_not_found"
            )
        self._verify_record(record)
        draft = await self._source.review_request_source(
            draft_id=record.source_draft_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        return record, frozenset((record.requested_by, draft.curated_by))

    async def protected_content_lineage(
        self, *, review_request_id: str
    ) -> tuple[
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]:
        record = await self._repository.get(review_request_id=review_request_id)
        if record is None:
            if self._resubmission_source is not None:
                return await self._resubmission_source.protected_content_lineage(
                    review_request_id=review_request_id
                )
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_record_not_found"
            )
        self._verify_record(record)
        draft = await self._source.review_request_source(
            draft_id=record.source_draft_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        if (
            draft.draft_id != record.source_draft_id
            or draft.canonical_digest != record.source_draft_digest
            or draft.draft_content_digest != record.draft_content_digest
            or draft.knowledge_item_id != record.knowledge_item_id
            or draft.draft_version_id != record.draft_version_id
        ):
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_lineage_invalid"
            )
        return record, draft

    async def _reuse(
        self,
        claim: OperationalKnowledgeReviewRequestClaim,
        actor: AuthenticatedSubject,
        request_binding_digest: str,
        idempotency_digest: str,
    ) -> OperationalKnowledgeReviewRequestRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by != actor.subject_id
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_idempotency_conflict"
            )
        self._require_scope(actor, claim.organization_id, claim.environment_id)
        record = await self._repository.get(review_request_id=claim.review_request_id)
        if record is None:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_already_claimed"
            )
        self._verify_record(record)
        return replace(record, reused=True)

    @staticmethod
    def _verify_source(
        *,
        source: OperationalEvidenceKnowledgeDraftRecord,
        policy: OperationalKnowledgeReviewRequestPolicySnapshot,
        source_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        later_authority = (
            source.domain_review_completed,
            source.security_review_completed,
            source.knowledge_approved,
            source.knowledge_published,
            source.chunks_created,
            source.embeddings_created,
            source.retrieval_published,
            source.model_context_available,
            source.graph_updated,
            source.scheduled,
            source.workflow_continued,
            source.execution_authorized,
            source.deployment_approved,
            source.infrastructure_mutation_performed,
        )
        if (
            source.canonical_digest != source_digest
            or policy.canonical_digest != policy_digest
            or policy.organization_id != source.organization_id
            or policy.environment_id != source.environment_id
            or policy.required_source_schema != source.schema_version
            or policy.required_source_state != source.instance_state
            or source.instance_state != DRAFT_OPERATIONAL_KNOWLEDGE_CREATED
            or source.knowledge_lifecycle != "draft"
            or not all(
                (
                    source.knowledge_item_created,
                    source.immutable_draft_confirmed,
                    source.encrypted_at_rest,
                    source.transient_buffers_erased,
                    source.artifact_channel_closed,
                )
            )
            or any(later_authority)
            or now - source.created_at > timedelta(minutes=policy.maximum_source_age_minutes)
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_source_invalid"
            )

    @staticmethod
    def _instruction(
        review_request_id: str,
        source: OperationalEvidenceKnowledgeDraftRecord,
        policy: OperationalKnowledgeReviewRequestPolicySnapshot,
    ) -> OperationalKnowledgeReviewRequestInstruction:
        return OperationalKnowledgeReviewRequestInstruction(
            review_request_id=review_request_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            draft_id=source.draft_id,
            draft_digest=source.canonical_digest,
            knowledge_item_id=source.knowledge_item_id,
            draft_version_id=source.draft_version_id,
            draft_artifact_id=source.draft_artifact_id,
            draft_schema_version=source.draft_schema_version,
            draft_content_digest=source.draft_content_digest,
            draft_metadata_digest=source.draft_metadata_digest,
            provenance_digest=source.provenance_digest,
            classification=source.classification,
            access_policy_id=source.access_policy_id,
            access_policy_digest=source.access_policy_digest,
            retention_policy_id=source.retention_policy_id,
            retention_policy_digest=source.retention_policy_digest,
            encryption_profile_id=source.encryption_profile_id,
            encryption_profile_digest=source.encryption_profile_digest,
            draft_item_count=source.draft_item_count,
            draft_bytes=source.draft_bytes,
            draft_created_at=source.created_at,
            domain_track_code=policy.domain_track_code,
            security_track_code=policy.security_track_code,
            domain_queue_id=policy.domain_queue_id,
            security_queue_id=policy.security_queue_id,
            assignment_strategy=policy.assignment_strategy,
            sla_class=policy.sla_class,
            maximum_manifest_bytes=policy.maximum_manifest_bytes,
            orchestration_policy_digest=policy.canonical_digest,
        )

    @classmethod
    def _verify_receipt(
        cls,
        instruction: OperationalKnowledgeReviewRequestInstruction,
        receipt: OperationalKnowledgeReviewRequestReceipt,
        policy: OperationalKnowledgeReviewRequestPolicySnapshot,
    ) -> None:
        if (
            cls._receipt_digest(receipt) != receipt.canonical_digest
            or receipt.review_request_id != instruction.review_request_id
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.adapter_id != policy.required_adapter_id
            or receipt.attested_by != policy.required_adapter_attestor_id
            or receipt.draft_id != instruction.draft_id
            or receipt.draft_digest != instruction.draft_digest
            or receipt.draft_content_digest != instruction.draft_content_digest
            or receipt.domain_track_code != policy.domain_track_code
            or receipt.security_track_code != policy.security_track_code
            or receipt.domain_queue_id != policy.domain_queue_id
            or receipt.security_queue_id != policy.security_queue_id
            or receipt.assignment_strategy != policy.assignment_strategy
            or receipt.sla_class != policy.sla_class
            or receipt.domain_status != AWAITING_REVIEWER
            or receipt.security_status != AWAITING_REVIEWER
            or receipt.manifest_bytes > policy.maximum_manifest_bytes
        ):
            raise OperationalKnowledgeReviewRequestUncertainError(
                "operational_knowledge_review_request_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: OperationalKnowledgeReviewRequestClaim,
        source: OperationalEvidenceKnowledgeDraftRecord,
        policy: OperationalKnowledgeReviewRequestPolicySnapshot,
        receipt: OperationalKnowledgeReviewRequestReceipt,
        actor: AuthenticatedSubject,
        purpose: str,
    ) -> OperationalKnowledgeReviewRequestRecord:
        record = OperationalKnowledgeReviewRequestRecord(
            review_request_id=receipt.review_request_id,
            schema_version=REVIEW_REQUEST_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_draft_id=source.draft_id,
            source_draft_digest=source.canonical_digest,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            knowledge_item_id=source.knowledge_item_id,
            draft_version_id=source.draft_version_id,
            source_ingestion_id=source.source_ingestion_id,
            source_invocation_id=source.source_invocation_id,
            connector_id=source.connector_id,
            instance_id=source.instance_id,
            capability_id=source.capability_id,
            title=source.title,
            draft_domain=source.draft_domain,
            content_type=source.content_type,
            language=source.language,
            knowledge_lifecycle="review_requested",
            classification=source.classification,
            access_policy_id=source.access_policy_id,
            access_policy_digest=source.access_policy_digest,
            retention_policy_id=source.retention_policy_id,
            retention_policy_digest=source.retention_policy_digest,
            encryption_profile_id=source.encryption_profile_id,
            encryption_profile_digest=source.encryption_profile_digest,
            draft_content_digest=source.draft_content_digest,
            draft_metadata_digest=source.draft_metadata_digest,
            provenance_digest=source.provenance_digest,
            manifest_id=receipt.manifest_id,
            manifest_artifact_id=receipt.manifest_artifact_id,
            manifest_schema_version=receipt.manifest_schema_version,
            manifest_digest=receipt.manifest_digest,
            routing_digest=receipt.routing_digest,
            governance_digest=receipt.governance_digest,
            artifact_digest=receipt.artifact_digest,
            orchestration_policy_id=policy.policy_id,
            orchestration_policy_digest=policy.canonical_digest,
            orchestration_policy_version=policy.policy_version,
            orchestration_adapter_id=receipt.adapter_id,
            domain_track_code=receipt.domain_track_code,
            security_track_code=receipt.security_track_code,
            domain_queue_id=receipt.domain_queue_id,
            security_queue_id=receipt.security_queue_id,
            assignment_strategy=receipt.assignment_strategy,
            sla_class=receipt.sla_class,
            domain_status=receipt.domain_status,
            security_status=receipt.security_status,
            manifest_bytes=receipt.manifest_bytes,
            created_at=receipt.created_at,
            instance_state=OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
            requested_by=actor.subject_id,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._record_payload(record)))

    @classmethod
    def _verify_snapshot(cls, policy: OperationalKnowledgeReviewRequestPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: OperationalKnowledgeReviewRequestClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: OperationalKnowledgeReviewRequestRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_record_integrity_failed"
            )

    @classmethod
    def _claim_payload(cls, claim: OperationalKnowledgeReviewRequestClaim) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: OperationalKnowledgeReviewRequestRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: OperationalKnowledgeReviewRequestReceipt) -> str:
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
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_human_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_record_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = KNOWLEDGE_DRAFT_REVIEW_REQUEST_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-review-request",
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
                resource_type="resource.knowledge.operational-review-requests",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def _signed_policy(policy: OperationalKnowledgeReviewRequestPolicySnapshot) -> str:
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return OperationalKnowledgeReviewRequestService._digest(
        OperationalKnowledgeReviewRequestService._normalize(payload)
    )


def build_development_operational_knowledge_review_request_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeReviewRequestPolicySnapshot:
    policy = OperationalKnowledgeReviewRequestPolicySnapshot(
        policy_id="operational-knowledge-review-request-policy.development",
        schema_version=REVIEW_REQUEST_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.operational-evidence-knowledge-draft.v1",
        required_source_state=DRAFT_OPERATIONAL_KNOWLEDGE_CREATED,
        required_adapter_id="operational-knowledge-review-request-adapter.synthetic",
        required_adapter_attestor_id=(
            "subject.operational-knowledge-review-request-adapter-attestor"
        ),
        required_receipt_schema="atlas.operational-knowledge-review-request-receipt.v1",
        domain_track_code="review-track.domain",
        security_track_code="review-track.security",
        domain_queue_id="review-queue.operational-domain",
        security_queue_id="review-queue.knowledge-security",
        assignment_strategy="assignment-strategy.policy-controlled",
        sla_class="sla.knowledge-review-standard",
        maximum_source_age_minutes=120,
        maximum_manifest_bytes=65_536,
        require_classification_inheritance=True,
        require_access_policy_inheritance=True,
        require_retention_policy_inheritance=True,
        require_encryption_profile_inheritance=True,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        signed_by="subject.operational-knowledge-review-request-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(policy, canonical_digest=_signed_policy(policy))
