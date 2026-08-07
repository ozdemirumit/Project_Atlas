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
    KNOWLEDGE_PROTECTED_RETRIEVAL_CREATE,
    KNOWLEDGE_PROTECTED_RETRIEVAL_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.application.protected_retrieval_ports import (
    OperationalKnowledgeRetrievalError,
    OperationalKnowledgeRetrievalPermissionAuthorizer,
    OperationalKnowledgeRetrievalPolicySource,
    OperationalKnowledgeRetrievalPublicationSource,
    OperationalKnowledgeRetrievalRepository,
    OperationalKnowledgeRetrievalUncertainError,
    OperationalKnowledgeTrustedRetriever,
)
from atlas.modules.knowledge.domain.protected_retrieval import (
    RETRIEVED_STATE,
    OperationalKnowledgeRetrievalClaim,
    OperationalKnowledgeRetrievalInstruction,
    OperationalKnowledgeRetrievalPolicySnapshot,
    OperationalKnowledgeRetrievalReceipt,
    OperationalKnowledgeRetrievalRecord,
    OperationalKnowledgeRetrievalResult,
)
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    RETRIEVAL_PUBLISHED_STATE,
    OperationalKnowledgeRetrievalPublicationRecord,
)

RETRIEVAL_POLICY_SCHEMA = "atlas.operational-knowledge-retrieval-policy.v1"
RETRIEVAL_CLAIM_SCHEMA = "atlas.operational-knowledge-retrieval-claim.v1"
RETRIEVAL_RECORD_SCHEMA = "atlas.operational-knowledge-retrieval.v1"


