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
    KNOWLEDGE_PUBLICATION_PREPARATION_CREATE,
    KNOWLEDGE_PUBLICATION_PREPARATION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.application.publication_preparation_ports import (
    OperationalKnowledgePublicationPreparationError,
    OperationalKnowledgePublicationPreparationPermissionAuthorizer,
    OperationalKnowledgePublicationPreparationPolicySource,
    OperationalKnowledgePublicationPreparationRepository,
    OperationalKnowledgePublicationPreparationSource,
    OperationalKnowledgePublicationPreparationUncertainError,
    OperationalKnowledgePublicationPreparer,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED,
)
from atlas.modules.knowledge.domain.evidence_draft import DRAFT_OPERATIONAL_KNOWLEDGE_CREATED
from atlas.modules.knowledge.domain.final_resolution import FINAL_APPROVED, FINAL_APPROVED_STATE
from atlas.modules.knowledge.domain.publication_preparation import (
    PUBLICATION_PREPARED_STATE,
    OperationalKnowledgePublicationPreparationClaim,
    OperationalKnowledgePublicationPreparationInstruction,
    OperationalKnowledgePublicationPreparationPolicySnapshot,
    OperationalKnowledgePublicationPreparationReceipt,
    OperationalKnowledgePublicationPreparationRecord,
)
from atlas.modules.knowledge.domain.review_decision import (
    OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED,
    TRACKS,
)

PUBLICATION_PREPARATION_POLICY_SCHEMA = (
    "atlas.operational-knowledge-publication-preparation-policy.v1"
)
PUBLICATION_PREPARATION_CLAIM_SCHEMA = (
    "atlas.operational-knowledge-publication-preparation-claim.v1"
)
PUBLICATION_PREPARATION_RECORD_SCHEMA = "atlas.operational-knowledge-publication-preparation.v1"


