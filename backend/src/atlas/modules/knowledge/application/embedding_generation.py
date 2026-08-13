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
    KNOWLEDGE_EMBEDDING_GENERATION_CREATE,
    KNOWLEDGE_EMBEDDING_GENERATION_READ,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.application.embedding_generation_ports import (
    OperationalKnowledgeChunkSetSource,
    OperationalKnowledgeEmbedder,
    OperationalKnowledgeEmbeddingError,
    OperationalKnowledgeEmbeddingPermissionAuthorizer,
    OperationalKnowledgeEmbeddingPolicySource,
    OperationalKnowledgeEmbeddingRepository,
    OperationalKnowledgeEmbeddingUncertainError,
)
from atlas.modules.knowledge.domain.deterministic_chunking import (
    CHUNKS_CREATED_STATE,
    OperationalKnowledgeChunkingRecord,
)
from atlas.modules.knowledge.domain.embedding_generation import (
    EMBEDDINGS_CREATED_STATE,
    OperationalKnowledgeEmbeddingClaim,
    OperationalKnowledgeEmbeddingInstruction,
    OperationalKnowledgeEmbeddingPolicySnapshot,
    OperationalKnowledgeEmbeddingReceipt,
    OperationalKnowledgeEmbeddingRecord,
)

EMBEDDING_POLICY_SCHEMA = "atlas.operational-knowledge-embedding-policy.v1"
EMBEDDING_CLAIM_SCHEMA = "atlas.operational-knowledge-embedding-claim.v1"
EMBEDDING_RECORD_SCHEMA = "atlas.operational-knowledge-embedding-set.v1"


