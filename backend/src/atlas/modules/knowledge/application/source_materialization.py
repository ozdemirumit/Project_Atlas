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
    KNOWLEDGE_SOURCE_MATERIALIZATION_CREATE,
    KNOWLEDGE_SOURCE_MATERIALIZATION_READ,
)
from atlas.modules.identity.domain.models import (
    AuthenticatedSubject,
    SubjectKind,
)
from atlas.modules.knowledge.application.source_materialization_ports import (
    OperationalKnowledgePublicationPreparationRecordSource,
    OperationalKnowledgeSourceLineage,
    OperationalKnowledgeSourceMaterializationError,
    OperationalKnowledgeSourceMaterializationPermissionAuthorizer,
    OperationalKnowledgeSourceMaterializationPolicySource,
    OperationalKnowledgeSourceMaterializationRepository,
    OperationalKnowledgeSourceMaterializationUncertainError,
    OperationalKnowledgeSourceMaterializer,
)
from atlas.modules.knowledge.domain.evidence_draft import DRAFT_OPERATIONAL_KNOWLEDGE_CREATED
from atlas.modules.knowledge.domain.final_resolution import FINAL_APPROVED, FINAL_APPROVED_STATE
from atlas.modules.knowledge.domain.publication_preparation import PUBLICATION_PREPARED_STATE
from atlas.modules.knowledge.domain.review_decision import (
    OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED,
    TRACKS,
)
from atlas.modules.knowledge.domain.source_materialization import (
    SOURCE_MATERIALIZED_STATE,
    OperationalKnowledgeSourceMaterializationClaim,
    OperationalKnowledgeSourceMaterializationInstruction,
    OperationalKnowledgeSourceMaterializationPolicySnapshot,
    OperationalKnowledgeSourceMaterializationReceipt,
    OperationalKnowledgeSourceMaterializationRecord,
)

SOURCE_MATERIALIZATION_POLICY_SCHEMA = (
    "atlas.operational-knowledge-source-materialization-policy.v1"
)
SOURCE_MATERIALIZATION_CLAIM_SCHEMA = "atlas.operational-knowledge-source-materialization-claim.v1"
SOURCE_MATERIALIZATION_RECORD_SCHEMA = "atlas.operational-knowledge-source-materialization.v1"