class OperationalKnowledgePublicationPreparationService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgePublicationPreparationRepository,
        source: OperationalKnowledgePublicationPreparationSource,
        policy_source: OperationalKnowledgePublicationPreparationPolicySource,
        permission_authorizer: OperationalKnowledgePublicationPreparationPermissionAuthorizer,
        preparer: OperationalKnowledgePublicationPreparer,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._preparer = preparer
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        resolution_id: str,
        resolution_digest: str,
        preparation_policy_id: str,
        preparation_policy_digest: str,
        purpose: str,
        immutable_generation_acknowledged: bool,
        metadata_only_acknowledged: bool,
        no_processing_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgePublicationPreparationRecord:
        self._require_enterprise_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    immutable_generation_acknowledged,
                    metadata_only_acknowledged,
                    no_processing_or_operational_authority_acknowledged,
                )
            )
        ):
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_request_invalid"
            )
        try:
            (
                resolution,
                decisions,
                request,
                draft,
            ) = await self._source.publication_preparation_source(resolution_id=resolution_id)
        except Exception as error:
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=preparation_policy_id)
        if policy is None:
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        ordered = tuple(sorted(decisions, key=lambda item: item.track_code))
        later_resolution_authority = any(
            (
                resolution.knowledge_published,
                resolution.chunks_created,
                resolution.embeddings_created,
                resolution.retrieval_published,
                resolution.model_context_available,
                resolution.graph_updated,
                resolution.scheduled,
                resolution.workflow_continued,
                resolution.execution_authorized,
                resolution.deployment_approved,
                resolution.infrastructure_mutation_performed,
            )
        )
        if (
            resolution.resolution_id != resolution_id
            or resolution.canonical_digest != resolution_digest
            or resolution.schema_version != policy.required_resolution_schema
            or resolution.instance_state != policy.required_resolution_state
            or resolution.disposition_code != policy.required_resolution_disposition
            or resolution.disposition_code != FINAL_APPROVED
            or not resolution.knowledge_approved
            or not resolution.publication_ready
            or later_resolution_authority
            or resolution.review_request_id != request.review_request_id
            or resolution.review_request_digest != request.canonical_digest
            or resolution.source_draft_id != draft.draft_id
            or resolution.source_draft_digest != draft.canonical_digest
            or resolution.knowledge_item_id != draft.knowledge_item_id
            or resolution.organization_id != request.organization_id
            or resolution.environment_id != request.environment_id
            or request.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED
            or draft.instance_state != DRAFT_OPERATIONAL_KNOWLEDGE_CREATED
            or len(ordered) != 2
            or {item.track_code for item in ordered} != TRACKS
            or tuple(item.decision_id for item in ordered) != resolution.decision_ids
            or tuple(item.canonical_digest for item in ordered) != resolution.decision_digests
            or any(
                item.instance_state != OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED
                for item in ordered
            )
            or any(item.disposition_code != "review-disposition.passed" for item in ordered)
            or any(item.correction_required or item.correction_created for item in ordered)
            or policy.canonical_digest != preparation_policy_digest
            or policy.organization_id != resolution.organization_id
            or policy.environment_id != resolution.environment_id
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_source_invalid"
            )
        self._require_scope(actor, resolution.organization_id, resolution.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        if (
            subject_digest == resolution.approved_by_subject_digest
            or actor.subject_id == draft.curated_by
            or subject_digest in {item.decided_by_subject_digest for item in ordered}
            or actor.subject_id in {policy.signed_by, policy.required_preparer_id}
        ):
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=resolution.organization_id,
            environment_id=resolution.environment_id,
            correlation_id=correlation_id,
        )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        request_binding_digest = self._digest(
            [
                resolution_id,
                resolution_digest,
                preparation_policy_digest,
                policy.preparation_profile_digest,
                policy.chunking_profile_digest,
                policy.embedding_profile_digest,
                policy.index_profile_digest,
                policy.validation_profile_digest,
                purpose,
                subject_digest,
                browser_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, resolution_id, idempotency_key])
        existing = await self._repository.get_claim_by_resolution(resolution_id=resolution_id)
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
        seed = self._digest([resolution_id, request_binding_digest])
        preparation_id = f"operational-knowledge-publication-preparation.{seed[:24]}"
        claim = OperationalKnowledgePublicationPreparationClaim(
            claim_id=f"operational-knowledge-publication-preparation-claim.{seed[:24]}",
            schema_version=PUBLICATION_PREPARATION_CLAIM_SCHEMA,
            version=1,
            resolution_id=resolution_id,
            preparation_id=preparation_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            organization_id=resolution.organization_id,
            environment_id=resolution.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_publication_preparation_requested",
            resolution_id,
        )
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_resolution(resolution_id=resolution_id)
            if concurrent is None:
                raise OperationalKnowledgePublicationPreparationUncertainError(
                    "operational_knowledge_publication_preparation_claim_uncertain"
                )
            return await self._reuse(
                concurrent,
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
            "operational_knowledge_publication_preparation_claimed",
            preparation_id,
        )
        instruction = OperationalKnowledgePublicationPreparationInstruction(
            preparation_id=preparation_id,
            organization_id=resolution.organization_id,
            environment_id=resolution.environment_id,
            resolution_id=resolution_id,
            resolution_digest=resolution_digest,
            review_request_id=resolution.review_request_id,
            review_request_digest=resolution.review_request_digest,
            source_draft_id=resolution.source_draft_id,
            source_draft_digest=resolution.source_draft_digest,
            knowledge_item_id=resolution.knowledge_item_id,
            steward_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            preparation_profile_id=policy.preparation_profile_id,
            preparation_profile_digest=policy.preparation_profile_digest,
            chunking_profile_id=policy.chunking_profile_id,
            chunking_profile_digest=policy.chunking_profile_digest,
            embedding_profile_id=policy.embedding_profile_id,
            embedding_profile_digest=policy.embedding_profile_digest,
            index_profile_id=policy.index_profile_id,
            index_profile_digest=policy.index_profile_digest,
            validation_profile_id=policy.validation_profile_id,
            validation_profile_digest=policy.validation_profile_digest,
            purpose=purpose,
            requested_at=now,
        )
        try:
            receipt = await self._preparer.prepare(instruction)
            self._verify_receipt(receipt, instruction, policy)
        except OperationalKnowledgePublicationPreparationError:
            raise
        except Exception as error:
            raise OperationalKnowledgePublicationPreparationUncertainError(
                "operational_knowledge_publication_preparation_outcome_uncertain"
            ) from error
        record = OperationalKnowledgePublicationPreparationRecord(
            preparation_id=preparation_id,
            schema_version=PUBLICATION_PREPARATION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            resolution_id=resolution_id,
            resolution_digest=resolution_digest,
            review_request_id=resolution.review_request_id,
            review_request_digest=resolution.review_request_digest,
            source_draft_id=resolution.source_draft_id,
            source_draft_digest=resolution.source_draft_digest,
            knowledge_item_id=resolution.knowledge_item_id,
            organization_id=resolution.organization_id,
            environment_id=resolution.environment_id,
            classification=resolution.classification,
            access_policy_id=resolution.access_policy_id,
            retention_policy_id=resolution.retention_policy_id,
            final_approver_subject_digest=resolution.approved_by_subject_digest,
            prepared_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            preparation_policy_id=policy.policy_id,
            preparation_policy_digest=policy.canonical_digest,
            preparation_policy_version=policy.policy_version,
            preparation_profile_id=policy.preparation_profile_id,
            preparation_profile_digest=policy.preparation_profile_digest,
            chunking_profile_id=policy.chunking_profile_id,
            chunking_profile_digest=policy.chunking_profile_digest,
            embedding_profile_id=policy.embedding_profile_id,
            embedding_profile_digest=policy.embedding_profile_digest,
            index_profile_id=policy.index_profile_id,
            index_profile_digest=policy.index_profile_digest,
            validation_profile_id=policy.validation_profile_id,
            validation_profile_digest=policy.validation_profile_digest,
            preparer_id=receipt.preparer_id,
            preparation_receipt_digest=receipt.canonical_digest,
            source_artifact_digest=receipt.source_artifact_digest,
            metadata_manifest_digest=receipt.metadata_manifest_digest,
            access_manifest_digest=receipt.access_manifest_digest,
            retention_manifest_digest=receipt.retention_manifest_digest,
            prepared_at=receipt.prepared_at,
            instance_state=PUBLICATION_PREPARED_STATE,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise OperationalKnowledgePublicationPreparationUncertainError(
                "operational_knowledge_publication_preparation_persistence_uncertain"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_publication_preparation_recorded",
            preparation_id,
        )
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        preparation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgePublicationPreparationRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(preparation_id=preparation_id)
        if record is None:
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_not_found"
            )
        policy = await self._policy_source.get_by_id(policy_id=record.preparation_policy_id)
        if policy is None or not policy.issued_at <= self._clock() < policy.expires_at:
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            subject_digest != record.prepared_by_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_publication_preparation_read",
            preparation_id,
            permission_id=KNOWLEDGE_PUBLICATION_PREPARATION_READ,
        )
        return replace(record, reused=True)

    async def close(self) -> None:
        await self._repository.close()

    async def source_materialization_preparation(
        self, *, preparation_id: str
    ) -> OperationalKnowledgePublicationPreparationRecord | None:
        return await self._repository.get(preparation_id=preparation_id)

    async def _reuse(
        self,
        claim: OperationalKnowledgePublicationPreparationClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgePublicationPreparationRecord:
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_idempotency_conflict"
            )
        record = await self._repository.get(preparation_id=claim.preparation_id)
        if record is None:
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_already_claimed"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_publication_preparation_read",
            record.preparation_id,
            permission_id=KNOWLEDGE_PUBLICATION_PREPARATION_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _verify_receipt(
        cls,
        receipt: OperationalKnowledgePublicationPreparationReceipt,
        instruction: OperationalKnowledgePublicationPreparationInstruction,
        policy: OperationalKnowledgePublicationPreparationPolicySnapshot,
    ) -> None:
        if (
            receipt.preparation_id != instruction.preparation_id
            or receipt.preparer_id != policy.required_preparer_id
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or receipt.source_artifact_digest != instruction.source_draft_digest
            or not receipt.signature_verified
        ):
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_receipt_invalid"
            )

    @classmethod
    def _verify_policy(
        cls, policy: OperationalKnowledgePublicationPreparationPolicySnapshot
    ) -> None:
        if policy.canonical_digest != cls._digest(cls._payload(policy)):
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_policy_invalid"
            )

    @staticmethod
    def _payload(
        value: OperationalKnowledgePublicationPreparationPolicySnapshot
        | OperationalKnowledgePublicationPreparationClaim
        | OperationalKnowledgePublicationPreparationRecord,
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(value))
        payload.pop("canonical_digest", None)
        payload.pop("reused", None)
        return payload

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
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = KNOWLEDGE_PUBLICATION_PREPARATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-publication-preparation",
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
                resource_type="resource.knowledge.operational-publication-preparations",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )


def build_development_operational_knowledge_publication_preparation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgePublicationPreparationPolicySnapshot:
    digest = OperationalKnowledgePublicationPreparationService._digest
    profile_ids = {
        "preparation": "publication-preparation-profile.development-v1",
        "chunking": "knowledge-chunking-profile.development-v1",
        "embedding": "knowledge-embedding-profile.development-v1",
        "index": "knowledge-index-profile.development-v1",
        "validation": "knowledge-publication-validation-profile.development-v1",
    }
    policy = OperationalKnowledgePublicationPreparationPolicySnapshot(
        policy_id="operational-knowledge-publication-preparation-policy.development",
        schema_version=PUBLICATION_PREPARATION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.operational-knowledge-publication-preparation-development-v1",
        required_resolution_schema="atlas.operational-knowledge-final-resolution.v1",
        required_resolution_state=FINAL_APPROVED_STATE,
        required_resolution_disposition=FINAL_APPROVED,
        preparation_profile_id=profile_ids["preparation"],
        preparation_profile_digest=digest([profile_ids["preparation"], "metadata-only"]),
        chunking_profile_id=profile_ids["chunking"],
        chunking_profile_digest=digest([profile_ids["chunking"], "not-authorized"]),
        embedding_profile_id=profile_ids["embedding"],
        embedding_profile_digest=digest([profile_ids["embedding"], "not-authorized"]),
        index_profile_id=profile_ids["index"],
        index_profile_digest=digest([profile_ids["index"], "not-authorized"]),
        validation_profile_id=profile_ids["validation"],
        validation_profile_digest=digest([profile_ids["validation"], "not-authorized"]),
        maximum_authentication_age_minutes=15,
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        browser_binding_key_digest=digest(["operational-knowledge-publication-browser-key"]),
        required_preparer_id="operational-knowledge-publication-preparer.synthetic",
        signed_by="subject.operational-knowledge-publication-preparation-policy-signer",
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(OperationalKnowledgePublicationPreparationService._payload(policy)),
    )
