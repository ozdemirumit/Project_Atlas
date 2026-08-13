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
    KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE,
    KNOWLEDGE_RETRIEVAL_PUBLICATION_READ,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.application.retrieval_index_publication_ports import (
    OperationalKnowledgeIndexStagingSource,
    OperationalKnowledgeRetrievalPublicationError,
    OperationalKnowledgeRetrievalPublicationPermissionAuthorizer,
    OperationalKnowledgeRetrievalPublicationPolicySource,
    OperationalKnowledgeRetrievalPublicationRepository,
    OperationalKnowledgeRetrievalPublicationUncertainError,
    OperationalKnowledgeRetrievalPublisher,
)
from atlas.modules.knowledge.domain.index_staging_validation import (
    INDEX_VALIDATED_STATE,
    OperationalKnowledgeIndexPolicySnapshot,
    OperationalKnowledgeIndexRecord,
)
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    RETRIEVAL_PUBLISHED_STATE,
    OperationalKnowledgeRetrievalPublicationClaim,
    OperationalKnowledgeRetrievalPublicationInstruction,
    OperationalKnowledgeRetrievalPublicationPolicySnapshot,
    OperationalKnowledgeRetrievalPublicationReceipt,
    OperationalKnowledgeRetrievalPublicationRecord,
)

PUBLICATION_POLICY_SCHEMA = "atlas.operational-knowledge-retrieval-publication-policy.v1"
PUBLICATION_CLAIM_SCHEMA = "atlas.operational-knowledge-retrieval-publication-claim.v1"
PUBLICATION_RECORD_SCHEMA = "atlas.operational-knowledge-retrieval-publication.v1"


