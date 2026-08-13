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
    KNOWLEDGE_PROTECTED_INSPECTION_LEASE_CREATE,
    KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.knowledge.application.protected_inspection_ports import (
    OperationalKnowledgeProtectedInspectionBroker,
    OperationalKnowledgeProtectedInspectionError,
    OperationalKnowledgeProtectedInspectionPermissionAuthorizer,
    OperationalKnowledgeProtectedInspectionPolicySource,
    OperationalKnowledgeProtectedInspectionRepository,
    OperationalKnowledgeProtectedInspectionSource,
    OperationalKnowledgeProtectedInspectionUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.protected_inspection import (
    OPERATIONAL_KNOWLEDGE_PROTECTED_INSPECTION_LEASED,
    TRACKS,
    OperationalKnowledgeProtectedInspectionClaim,
    OperationalKnowledgeProtectedInspectionGrant,
    OperationalKnowledgeProtectedInspectionInstruction,
    OperationalKnowledgeProtectedInspectionPolicySnapshot,
    OperationalKnowledgeProtectedInspectionReceipt,
    OperationalKnowledgeProtectedInspectionRecord,
)
from atlas.modules.knowledge.domain.reviewer_assignment import (
    OPERATIONAL_KNOWLEDGE_REVIEWERS_ASSIGNED,
    OperationalKnowledgeReviewerAssignmentPolicySnapshot,
    OperationalKnowledgeReviewerAssignmentRecord,
)

INSPECTION_POLICY_SCHEMA = "atlas.operational-knowledge-protected-inspection-policy.v1"
INSPECTION_CLAIM_SCHEMA = "atlas.operational-knowledge-protected-inspection-claim.v1"
INSPECTION_RECORD_SCHEMA = "atlas.operational-knowledge-protected-inspection-lease.v1"


class OperationalKnowledgeProtectedInspectionService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeProtectedInspectionRepository,
        source: OperationalKnowledgeProtectedInspectionSource,
        policy_source: OperationalKnowledgeProtectedInspectionPolicySource,
        permission_authorizer: OperationalKnowledgeProtectedInspectionPermissionAuthorizer,
        broker: OperationalKnowledgeProtectedInspectionBroker,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._broker = broker
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        source_assignment_set_id: str,
        source_assignment_set_digest: str,
        track_code: str,
        inspection_policy_id: str,
        inspection_policy_digest: str,
        purpose: str,
        lease_only_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeProtectedInspectionGrant:
        self._require_human(actor)
        if not lease_only_acknowledged:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_acknowledgement_required"
            )
        purpose = purpose.strip()
        if (
            track_code not in TRACKS
            or not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_request_invalid"
            )
        try:
            source, assignment_policy = await self._source.protected_inspection_source(
                assignment_set_id=source_assignment_set_id
            )
        except Exception as error:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=inspection_policy_id)
        if policy is None:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_policy_not_found"
            )
        self._verify_snapshot(policy)
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_assurance_required"
            )
        now = self._clock()
        self._verify_source(
            source=source,
            assignment_policy=assignment_policy,
            policy=policy,
            source_digest=source_assignment_set_digest,
            policy_digest=inspection_policy_digest,
            now=now,
        )
        self._require_scope(actor, source.organization_id, source.environment_id)
        if now - actor.authenticated_at > timedelta(
            minutes=policy.maximum_authentication_age_minutes
        ):
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_recent_authentication_required"
            )
        current_subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        expected_subject_digest, opaque_assignment_id = self._track_binding(source, track_code)
        if current_subject_digest != expected_subject_digest:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_source_not_found"
            )
        browser_binding_digest = self._digest(
            [policy.browser_binding_key_digest, browser_session_id]
        )
        request_binding_digest = self._digest(
            {
                "source_assignment_set_id": source_assignment_set_id,
                "source_assignment_set_digest": source_assignment_set_digest,
                "track_code": track_code,
                "inspection_policy_id": inspection_policy_id,
                "inspection_policy_digest": inspection_policy_digest,
                "purpose": purpose,
                "browser_session_binding_digest": browser_binding_digest,
            }
        )
        idempotency_digest = self._digest(
            [current_subject_digest, browser_binding_digest, idempotency_key]
        )
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=current_subject_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                current_subject_digest,
                browser_binding_digest,
                request_binding_digest,
                idempotency_digest,
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            correlation_id=correlation_id,
        )
        seed = self._digest(
            [source.assignment_set_id, source.canonical_digest, track_code, policy.canonical_digest]
        )
        lease_id = f"operational-knowledge-protected-inspection-lease.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_protected_inspection_requested",
            source.assignment_set_id,
            (("track_code", track_code),),
        )
        claim = OperationalKnowledgeProtectedInspectionClaim(
            claim_id=f"operational-knowledge-protected-inspection-claim.{seed[:24]}",
            schema_version=INSPECTION_CLAIM_SCHEMA,
            version=1,
            source_assignment_set_id=source.assignment_set_id,
            source_assignment_set_digest=source.canonical_digest,
            track_code=track_code,
            lease_id=lease_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            claimed_by_subject_digest=current_subject_digest,
            purpose=purpose,
            claimed_at=now,
            browser_session_binding_digest=browser_binding_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._claim_payload(claim)))
        if not await self._repository.claim(claim):
            prior = await self._repository.get_claim_by_source_track(
                source_assignment_set_id=source.assignment_set_id,
                track_code=track_code,
            )
            if prior is None:
                raise OperationalKnowledgeProtectedInspectionUncertainError(
                    "operational_knowledge_protected_inspection_claim_uncertain"
                )
            return await self._reuse(
                prior,
                current_subject_digest,
                browser_binding_digest,
                request_binding_digest,
                idempotency_digest,
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_assignment_track_claimed_for_inspection",
            claim.claim_id,
            (("lease_id", lease_id), ("track_code", track_code)),
        )
        instruction = OperationalKnowledgeProtectedInspectionInstruction(
            lease_id=lease_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            assignment_set_id=source.assignment_set_id,
            assignment_set_digest=source.canonical_digest,
            review_request_id=source.source_review_request_id,
            source_draft_id=source.source_draft_id,
            source_draft_digest=source.source_draft_digest,
            knowledge_item_id=source.knowledge_item_id,
            draft_version_id=source.draft_version_id,
            manifest_id=source.manifest_id,
            manifest_digest=source.manifest_digest,
            track_code=track_code,
            opaque_assignment_id=opaque_assignment_id,
            assigned_reviewer_subject_digest=expected_subject_digest,
            current_subject_digest=current_subject_digest,
            browser_session_binding_digest=browser_binding_digest,
            lease_ttl_minutes=policy.lease_ttl_minutes,
            inspection_policy_digest=policy.canonical_digest,
        )
        try:
            broker_grant = await self._broker.issue(instruction)
        except OperationalKnowledgeProtectedInspectionError as error:
            await self._audit(
                actor,
                correlation_id,
                (
                    "operational_knowledge_protected_inspection_uncertain"
                    if isinstance(error, OperationalKnowledgeProtectedInspectionUncertainError)
                    else "operational_knowledge_protected_inspection_failed"
                ),
                lease_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "operational_knowledge_protected_inspection_uncertain",
                lease_id,
                (("claim_persisted", "true"),),
            )
            raise OperationalKnowledgeProtectedInspectionUncertainError(
                "operational_knowledge_protected_inspection_outcome_uncertain"
            ) from error
        receipt = broker_grant.receipt
        self._verify_receipt(instruction, receipt, policy, broker_grant.lease_secret)
        record = self._record(claim, source, policy, receipt, purpose)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_protected_inspection_leased",
            lease_id,
            (("track_code", track_code),),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source_track(
                source_assignment_set_id=source.assignment_set_id,
                track_code=track_code,
            )
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise OperationalKnowledgeProtectedInspectionUncertainError(
                    "operational_knowledge_protected_inspection_persistence_uncertain"
                )
            return OperationalKnowledgeProtectedInspectionGrant(
                record=replace(raced, reused=True), lease_secret=None
            )
        return OperationalKnowledgeProtectedInspectionGrant(
            record=record, lease_secret=broker_grant.lease_secret
        )

    async def get(
        self, *, actor: AuthenticatedSubject, lease_id: str, correlation_id: str
    ) -> OperationalKnowledgeProtectedInspectionRecord:
        self._require_human(actor)
        record = await self._repository.get(lease_id=lease_id)
        if record is None:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_record_not_found"
            )
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_protected_inspection_read",
            record.lease_id,
            (("track_code", record.track_code),),
            permission_id=KNOWLEDGE_PROTECTED_INSPECTION_LEASE_READ,
        )
        return record

    async def close(self) -> None:
        await self._repository.close()

    async def protected_content_source(
        self, *, lease_id: str
    ) -> tuple[
        OperationalKnowledgeProtectedInspectionRecord,
        OperationalKnowledgeProtectedInspectionPolicySnapshot,
        OperationalKnowledgeReviewerAssignmentRecord,
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]:
        record = await self._repository.get(lease_id=lease_id)
        if record is None:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_record_not_found"
            )
        self._verify_record(record)
        policy = await self._policy_source.get_by_id(policy_id=record.inspection_policy_id)
        if policy is None or policy.canonical_digest != record.inspection_policy_digest:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_policy_not_found"
            )
        self._verify_snapshot(policy)
        assignment, review_request, draft = await self._source.protected_content_lineage(
            assignment_set_id=record.source_assignment_set_id
        )
        if (
            assignment.canonical_digest != record.source_assignment_set_digest
            or assignment.source_review_request_id != record.review_request_id
            or review_request.source_draft_id != record.source_draft_id
            or review_request.source_draft_digest != record.source_draft_digest
        ):
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_lineage_invalid"
            )
        return record, policy, assignment, review_request, draft

    async def _reuse(
        self,
        claim: OperationalKnowledgeProtectedInspectionClaim,
        current_subject_digest: str,
        browser_binding_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
    ) -> OperationalKnowledgeProtectedInspectionGrant:
        self._verify_claim(claim)
        if (
            claim.claimed_by_subject_digest != current_subject_digest
            or claim.browser_session_binding_digest != browser_binding_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_idempotency_conflict"
            )
        record = await self._repository.get(lease_id=claim.lease_id)
        if record is None:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_already_claimed"
            )
        self._verify_record(record)
        return OperationalKnowledgeProtectedInspectionGrant(
            record=replace(record, reused=True), lease_secret=None
        )

    @staticmethod
    def _track_binding(
        source: OperationalKnowledgeReviewerAssignmentRecord, track_code: str
    ) -> tuple[str, str]:
        if track_code == "review-track.domain":
            return source.domain_reviewer_subject_digest, source.domain_assignment_id
        if track_code == "review-track.security":
            return source.security_reviewer_subject_digest, source.security_assignment_id
        raise OperationalKnowledgeProtectedInspectionError(
            "operational_knowledge_protected_inspection_track_invalid"
        )

    @staticmethod
    def _verify_source(
        *,
        source: OperationalKnowledgeReviewerAssignmentRecord,
        assignment_policy: OperationalKnowledgeReviewerAssignmentPolicySnapshot,
        policy: OperationalKnowledgeProtectedInspectionPolicySnapshot,
        source_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        later_authority = (
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
            or source.instance_state != OPERATIONAL_KNOWLEDGE_REVIEWERS_ASSIGNED
            or not source.review_requested
            or not source.reviewer_assigned
            or any(later_authority)
            or now >= source.expires_at
            or now - source.created_at > timedelta(minutes=policy.maximum_source_age_minutes)
            or not policy.issued_at <= now < policy.expires_at
            or assignment_policy.subject_digest_salt_digest != policy.subject_digest_salt_digest
        ):
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_source_invalid"
            )

    @classmethod
    def _verify_receipt(
        cls,
        instruction: OperationalKnowledgeProtectedInspectionInstruction,
        receipt: OperationalKnowledgeProtectedInspectionReceipt,
        policy: OperationalKnowledgeProtectedInspectionPolicySnapshot,
        lease_secret: str,
    ) -> None:
        expected_secret_digest = cls._digest(
            [policy.canonical_digest, "lease-secret", lease_secret]
        )
        if (
            cls._receipt_digest(receipt) != receipt.canonical_digest
            or receipt.lease_id != instruction.lease_id
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.broker_id != policy.required_broker_id
            or receipt.attested_by != policy.required_broker_attestor_id
            or receipt.assignment_set_id != instruction.assignment_set_id
            or receipt.assignment_set_digest != instruction.assignment_set_digest
            or receipt.track_code != instruction.track_code
            or receipt.opaque_assignment_id != instruction.opaque_assignment_id
            or receipt.lease_holder_subject_digest != instruction.current_subject_digest
            or receipt.browser_session_binding_digest != instruction.browser_session_binding_digest
            or receipt.lease_secret_digest != expected_secret_digest
            or receipt.expires_at != receipt.issued_at + timedelta(minutes=policy.lease_ttl_minutes)
        ):
            raise OperationalKnowledgeProtectedInspectionUncertainError(
                "operational_knowledge_protected_inspection_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: OperationalKnowledgeProtectedInspectionClaim,
        source: OperationalKnowledgeReviewerAssignmentRecord,
        policy: OperationalKnowledgeProtectedInspectionPolicySnapshot,
        receipt: OperationalKnowledgeProtectedInspectionReceipt,
        purpose: str,
    ) -> OperationalKnowledgeProtectedInspectionRecord:
        record = OperationalKnowledgeProtectedInspectionRecord(
            lease_id=receipt.lease_id,
            schema_version=INSPECTION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_assignment_set_id=source.assignment_set_id,
            source_assignment_set_digest=source.canonical_digest,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            review_request_id=source.source_review_request_id,
            source_draft_id=source.source_draft_id,
            source_draft_digest=source.source_draft_digest,
            knowledge_item_id=source.knowledge_item_id,
            draft_version_id=source.draft_version_id,
            source_ingestion_id=source.source_ingestion_id,
            source_invocation_id=source.source_invocation_id,
            connector_id=source.connector_id,
            instance_id=source.instance_id,
            capability_id=source.capability_id,
            title=source.title,
            classification=source.classification,
            access_policy_id=source.access_policy_id,
            retention_policy_id=source.retention_policy_id,
            encryption_profile_id=source.encryption_profile_id,
            manifest_id=source.manifest_id,
            manifest_digest=source.manifest_digest,
            track_code=receipt.track_code,
            opaque_assignment_id=receipt.opaque_assignment_id,
            lease_holder_subject_digest=receipt.lease_holder_subject_digest,
            browser_session_binding_digest=receipt.browser_session_binding_digest,
            lease_secret_digest=receipt.lease_secret_digest,
            lease_digest=receipt.lease_digest,
            assignment_binding_digest=receipt.assignment_binding_digest,
            policy_binding_digest=receipt.policy_binding_digest,
            cleanup_digest=receipt.cleanup_digest,
            inspection_policy_id=policy.policy_id,
            inspection_policy_digest=policy.canonical_digest,
            inspection_policy_version=policy.policy_version,
            lease_broker_id=receipt.broker_id,
            issued_at=receipt.issued_at,
            expires_at=receipt.expires_at,
            instance_state=OPERATIONAL_KNOWLEDGE_PROTECTED_INSPECTION_LEASED,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._record_payload(record)))

    @classmethod
    def _verify_snapshot(
        cls, policy: OperationalKnowledgeProtectedInspectionPolicySnapshot
    ) -> None:
        payload = cast(dict[str, object], asdict(policy))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: OperationalKnowledgeProtectedInspectionClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: OperationalKnowledgeProtectedInspectionRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_record_integrity_failed"
            )

    @classmethod
    def _claim_payload(
        cls, claim: OperationalKnowledgeProtectedInspectionClaim
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(
        cls, record: OperationalKnowledgeProtectedInspectionRecord
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: OperationalKnowledgeProtectedInspectionReceipt) -> str:
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
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_human_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise OperationalKnowledgeProtectedInspectionError(
                "operational_knowledge_protected_inspection_record_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = KNOWLEDGE_PROTECTED_INSPECTION_LEASE_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-protected-inspection",
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
                resource_type="resource.knowledge.operational-protected-inspections",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def _signed_policy(policy: OperationalKnowledgeProtectedInspectionPolicySnapshot) -> str:
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return OperationalKnowledgeProtectedInspectionService._digest(
        OperationalKnowledgeProtectedInspectionService._normalize(payload)
    )


def build_development_operational_knowledge_protected_inspection_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeProtectedInspectionPolicySnapshot:
    digest = OperationalKnowledgeProtectedInspectionService._digest
    policy = OperationalKnowledgeProtectedInspectionPolicySnapshot(
        policy_id="operational-knowledge-protected-inspection-policy.development",
        schema_version=INSPECTION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.operational-knowledge-reviewer-assignment.v1",
        required_source_state=OPERATIONAL_KNOWLEDGE_REVIEWERS_ASSIGNED,
        required_broker_id="operational-knowledge-protected-inspection-broker.synthetic",
        required_broker_attestor_id=(
            "subject.operational-knowledge-protected-inspection-broker-attestor"
        ),
        required_receipt_schema="atlas.operational-knowledge-protected-inspection-receipt.v1",
        subject_digest_salt_id="subject-digest-salt.knowledge-review-assignment-v1",
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        browser_binding_key_id="browser-binding-key.knowledge-inspection-v1",
        browser_binding_key_digest=digest(
            [organization_id, environment_id, "inspection-browser-binding-v1"]
        ),
        maximum_source_age_minutes=1440,
        maximum_authentication_age_minutes=15,
        lease_ttl_minutes=10,
        maximum_concurrent_leases=1,
        require_browser_session_binding=True,
        require_exact_assignee=True,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        signed_by="subject.operational-knowledge-protected-inspection-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(policy, canonical_digest=_signed_policy(policy))
