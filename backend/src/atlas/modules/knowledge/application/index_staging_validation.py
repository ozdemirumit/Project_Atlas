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
    KNOWLEDGE_INDEX_STAGING_CREATE,
    KNOWLEDGE_INDEX_STAGING_READ,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.application.index_staging_validation_ports import (
    OperationalKnowledgeEmbeddingSetSource,
    OperationalKnowledgeIndexer,
    OperationalKnowledgeIndexError,
    OperationalKnowledgeIndexPermissionAuthorizer,
    OperationalKnowledgeIndexPolicySource,
    OperationalKnowledgeIndexRepository,
    OperationalKnowledgeIndexUncertainError,
)
from atlas.modules.knowledge.domain.embedding_generation import (
    EMBEDDINGS_CREATED_STATE,
    OperationalKnowledgeEmbeddingPolicySnapshot,
    OperationalKnowledgeEmbeddingRecord,
)
from atlas.modules.knowledge.domain.index_staging_validation import (
    INDEX_VALIDATED_STATE,
    OperationalKnowledgeIndexClaim,
    OperationalKnowledgeIndexInstruction,
    OperationalKnowledgeIndexPolicySnapshot,
    OperationalKnowledgeIndexReceipt,
    OperationalKnowledgeIndexRecord,
)

INDEX_POLICY_SCHEMA = "atlas.operational-knowledge-index-policy.v1"
INDEX_CLAIM_SCHEMA = "atlas.operational-knowledge-index-claim.v1"
INDEX_RECORD_SCHEMA = "atlas.operational-knowledge-index-staging.v1"


