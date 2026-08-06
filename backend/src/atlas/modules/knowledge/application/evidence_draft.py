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
    KNOWLEDGE_EVIDENCE_DRAFT_CREATE,
    KNOWLEDGE_EVIDENCE_DRAFT_READ,
)
from atlas.modules.connectors.domain.invocation_evidence import (
    ENABLED_INVOCATION_EVIDENCE_INGESTED,
    ConnectorInvocationEvidenceRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.application.evidence_draft_ports import (
    OperationalEvidenceKnowledgeDraftAdapter,
    OperationalEvidenceKnowledgeDraftError,
    OperationalEvidenceKnowledgeDraftPermissionAuthorizer,
    OperationalEvidenceKnowledgeDraftPolicySource,
    OperationalEvidenceKnowledgeDraftRepository,
    OperationalEvidenceKnowledgeDraftSource,
    OperationalEvidenceKnowledgeDraftUncertainError,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    DRAFT_OPERATIONAL_KNOWLEDGE_CREATED,
    OperationalEvidenceKnowledgeDraftClaim,
    OperationalEvidenceKnowledgeDraftInstruction,
    OperationalEvidenceKnowledgeDraftPolicySnapshot,
    OperationalEvidenceKnowledgeDraftReceipt,
    OperationalEvidenceKnowledgeDraftRecord,
)

EVIDENCE_DRAFT_POLICY_SCHEMA = "atlas.operational-evidence-knowledge-draft-policy.v1"
EVIDENCE_DRAFT_CLAIM_SCHEMA = "atlas.operational-evidence-knowledge-draft-claim.v1"
EVIDENCE_DRAFT_RECORD_SCHEMA = "atlas.operational-evidence-knowledge-draft.v1"


class OperationalEvidenceKnowledgeDraftService:
    def __init__(
        self,
        *,
        repository: OperationalEvidenceKnowledgeDraftRepository,
        source: OperationalEvidenceKnowledgeDraftSource,
        policy_source: OperationalEvidenceKnowledgeDraftPolicySource,
        permission_authorizer: OperationalEvidenceKnowledgeDraftPermissionAuthorizer,
        adapter: OperationalEvidenceKnowledgeDraftAdapter,
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
        source_ingestion_id: str,
        source_ingestion_digest: str,
        curation_policy_id: str,
        curation_policy_digest: str,
        purpose: str,
        unapproved_non_retrievable_draft_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalEvidenceKnowledgeDraftRecord:
        self._require_enterprise_human(actor)
        if not unapproved_non_retrievable_draft_acknowledged:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_acknowledgement_required"
            )
        purpose = purpose.strip()
        if not 20 <= len(purpose) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_request_invalid"
            )
        request_binding_digest = self._digest(
            {
                "source_ingestion_id": source_ingestion_id,
                "source_ingestion_digest": source_ingestion_digest,
                "curation_policy_id": curation_policy_id,
                "curation_policy_digest": curation_policy_digest,
                "purpose": purpose,
            }
        )
        idempotency_digest = self._digest([actor.subject_id, idempotency_key])
        existing_claim = await self._repository.get_claim_by_idempotency(
            claimed_by=actor.subject_id, idempotency_digest=idempotency_digest
        )
        if existing_claim is not None:
            return await self._reuse(
                existing_claim, actor, request_binding_digest, idempotency_digest
            )
        try:
            source, source_actors = await self._source.knowledge_draft_source(
                ingestion_id=source_ingestion_id
            )
        except Exception as error:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_source_not_found"
            ) from error
        policy = await self._policy_source.get_by_id(policy_id=curation_policy_id)
        if policy is None:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_policy_not_found"
            )
        self._verify_snapshot(policy)
        now = self._clock()
        self._verify_source(
            source=source,
            policy=policy,
            source_digest=source_ingestion_digest,
            policy_digest=curation_policy_digest,
            now=now,
        )
        self._require_scope(actor, source.organization_id, source.environment_id)
        if actor.subject_id in source_actors | {
            source.ingested_by,
            policy.signed_by,
            policy.required_adapter_attestor_id,
        }:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            correlation_id=correlation_id,
        )
        seed = self._digest([source.ingestion_id, source.canonical_digest, policy.canonical_digest])
        draft_id = f"operational-evidence-knowledge-draft.{seed[:24]}"
        await self._audit(
            actor,
            correlation_id,
            "operational_evidence_knowledge_draft_requested",
            source.ingestion_id,
            (("evidence_package_id", source.evidence_package_id),),
        )
        claim = OperationalEvidenceKnowledgeDraftClaim(
            claim_id=f"operational-evidence-knowledge-draft-claim.{seed[:24]}",
            schema_version=EVIDENCE_DRAFT_CLAIM_SCHEMA,
            version=1,
            source_ingestion_id=source.ingestion_id,
            source_ingestion_digest=source.canonical_digest,
            draft_id=draft_id,
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
                source_ingestion_id=source.ingestion_id
            )
            if prior is None:
                raise OperationalEvidenceKnowledgeDraftUncertainError(
                    "operational_evidence_knowledge_draft_claim_uncertain"
                )
            return await self._reuse(prior, actor, request_binding_digest, idempotency_digest)
        await self._audit(
            actor,
            correlation_id,
            "operational_evidence_knowledge_draft_source_claimed",
            claim.claim_id,
            (("draft_id", draft_id),),
        )
        instruction = self._instruction(draft_id, source, policy)
        try:
            receipt = await self._adapter.create_draft(instruction)
        except OperationalEvidenceKnowledgeDraftError as error:
            await self._audit(
                actor,
                correlation_id,
                (
                    "operational_evidence_knowledge_draft_uncertain"
                    if isinstance(error, OperationalEvidenceKnowledgeDraftUncertainError)
                    else "operational_evidence_knowledge_draft_failed"
                ),
                draft_id,
                (("claim_persisted", "true"),),
            )
            raise
        except Exception as error:
            await self._audit(
                actor,
                correlation_id,
                "operational_evidence_knowledge_draft_uncertain",
                draft_id,
                (("claim_persisted", "true"),),
            )
            raise OperationalEvidenceKnowledgeDraftUncertainError(
                "operational_evidence_knowledge_draft_outcome_uncertain"
            ) from error
        try:
            self._verify_receipt(instruction, receipt, policy)
        except OperationalEvidenceKnowledgeDraftUncertainError:
            await self._audit(
                actor,
                correlation_id,
                "operational_evidence_knowledge_draft_uncertain",
                draft_id,
                (("claim_persisted", "true"),),
            )
            raise
        record = self._record(claim, source, policy, receipt, actor, purpose)
        await self._audit(
            actor,
            correlation_id,
            "operational_evidence_knowledge_draft_created",
            record.draft_id,
            (("knowledge_lifecycle", record.knowledge_lifecycle),),
        )
        if not await self._repository.add(record):
            raced = await self._repository.get_by_source(source_ingestion_id=source.ingestion_id)
            if raced is None or raced.canonical_digest != record.canonical_digest:
                raise OperationalEvidenceKnowledgeDraftUncertainError(
                    "operational_evidence_knowledge_draft_persistence_uncertain"
                )
            return replace(raced, reused=True)
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, draft_id: str, correlation_id: str
    ) -> OperationalEvidenceKnowledgeDraftRecord:
        self._require_enterprise_human(actor)
        record = await self._repository.get(draft_id=draft_id)
        if record is None:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_record_not_found"
            )
        self._verify_record(record)
        self._require_scope(actor, record.organization_id, record.environment_id)
        await self._audit(
            actor,
            correlation_id,
            "operational_evidence_knowledge_draft_read",
            record.draft_id,
            (),
            permission_id=KNOWLEDGE_EVIDENCE_DRAFT_READ,
        )
        return record

    async def close(self) -> None:
        await self._repository.close()

    async def review_request_source(
        self, *, draft_id: str
    ) -> OperationalEvidenceKnowledgeDraftRecord:
        record = await self._repository.get(draft_id=draft_id)
        if record is None:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_record_not_found"
            )
        self._verify_record(record)
        return record

    async def _reuse(
        self,
        claim: OperationalEvidenceKnowledgeDraftClaim,
        actor: AuthenticatedSubject,
        request_binding_digest: str,
        idempotency_digest: str,
    ) -> OperationalEvidenceKnowledgeDraftRecord:
        self._verify_claim(claim)
        if (
            claim.claimed_by != actor.subject_id
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_idempotency_conflict"
            )
        self._require_scope(actor, claim.organization_id, claim.environment_id)
        record = await self._repository.get(draft_id=claim.draft_id)
        if record is None:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_already_claimed"
            )
        self._verify_record(record)
        return replace(record, reused=True)

    @staticmethod
    def _verify_source(
        *,
        source: ConnectorInvocationEvidenceRecord,
        policy: OperationalEvidenceKnowledgeDraftPolicySnapshot,
        source_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        later_authority = (
            source.knowledge_item_created,
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
            or source.instance_state != ENABLED_INVOCATION_EVIDENCE_INGESTED
            or not all(
                (
                    source.source_invocation_completed,
                    source.evidence_ingested,
                    source.immutable_storage_confirmed,
                    source.encrypted_at_rest,
                    source.transient_buffers_erased,
                    source.artifact_channel_closed,
                )
            )
            or any(later_authority)
            or not 1 <= source.evidence_item_count <= policy.maximum_draft_items
            or not 0 <= source.evidence_bytes <= policy.maximum_draft_bytes
            or now - source.ingested_at > timedelta(minutes=policy.maximum_source_age_minutes)
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_source_invalid"
            )

    @staticmethod
    def _instruction(
        draft_id: str,
        source: ConnectorInvocationEvidenceRecord,
        policy: OperationalEvidenceKnowledgeDraftPolicySnapshot,
    ) -> OperationalEvidenceKnowledgeDraftInstruction:
        return OperationalEvidenceKnowledgeDraftInstruction(
            draft_id=draft_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            source_ingestion_id=source.ingestion_id,
            source_ingestion_digest=source.canonical_digest,
            evidence_package_id=source.evidence_package_id,
            evidence_schema_version=source.evidence_schema_version,
            evidence_content_digest=source.evidence_content_digest,
            evidence_metadata_digest=source.evidence_metadata_digest,
            connector_id=source.connector_id,
            display_name=source.display_name,
            capability_id=source.capability_id,
            classification=source.classification,
            access_policy_id=source.access_policy_id,
            access_policy_digest=source.access_policy_digest,
            retention_policy_id=source.retention_policy_id,
            retention_policy_digest=source.retention_policy_digest,
            encryption_profile_id=source.encryption_profile_id,
            encryption_profile_digest=source.encryption_profile_digest,
            evidence_item_count=source.evidence_item_count,
            evidence_bytes=source.evidence_bytes,
            observed_from=source.observed_from,
            observed_to=source.observed_to,
            source_ingested_at=source.ingested_at,
            draft_domain=policy.draft_domain,
            content_type=policy.content_type,
            source_authority=policy.source_authority,
            language=policy.language,
            title_template_id=policy.title_template_id,
            title_template_digest=policy.title_template_digest,
            maximum_draft_items=policy.maximum_draft_items,
            maximum_draft_bytes=policy.maximum_draft_bytes,
            curation_policy_digest=policy.canonical_digest,
        )

    @classmethod
    def _verify_receipt(
        cls,
        instruction: OperationalEvidenceKnowledgeDraftInstruction,
        receipt: OperationalEvidenceKnowledgeDraftReceipt,
        policy: OperationalEvidenceKnowledgeDraftPolicySnapshot,
    ) -> None:
        if (
            cls._receipt_digest(receipt) != receipt.canonical_digest
            or receipt.draft_id != instruction.draft_id
            or receipt.schema_version != policy.required_receipt_schema
            or receipt.adapter_id != policy.required_adapter_id
            or receipt.attested_by != policy.required_adapter_attestor_id
            or receipt.source_ingestion_digest != instruction.source_ingestion_digest
            or receipt.evidence_package_id != instruction.evidence_package_id
            or receipt.evidence_content_digest != instruction.evidence_content_digest
            or receipt.draft_domain != policy.draft_domain
            or receipt.content_type != policy.content_type
            or receipt.source_authority != policy.source_authority
            or receipt.language != policy.language
            or receipt.knowledge_lifecycle != "draft"
            or receipt.classification != instruction.classification
            or receipt.access_policy_id != instruction.access_policy_id
            or receipt.access_policy_digest != instruction.access_policy_digest
            or receipt.retention_policy_id != instruction.retention_policy_id
            or receipt.retention_policy_digest != instruction.retention_policy_digest
            or receipt.encryption_profile_id != instruction.encryption_profile_id
            or receipt.encryption_profile_digest != instruction.encryption_profile_digest
            or receipt.draft_item_count != instruction.evidence_item_count
            or receipt.draft_bytes != instruction.evidence_bytes
            or receipt.observed_from != instruction.observed_from
            or receipt.observed_to != instruction.observed_to
            or receipt.draft_item_count > instruction.maximum_draft_items
            or receipt.draft_bytes > instruction.maximum_draft_bytes
        ):
            raise OperationalEvidenceKnowledgeDraftUncertainError(
                "operational_evidence_knowledge_draft_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: OperationalEvidenceKnowledgeDraftClaim,
        source: ConnectorInvocationEvidenceRecord,
        policy: OperationalEvidenceKnowledgeDraftPolicySnapshot,
        receipt: OperationalEvidenceKnowledgeDraftReceipt,
        actor: AuthenticatedSubject,
        purpose: str,
    ) -> OperationalEvidenceKnowledgeDraftRecord:
        record = OperationalEvidenceKnowledgeDraftRecord(
            draft_id=receipt.draft_id,
            schema_version=EVIDENCE_DRAFT_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            source_ingestion_id=source.ingestion_id,
            source_ingestion_digest=source.canonical_digest,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            source_invocation_id=source.source_invocation_id,
            evidence_package_id=source.evidence_package_id,
            evidence_content_digest=source.evidence_content_digest,
            evidence_metadata_digest=source.evidence_metadata_digest,
            connector_id=source.connector_id,
            instance_id=source.instance_id,
            capability_id=source.capability_id,
            knowledge_item_id=receipt.knowledge_item_id,
            draft_version_id=receipt.draft_version_id,
            draft_artifact_id=receipt.draft_artifact_id,
            draft_schema_version=receipt.draft_schema_version,
            title=receipt.title,
            draft_domain=receipt.draft_domain,
            content_type=receipt.content_type,
            source_authority=receipt.source_authority,
            language=receipt.language,
            knowledge_lifecycle=receipt.knowledge_lifecycle,
            classification=receipt.classification,
            access_policy_id=receipt.access_policy_id,
            access_policy_digest=receipt.access_policy_digest,
            retention_policy_id=receipt.retention_policy_id,
            retention_policy_digest=receipt.retention_policy_digest,
            encryption_profile_id=receipt.encryption_profile_id,
            encryption_profile_digest=receipt.encryption_profile_digest,
            draft_content_digest=receipt.draft_content_digest,
            draft_metadata_digest=receipt.draft_metadata_digest,
            provenance_digest=receipt.provenance_digest,
            draft_access_digest=receipt.draft_access_digest,
            draft_retention_digest=receipt.draft_retention_digest,
            curation_policy_id=policy.policy_id,
            curation_policy_digest=policy.canonical_digest,
            curation_policy_version=policy.policy_version,
            curation_adapter_id=receipt.adapter_id,
            draft_item_count=receipt.draft_item_count,
            draft_bytes=receipt.draft_bytes,
            observed_from=receipt.observed_from,
            observed_to=receipt.observed_to,
            created_at=receipt.created_at,
            instance_state=DRAFT_OPERATIONAL_KNOWLEDGE_CREATED,
            curated_by=actor.subject_id,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._record_payload(record)))

    @classmethod
    def _verify_snapshot(cls, policy: OperationalEvidenceKnowledgeDraftPolicySnapshot) -> None:
        payload = cast(dict[str, object], asdict(policy))
        digest = str(payload.pop("canonical_digest"))
        if cls._digest(cls._normalize(payload)) != digest:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_policy_integrity_failed"
            )

    @classmethod
    def _verify_claim(cls, claim: OperationalEvidenceKnowledgeDraftClaim) -> None:
        if cls._digest(cls._claim_payload(claim)) != claim.canonical_digest:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_claim_integrity_failed"
            )

    @classmethod
    def _verify_record(cls, record: OperationalEvidenceKnowledgeDraftRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_record_integrity_failed"
            )

    @classmethod
    def _claim_payload(cls, claim: OperationalEvidenceKnowledgeDraftClaim) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(claim))
        payload.pop("canonical_digest")
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _record_payload(cls, record: OperationalEvidenceKnowledgeDraftRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in ("canonical_digest", "reused"):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _receipt_digest(cls, receipt: OperationalEvidenceKnowledgeDraftReceipt) -> str:
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
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or self._environment_id != environment_id:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_record_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        *,
        permission_id: str = KNOWLEDGE_EVIDENCE_DRAFT_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-evidence-draft",
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
                resource_type="resource.knowledge.operational-evidence-drafts",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=metadata,
            )
        )