class OperationalKnowledgeRetrievalIndexPublicationService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeRetrievalPublicationRepository,
        index_source: OperationalKnowledgeIndexStagingSource,
        policy_source: OperationalKnowledgeRetrievalPublicationPolicySource,
        permission_authorizer: OperationalKnowledgeRetrievalPublicationPermissionAuthorizer,
        publisher: OperationalKnowledgeRetrievalPublisher,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._index_source = index_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._publisher = publisher
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        index_staging_id: str,
        index_staging_digest: str,
        publication_policy_id: str,
        publication_policy_digest: str,
        purpose: str,
        policy_filtered_visibility_acknowledged: bool,
        no_vector_store_disclosure_acknowledged: bool,
        no_context_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalPublicationRecord:
        self._require_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    policy_filtered_visibility_acknowledged,
                    no_vector_store_disclosure_acknowledged,
                    no_context_or_operational_authority_acknowledged,
                )
            )
        ):
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_request_invalid"
            )
        index = await self._index_source.source_for_retrieval_publication(
            index_staging_id=index_staging_id
        )
        if index is None:
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_source_not_found"
            )
        policy = await self._policy_source.get_by_id(policy_id=publication_policy_id)
        if policy is None:
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_policy_not_found"
            )
        self._verify_policy(policy)
        now = self._clock()
        later_authority = any(
            (
                index.knowledge_published,
                index.retrieval_published,
                index.model_context_available,
                index.graph_updated,
                index.scheduled,
                index.workflow_continued,
                index.execution_authorized,
                index.deployment_approved,
                index.infrastructure_mutation_performed,
            )
        )
        if (
            index.index_staging_id != index_staging_id
            or index.canonical_digest != index_staging_digest
            or index.canonical_digest != self._digest(self._payload(index))
            or index.schema_version != policy.required_index_schema
            or index.instance_state != policy.required_index_state
            or index.instance_state != INDEX_VALIDATED_STATE
            or not all(
                (
                    index.knowledge_approved,
                    index.publication_ready,
                    index.publication_prepared,
                    index.source_materialized,
                    index.chunks_created,
                    index.embeddings_created,
                    index.index_staged,
                    index.index_validated,
                )
            )
            or later_authority
            or index.index_profile_digest != policy.required_index_profile_digest
            or index.staging_boundary_digest != policy.required_staging_boundary_digest
            or (
                index.authorization_payload_profile_digest
                != policy.required_authorization_payload_profile_digest
            )
            or policy.canonical_digest != publication_policy_digest
            or policy.organization_id != index.organization_id
            or policy.environment_id != index.environment_id
            or not policy.issued_at <= now < policy.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_source_invalid"
            )
        self._require_scope(actor, index.organization_id, index.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        separated_digests = {
            index.index_steward_subject_digest,
            *index.upstream_accountable_subject_digests,
        }
        separated_identities = {
            policy.signed_by,
            policy.required_publisher_id,
            policy.route_profile_owner_id,
            index.indexer_id,
        }
        if subject_digest in separated_digests or actor.subject_id in separated_identities:
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=index.organization_id,
            environment_id=index.environment_id,
            correlation_id=correlation_id,
        )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        request_binding_digest = self._digest(
            [
                index_staging_id,
                index_staging_digest,
                publication_policy_digest,
                index.projection_manifest_digest,
                index.point_coverage_digest,
                index.authorization_metadata_validation_digest,
                index.reconciliation_digest,
                index.governance_binding_digest,
                policy.publication_profile_digest,
                policy.retrieval_route_profile_digest,
                purpose,
                subject_digest,
                browser_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, index_staging_id, idempotency_key])
        existing = await self._repository.get_claim_by_index_staging(
            index_staging_id=index_staging_id
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
        seed = self._digest([index_staging_id, request_binding_digest])
        publication_id = f"operational-knowledge-retrieval-publication.{seed[:24]}"
        claim = OperationalKnowledgeRetrievalPublicationClaim(
            claim_id=f"operational-knowledge-retrieval-publication-claim.{seed[:24]}",
            schema_version=PUBLICATION_CLAIM_SCHEMA,
            version=1,
            index_staging_id=index_staging_id,
            publication_id=publication_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            organization_id=index.organization_id,
            environment_id=index.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_retrieval_publication_requested",
            index_staging_id,
        )
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_index_staging(
                index_staging_id=index_staging_id
            )
            if concurrent is None:
                raise OperationalKnowledgeRetrievalPublicationUncertainError(
                    "operational_knowledge_retrieval_publication_claim_uncertain"
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
            "operational_knowledge_retrieval_publication_claimed",
            publication_id,
        )
        instruction = OperationalKnowledgeRetrievalPublicationInstruction(
            publication_id=publication_id,
            organization_id=index.organization_id,
            environment_id=index.environment_id,
            index_staging_id=index_staging_id,
            index_staging_digest=index_staging_digest,
            knowledge_item_id=index.knowledge_item_id,
            classification=index.classification,
            access_policy_id=index.access_policy_id,
            retention_policy_id=index.retention_policy_id,
            governance_binding_digest=index.governance_binding_digest,
            model_profile_digest=index.model_profile_digest,
            projection_manifest_digest=index.projection_manifest_digest,
            point_coverage_digest=index.point_coverage_digest,
            authorization_metadata_validation_digest=(
                index.authorization_metadata_validation_digest
            ),
            reconciliation_digest=index.reconciliation_digest,
            steward_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            publication_profile_id=policy.publication_profile_id,
            publication_profile_digest=policy.publication_profile_digest,
            retrieval_route_profile_digest=policy.retrieval_route_profile_digest,
            purpose=purpose,
            requested_at=now,
        )
        try:
            receipt = await self._publisher.publish(instruction)
            self._verify_receipt(receipt, instruction, policy)
        except OperationalKnowledgeRetrievalPublicationError:
            raise
        except Exception as error:
            raise OperationalKnowledgeRetrievalPublicationUncertainError(
                "operational_knowledge_retrieval_publication_outcome_uncertain"
            ) from error
        upstream = tuple(
            sorted(
                {
                    index.index_steward_subject_digest,
                    *index.upstream_accountable_subject_digests,
                }
            )
        )
        record = OperationalKnowledgeRetrievalPublicationRecord(
            publication_id=publication_id,
            schema_version=PUBLICATION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            index_staging_id=index_staging_id,
            index_staging_digest=index_staging_digest,
            embedding_set_id=index.embedding_set_id,
            chunk_set_id=index.chunk_set_id,
            materialization_id=index.materialization_id,
            preparation_id=index.preparation_id,
            resolution_id=index.resolution_id,
            review_request_id=index.review_request_id,
            source_draft_id=index.source_draft_id,
            knowledge_item_id=index.knowledge_item_id,
            organization_id=index.organization_id,
            environment_id=index.environment_id,
            classification=index.classification,
            access_policy_id=index.access_policy_id,
            retention_policy_id=index.retention_policy_id,
            publication_steward_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            publication_policy_id=policy.policy_id,
            publication_policy_digest=policy.canonical_digest,
            publication_policy_version=policy.policy_version,
            publication_profile_id=policy.publication_profile_id,
            publication_profile_digest=policy.publication_profile_digest,
            retrieval_route_profile_digest=policy.retrieval_route_profile_digest,
            publisher_id=receipt.publisher_id,
            publication_receipt_digest=receipt.canonical_digest,
            index_profile_digest=index.index_profile_digest,
            staging_boundary_digest=index.staging_boundary_digest,
            authorization_payload_profile_digest=index.authorization_payload_profile_digest,
            model_profile_digest=index.model_profile_digest,
            governance_binding_digest=index.governance_binding_digest,
            projection_manifest_digest=index.projection_manifest_digest,
            point_coverage_digest=index.point_coverage_digest,
            authorization_metadata_validation_digest=(
                index.authorization_metadata_validation_digest
            ),
            reconciliation_digest=index.reconciliation_digest,
            route_generation_digest=receipt.route_generation_digest,
            activation_digest=receipt.activation_digest,
            route_verification_digest=receipt.route_verification_digest,
            authorization_enforcement_digest=receipt.authorization_enforcement_digest,
            lifecycle_filter_digest=receipt.lifecycle_filter_digest,
            rollback_metadata_digest=receipt.rollback_metadata_digest,
            published_at=receipt.published_at,
            instance_state=RETRIEVAL_PUBLISHED_STATE,
            purpose=purpose,
            canonical_digest="0" * 64,
            upstream_accountable_subject_digests=upstream,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise OperationalKnowledgeRetrievalPublicationUncertainError(
                "operational_knowledge_retrieval_publication_persistence_uncertain"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_retrieval_published",
            publication_id,
        )
        return record

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        publication_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalPublicationRecord:
        self._require_human(actor)
        record = await self._repository.get(publication_id=publication_id)
        if record is None:
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_not_found"
            )
        policy = await self._policy_source.get_by_id(policy_id=record.publication_policy_id)
        if policy is None or not policy.issued_at <= self._clock() < policy.expires_at:
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            subject_digest != record.publication_steward_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_not_found"
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
            "operational_knowledge_retrieval_publication_read",
            publication_id,
            permission_id=KNOWLEDGE_RETRIEVAL_PUBLICATION_READ,
        )
        return replace(record, reused=True)

    async def source_for_governed_retrieval(
        self, *, publication_id: str
    ) -> OperationalKnowledgeRetrievalPublicationRecord | None:
        return await self._repository.get(publication_id=publication_id)

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: OperationalKnowledgeRetrievalPublicationClaim,
        *,
        subject_digest: str,
        browser_digest: str,
        request_binding_digest: str,
        idempotency_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalPublicationRecord:
        if (
            claim.claimed_by_subject_digest != subject_digest
            or claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.idempotency_digest != idempotency_digest
        ):
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_idempotency_conflict"
            )
        record = await self._repository.get(publication_id=claim.publication_id)
        if record is None:
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_already_claimed"
            )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_retrieval_publication_read",
            record.publication_id,
            permission_id=KNOWLEDGE_RETRIEVAL_PUBLICATION_READ,
        )
        return replace(record, reused=True)

    @classmethod
    def _verify_receipt(
        cls,
        receipt: OperationalKnowledgeRetrievalPublicationReceipt,
        instruction: OperationalKnowledgeRetrievalPublicationInstruction,
        policy: OperationalKnowledgeRetrievalPublicationPolicySnapshot,
    ) -> None:
        if (
            receipt.publication_id != instruction.publication_id
            or receipt.publisher_id != policy.required_publisher_id
            or receipt.instruction_digest != cls._digest(asdict(instruction))
            or receipt.index_staging_digest != instruction.index_staging_digest
            or receipt.projection_manifest_digest != instruction.projection_manifest_digest
            or receipt.publication_profile_digest != policy.publication_profile_digest
            or receipt.retrieval_route_profile_digest != policy.retrieval_route_profile_digest
            or not receipt.atomic_activation
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or not receipt.signature_verified
        ):
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_receipt_invalid"
            )

    @classmethod
    def _verify_policy(cls, policy: OperationalKnowledgeRetrievalPublicationPolicySnapshot) -> None:
        if policy.canonical_digest != cls._digest(cls._payload(policy)):
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_policy_invalid"
            )

    @staticmethod
    def _payload(
        value: OperationalKnowledgeIndexRecord
        | OperationalKnowledgeRetrievalPublicationPolicySnapshot
        | OperationalKnowledgeRetrievalPublicationClaim
        | OperationalKnowledgeRetrievalPublicationReceipt
        | OperationalKnowledgeRetrievalPublicationRecord,
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
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_human_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = KNOWLEDGE_RETRIEVAL_PUBLICATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-retrieval-index-publication",
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
                resource_type="resource.knowledge.operational-retrieval-publication",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )


def build_development_operational_knowledge_retrieval_publication_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
    index_policy: OperationalKnowledgeIndexPolicySnapshot,
) -> OperationalKnowledgeRetrievalPublicationPolicySnapshot:
    digest = OperationalKnowledgeRetrievalIndexPublicationService._digest
    publication_profile_id = "knowledge-retrieval-publication-profile.development-v1"
    route_profile_digest = digest(
        [
            "knowledge-retrieval-route-profile.v1",
            organization_id,
            environment_id,
            index_policy.index_profile_digest,
            index_policy.authorization_payload_profile_digest,
            "atomic-policy-filtered-route",
        ]
    )
    publication_profile_digest = digest(
        [
            publication_profile_id,
            index_policy.index_profile_digest,
            index_policy.staging_boundary_digest,
            route_profile_digest,
            "zero-partial-visibility-v1",
        ]
    )
    policy = OperationalKnowledgeRetrievalPublicationPolicySnapshot(
        policy_id="operational-knowledge-retrieval-publication-policy.development",
        schema_version=PUBLICATION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.operational-knowledge-retrieval-publication-development-v1",
        required_index_schema="atlas.operational-knowledge-index-staging.v1",
        required_index_state=INDEX_VALIDATED_STATE,
        required_index_profile_digest=index_policy.index_profile_digest,
        required_staging_boundary_digest=index_policy.staging_boundary_digest,
        required_authorization_payload_profile_digest=(
            index_policy.authorization_payload_profile_digest
        ),
        publication_profile_id=publication_profile_id,
        publication_profile_digest=publication_profile_digest,
        retrieval_route_profile_digest=route_profile_digest,
        maximum_authentication_age_minutes=15,
        subject_digest_salt_digest=index_policy.subject_digest_salt_digest,
        browser_binding_key_digest=digest(
            ["operational-knowledge-retrieval-publication-browser-key"]
        ),
        required_publisher_id="operational-knowledge-retrieval-publisher.synthetic",
        route_profile_owner_id="subject.operational-knowledge-retrieval-route-profile-owner",
        signed_by="subject.operational-knowledge-retrieval-publication-policy-signer",
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(
            OperationalKnowledgeRetrievalIndexPublicationService._payload(policy)
        ),
    )