class OperationalKnowledgeIndexStagingValidationService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeIndexRepository,
        embedding_source: OperationalKnowledgeEmbeddingSetSource,
        policy_source: OperationalKnowledgeIndexPolicySource,
        permission_authorizer: OperationalKnowledgeIndexPermissionAuthorizer,
        indexer: OperationalKnowledgeIndexer,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._embedding_source = embedding_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._indexer = indexer
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        embedding_set_id: str,
        embedding_set_digest: str,
        index_policy_id: str,
        index_policy_digest: str,
        purpose: str,
        protected_vector_boundary_acknowledged: bool,
        inactive_projection_acknowledged: bool,
        no_publication_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeIndexRecord:
        self._require_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    protected_vector_boundary_acknowledged,
                    inactive_projection_acknowledged,
                    no_publication_or_operational_authority_acknowledged,
                )
            )
        ):
            raise OperationalKnowledgeIndexError("operational_knowledge_index_request_invalid")
        embedding = await self._embedding_source.source_for_index_staging(
            embedding_set_id=embedding_set_id
        )
        if embedding is None:
            raise OperationalKnowledgeIndexError("operational_knowledge_index_source_not_found")
        policy = await self._policy_source.get_by_id(policy_id=index_policy_id)
        if policy is None:
            raise OperationalKnowledgeIndexError("operational_knowledge_index_policy_not_found")
        self._verify_policy(policy)
        now = self._clock()
        later_authority = any(
            (
                embedding.index_staged,
                embedding.index_validated,
                embedding.knowledge_published,
                embedding.retrieval_published,
                embedding.model_context_available,
                embedding.graph_updated,
                embedding.scheduled,
                embedding.workflow_continued,
                embedding.execution_authorized,
                embedding.deployment_approved,
                embedding.infrastructure_mutation_performed,
            )
        )
        if (
            embedding.embedding_set_id != embedding_set_id
            or embedding.canonical_digest != embedding_set_digest
            or embedding.canonical_digest != self._digest(self._payload(embedding))
            or embedding.schema_version != policy.required_embedding_set_schema
            or embedding.instance_state != policy.required_embedding_set_state
            or embedding.instance_state != EMBEDDINGS_CREATED_STATE
            or not all(
                (
                    embedding.knowledge_approved,
                    embedding.publication_ready,
                    embedding.publication_prepared,
                    embedding.source_materialized,
                    embedding.chunks_created,
                    embedding.embeddings_created,
                )
            )
            or later_authority
            or embedding.model_profile_digest != policy.required_model_profile_digest
            or embedding.vector_dimension != policy.required_vector_dimension
            or embedding.normalization_profile_id != policy.required_normalization_profile_id
            or embedding.distance_metric_id != policy.required_distance_metric_id
            or embedding.embedding_count > policy.maximum_points
            or policy.canonical_digest != index_policy_digest
            or policy.organization_id != embedding.organization_id
            or policy.environment_id != embedding.environment_id
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgeIndexError("operational_knowledge_index_source_invalid")
        self._require_scope(actor, embedding.organization_id, embedding.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        separated_digests = {
            embedding.publication_steward_subject_digest,
            embedding.materialization_steward_subject_digest,
            embedding.chunking_steward_subject_digest,
            embedding.embedded_by_subject_digest,
            *embedding.upstream_accountable_subject_digests,
        }
        separated_identities = {
            policy.signed_by,
            policy.required_indexer_id,
            policy.index_profile_owner_id,
            embedding.embedder_id,
        }
        if subject_digest in separated_digests or actor.subject_id in separated_identities:
            raise OperationalKnowledgeIndexError(
                "operational_knowledge_index_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=embedding.organization_id,
            environment_id=embedding.environment_id,
            correlation_id=correlation_id,
        )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        request_binding_digest = self._digest(
            [
                embedding_set_id,
                embedding_set_digest,
                index_policy_digest,
                embedding.vector_manifest_digest,
                embedding.chunk_vector_binding_digest,
                embedding.governance_binding_digest,
                policy.index_profile_digest,
                policy.staging_boundary_digest,
                policy.authorization_payload_profile_digest,
                purpose,
                subject_digest,
                browser_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, embedding_set_id, idempotency_key])
        existing = await self._repository.get_claim_by_embedding_set(
            embedding_set_id=embedding_set_id
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
        seed = self._digest([embedding_set_id, request_binding_digest])
        index_staging_id = f"operational-knowledge-index-staging.{seed[:24]}"
        claim = OperationalKnowledgeIndexClaim(
            claim_id=f"operational-knowledge-index-claim.{seed[:24]}",
            schema_version=INDEX_CLAIM_SCHEMA,
            version=1,
            embedding_set_id=embedding_set_id,
            index_staging_id=index_staging_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            organization_id=embedding.organization_id,
            environment_id=embedding.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_index_staging_requested",
            embedding_set_id,
        )
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_embedding_set(
                embedding_set_id=embedding_set_id
            )
            if concurrent is None:
                raise OperationalKnowledgeIndexUncertainError(
                    "operational_knowledge_index_claim_uncertain"
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
            "operational_knowledge_index_staging_claimed",
            index_staging_id,
        )
        instruction = OperationalKnowledgeIndexInstruction(
            index_staging_id=index_staging_id,
            organization_id=embedding.organization_id,
            environment_id=embedding.environment_id,
            embedding_set_id=embedding_set_id,
            embedding_set_digest=embedding_set_digest,
            chunk_set_id=embedding.chunk_set_id,
            knowledge_item_id=embedding.knowledge_item_id,
            classification=embedding.classification,
            access_policy_id=embedding.access_policy_id,
            retention_policy_id=embedding.retention_policy_id,
            governance_binding_digest=embedding.governance_binding_digest,
            model_profile_digest=embedding.model_profile_digest,
            vector_dimension=embedding.vector_dimension,
            normalization_profile_id=embedding.normalization_profile_id,
            distance_metric_id=embedding.distance_metric_id,
            embedding_count=embedding.embedding_count,
            vector_manifest_digest=embedding.vector_manifest_digest,
            chunk_vector_binding_digest=embedding.chunk_vector_binding_digest,
            steward_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            index_profile_id=policy.index_profile_id,
            index_profile_digest=policy.index_profile_digest,
            staging_boundary_id=policy.staging_boundary_id,
            staging_boundary_digest=policy.staging_boundary_digest,
            authorization_payload_profile_digest=(policy.authorization_payload_profile_digest),
            maximum_batch_size=policy.maximum_batch_size,
            purpose=purpose,
            requested_at=now,
        )
        try:
            receipt = await self._indexer.stage_and_validate(instruction)
            self._verify_receipt(receipt, instruction, policy)
        except OperationalKnowledgeIndexError:
            raise
        except Exception as error:
            raise OperationalKnowledgeIndexUncertainError(
                "operational_knowledge_index_outcome_uncertain"
            ) from error
        upstream = tuple(
            sorted(
                {
                    embedding.publication_steward_subject_digest,
                    embedding.materialization_steward_subject_digest,
                    embedding.chunking_steward_subject_digest,
                    embedding.embedded_by_subject_digest,
                    *embedding.upstream_accountable_subject_digests,
                }
            )
        )
        record = OperationalKnowledgeIndexRecord(
            index_staging_id=index_staging_id,
            schema_version=INDEX_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            embedding_set_id=embedding_set_id,
            embedding_set_digest=embedding_set_digest,
            chunk_set_id=embedding.chunk_set_id,
            materialization_id=embedding.materialization_id,
            preparation_id=embedding.preparation_id,
            resolution_id=embedding.resolution_id,
            review_request_id=embedding.review_request_id,
            source_draft_id=embedding.source_draft_id,
            knowledge_item_id=embedding.knowledge_item_id,
            organization_id=embedding.organization_id,
            environment_id=embedding.environment_id,
            classification=embedding.classification,
            access_policy_id=embedding.access_policy_id,
            retention_policy_id=embedding.retention_policy_id,
            index_steward_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            index_policy_id=policy.policy_id,
            index_policy_digest=policy.canonical_digest,
            index_policy_version=policy.policy_version,
            index_profile_id=policy.index_profile_id,
            index_profile_digest=policy.index_profile_digest,
            staging_boundary_id=policy.staging_boundary_id,
            staging_boundary_digest=policy.staging_boundary_digest,
            authorization_payload_profile_digest=(policy.authorization_payload_profile_digest),
            indexer_id=receipt.indexer_id,
            index_receipt_digest=receipt.canonical_digest,
            model_profile_digest=embedding.model_profile_digest,
            vector_dimension=embedding.vector_dimension,
            normalization_profile_id=embedding.normalization_profile_id,
            distance_metric_id=embedding.distance_metric_id,
            embedding_count=embedding.embedding_count,
            vector_manifest_digest=embedding.vector_manifest_digest,
            chunk_vector_binding_digest=embedding.chunk_vector_binding_digest,
            governance_binding_digest=embedding.governance_binding_digest,
            staged_point_count=receipt.staged_point_count,
            projection_manifest_digest=receipt.projection_manifest_digest,
            point_coverage_digest=receipt.point_coverage_digest,
            authorization_metadata_validation_digest=(
                receipt.authorization_metadata_validation_digest
            ),
            model_compatibility_validation_digest=(receipt.model_compatibility_validation_digest),
            isolation_validation_digest=receipt.isolation_validation_digest,
            reconciliation_digest=receipt.reconciliation_digest,
            validated_at=receipt.validated_at,
            instance_state=INDEX_VALIDATED_STATE,
            purpose=purpose,
            canonical_digest="0" * 64,
            upstream_accountable_subject_digests=upstream,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise OperationalKnowledgeIndexUncertainError(
                "operational_knowledge_index_persistence_uncertain"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_index_validated",
            index_staging_id,
        )
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        index_staging_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeIndexRecord:
        self._require_human(actor)
        record = await self._repository.get(index_staging_id=index_staging_id)
        if record is None:
            raise OperationalKnowledgeIndexError("operational_knowledge_index_not_found")
        policy = await self._policy_source.get_by_id(policy_id=record.index_policy_id)
        if policy is None or not policy.issued_at <= self._clock() < policy.expires_at:
            raise OperationalKnowledgeIndexError("operational_knowledge_index_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            subject_digest != record.index_steward_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise OperationalKnowledgeIndexError("operational_knowledge_index_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_index_read",
            index_staging_id,
            permission_id=KNOWLEDGE_INDEX_STAGING_READ,
        )
        return replace(record, reused=True)

    async def source_for_retrieval_publication(
        self, *, index_staging_id: str
    ) -> OperationalKnowledgeIndexRecord | None:
        return await self._repository.get(index_staging_id=index_staging_id)

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: OperationalKnowledgeIndexClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgeIndexRecord:
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeIndexError("operational_knowledge_index_idempotency_conflict")
        record = await self._repository.get(index_staging_id=claim.index_staging_id)
        if record is None:
            raise OperationalKnowledgeIndexError("operational_knowledge_index_already_claimed")
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_index_read",
            record.index_staging_id,
            permission_id=KNOWLEDGE_INDEX_STAGING_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _verify_receipt(
        cls,
        receipt: OperationalKnowledgeIndexReceipt,
        instruction: OperationalKnowledgeIndexInstruction,
        policy: OperationalKnowledgeIndexPolicySnapshot,
    ) -> None:
        if (
            receipt.index_staging_id != instruction.index_staging_id
            or receipt.indexer_id != policy.required_indexer_id
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or receipt.embedding_set_digest != instruction.embedding_set_digest
            or receipt.model_profile_digest != instruction.model_profile_digest
            or receipt.vector_dimension != instruction.vector_dimension
            or receipt.normalization_profile_id != instruction.normalization_profile_id
            or receipt.distance_metric_id != instruction.distance_metric_id
            or receipt.index_profile_digest != policy.index_profile_digest
            or receipt.staging_boundary_digest != policy.staging_boundary_digest
            or receipt.expected_point_count != instruction.embedding_count
            or receipt.staged_point_count != instruction.embedding_count
            or not receipt.projection_sealed
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or not receipt.signature_verified
        ):
            raise OperationalKnowledgeIndexError("operational_knowledge_index_receipt_invalid")

    @classmethod
    def _verify_policy(cls, policy: OperationalKnowledgeIndexPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._payload(policy)):
            raise OperationalKnowledgeIndexError("operational_knowledge_index_policy_invalid")

    @staticmethod
    def _payload(
        value: OperationalKnowledgeEmbeddingRecord
        | OperationalKnowledgeIndexPolicySnapshot
        | OperationalKnowledgeIndexClaim
        | OperationalKnowledgeIndexReceipt
        | OperationalKnowledgeIndexRecord,
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
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise OperationalKnowledgeIndexError("operational_knowledge_index_human_required")

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeIndexError("operational_knowledge_index_source_not_found")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = KNOWLEDGE_INDEX_STAGING_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-index-staging-validation",
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
                resource_type="resource.knowledge.operational-index-staging",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )


def build_development_operational_knowledge_index_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
    embedding_policy: OperationalKnowledgeEmbeddingPolicySnapshot,
) -> OperationalKnowledgeIndexPolicySnapshot:
    digest = OperationalKnowledgeIndexStagingValidationService._digest
    index_profile_id = "knowledge-index-profile.development-v1"
    staging_boundary_id = "index-staging-boundary.local-development"
    authorization_payload_profile_digest = digest(
        ["knowledge-index-authorization-payload.v1", organization_id, environment_id]
    )
    index_profile_digest = digest(
        [
            index_profile_id,
            embedding_policy.model_profile_digest,
            embedding_policy.vector_dimension,
            embedding_policy.normalization_profile_id,
            embedding_policy.distance_metric_id,
            authorization_payload_profile_digest,
            "inactive-sealed-projection-v1",
        ]
    )
    policy = OperationalKnowledgeIndexPolicySnapshot(
        policy_id="operational-knowledge-index-policy.development",
        schema_version=INDEX_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.operational-knowledge-index-development-v1",
        required_embedding_set_schema="atlas.operational-knowledge-embedding-set.v1",
        required_embedding_set_state=EMBEDDINGS_CREATED_STATE,
        required_model_profile_digest=embedding_policy.model_profile_digest,
        required_vector_dimension=embedding_policy.vector_dimension,
        required_normalization_profile_id=embedding_policy.normalization_profile_id,
        required_distance_metric_id=embedding_policy.distance_metric_id,
        index_profile_id=index_profile_id,
        index_profile_digest=index_profile_digest,
        staging_boundary_id=staging_boundary_id,
        staging_boundary_digest=digest(
            [staging_boundary_id, organization_id, environment_id, "inactive"]
        ),
        authorization_payload_profile_digest=authorization_payload_profile_digest,
        maximum_points=4096,
        maximum_batch_size=64,
        maximum_authentication_age_minutes=15,
        subject_digest_salt_digest=embedding_policy.subject_digest_salt_digest,
        browser_binding_key_digest=digest(["operational-knowledge-index-staging-browser-key"]),
        required_indexer_id="operational-knowledge-indexer.synthetic",
        index_profile_owner_id="subject.operational-knowledge-index-profile-owner",
        signed_by="subject.operational-knowledge-index-policy-signer",
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(OperationalKnowledgeIndexStagingValidationService._payload(policy)),
    )