def _signed_policy(policy: OperationalEvidenceKnowledgeDraftPolicySnapshot) -> str:
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return OperationalEvidenceKnowledgeDraftService._digest(
        OperationalEvidenceKnowledgeDraftService._normalize(payload)
    )


def build_development_operational_evidence_knowledge_draft_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> OperationalEvidenceKnowledgeDraftPolicySnapshot:
    policy = OperationalEvidenceKnowledgeDraftPolicySnapshot(
        policy_id="operational-evidence-knowledge-draft-policy.development",
        schema_version=EVIDENCE_DRAFT_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-v1",
        required_source_schema="atlas.connector-invocation-evidence-ingestion.v1",
        required_source_state=ENABLED_INVOCATION_EVIDENCE_INGESTED,
        required_adapter_id="operational-evidence-knowledge-draft-adapter.synthetic",
        required_adapter_attestor_id=(
            "subject.operational-evidence-knowledge-draft-adapter-attestor"
        ),
        required_receipt_schema="atlas.operational-evidence-knowledge-draft-receipt.v1",
        draft_domain="domain.operational",
        content_type="content-type.connector-observations",
        source_authority="source-authority.system-generated",
        language="language.en",
        title_template_id="knowledge-draft-title-template.connector-observations-v1",
        title_template_digest=OperationalEvidenceKnowledgeDraftService._digest(
            ["connector-display-name", "capability-id", "operational-evidence", "v1"]
        ),
        maximum_source_age_minutes=60,
        maximum_draft_items=100,
        maximum_draft_bytes=524_288,
        require_classification_inheritance=True,
        require_access_policy_inheritance=True,
        require_retention_policy_inheritance=True,
        require_encryption_profile_inheritance=True,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.operational-evidence-knowledge-draft-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(policy, canonical_digest=_signed_policy(policy))