class OperationalKnowledgeProtectedRetrievalService:
    def __init__(
        self,
        *,
        repository: OperationalKnowledgeRetrievalRepository,
        publication_source: OperationalKnowledgeRetrievalPublicationSource,
        policy_source: OperationalKnowledgeRetrievalPolicySource,
        permission_authorizer: OperationalKnowledgeRetrievalPermissionAuthorizer,
        retriever: OperationalKnowledgeTrustedRetriever,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._publication_source = publication_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._retriever = retriever
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        publication_id: str,
        publication_digest: str,
        retrieval_policy_id: str,
        retrieval_policy_digest: str,
        query: str,
        purpose: str,
        untrusted_evidence_acknowledged: bool,
        unsafe_instructions_acknowledged: bool,
        no_model_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalResult:
        self._require_enterprise_human(actor)
        query, purpose = query.strip(), purpose.strip()
        if (
            not 3 <= len(query) <= 4_000
            or not 20 <= len(purpose) <= 1_000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    untrusted_evidence_acknowledged,
                    unsafe_instructions_acknowledged,
                    no_model_or_operational_authority_acknowledged,
                )
            )
        ):
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_request_invalid"
            )
        publication = await self._publication_source.source_for_governed_retrieval(
            publication_id=publication_id
        )
        policy = await self._policy_source.get_by_id(policy_id=retrieval_policy_id)
        if publication is None or policy is None:
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_source_not_found"
            )
        now = self._clock()
        self._verify_source(publication, policy, publication_digest, retrieval_policy_digest, now)
        if len(query) > policy.maximum_query_characters or now - actor.authenticated_at > timedelta(
            minutes=policy.maximum_authentication_age_minutes
        ):
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_request_invalid"
            )
        self._require_scope(actor, publication.organization_id, publication.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        separated = {
            publication.publication_steward_subject_digest,
            *publication.upstream_accountable_subject_digests,
        }
        separated_identities = {
            policy.signed_by,
            policy.required_retriever_id,
            publication.publisher_id,
        }
        if subject_digest in separated or actor.subject_id in separated_identities:
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=publication.organization_id,
            environment_id=publication.environment_id,
            correlation_id=correlation_id,
        )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        query_digest = self._digest([query])
        authorization_context_digest = self._digest(
            [
                actor.organization_id,
                publication.environment_id,
                publication.classification,
                publication.access_policy_id,
                purpose,
                policy.authorization_profile_digest,
                actor.role_ids,
            ]
        )
        request_binding_digest = self._digest(
            [
                publication_id,
                publication_digest,
                retrieval_policy_digest,
                query_digest,
                purpose,
                subject_digest,
                browser_digest,
                authorization_context_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, publication_id, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=subject_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                actor=actor,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                query_digest=query_digest,
                authorization_context_digest=authorization_context_digest,
                correlation_id=correlation_id,
            )
        seed = self._digest([publication_id, subject_digest, idempotency_digest])
        retrieval_id = f"operational-knowledge-retrieval.{seed[:24]}"
        claim = OperationalKnowledgeRetrievalClaim(
            claim_id=f"operational-knowledge-retrieval-claim.{seed[:24]}",
            schema_version=RETRIEVAL_CLAIM_SCHEMA,
            version=1,
            retrieval_id=retrieval_id,
            publication_id=publication_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            query_digest=query_digest,
            organization_id=publication.organization_id,
            environment_id=publication.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor, correlation_id, "operational_knowledge_retrieval_requested", publication_id
        )
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_idempotency(
                claimed_by_subject_digest=subject_digest,
                idempotency_digest=idempotency_digest,
            )
            if concurrent is None:
                raise OperationalKnowledgeRetrievalUncertainError(
                    "operational_knowledge_retrieval_claim_uncertain"
                )
            return await self._reuse(
                concurrent,
                actor=actor,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                query_digest=query_digest,
                authorization_context_digest=authorization_context_digest,
                correlation_id=correlation_id,
            )
        await self._audit(
            actor, correlation_id, "operational_knowledge_retrieval_claimed", retrieval_id
        )
        expires_at = now + timedelta(minutes=policy.retention_minutes)
        instruction = OperationalKnowledgeRetrievalInstruction(
            retrieval_id=retrieval_id,
            organization_id=publication.organization_id,
            environment_id=publication.environment_id,
            publication_id=publication.publication_id,
            publication_digest=publication.canonical_digest,
            route_generation_digest=publication.route_generation_digest,
            classification=publication.classification,
            access_policy_id=publication.access_policy_id,
            retention_policy_id=publication.retention_policy_id,
            consumer_subject_digest=subject_digest,
            authorization_context_digest=authorization_context_digest,
            browser_session_binding_digest=browser_digest,
            query=query,
            query_digest=query_digest,
            purpose=purpose,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            retrieval_profile_digest=policy.retrieval_profile_digest,
            authorization_profile_digest=policy.authorization_profile_digest,
            ranking_profile_digest=policy.ranking_profile_digest,
            evidence_profile_digest=policy.evidence_profile_digest,
            maximum_results=policy.maximum_results,
            maximum_excerpt_characters=policy.maximum_excerpt_characters,
            protected_vault_id=policy.protected_vault_id,
            requested_at=now,
            expires_at=expires_at,
        )
        try:
            receipt, evidence = await self._retriever.retrieve(instruction)
            self._verify_receipt(receipt, instruction, policy, evidence.canonical_digest)
        except OperationalKnowledgeRetrievalError:
            raise
        except Exception as error:
            raise OperationalKnowledgeRetrievalUncertainError(
                "operational_knowledge_retrieval_outcome_uncertain"
            ) from error
        record = OperationalKnowledgeRetrievalRecord(
            retrieval_id=retrieval_id,
            schema_version=RETRIEVAL_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            publication_id=publication.publication_id,
            publication_digest=publication.canonical_digest,
            knowledge_item_id=publication.knowledge_item_id,
            organization_id=publication.organization_id,
            environment_id=publication.environment_id,
            classification=publication.classification,
            access_policy_id=publication.access_policy_id,
            retention_policy_id=publication.retention_policy_id,
            consumer_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            retrieval_policy_id=policy.policy_id,
            retrieval_policy_digest=policy.canonical_digest,
            retrieval_policy_version=policy.policy_version,
            retriever_id=receipt.retriever_id,
            retrieval_receipt_digest=receipt.canonical_digest,
            query_digest=query_digest,
            authorization_context_digest=authorization_context_digest,
            evidence_package_digest=receipt.evidence_package_digest,
            protected_artifact_reference=receipt.protected_artifact_reference,
            protected_artifact_digest=receipt.protected_artifact_digest,
            result_count=receipt.result_count,
            outcome=receipt.outcome,
            retrieved_at=receipt.retrieved_at,
            expires_at=receipt.expires_at,
            instance_state=RETRIEVED_STATE,
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise OperationalKnowledgeRetrievalUncertainError(
                "operational_knowledge_retrieval_persistence_uncertain"
            )
        await self._audit(actor, correlation_id, "operational_knowledge_retrieved", retrieval_id)
        return OperationalKnowledgeRetrievalResult(record=record, evidence=evidence)

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        retrieval_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalResult:
        self._require_enterprise_human(actor)
        record = await self._repository.get(retrieval_id=retrieval_id)
        if record is None:
            raise OperationalKnowledgeRetrievalError("operational_knowledge_retrieval_not_found")
        policy = await self._policy_source.get_by_id(policy_id=record.retrieval_policy_id)
        publication = await self._publication_source.source_for_governed_retrieval(
            publication_id=record.publication_id
        )
        now = self._clock()
        if (
            policy is None
            or publication is None
            or now >= record.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise OperationalKnowledgeRetrievalError("operational_knowledge_retrieval_not_found")
        self._verify_source(
            publication,
            policy,
            record.publication_digest,
            record.retrieval_policy_digest,
            now,
        )
        self._require_scope(actor, record.organization_id, record.environment_id)
        subject_digest = self._digest([policy.subject_digest_salt_digest, actor.subject_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            subject_digest != record.consumer_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise OperationalKnowledgeRetrievalError("operational_knowledge_retrieval_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        authorization_context_digest = self._digest(
            [
                actor.organization_id,
                record.environment_id,
                record.classification,
                record.access_policy_id,
                record.purpose,
                policy.authorization_profile_digest,
                actor.role_ids,
            ]
        )
        if authorization_context_digest != record.authorization_context_digest:
            raise OperationalKnowledgeRetrievalError("operational_knowledge_retrieval_not_found")
        evidence = await self._retriever.rehydrate(
            record=record,
            authorization_context_digest=authorization_context_digest,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_retrieval_read",
            retrieval_id,
            permission_id=KNOWLEDGE_PROTECTED_RETRIEVAL_READ,
        )
        return OperationalKnowledgeRetrievalResult(
            record=replace(record, reused=True), evidence=evidence
        )

    async def close(self) -> None:
        await self._repository.close()

    async def _reuse(
        self,
        claim: OperationalKnowledgeRetrievalClaim,
        *,
        actor: AuthenticatedSubject,
        browser_digest: str,
        request_binding_digest: str,
        query_digest: str,
        authorization_context_digest: str,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.query_digest != query_digest
        ):
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_idempotency_conflict"
            )
        record = await self._repository.get(retrieval_id=claim.retrieval_id)
        if record is None:
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_already_claimed"
            )
        evidence = await self._retriever.rehydrate(
            record=record,
            authorization_context_digest=authorization_context_digest,
        )
        await self._audit(
            actor,
            correlation_id,
            "operational_knowledge_retrieval_read",
            record.retrieval_id,
            permission_id=KNOWLEDGE_PROTECTED_RETRIEVAL_READ,
        )
        return OperationalKnowledgeRetrievalResult(
            record=replace(record, reused=True), evidence=evidence
        )

    def _verify_source(
        self,
        publication: OperationalKnowledgeRetrievalPublicationRecord,
        policy: OperationalKnowledgeRetrievalPolicySnapshot,
        publication_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        later = (
            publication.model_context_available,
            publication.graph_updated,
            publication.scheduled,
            publication.workflow_continued,
            publication.execution_authorized,
            publication.deployment_approved,
            publication.infrastructure_mutation_performed,
        )
        if (
            publication.canonical_digest != publication_digest
            or publication.canonical_digest != self._digest(self._payload(publication))
            or publication.schema_version != policy.required_publication_schema
            or publication.instance_state != policy.required_publication_state
            or publication.instance_state != RETRIEVAL_PUBLISHED_STATE
            or not publication.knowledge_published
            or not publication.retrieval_published
            or any(later)
            or policy.canonical_digest != policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or policy.organization_id != publication.organization_id
            or policy.environment_id != publication.environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_source_invalid"
            )

    @staticmethod
    def _verify_receipt(
        receipt: OperationalKnowledgeRetrievalReceipt,
        instruction: OperationalKnowledgeRetrievalInstruction,
        policy: OperationalKnowledgeRetrievalPolicySnapshot,
        evidence_digest: str,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.retriever_id != policy.required_retriever_id
            or receipt.attested_by != policy.required_retriever_attestor_id
            or receipt.retrieval_id != instruction.retrieval_id
            or receipt.publication_id != instruction.publication_id
            or receipt.publication_digest != instruction.publication_digest
            or receipt.consumer_subject_digest != instruction.consumer_subject_digest
            or receipt.query_digest != instruction.query_digest
            or receipt.authorization_context_digest != instruction.authorization_context_digest
            or receipt.evidence_package_digest != evidence_digest
            or receipt.result_count > policy.maximum_results
            or receipt.expires_at != instruction.expires_at
            or receipt.canonical_digest
            != OperationalKnowledgeProtectedRetrievalService._digest(
                OperationalKnowledgeProtectedRetrievalService._payload(receipt)
            )
        ):
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_receipt_invalid"
            )

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise OperationalKnowledgeRetrievalError(
                "operational_knowledge_retrieval_source_not_found"
            )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = KNOWLEDGE_PROTECTED_RETRIEVAL_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.operational-protected-retrieval",
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
                resource_type="resource.knowledge.operational-protected-retrieval",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    @classmethod
    def _payload(
        cls,
        value: OperationalKnowledgeRetrievalPolicySnapshot
        | OperationalKnowledgeRetrievalPublicationRecord
        | OperationalKnowledgeRetrievalClaim
        | OperationalKnowledgeRetrievalReceipt
        | OperationalKnowledgeRetrievalRecord,
    ) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(value))
        payload.pop("canonical_digest", None)
        payload.pop("reused", None)
        return payload

    @classmethod
    def _digest(cls, value: object) -> str:
        return sha256(
            json.dumps(
                cls._normalize(value),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest()

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value


def build_development_operational_knowledge_retrieval_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
    subject_digest_salt_digest: str,
) -> OperationalKnowledgeRetrievalPolicySnapshot:
    digest = OperationalKnowledgeProtectedRetrievalService._digest
    policy = OperationalKnowledgeRetrievalPolicySnapshot(
        policy_id="operational-knowledge-retrieval-policy.development",
        schema_version=RETRIEVAL_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.operational-knowledge-retrieval-development-v1",
        required_publication_schema="atlas.operational-knowledge-retrieval-publication.v1",
        required_publication_state=RETRIEVAL_PUBLISHED_STATE,
        required_retriever_id="operational-knowledge-trusted-retriever.synthetic",
        required_retriever_attestor_id=("subject.operational-knowledge-trusted-retriever-attestor"),
        required_receipt_schema="atlas.operational-knowledge-retrieval-receipt.v1",
        protected_vault_id="protected-retrieval-vault.development",
        retrieval_profile_digest=digest(["retrieval-profile.development-v1"]),
        authorization_profile_digest=digest(["authorization-filter.before-scoring-v1"]),
        ranking_profile_digest=digest(["ranking-profile.deterministic-v1"]),
        evidence_profile_digest=digest(["evidence-profile.citation-safe-v1"]),
        subject_digest_salt_digest=subject_digest_salt_digest,
        browser_binding_key_digest=digest(["operational-knowledge-retrieval-browser-key"]),
        maximum_authentication_age_minutes=15,
        maximum_query_characters=1_000,
        maximum_results=5,
        maximum_excerpt_characters=1_000,
        retention_minutes=30,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.operational-knowledge-retrieval-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(OperationalKnowledgeProtectedRetrievalService._payload(policy)),
    )
