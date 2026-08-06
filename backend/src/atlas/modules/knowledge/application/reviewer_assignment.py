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
    KNOWLEDGE_REVIEWER_ASSIGNMENT_CREATE,
    KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.application.reviewer_assignment_ports import (
    OperationalKnowledgeReviewerAssignmentAdapter,
    OperationalKnowledgeReviewerAssignmentError,
    OperationalKnowledgeReviewerAssignmentPermissionAuthorizer,
    OperationalKnowledgeReviewerAssignmentPolicySource,
    OperationalKnowledgeReviewerAssignmentRepository,
    OperationalKnowledgeReviewerAssignmentSource,
    OperationalKnowledgeReviewerAssignmentUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    ASSIGNED,
    OPERATIONAL_KNOWLEDGE_REVIEWERS_ASSIGNED,
    OperationalKnowledgeReviewerAssignmentClaim,
    OperationalKnowledgeReviewerAssignmentInstruction,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentReceipt,
    OperationalKnowledgeReviewerAssignmentRecord,
)

ASSIGNMENT_POLICY_SCHEMA = "atlas.operational-knowledge-reviewer-assignment-policy.v1"
ASSIGNMENT_CLAIM_SCHEMA = "atlas.operational-knowledge-reviewer-assignment-claim.v1"
ASSIGNMENT_RECORD_SCHEMA = "atlas.operational-knowledge-reviewer-assignment.v1"