class OperationalKnowledgeSourceMaterializationService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeSourceMaterializationRepository,
        preparation_source: OperationalKnowledgePublicationPreparationRecordSource,
        lineage_source: OperationalKnowledgeSourceLineage,
        policy_source: OperationalKnowledgeSourceMaterializationPolicySource,
        permission_authorizer: OperationalKnowledgeSourceMaterializationPermissionAuthorizer,
        materializer: OperationalKnowledgeSourceMaterializer,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._preparation_source = preparation_source
        self._lineage_source = lineage_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._materializer = materializer
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        preparation_id: str,
        preparation_digest: str,
        materialization_policy_id: str,
        materialization_policy_digest: str,
        purpose: str,
        immutable_source_acknowledged: bool,
        protected_boundary_acknowledged: bool,
        no_chunking_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeSourceMaterializationRecord:
        self._require_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    immutable_source_acknowledged,
                    protected_boundary_acknowledged,
                    no_chunking_or_operational_authority_acknowledged,
                )
            )
        ):
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_request_invalid"
            )
        preparation = await self._preparation_source.source_materialization_preparation(
            preparation_id=preparation_id
        )
        if preparation is None:
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_source_not_found"
            )
        try:
            (
                resolution,
                decisions,
                request,
                draft,
            ) = await self._lineage_source.publication_preparation_source(
                resolution_id=preparation.resolution_id
            )
        except Exception as error:
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=materialization_policy_id)
        if policy is None:
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        ordered = tuple(sorted(decisions, key=lambda item: item.track_code))
        later_preparation_authority = any(
            (
                preparation.knowledge_published,
                preparation.chunks_created,
                preparation.embeddings_created,
                preparation.index_staged,
                preparation.index_validated,
                preparation.retrieval_published,
                preparation.model_context_available,
                preparation.graph_updated,
                preparation.scheduled,
                preparation.workflow_continued,
                preparation.execution_authorized,
                preparation.deployment_approved,
                preparation.infrastructure_mutation_performed,
            )
        )
        if (
            preparation.preparation_id != preparation_id
            or preparation.canonical_digest != preparation_digest
            or preparation.schema_version != policy.required_preparation_schema
            or preparation.instance_state != policy.required_preparation_state
            or preparation.instance_state != PUBLICATION_PREPARED_STATE
            or not all(
                (
                    preparation.knowledge_approved,
                    preparation.publication_ready,
                    preparation.publication_prepared,
                )
            )
            or later_preparation_authority
            or resolution.resolution_id != preparation.resolution_id
            or resolution.canonical_digest != preparation.resolution_digest
            or resolution.instance_state != FINAL_APPROVED_STATE
            or resolution.disposition_code != FINAL_APPROVED
            or not resolution.knowledge_approved
            or not resolution.publication_ready
            or resolution.review_request_id != preparation.review_request_id
            or resolution.source_draft_id != preparation.source_draft_id
            or resolution.source_draft_digest != preparation.source_draft_digest
            or resolution.knowledge_item_id != preparation.knowledge_item_id
            or request.review_request_id != preparation.review_request_id
            or draft.draft_id != preparation.source_draft_id
            or draft.canonical_digest != preparation.source_draft_digest
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
            or policy.canonical_digest != materialization_policy_digest
            or policy.organization_id != preparation.organization_id
            or policy.environment_id != preparation.environment_id
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_source_invalid"
            )
        self._require_scope(actor, preparation.organization_id, preparation.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        if (
            subject_digest
            in {
                preparation.prepared_by_subject_digest,
                preparation.final_approver_subject_digest,
                *(item.decided_by_subject_digest for item in ordered),
            }
            or actor.subject_id == draft.curated_by
            or actor.subject_id
            in {
                policy.signed_by,
                policy.required_materializer_id,
                preparation.preparer_id,
            }
        ):
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=preparation.organization_id,
            environment_id=preparation.environment_id,
            correlation_id=correlation_id,
        )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        request_binding_digest = self._digest(
            [
                preparation_id,
                preparation_digest,
                materialization_policy_digest,
                policy.canonicalization_profile_digest,
                policy.source_security_profile_digest,
                policy.media_type_allowlist_digest,
                purpose,
                subject_digest,
                browser_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, preparation_id, idempotency_key])
        existing = await self._repository.get_claim_by_preparation(preparation_id=preparation_id)
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
        seed = self._digest([preparation_id, request_binding_digest])
        materialization_id = f"operational-knowledge-source-materialization.{seed[:24]}"
        claim = OperationalKnowledgeSourceMaterializationClaim(
            claim_id=f"operational-knowledge-source-materialization-claim.{seed[:24]}",
            schema_version=SOURCE_MATERIALIZATION_CLAIM_SCHEMA,
            version=1,
            preparation_id=preparation_id,
            materialization_id=materialization_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            organization_id=preparation.organization_id,
            environment_id=preparation.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_source_materialization_requested",
            preparation_id,
        )
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_preparation(
                preparation_id=preparation_id
            )
            if concurrent is None:
                raise OperationalKnowledgeSourceMaterializationUncertainError(
                    "operational_knowledge_source_materialization_claim_uncertain"
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
            "operational_knowledge_source_materialization_claimed",
            materialization_id,
        )
        instruction = OperationalKnowledgeSourceMaterializationInstruction(
            materialization_id=materialization_id,
            organization_id=preparation.organization_id,
            environment_id=preparation.environment_id,
            preparation_id=preparation_id,
            preparation_digest=preparation_digest,
            resolution_id=preparation.resolution_id,
            resolution_digest=preparation.resolution_digest,
            source_draft_id=preparation.source_draft_id,
            source_draft_digest=preparation.source_draft_digest,
            knowledge_item_id=preparation.knowledge_item_id,
            source_artifact_digest=preparation.source_artifact_digest,
            metadata_manifest_digest=preparation.metadata_manifest_digest,
            access_manifest_digest=preparation.access_manifest_digest,
            retention_manifest_digest=preparation.retention_manifest_digest,
            chunking_profile_digest=preparation.chunking_profile_digest,
            embedding_profile_digest=preparation.embedding_profile_digest,
            index_profile_digest=preparation.index_profile_digest,
            validation_profile_digest=preparation.validation_profile_digest,
            steward_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            canonicalization_profile_id=policy.canonicalization_profile_id,
            canonicalization_profile_digest=policy.canonicalization_profile_digest,
            source_security_profile_id=policy.source_security_profile_id,
            source_security_profile_digest=policy.source_security_profile_digest,
            media_type_allowlist_digest=policy.media_type_allowlist_digest,
            maximum_source_bytes=policy.maximum_source_bytes,
            maximum_canonical_characters=policy.maximum_canonical_characters,
            purpose=purpose,
            requested_at=now,
        )
        try:
            receipt = await self._materializer.materialize(instruction)
            self._verify_receipt(receipt, instruction, policy)
        except OperationalKnowledgeSourceMaterializationError:
            raise
        except Exception as error:
            raise OperationalKnowledgeSourceMaterializationUncertainError(
                "operational_knowledge_source_materialization_outcome_uncertain"
            ) from error
        record = OperationalKnowledgeSourceMaterializationRecord(
            materialization_id=materialization_id,
            schema_version=SOURCE_MATERIALIZATION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            preparation_id=preparation_id,
            preparation_digest=preparation_digest,
            resolution_id=preparation.resolution_id,
            resolution_digest=preparation.resolution_digest,
            review_request_id=preparation.review_request_id,
            source_draft_id=preparation.source_draft_id,
            source_draft_digest=preparation.source_draft_digest,
            knowledge_item_id=preparation.knowledge_item_id,
            organization_id=preparation.organization_id,
            environment_id=preparation.environment_id,
            classification=preparation.classification,
            access_policy_id=preparation.access_policy_id,
            retention_policy_id=preparation.retention_policy_id,
            publication_steward_subject_digest=preparation.prepared_by_subject_digest,
            materialized_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            materialization_policy_id=policy.policy_id,
            materialization_policy_digest=policy.canonical_digest,
            materialization_policy_version=policy.policy_version,
            canonicalization_profile_id=policy.canonicalization_profile_id,
            canonicalization_profile_digest=policy.canonicalization_profile_digest,
            source_security_profile_id=policy.source_security_profile_id,
            source_security_profile_digest=policy.source_security_profile_digest,
            materializer_id=receipt.materializer_id,
            materialization_receipt_digest=receipt.canonical_digest,
            source_artifact_digest=receipt.source_artifact_digest,
            protected_material_digest=receipt.protected_material_digest,
            chunking_profile_digest=preparation.chunking_profile_digest,
            media_type=receipt.media_type,
            source_bytes=receipt.source_bytes,
            canonical_bytes=receipt.canonical_bytes,
            canonical_characters=receipt.canonical_characters,
            security_scan_evidence_digest=receipt.security_scan_evidence_digest,
            governance_binding_digest=receipt.governance_binding_digest,
            materialized_at=receipt.materialized_at,
            instance_state=SOURCE_MATERIALIZED_STATE,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise OperationalKnowledgeSourceMaterializationUncertainError(
                "operational_knowledge_source_materialization_persistence_uncertain"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_source_materialization_recorded",
            materialization_id,
        )
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        materialization_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeSourceMaterializationRecord:
        self._require_human(actor)
        record = await self._repository.get(materialization_id=materialization_id)
        if record is None:
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_not_found"
            )
        policy = await self._policy_source.get_by_id(policy_id=record.materialization_policy_id)
        if policy is None or not policy.issued_at <= self._clock() < policy.expires_at:
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            subject_digest != record.materialized_by_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_not_found"
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
            "operational_knowledge_source_materialization_read",
            materialization_id,
            permission_id=KNOWLEDGE_SOURCE_MATERIALIZATION_READ,
        )
        return replace(record, reused=True)

    async def source_for_chunking(
        self, *, materialization_id: str
    ) -> OperationalKnowledgeSourceMaterializationRecord | None:
        return await self._repository.get(materialization_id=materialization_id)

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: OperationalKnowledgeSourceMaterializationClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgeSourceMaterializationRecord:
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_idempotency_conflict"
            )
        record = await self._repository.get(materialization_id=claim.materialization_id)
        if record is None:
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_already_claimed"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_source_materialization_read",
            record.materialization_id,
            permission_id=KNOWLEDGE_SOURCE_MATERIALIZATION_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _verify_receipt(
        cls,
        receipt: OperationalKnowledgeSourceMaterializationReceipt,
        instruction: OperationalKnowledgeSourceMaterializationInstruction,
        policy: OperationalKnowledgeSourceMaterializationPolicySnapshot,
    ) -> None:
        if (
            receipt.materialization_id != instruction.materialization_id
            or receipt.materializer_id != policy.required_materializer_id
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or receipt.source_artifact_digest != instruction.source_artifact_digest
            or receipt.canonicalization_profile_digest
            != instruction.canonicalization_profile_digest
            or receipt.source_bytes > instruction.maximum_source_bytes
            or receipt.canonical_characters > instruction.maximum_canonical_characters
            or not receipt.signature_verified
        ):
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_receipt_invalid"
            )

    @classmethod
    def _verify_policy(
        cls, policy: OperationalKnowledgeSourceMaterializationPolicySnapshot
    ) -> None:
        if policy.canonical_digest != cls._digest(cls._payload(policy)):
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_policy_invalid"
            )

    @staticmethod
    def _payload(
        value: OperationalKnowledgeSourceMaterializationPolicySnapshot
        | OperationalKnowledgeSourceMaterializationClaim
        | OperationalKnowledgeSourceMaterializationRecord,
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
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_human_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = KNOWLEDGE_SOURCE_MATERIALIZATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-source-materialization",
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
                resource_type="resource.knowledge.operational-source-materializations",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )


