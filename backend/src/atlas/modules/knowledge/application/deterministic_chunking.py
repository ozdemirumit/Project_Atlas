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
    KNOWLEDGE_DETERMINISTIC_CHUNKING_CREATE,
    KNOWLEDGE_DETERMINISTIC_CHUNKING_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.application.deterministic_chunking_ports import (
    OperationalKnowledgeChunker,
    OperationalKnowledgeChunkingError,
    OperationalKnowledgeChunkingLineage,
    OperationalKnowledgeChunkingPermissionAuthorizer,
    OperationalKnowledgeChunkingPolicySource,
    OperationalKnowledgeChunkingPreparationSource,
    OperationalKnowledgeChunkingRepository,
    OperationalKnowledgeChunkingUncertainError,
    OperationalKnowledgeSourceMaterializationRecordSource,
)
from atlas.modules.knowledge.domain.deterministic_chunking import (
    CHUNKS_CREATED_STATE,
    OperationalKnowledgeChunkingClaim,
    OperationalKnowledgeChunkingInstruction,
    OperationalKnowledgeChunkingPolicySnapshot,
    OperationalKnowledgeChunkingReceipt,
    OperationalKnowledgeChunkingRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import DRAFT_OPERATIONAL_KNOWLEDGE_CREATED
from atlas.modules.knowledge.domain.final_resolution import FINAL_APPROVED, FINAL_APPROVED_STATE
from atlas.modules.knowledge.domain.publication_preparation import PUBLICATION_PREPARED_STATE
from atlas.modules.knowledge.domain.review_decision import (
    OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED,
    TRACKS,
)
from atlas.modules.knowledge.domain.source_materialization import SOURCE_MATERIALIZED_STATE

CHUNKING_POLICY_SCHEMA = "atlas.operational-knowledge-chunking-policy.v1"
CHUNKING_CLAIM_SCHEMA = "atlas.operational-knowledge-chunking-claim.v1"
CHUNKING_RECORD_SCHEMA = "atlas.operational-knowledge-chunk-set.v1"


class OperationalKnowledgeDeterministicChunkingService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeChunkingRepository,
        materialization_source: OperationalKnowledgeSourceMaterializationRecordSource,
        preparation_source: OperationalKnowledgeChunkingPreparationSource,
        lineage_source: OperationalKnowledgeChunkingLineage,
        policy_source: OperationalKnowledgeChunkingPolicySource,
        permission_authorizer: OperationalKnowledgeChunkingPermissionAuthorizer,
        chunker: OperationalKnowledgeChunker,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._materialization_source = materialization_source
        self._preparation_source = preparation_source
        self._lineage_source = lineage_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._chunker = chunker
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        materialization_id: str,
        materialization_digest: str,
        chunking_policy_id: str,
        chunking_policy_digest: str,
        purpose: str,
        protected_boundary_acknowledged: bool,
        immutable_profile_acknowledged: bool,
        no_embedding_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeChunkingRecord:
        self._require_enterprise_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    protected_boundary_acknowledged,
                    immutable_profile_acknowledged,
                    no_embedding_or_operational_authority_acknowledged,
                )
            )
        ):
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_request_invalid"
            )
        materialization = await self._materialization_source.source_for_chunking(
            materialization_id=materialization_id
        )
        if materialization is None:
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_source_not_found"
            )
        preparation = await self._preparation_source.source_materialization_preparation(
            preparation_id=materialization.preparation_id
        )
        if preparation is None:
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_source_not_found"
            )
        try:
            (
                resolution,
                decisions,
                request,
                draft,
            ) = await self._lineage_source.publication_preparation_source(
                resolution_id=materialization.resolution_id
            )
        except Exception as error:
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=chunking_policy_id)
        if policy is None:
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        ordered = tuple(sorted(decisions, key=lambda item: item.track_code))
        later_authority = any(
            (
                materialization.chunks_created,
                materialization.embeddings_created,
                materialization.index_staged,
                materialization.index_validated,
                materialization.knowledge_published,
                materialization.retrieval_published,
                materialization.model_context_available,
                materialization.graph_updated,
                materialization.scheduled,
                materialization.workflow_continued,
                materialization.execution_authorized,
                materialization.deployment_approved,
                materialization.infrastructure_mutation_performed,
            )
        )
        if (
            materialization.materialization_id != materialization_id
            or materialization.canonical_digest != materialization_digest
            or materialization.schema_version != policy.required_materialization_schema
            or materialization.instance_state != policy.required_materialization_state
            or materialization.instance_state != SOURCE_MATERIALIZED_STATE
            or not all(
                (
                    materialization.knowledge_approved,
                    materialization.publication_ready,
                    materialization.publication_prepared,
                    materialization.source_materialized,
                )
            )
            or later_authority
            or preparation.preparation_id != materialization.preparation_id
            or preparation.canonical_digest != materialization.preparation_digest
            or preparation.instance_state != PUBLICATION_PREPARED_STATE
            or preparation.resolution_id != materialization.resolution_id
            or preparation.resolution_digest != materialization.resolution_digest
            or preparation.review_request_id != materialization.review_request_id
            or preparation.source_draft_id != materialization.source_draft_id
            or preparation.source_draft_digest != materialization.source_draft_digest
            or preparation.knowledge_item_id != materialization.knowledge_item_id
            or preparation.source_artifact_digest != materialization.source_artifact_digest
            or preparation.chunking_profile_digest != materialization.chunking_profile_digest
            or preparation.organization_id != materialization.organization_id
            or preparation.environment_id != materialization.environment_id
            or resolution.resolution_id != materialization.resolution_id
            or resolution.canonical_digest != materialization.resolution_digest
            or resolution.instance_state != FINAL_APPROVED_STATE
            or resolution.disposition_code != FINAL_APPROVED
            or not resolution.knowledge_approved
            or not resolution.publication_ready
            or request.review_request_id != materialization.review_request_id
            or draft.draft_id != materialization.source_draft_id
            or draft.canonical_digest != materialization.source_draft_digest
            or draft.instance_state != DRAFT_OPERATIONAL_KNOWLEDGE_CREATED
            or len(ordered) != 2
            or {item.track_code for item in ordered} != TRACKS
            or tuple(item.decision_id for item in ordered) != resolution.decision_ids
            or any(
                item.instance_state != OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED
                or item.disposition_code != "review-disposition.passed"
                or item.correction_required
                or item.correction_created
                for item in ordered
            )
            or policy.canonical_digest != chunking_policy_digest
            or policy.organization_id != materialization.organization_id
            or policy.environment_id != materialization.environment_id
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgeChunkingError("operational_knowledge_chunking_source_invalid")
        self._require_scope(actor, materialization.organization_id, materialization.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        separated_digests = {
            materialization.publication_steward_subject_digest,
            materialization.materialized_by_subject_digest,
            preparation.final_approver_subject_digest,
            preparation.prepared_by_subject_digest,
            *(item.decided_by_subject_digest for item in ordered),
        }
        separated_identities = {
            draft.curated_by,
            policy.signed_by,
            policy.required_chunker_id,
            preparation.preparer_id,
            materialization.materializer_id,
        }
        if subject_digest in separated_digests or actor.subject_id in separated_identities:
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=materialization.organization_id,
            environment_id=materialization.environment_id,
            correlation_id=correlation_id,
        )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        request_binding_digest = self._digest(
            [
                materialization_id,
                materialization_digest,
                chunking_policy_digest,
                materialization.protected_material_digest,
                materialization.chunking_profile_digest,
                materialization.governance_binding_digest,
                policy.algorithm_profile_digest,
                purpose,
                subject_digest,
                browser_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, materialization_id, idempotency_key])
        existing = await self._repository.get_claim_by_materialization(
            materialization_id=materialization_id
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
        seed = self._digest([materialization_id, request_binding_digest])
        chunk_set_id = f"operational-knowledge-chunk-set.{seed[:24]}"
        claim = OperationalKnowledgeChunkingClaim(
            claim_id=f"operational-knowledge-chunking-claim.{seed[:24]}",
            schema_version=CHUNKING_CLAIM_SCHEMA,
            version=1,
            materialization_id=materialization_id,
            chunk_set_id=chunk_set_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            organization_id=materialization.organization_id,
            environment_id=materialization.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_chunking_requested",
            materialization_id,
        )
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_materialization(
                materialization_id=materialization_id
            )
            if concurrent is None:
                raise OperationalKnowledgeChunkingUncertainError(
                    "operational_knowledge_chunking_claim_uncertain"
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
            actor, correlation_id, "operational_knowledge_chunking_claimed", chunk_set_id
        )
        instruction = OperationalKnowledgeChunkingInstruction(
            chunk_set_id=chunk_set_id,
            organization_id=materialization.organization_id,
            environment_id=materialization.environment_id,
            materialization_id=materialization_id,
            materialization_digest=materialization_digest,
            preparation_id=materialization.preparation_id,
            preparation_digest=materialization.preparation_digest,
            knowledge_item_id=materialization.knowledge_item_id,
            source_artifact_digest=materialization.source_artifact_digest,
            protected_material_digest=materialization.protected_material_digest,
            chunking_profile_digest=materialization.chunking_profile_digest,
            governance_binding_digest=materialization.governance_binding_digest,
            media_type=materialization.media_type,
            canonical_characters=materialization.canonical_characters,
            steward_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            algorithm_profile_id=policy.algorithm_profile_id,
            algorithm_profile_digest=policy.algorithm_profile_digest,
            maximum_chunks=policy.maximum_chunks,
            maximum_chunk_characters=policy.maximum_chunk_characters,
            maximum_chunk_tokens=policy.maximum_chunk_tokens,
            maximum_overlap_characters=policy.maximum_overlap_characters,
            maximum_hierarchy_depth=policy.maximum_hierarchy_depth,
            purpose=purpose,
            requested_at=now,
        )
        try:
            receipt = await self._chunker.chunk(instruction)
            self._verify_receipt(receipt, instruction, policy)
        except OperationalKnowledgeChunkingError:
            raise
        except Exception as error:
            raise OperationalKnowledgeChunkingUncertainError(
                "operational_knowledge_chunking_outcome_uncertain"
            ) from error
        record = OperationalKnowledgeChunkingRecord(
            chunk_set_id=chunk_set_id,
            schema_version=CHUNKING_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            materialization_id=materialization_id,
            materialization_digest=materialization_digest,
            preparation_id=materialization.preparation_id,
            preparation_digest=materialization.preparation_digest,
            resolution_id=materialization.resolution_id,
            resolution_digest=materialization.resolution_digest,
            review_request_id=materialization.review_request_id,
            source_draft_id=materialization.source_draft_id,
            source_draft_digest=materialization.source_draft_digest,
            knowledge_item_id=materialization.knowledge_item_id,
            organization_id=materialization.organization_id,
            environment_id=materialization.environment_id,
            classification=materialization.classification,
            access_policy_id=materialization.access_policy_id,
            retention_policy_id=materialization.retention_policy_id,
            publication_steward_subject_digest=(materialization.publication_steward_subject_digest),
            materialization_steward_subject_digest=(materialization.materialized_by_subject_digest),
            chunked_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            chunking_policy_id=policy.policy_id,
            chunking_policy_digest=policy.canonical_digest,
            chunking_policy_version=policy.policy_version,
            algorithm_profile_id=policy.algorithm_profile_id,
            algorithm_profile_digest=policy.algorithm_profile_digest,
            chunker_id=receipt.chunker_id,
            chunking_receipt_digest=receipt.canonical_digest,
            source_artifact_digest=materialization.source_artifact_digest,
            protected_material_digest=materialization.protected_material_digest,
            chunking_profile_digest=materialization.chunking_profile_digest,
            ordered_chunk_manifest_digest=receipt.ordered_chunk_manifest_digest,
            structure_manifest_digest=receipt.structure_manifest_digest,
            governance_binding_digest=receipt.governance_binding_digest,
            determinism_evidence_digest=receipt.determinism_evidence_digest,
            media_type=materialization.media_type,
            chunk_count=receipt.chunk_count,
            total_chunk_characters=receipt.total_chunk_characters,
            total_chunk_tokens=receipt.total_chunk_tokens,
            minimum_chunk_characters=receipt.minimum_chunk_characters,
            maximum_chunk_characters=receipt.maximum_chunk_characters,
            overlap_characters=receipt.overlap_characters,
            chunked_at=receipt.chunked_at,
            instance_state=CHUNKS_CREATED_STATE,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise OperationalKnowledgeChunkingUncertainError(
                "operational_knowledge_chunking_persistence_uncertain"
            )
        await self._audit(
            actor, correlation_id, "operational_knowledge_chunking_recorded", chunk_set_id
        )
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        chunk_set_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeChunkingRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(chunk_set_id=chunk_set_id)
        if record is None:
            raise OperationalKnowledgeChunkingError("operational_knowledge_chunking_not_found")
        policy = await self._policy_source.get_by_id(policy_id=record.chunking_policy_id)
        if policy is None or not policy.issued_at <= self._clock() < policy.expires_at:
            raise OperationalKnowledgeChunkingError("operational_knowledge_chunking_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            subject_digest != record.chunked_by_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise OperationalKnowledgeChunkingError("operational_knowledge_chunking_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_chunking_read",
            chunk_set_id,
            permission_id=KNOWLEDGE_DETERMINISTIC_CHUNKING_READ,
        )
        return replace(record, reused=True)

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: OperationalKnowledgeChunkingClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgeChunkingRecord:
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_idempotency_conflict"
            )
        record = await self._repository.get(chunk_set_id=claim.chunk_set_id)
        if record is None:
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_already_claimed"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_chunking_read",
            record.chunk_set_id,
            permission_id=KNOWLEDGE_DETERMINISTIC_CHUNKING_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _verify_receipt(
        cls,
        receipt: OperationalKnowledgeChunkingReceipt,
        instruction: OperationalKnowledgeChunkingInstruction,
        policy: OperationalKnowledgeChunkingPolicySnapshot,
    ) -> None:
        if (
            receipt.chunk_set_id != instruction.chunk_set_id
            or receipt.chunker_id != policy.required_chunker_id
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or receipt.materialization_digest != instruction.materialization_digest
            or receipt.protected_material_digest != instruction.protected_material_digest
            or receipt.chunking_profile_digest != instruction.chunking_profile_digest
            or receipt.algorithm_profile_digest != instruction.algorithm_profile_digest
            or receipt.governance_binding_digest != instruction.governance_binding_digest
            or receipt.chunk_count > instruction.maximum_chunks
            or receipt.maximum_chunk_characters > instruction.maximum_chunk_characters
            or receipt.total_chunk_tokens
            > instruction.maximum_chunks * instruction.maximum_chunk_tokens
            or receipt.overlap_characters > instruction.maximum_overlap_characters
            or not receipt.signature_verified
        ):
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_receipt_invalid"
            )

    @classmethod
    def _verify_policy(cls, policy: OperationalKnowledgeChunkingPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._payload(policy)):
            raise OperationalKnowledgeChunkingError("operational_knowledge_chunking_policy_invalid")

    @staticmethod
    def _payload(
        value: OperationalKnowledgeChunkingPolicySnapshot
        | OperationalKnowledgeChunkingClaim
        | OperationalKnowledgeChunkingRecord,
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
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = KNOWLEDGE_DETERMINISTIC_CHUNKING_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-deterministic-chunking",
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
                resource_type="resource.knowledge.operational-deterministic-chunking",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )


def build_development_operational_knowledge_chunking_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeChunkingPolicySnapshot:
    digest = OperationalKnowledgeDeterministicChunkingService._digest
    algorithm_profile_id = "knowledge-chunking-algorithm.development-v1"
    policy = OperationalKnowledgeChunkingPolicySnapshot(
        policy_id="operational-knowledge-chunking-policy.development",
        schema_version=CHUNKING_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.operational-knowledge-chunking-development-v1",
        required_materialization_schema="atlas.operational-knowledge-source-materialization.v1",
        required_materialization_state=SOURCE_MATERIALIZED_STATE,
        algorithm_profile_id=algorithm_profile_id,
        algorithm_profile_digest=digest(
            [algorithm_profile_id, "heading-aware", "stable-order", "manifest-double-pass"]
        ),
        maximum_chunks=4096,
        maximum_chunk_characters=8192,
        maximum_chunk_tokens=2048,
        maximum_overlap_characters=512,
        maximum_hierarchy_depth=16,
        maximum_authentication_age_minutes=15,
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        browser_binding_key_digest=digest(["operational-knowledge-chunking-browser-key"]),
        required_chunker_id="operational-knowledge-chunker.synthetic",
        signed_by="subject.operational-knowledge-chunking-policy-signer",
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(OperationalKnowledgeDeterministicChunkingService._payload(policy)),
    )