class OperationalKnowledgeReviewerAssignmentService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeReviewerAssignmentRepository,
        source: OperationalKnowledgeReviewerAssignmentSource,
        policy_source: OperationalKnowledgeReviewerAssignmentPolicySource,
        permission_authorizer: OperationalKnowledgeReviewerAssignmentPermissionAuthorizer,
        adapter: OperationalKnowledgeReviewerAssignmentAdapter,
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
        assignment_policy_id: str,
        assignment_policy_digest: str,
        purpose: str,
        assignment_only_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        self._require_enterprise_human(actor)
        if not assignment_only_acknowledged:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_request_invalid"
            )
        request_binding_digest = self._digest(
            {
                "source_review_request_id": source_review_request_id,
                "source_review_request_digest": source_review_request_digest,
                "assignment_policy_id": assignment_policy_id,
                "assignment_policy_digest": assignment_policy_digest,
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
            source, source_actors = await self._source.reviewer_assignment_source(
                review_request_id=source_review_request_id
            )
        except Exception as error:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=assignment_policy_id)
        if policy is None:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_policy_not_found"
            )
        self._verify_snapshot(policy)
        now = self._clock()
        self._verify_source(
            source=source,
            policy=policy,
            source_digest=source_review_request_digest,
            policy_digest=assignment_policy_digest,
            now=now,
        )
        self._require_scope(actor, source.organization_id, source.environment_id)
        if actor.subject_id in {policy.signed_by, policy.required_adapter_attestor_id}:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            correlation_id=correlation_id,
        )
        seed = self._digest(
            [source.review_request_id, source.canonical_digest, policy.canonical_digest]
        )
        assignment_set_id = f"operational-knowledge-reviewer-assignment.{seed[:24]}"
        exclusion_subject_digests = tuple(
            sorted(
                self._digest([policy.subject_digest_salt_digest, subject_id])
                for subject_id in source_actors
                | {
                    actor.subject_id,
                    policy.signed_by,
                    policy.required_adapter_attestor_id,
                }
            )
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_reviewer_assignment_requested",
            source.review_request_id,
            (("manifest_id", source.manifest_id),),
        )
        claim = OperationalKnowledgeReviewerAssignmentClaim(
            claim_id=f"operational-knowledge-reviewer-assignment-claim.{seed[:24]}",
            schema_version=ASSIGNMENT_CLAIM_SCHEMA,
            version=1,
            source_review_request_id=source.review_request_id,
            source_review_request_digest=source.canonical_digest,
            assignment_set_id=assignment_set_id,
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
            prior = await self._repository.get_claim_by_source(
                source_review_request_id=source.review_request_id
            )
            if prior is None:
                raise OperationalKnowledgeReviewerAssignmentUncertainError(
                    "operational_knowledge_reviewer_assignment_claim_uncertain"
                )
            return await self._reuse(prior, actor, request_binding_digest, idempotency_digest)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_review_request_claimed_for_assignment",
            claim.claim_id,
            (("assignment_set_id", assignment_set_id),),
        )
        instruction = self._instruction(
            assignment_set_id, source, policy, exclusion_subject_digests
        )
        try:
            receipt = await self._adapter.assign_reviewers(instruction)
        except OperationalKnowledgeReviewerAssignmentError as error:
            await self._audit(
                actor,
                correlation_id,
                (
                    "operational_knowledge_reviewer_assignment_uncertain"
                    if isinstance(error, OperationalKnowledgeReviewerAssignmentUncertainError)
                    else "operational_knowledge_reviewer_assignment_failed"
                ),
                assignment_set_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_reviewer_assignment_uncertain",
                assignment_set_id,
                (("claim_persisted", "true"),),
            )
            raise OperationalKnowledgeReviewerAssignmentUncertainError(
                "operational_knowledge_reviewer_assignment_outcome_uncertain"
            ) from error
        try:
            self._verify_receipt(instruction, receipt, policy)
        except OperationalKnowledgeReviewerAssignmentUncertainError:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_reviewer_assignment_uncertain",
                assignment_set_id,
                (("claim_persisted", "true"),),
            )
            raise
        record = self._record(claim, source, policy, receipt, actor, purpose)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_reviewers_assigned",
            record.assignment_set_id,
            (("state", record.instance_state),),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source(
                source_review_request_id=source.review_request_id
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise OperationalKnowledgeReviewerAssignmentUncertainError(
                    "operational_knowledge_reviewer_assignment_persistence_uncertain"
                )
            return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, assignment_set_id: str, correlation_id: str
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(assignment_set_id=assignment_set_id)
        if record is None:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_record_not_found"
            )
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_reviewer_assignment_read",
            record.assignment_set_id,
            (),
            permission_id=KNOWLEDGE_REVIEWER_ASSIGNMENT_READ,
        )
        return record

    async def protected_inspection_source(
        self, *, assignment_set_id: str
    ) -> tuple[
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ]:
        record = await self._repository.get(assignment_set_id=assignment_set_id)
        if record is None:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_record_not_found"
            )
        self._verify_record(record)
        policy = await self._policy_source.get_by_id(policy_id=record.assignment_policy_id)
        if policy is None or policy.canonical_digest != record.assignment_policy_digest:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_policy_not_found"
            )
        self._verify_snapshot(policy)
        return record, policy

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: OperationalKnowledgeReviewerAssignmentClaim,
        actor: AuthenticatedSubject,
        request_binding_digest: str,
        idempotency_digest: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by != actor.subject_id
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_idempotency_conflict"
            )
        self._require_scope(actor, claim.organization_id, claim.environment_id)
        record = await self._repository.get(assignment_set_id=claim.assignment_set_id)
        if record is None:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_already_claimed"
            )
        self._verify_record(record)
        return replace(record, reused=True)

    @staticmethod
    def _verify_source(
        *,
        source: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
        source_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        later_authority = (
            source.reviewer_assigned,
            source.content_inspection_opened,
            source.domain_review_completed,
            source.security_review_completed,
            source.correction_created,
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
            or source.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED
            or source.knowledge_lifecycle != "review_requested"
            or not all(
                (
                    source.review_requested,
                    source.immutable_manifest_confirmed,
                    source.encrypted_at_rest,
                    source.transient_buffers_erased,
                    source.artifact_channel_closed,
                )
            )
            or any(later_authority)
            or now - source.created_at > timedelta(minutes=policy.maximum_source_age_minutes)
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_source_invalid"
            )

    @staticmethod
    def _instruction(
        assignment_set_id: str,
        source: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
        exclusion_subject_digests: tuple[str, ...],
    ) -> OperationalKnowledgeReviewerAssignmentInstruction:
        return OperationalKnowledgeReviewerAssignmentInstruction(
            assignment_set_id=assignment_set_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            review_request_id=source.review_request_id,
            review_request_digest=source.canonical_digest,
            source_draft_id=source.source_draft_id,
            source_draft_digest=source.source_draft_digest,
            knowledge_item_id=source.knowledge_item_id,
            manifest_id=source.manifest_id,
            manifest_digest=source.manifest_digest,
            routing_digest=source.routing_digest,
            governance_digest=source.governance_digest,
            domain_track_code=source.domain_track_code,
            security_track_code=source.security_track_code,
            domain_queue_id=source.domain_queue_id,
            security_queue_id=source.security_queue_id,
            domain_status=source.domain_status,
            security_status=source.security_status,
            directory_source_id=policy.directory_source_id,
            directory_source_digest=policy.directory_source_digest,
            domain_eligibility_profile_id=policy.domain_eligibility_profile_id,
            domain_eligibility_profile_digest=policy.domain_eligibility_profile_digest,
            security_eligibility_profile_id=policy.security_eligibility_profile_id,
            security_eligibility_profile_digest=policy.security_eligibility_profile_digest,
            subject_digest_salt_id=policy.subject_digest_salt_id,
            subject_digest_salt_digest=policy.subject_digest_salt_digest,
            exclusion_subject_digests=exclusion_subject_digests,
            assignment_ttl_minutes=policy.assignment_ttl_minutes,
            assignment_policy_digest=policy.canonical_digest,
        )

    @classmethod
    def _verify_receipt(
        cls,
        instruction: OperationalKnowledgeReviewerAssignmentInstruction,
        receipt: OperationalKnowledgeReviewerAssignmentReceipt,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    ) -> None:
        if (
            cls._receipt_digest(receipt) != receipt.canonical_digest
            or receipt.assignment_set_id != instruction.assignment_set_id
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.adapter_id != policy.required_adapter_id
            or receipt.attested_by != policy.required_adapter_attestor_id
            or receipt.review_request_id != instruction.review_request_id
            or receipt.review_request_digest != instruction.review_request_digest
            or receipt.manifest_id != instruction.manifest_id
            or receipt.manifest_digest != instruction.manifest_digest
            or receipt.domain_track_code != instruction.domain_track_code
            or receipt.security_track_code != instruction.security_track_code
            or receipt.domain_queue_id != instruction.domain_queue_id
            or receipt.security_queue_id != instruction.security_queue_id
            or receipt.domain_status != ASSIGNED
            or receipt.security_status != ASSIGNED
            or receipt.routing_digest != instruction.routing_digest
            or receipt.domain_reviewer_subject_digest in instruction.exclusion_subject_digests
            or receipt.security_reviewer_subject_digest in instruction.exclusion_subject_digests
            or receipt.domain_reviewer_subject_digest == receipt.security_reviewer_subject_digest
            or receipt.expires_at
            != receipt.created_at + timedelta(minutes=policy.assignment_ttl_minutes)
        ):
            raise OperationalKnowledgeReviewerAssignmentUncertainError(
                "operational_knowledge_reviewer_assignment_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: OperationalKnowledgeReviewerAssignmentClaim,
        source: OperationalKnowledgeReviewRequestRecord,
        policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
        receipt: OperationalKnowledgeReviewerAssignmentReceipt,
        actor: AuthenticatedSubject,
        purpose: str,
    ) -> OperationalKnowledgeReviewerAssignmentRecord:
        record = OperationalKnowledgeReviewerAssignmentRecord(
            assignment_set_id=receipt.assignment_set_id,
            schema_version=ASSIGNMENT_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_review_request_id=source.review_request_id,
            source_review_request_digest=source.canonical_digest,
            source_draft_id=source.source_draft_id,
            source_draft_digest=source.source_draft_digest,
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
            knowledge_lifecycle="reviewer_assigned",
            classification=source.classification,
            access_policy_id=source.access_policy_id,
            retention_policy_id=source.retention_policy_id,
            encryption_profile_id=source.encryption_profile_id,
            manifest_id=source.manifest_id,
            manifest_digest=source.manifest_digest,
            domain_assignment_id=receipt.domain_assignment_id,
            security_assignment_id=receipt.security_assignment_id,
            domain_reviewer_subject_digest=receipt.domain_reviewer_subject_digest,
            security_reviewer_subject_digest=receipt.security_reviewer_subject_digest,
            domain_track_code=receipt.domain_track_code,
            security_track_code=receipt.security_track_code,
            domain_queue_id=receipt.domain_queue_id,
            security_queue_id=receipt.security_queue_id,
            domain_status=receipt.domain_status,
            security_status=receipt.security_status,
            assignment_digest=receipt.assignment_digest,
            routing_digest=receipt.routing_digest,
            eligibility_digest=receipt.eligibility_digest,
            separation_digest=receipt.separation_digest,
            artifact_digest=receipt.artifact_digest,
            assignment_policy_id=policy.policy_id,
            assignment_policy_digest=policy.canonical_digest,
            assignment_policy_version=policy.policy_version,
            assignment_adapter_id=receipt.adapter_id,
            created_at=receipt.created_at,
            expires_at=receipt.expires_at,
            instance_state=OPERATIONAL_KNOWLEDGE_REVIEWERS_ASSIGNED,
            requested_by=actor.subject_id,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._record_payload(record)))

    @classmethod
    def _verify_snapshot(cls, policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: OperationalKnowledgeReviewerAssignmentClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: OperationalKnowledgeReviewerAssignmentRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_record_integrity_failed"
            )

    @classmethod
    def _claim_payload(
        cls, claim: OperationalKnowledgeReviewerAssignmentClaim
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(
        cls, record: OperationalKnowledgeReviewerAssignmentRecord
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: OperationalKnowledgeReviewerAssignmentReceipt) -> str:
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
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise OperationalKnowledgeReviewerAssignmentError(
                "operational_knowledge_reviewer_assignment_record_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = KNOWLEDGE_REVIEWER_ASSIGNMENT_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-reviewer-assignment",
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
                resource_type="resource.knowledge.operational-reviewer-assignments",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def _signed_policy(policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot) -> str:
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return OperationalKnowledgeReviewerAssignmentService._digest(
        OperationalKnowledgeReviewerAssignmentService._normalize(payload)
    )


def build_development_operational_knowledge_reviewer_assignment_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeReviewerAssignmentPolicySnapshot:
    digest = OperationalKnowledgeReviewerAssignmentService._digest
    policy = OperationalKnowledgeReviewerAssignmentPolicySnapshot(
        policy_id="operational-knowledge-reviewer-assignment-policy.development",
        schema_version=ASSIGNMENT_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.operational-knowledge-review-request.v1",
        required_source_state=OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
        required_adapter_id="operational-knowledge-reviewer-assignment-adapter.synthetic",
        required_adapter_attestor_id=(
            "subject.operational-knowledge-reviewer-assignment-adapter-attestor"
        ),
        required_receipt_schema="atlas.operational-knowledge-reviewer-assignment-receipt.v1",
        directory_source_id="identity-directory.synthetic-reviewers",
        directory_source_digest=digest(["synthetic-reviewer-directory", "v1"]),
        domain_eligibility_profile_id="reviewer-eligibility.operational-domain",
        domain_eligibility_profile_digest=digest(["domain", "hardware-mfa", "c3", "v1"]),
        security_eligibility_profile_id="reviewer-eligibility.knowledge-security",
        security_eligibility_profile_digest=digest(["security", "hardware-mfa", "c3", "v1"]),
        subject_digest_salt_id="subject-digest-salt.knowledge-review-assignment-v1",
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        maximum_source_age_minutes=120,
        assignment_ttl_minutes=1440,
        require_distinct_reviewers=True,
        require_upstream_actor_exclusion=True,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.operational-knowledge-reviewer-assignment-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(policy, canonical_digest=_signed_policy(policy))