class OperationalKnowledgeEmbeddingGenerationService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeEmbeddingRepository,
        chunk_source: OperationalKnowledgeChunkSetSource,
        policy_source: OperationalKnowledgeEmbeddingPolicySource,
        permission_authorizer: OperationalKnowledgeEmbeddingPermissionAuthorizer,
        embedder: OperationalKnowledgeEmbedder,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._chunk_source = chunk_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._embedder = embedder
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        chunk_set_id: str,
        chunk_set_digest: str,
        embedding_policy_id: str,
        embedding_policy_digest: str,
        purpose: str,
        protected_boundary_acknowledged: bool,
        immutable_model_profile_acknowledged: bool,
        no_index_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeEmbeddingRecord:
        self._require_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    protected_boundary_acknowledged,
                    immutable_model_profile_acknowledged,
                    no_index_or_operational_authority_acknowledged,
                )
            )
        ):
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_request_invalid"
            )
        chunk = await self._chunk_source.source_for_embedding(chunk_set_id=chunk_set_id)
        if chunk is None:
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_source_not_found"
            )
        policy = await self._policy_source.get_by_id(policy_id=embedding_policy_id)
        if policy is None:
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        later_authority = any(
            (
                chunk.embeddings_created,
                chunk.index_staged,
                chunk.index_validated,
                chunk.knowledge_published,
                chunk.retrieval_published,
                chunk.model_context_available,
                chunk.graph_updated,
                chunk.scheduled,
                chunk.workflow_continued,
                chunk.execution_authorized,
                chunk.deployment_approved,
                chunk.infrastructure_mutation_performed,
            )
        )
        if (
            chunk.chunk_set_id != chunk_set_id
            or chunk.canonical_digest != chunk_set_digest
            or chunk.canonical_digest != self._digest(self._payload(chunk))
            or chunk.schema_version != policy.required_chunk_set_schema
            or chunk.instance_state != policy.required_chunk_set_state
            or chunk.instance_state != CHUNKS_CREATED_STATE
            or not all(
                (
                    chunk.knowledge_approved,
                    chunk.publication_ready,
                    chunk.publication_prepared,
                    chunk.source_materialized,
                    chunk.chunks_created,
                )
            )
            or later_authority
            or chunk.chunk_count > policy.maximum_chunks
            or chunk.total_chunk_tokens > policy.maximum_total_tokens
            or policy.canonical_digest != embedding_policy_digest
            or policy.organization_id != chunk.organization_id
            or policy.environment_id != chunk.environment_id
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_source_invalid"
            )
        self._require_scope(actor, chunk.organization_id, chunk.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        separated_digests = {
            chunk.publication_steward_subject_digest,
            chunk.materialization_steward_subject_digest,
            chunk.chunked_by_subject_digest,
            *chunk.upstream_accountable_subject_digests,
        }
        separated_identities = {
            policy.signed_by,
            policy.required_embedder_id,
            policy.model_owner_id,
            chunk.chunker_id,
        }
        if subject_digest in separated_digests or actor.subject_id in separated_identities:
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=chunk.organization_id,
            environment_id=chunk.environment_id,
            correlation_id=correlation_id,
        )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        request_binding_digest = self._digest(
            [
                chunk_set_id,
                chunk_set_digest,
                embedding_policy_digest,
                chunk.protected_material_digest,
                chunk.ordered_chunk_manifest_digest,
                chunk.chunking_profile_digest,
                chunk.governance_binding_digest,
                policy.model_profile_digest,
                policy.model_artifact_digest,
                policy.tokenizer_profile_digest,
                purpose,
                subject_digest,
                browser_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, chunk_set_id, idempotency_key])
        existing = await self._repository.get_claim_by_chunk_set(chunk_set_id=chunk_set_id)
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
        seed = self._digest([chunk_set_id, request_binding_digest])
        embedding_set_id = f"operational-knowledge-embedding-set.{seed[:24]}"
        claim = OperationalKnowledgeEmbeddingClaim(
            claim_id=f"operational-knowledge-embedding-claim.{seed[:24]}",
            schema_version=EMBEDDING_CLAIM_SCHEMA,
            version=1,
            chunk_set_id=chunk_set_id,
            embedding_set_id=embedding_set_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            organization_id=chunk.organization_id,
            environment_id=chunk.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_embedding_requested",
            chunk_set_id,
        )
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_chunk_set(chunk_set_id=chunk_set_id)
            if concurrent is None:
                raise OperationalKnowledgeEmbeddingUncertainError(
                    "operational_knowledge_embedding_claim_uncertain"
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
            "operational_knowledge_embedding_claimed",
            embedding_set_id,
        )
        instruction = OperationalKnowledgeEmbeddingInstruction(
            embedding_set_id=embedding_set_id,
            organization_id=chunk.organization_id,
            environment_id=chunk.environment_id,
            chunk_set_id=chunk_set_id,
            chunk_set_digest=chunk_set_digest,
            materialization_id=chunk.materialization_id,
            preparation_id=chunk.preparation_id,
            knowledge_item_id=chunk.knowledge_item_id,
            protected_material_digest=chunk.protected_material_digest,
            ordered_chunk_manifest_digest=chunk.ordered_chunk_manifest_digest,
            chunking_profile_digest=chunk.chunking_profile_digest,
            governance_binding_digest=chunk.governance_binding_digest,
            chunk_count=chunk.chunk_count,
            total_chunk_tokens=chunk.total_chunk_tokens,
            steward_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            model_profile_id=policy.model_profile_id,
            model_profile_digest=policy.model_profile_digest,
            model_artifact_digest=policy.model_artifact_digest,
            tokenizer_profile_digest=policy.tokenizer_profile_digest,
            vector_dimension=policy.vector_dimension,
            normalization_profile_id=policy.normalization_profile_id,
            distance_metric_id=policy.distance_metric_id,
            data_boundary_id=policy.data_boundary_id,
            data_boundary_digest=policy.data_boundary_digest,
            maximum_batch_size=policy.maximum_batch_size,
            purpose=purpose,
            requested_at=now,
        )
        try:
            receipt = await self._embedder.embed(instruction)
            self._verify_receipt(receipt, instruction, policy)
        except OperationalKnowledgeEmbeddingError:
            raise
        except Exception as error:
            raise OperationalKnowledgeEmbeddingUncertainError(
                "operational_knowledge_embedding_outcome_uncertain"
            ) from error
        record = OperationalKnowledgeEmbeddingRecord(
            embedding_set_id=embedding_set_id,
            schema_version=EMBEDDING_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            chunk_set_id=chunk_set_id,
            chunk_set_digest=chunk_set_digest,
            materialization_id=chunk.materialization_id,
            preparation_id=chunk.preparation_id,
            resolution_id=chunk.resolution_id,
            review_request_id=chunk.review_request_id,
            source_draft_id=chunk.source_draft_id,
            knowledge_item_id=chunk.knowledge_item_id,
            organization_id=chunk.organization_id,
            environment_id=chunk.environment_id,
            classification=chunk.classification,
            access_policy_id=chunk.access_policy_id,
            retention_policy_id=chunk.retention_policy_id,
            publication_steward_subject_digest=chunk.publication_steward_subject_digest,
            materialization_steward_subject_digest=(chunk.materialization_steward_subject_digest),
            chunking_steward_subject_digest=chunk.chunked_by_subject_digest,
            embedded_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            embedding_policy_id=policy.policy_id,
            embedding_policy_digest=policy.canonical_digest,
            embedding_policy_version=policy.policy_version,
            model_profile_id=policy.model_profile_id,
            model_profile_digest=policy.model_profile_digest,
            model_artifact_digest=policy.model_artifact_digest,
            tokenizer_profile_digest=policy.tokenizer_profile_digest,
            vector_dimension=policy.vector_dimension,
            normalization_profile_id=policy.normalization_profile_id,
            distance_metric_id=policy.distance_metric_id,
            data_boundary_id=policy.data_boundary_id,
            data_boundary_digest=policy.data_boundary_digest,
            embedder_id=receipt.embedder_id,
            embedding_receipt_digest=receipt.canonical_digest,
            protected_material_digest=chunk.protected_material_digest,
            ordered_chunk_manifest_digest=chunk.ordered_chunk_manifest_digest,
            chunking_profile_digest=chunk.chunking_profile_digest,
            governance_binding_digest=chunk.governance_binding_digest,
            embedding_count=receipt.embedding_count,
            vector_manifest_digest=receipt.vector_manifest_digest,
            chunk_vector_binding_digest=receipt.chunk_vector_binding_digest,
            numeric_validation_digest=receipt.numeric_validation_digest,
            coverage_validation_digest=receipt.coverage_validation_digest,
            resource_evidence_digest=receipt.resource_evidence_digest,
            embedded_at=receipt.embedded_at,
            instance_state=EMBEDDINGS_CREATED_STATE,
            purpose=purpose,
            canonical_digest="0" * 64,
            upstream_accountable_subject_digests=tuple(
                sorted(
                    {
                        chunk.publication_steward_subject_digest,
                        chunk.materialization_steward_subject_digest,
                        chunk.chunked_by_subject_digest,
                        *chunk.upstream_accountable_subject_digests,
                    }
                )
            ),
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise OperationalKnowledgeEmbeddingUncertainError(
                "operational_knowledge_embedding_persistence_uncertain"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_embedding_recorded",
            embedding_set_id,
        )
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        embedding_set_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeEmbeddingRecord:
        self._require_human(actor)
        record = await self._repository.get(embedding_set_id=embedding_set_id)
        if record is None:
            raise OperationalKnowledgeEmbeddingError("operational_knowledge_embedding_not_found")
        policy = await self._policy_source.get_by_id(policy_id=record.embedding_policy_id)
        if policy is None or not policy.issued_at <= self._clock() < policy.expires_at:
            raise OperationalKnowledgeEmbeddingError("operational_knowledge_embedding_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            subject_digest != record.embedded_by_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise OperationalKnowledgeEmbeddingError("operational_knowledge_embedding_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_embedding_read",
            embedding_set_id,
            permission_id=KNOWLEDGE_EMBEDDING_GENERATION_READ,
        )
        return replace(record, reused=True)

    async def source_for_index_staging(
        self, *, embedding_set_id: str
    ) -> OperationalKnowledgeEmbeddingRecord | None:
        return await self._repository.get(embedding_set_id=embedding_set_id)

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: OperationalKnowledgeEmbeddingClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgeEmbeddingRecord:
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_idempotency_conflict"
            )
        record = await self._repository.get(embedding_set_id=claim.embedding_set_id)
        if record is None:
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_already_claimed"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_embedding_read",
            record.embedding_set_id,
            permission_id=KNOWLEDGE_EMBEDDING_GENERATION_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _verify_receipt(
        cls,
        receipt: OperationalKnowledgeEmbeddingReceipt,
        instruction: OperationalKnowledgeEmbeddingInstruction,
        policy: OperationalKnowledgeEmbeddingPolicySnapshot,
    ) -> None:
        if (
            receipt.embedding_set_id != instruction.embedding_set_id
            or receipt.embedder_id != policy.required_embedder_id
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or receipt.chunk_set_digest != instruction.chunk_set_digest
            or receipt.ordered_chunk_manifest_digest != instruction.ordered_chunk_manifest_digest
            or receipt.model_profile_digest != policy.model_profile_digest
            or receipt.model_artifact_digest != policy.model_artifact_digest
            or receipt.tokenizer_profile_digest != policy.tokenizer_profile_digest
            or receipt.vector_dimension != policy.vector_dimension
            or receipt.normalization_profile_id != policy.normalization_profile_id
            or receipt.distance_metric_id != policy.distance_metric_id
            or receipt.data_boundary_digest != policy.data_boundary_digest
            or receipt.embedding_count != instruction.chunk_count
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or not receipt.signature_verified
        ):
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_receipt_invalid"
            )

    @classmethod
    def _verify_policy(cls, policy: OperationalKnowledgeEmbeddingPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._payload(policy)):
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_policy_invalid"
            )

    @staticmethod
    def _payload(
        value: OperationalKnowledgeChunkingRecord
        | OperationalKnowledgeEmbeddingPolicySnapshot
        | OperationalKnowledgeEmbeddingClaim
        | OperationalKnowledgeEmbeddingReceipt
        | OperationalKnowledgeEmbeddingRecord,
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
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_human_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = KNOWLEDGE_EMBEDDING_GENERATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-embedding-generation",
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
                resource_type="resource.knowledge.operational-embedding-generation",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )


def build_development_operational_knowledge_embedding_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeEmbeddingPolicySnapshot:
    digest = OperationalKnowledgeEmbeddingGenerationService._digest
    model_profile_id = "knowledge-embedding-model.development-v1"
    model_artifact_digest = digest([model_profile_id, "synthetic-local-model-artifact-v1"])
    tokenizer_profile_digest = digest([model_profile_id, "synthetic-tokenizer-v1"])
    data_boundary_id = "data-boundary.local-development"
    policy = OperationalKnowledgeEmbeddingPolicySnapshot(
        policy_id="operational-knowledge-embedding-policy.development",
        schema_version=EMBEDDING_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.operational-knowledge-embedding-development-v1",
        required_chunk_set_schema="atlas.operational-knowledge-chunk-set.v1",
        required_chunk_set_state=CHUNKS_CREATED_STATE,
        model_profile_id=model_profile_id,
        model_profile_digest=digest(
            [
                model_profile_id,
                model_artifact_digest,
                tokenizer_profile_digest,
                384,
                "vector-normalization.l2",
                "vector-distance.cosine",
            ]
        ),
        model_artifact_digest=model_artifact_digest,
        tokenizer_profile_digest=tokenizer_profile_digest,
        vector_dimension=384,
        normalization_profile_id="vector-normalization.l2",
        distance_metric_id="vector-distance.cosine",
        data_boundary_id=data_boundary_id,
        data_boundary_digest=digest([data_boundary_id, organization_id, environment_id]),
        maximum_chunks=4096,
        maximum_total_tokens=8_388_608,
        maximum_batch_size=64,
        maximum_authentication_age_minutes=15,
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        browser_binding_key_digest=digest(
            ["operational-knowledge-embedding-generation-browser-key"]
        ),
        required_embedder_id="operational-knowledge-embedder.synthetic",
        model_owner_id="subject.operational-knowledge-model-owner",
        signed_by="subject.operational-knowledge-embedding-policy-signer",
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(OperationalKnowledgeEmbeddingGenerationService._payload(policy)),
    )