def build_development_operational_knowledge_source_materialization_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalKnowledgeSourceMaterializationPolicySnapshot:
    digest = OperationalKnowledgeSourceMaterializationService._digest
    canonicalization_profile_id = "knowledge-source-canonicalization.development-v1"
    source_security_profile_id = "knowledge-source-security.development-v1"
    policy = OperationalKnowledgeSourceMaterializationPolicySnapshot(
        policy_id="operational-knowledge-source-materialization-policy.development",
        schema_version=SOURCE_MATERIALIZATION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.operational-knowledge-source-materialization-development-v1",
        required_preparation_schema="atlas.operational-knowledge-publication-preparation.v1",
        required_preparation_state=PUBLICATION_PREPARED_STATE,
        canonicalization_profile_id=canonicalization_profile_id,
        canonicalization_profile_digest=digest(
            [canonicalization_profile_id, "utf8-lf-nfc-text-v1"]
        ),
        source_security_profile_id=source_security_profile_id,
        source_security_profile_digest=digest(
            [source_security_profile_id, "active-content-rejected", "scan-required"]
        ),
        media_type_allowlist_digest=digest(["text/plain", "text/markdown"]),
        maximum_source_bytes=1_048_576,
        maximum_canonical_characters=1_000_000,
        maximum_authentication_age_minutes=15,
        subject_digest_salt_digest=digest([organization_id, environment_id, "review-salt-v1"]),
        browser_binding_key_digest=digest(
            ["operational-knowledge-source-materialization-browser-key"]
        ),
        required_materializer_id="operational-knowledge-source-materializer.synthetic",
        signed_by="subject.operational-knowledge-source-materialization-policy-signer",
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(OperationalKnowledgeSourceMaterializationService._payload(policy)),
    )
