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
    AI_PROTECTED_MODEL_CONTEXT_CREATE,
    AI_PROTECTED_MODEL_CONTEXT_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.application.model_context_assembly_ports import (
    ProtectedModelContextError,
    ProtectedModelContextPermissionAuthorizer,
    ProtectedModelContextPolicySource,
    ProtectedModelContextRepository,
    ProtectedModelContextRetrievalSource,
    ProtectedModelContextUncertainError,
    TrustedProtectedModelContextAssembler,
)
from atlas.modules.knowledge.application.protected_retrieval_ports import (
    OperationalKnowledgeRetrievalError,
)
from atlas.modules.knowledge.domain.model_context_assembly import (
    ASSEMBLED_STATE,
    INSUFFICIENT_STATE,
    ProtectedModelContextClaim,
    ProtectedModelContextInstruction,
    ProtectedModelContextManifest,
    ProtectedModelContextPackage,
    ProtectedModelContextPolicySnapshot,
    ProtectedModelContextReceipt,
    ProtectedModelContextRecord,
    ProtectedModelContextResult,
)
from atlas.modules.knowledge.domain.protected_retrieval import (
    RETRIEVED_STATE,
    OperationalKnowledgeRetrievalRecord,
    OperationalKnowledgeRetrievalResult,
)

MODEL_CONTEXT_POLICY_SCHEMA = "atlas.protected-model-context-policy.v1"
MODEL_CONTEXT_CLAIM_SCHEMA = "atlas.protected-model-context-claim.v1"
MODEL_CONTEXT_RECORD_SCHEMA = "atlas.protected-model-context.v1"


class GovernedProtectedModelContextService:
    def __init__(
        self,
        *,
        repository: ProtectedModelContextRepository,
        retrieval_source: ProtectedModelContextRetrievalSource,
        policy_source: ProtectedModelContextPolicySource,
        permission_authorizer: ProtectedModelContextPermissionAuthorizer,
        assembler: TrustedProtectedModelContextAssembler,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._retrieval_source = retrieval_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._assembler = assembler
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        retrieval_id: str,
        retrieval_digest: str,
        context_policy_id: str,
        context_policy_digest: str,
        objective: str,
        purpose: str,
        untrusted_intent_acknowledged: bool,
        citation_boundaries_acknowledged: bool,
        no_model_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProtectedModelContextResult:
        self._require_enterprise_human(actor)
        objective, purpose = objective.strip(), purpose.strip()
        if (
            not 3 <= len(objective) <= 4_000
            or not 20 <= len(purpose) <= 1_000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    untrusted_intent_acknowledged,
                    citation_boundaries_acknowledged,
                    no_model_or_operational_authority_acknowledged,
                )
            )
        ):
            raise ProtectedModelContextError("protected_model_context_request_invalid")
        policy = await self._policy_source.get_by_id(policy_id=context_policy_id)
        if policy is None:
            raise ProtectedModelContextError("protected_model_context_source_not_found")
        retrieval = await self._get_retrieval(
            actor=actor,
            retrieval_id=retrieval_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        now = self._clock()
        self._verify_source(
            retrieval.record,
            policy,
            retrieval_digest=retrieval_digest,
            policy_digest=context_policy_digest,
            now=now,
        )
        if (
            len(objective) > policy.maximum_objective_characters
            or purpose != retrieval.record.purpose
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise ProtectedModelContextError("protected_model_context_request_invalid")
        self._require_scope(
            actor, retrieval.record.organization_id, retrieval.record.environment_id
        )
        if actor.subject_id in {policy.signed_by, policy.required_assembler_id}:
            raise ProtectedModelContextError("protected_model_context_actor_separation_required")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=retrieval.record.organization_id,
            environment_id=retrieval.record.environment_id,
            correlation_id=correlation_id,
        )
        subject_digest = retrieval.record.consumer_subject_digest
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        objective_digest = self._digest([objective])
        authorization_context_digest = self._digest(
            [
                actor.organization_id,
                retrieval.record.environment_id,
                retrieval.record.classification,
                retrieval.record.access_policy_id,
                purpose,
                policy.task_class,
                policy.safety_profile_digest,
                policy.destination_profile_digest,
                actor.role_ids,
            ]
        )
        request_binding_digest = self._digest(
            [
                retrieval_id,
                retrieval_digest,
                context_policy_digest,
                objective_digest,
                purpose,
                subject_digest,
                browser_digest,
                authorization_context_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, retrieval_id, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=subject_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                objective_digest=objective_digest,
                authorization_context_digest=authorization_context_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        seed = self._digest([retrieval_id, subject_digest, idempotency_digest])
        context_id = f"protected-model-context.{seed[:24]}"
        claim = ProtectedModelContextClaim(
            claim_id=f"protected-model-context-claim.{seed[:24]}",
            schema_version=MODEL_CONTEXT_CLAIM_SCHEMA,
            version=1,
            context_id=context_id,
            retrieval_id=retrieval_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_binding_digest,
            idempotency_digest=idempotency_digest,
            objective_digest=objective_digest,
            organization_id=retrieval.record.organization_id,
            environment_id=retrieval.record.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(actor, correlation_id, "protected_model_context_requested", retrieval_id)
        if not await self._repository.claim(claim):
            concurrent = await self._repository.get_claim_by_idempotency(
                claimed_by_subject_digest=subject_digest,
                idempotency_digest=idempotency_digest,
            )
            if concurrent is None:
                raise ProtectedModelContextUncertainError("protected_model_context_claim_uncertain")
            return await self._reuse(
                concurrent,
                browser_digest=browser_digest,
                request_binding_digest=request_binding_digest,
                objective_digest=objective_digest,
                authorization_context_digest=authorization_context_digest,
                actor=actor,
                correlation_id=correlation_id,
            )
        await self._audit(actor, correlation_id, "protected_model_context_claimed", context_id)
        expires_at = min(
            retrieval.record.expires_at, now + timedelta(minutes=policy.retention_minutes)
        )
        instruction = ProtectedModelContextInstruction(
            context_id=context_id,
            retrieval_id=retrieval_id,
            retrieval_digest=retrieval.record.canonical_digest,
            retrieval_receipt_digest=retrieval.record.retrieval_receipt_digest,
            evidence_package_digest=retrieval.record.evidence_package_digest,
            organization_id=retrieval.record.organization_id,
            environment_id=retrieval.record.environment_id,
            classification=retrieval.record.classification,
            access_policy_id=retrieval.record.access_policy_id,
            consumer_subject_digest=subject_digest,
            authorization_context_digest=authorization_context_digest,
            browser_session_binding_digest=browser_digest,
            objective=objective,
            objective_digest=objective_digest,
            purpose=purpose,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            task_class=policy.task_class,
            output_schema_version=policy.output_schema_version,
            context_profile_digest=policy.context_profile_digest,
            safety_profile_digest=policy.safety_profile_digest,
            budgeting_profile_digest=policy.budgeting_profile_digest,
            destination_profile_digest=policy.destination_profile_digest,
            maximum_context_characters=policy.maximum_context_characters,
            maximum_estimated_tokens=policy.maximum_estimated_tokens,
            maximum_evidence_items=policy.maximum_evidence_items,
            protected_vault_id=policy.protected_vault_id,
            requested_at=now,
            expires_at=expires_at,
        )
        try:
            receipt, package = await self._assembler.assemble(instruction, retrieval.evidence)
            self._verify_receipt(receipt, instruction, policy, package)
        except ProtectedModelContextError:
            raise
        except Exception as error:
            raise ProtectedModelContextUncertainError(
                "protected_model_context_outcome_uncertain"
            ) from error
        assembled = receipt.outcome == "context-outcome.assembled"
        record = ProtectedModelContextRecord(
            context_id=context_id,
            schema_version=MODEL_CONTEXT_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            retrieval_id=retrieval_id,
            retrieval_digest=retrieval.record.canonical_digest,
            publication_id=retrieval.record.publication_id,
            organization_id=retrieval.record.organization_id,
            environment_id=retrieval.record.environment_id,
            classification=retrieval.record.classification,
            access_policy_id=retrieval.record.access_policy_id,
            consumer_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            context_policy_id=policy.policy_id,
            context_policy_digest=policy.canonical_digest,
            context_policy_version=policy.policy_version,
            assembler_id=receipt.assembler_id,
            assembly_receipt_digest=receipt.canonical_digest,
            objective_digest=objective_digest,
            authorization_context_digest=authorization_context_digest,
            context_package_digest=receipt.context_package_digest,
            protected_artifact_reference=receipt.protected_artifact_reference,
            protected_artifact_digest=receipt.protected_artifact_digest,
            evidence_set_digest=receipt.evidence_set_digest,
            citation_set_digest=receipt.citation_set_digest,
            safety_validation_digest=receipt.safety_validation_digest,
            budget_allocation_digest=receipt.budget_allocation_digest,
            destination_profile_digest=receipt.destination_profile_digest,
            task_class=policy.task_class,
            output_schema_version=policy.output_schema_version,
            included_evidence_count=receipt.included_evidence_count,
            character_count=receipt.character_count,
            estimated_token_count=receipt.estimated_token_count,
            maximum_context_characters=policy.maximum_context_characters,
            maximum_estimated_tokens=policy.maximum_estimated_tokens,
            outcome=receipt.outcome,
            assembled_at=receipt.assembled_at,
            expires_at=receipt.expires_at,
            instance_state=ASSEMBLED_STATE if assembled else INSUFFICIENT_STATE,
            purpose=purpose,
            canonical_digest="0" * 64,
            model_context_available=assembled,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise ProtectedModelContextUncertainError(
                "protected_model_context_persistence_uncertain"
            )
        await self._audit(actor, correlation_id, record.instance_state, context_id)
        return ProtectedModelContextResult(record=record, manifest=self._manifest(record))

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        context_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedModelContextResult:
        self._require_enterprise_human(actor)
        record = await self._repository.get(context_id=context_id)
        if record is None or record.canonical_digest != self._digest(self._payload(record)):
            raise ProtectedModelContextError("protected_model_context_not_found")
        policy = await self._policy_source.get_by_id(policy_id=record.context_policy_id)
        now = self._clock()
        if (
            policy is None
            or now >= record.expires_at
            or now - actor.authenticated_at
            > timedelta(minutes=policy.maximum_authentication_age_minutes)
        ):
            raise ProtectedModelContextError("protected_model_context_not_found")
        retrieval = await self._get_retrieval(
            actor=actor,
            retrieval_id=record.retrieval_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        self._verify_source(
            retrieval.record,
            policy,
            retrieval_digest=record.retrieval_digest,
            policy_digest=record.context_policy_digest,
            now=now,
        )
        self._require_scope(actor, record.organization_id, record.environment_id)
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        if (
            retrieval.record.consumer_subject_digest != record.consumer_subject_digest
            or browser_digest != record.browser_session_binding_digest
        ):
            raise ProtectedModelContextError("protected_model_context_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        authorization_context_digest = self._authorization_context_digest(actor, record, policy)
        if authorization_context_digest != record.authorization_context_digest:
            raise ProtectedModelContextError("protected_model_context_not_found")
        package = await self._assembler.rehydrate(
            record=record,
            authorization_context_digest=authorization_context_digest,
        )
        if package.canonical_digest != record.context_package_digest:
            raise ProtectedModelContextError("protected_model_context_integrity_failed")
        await self._audit(
            actor,
            correlation_id,
            "protected_model_context_read",
            context_id,
            permission_id=AI_PROTECTED_MODEL_CONTEXT_READ,
        )
        return ProtectedModelContextResult(
            record=replace(record, reused=True), manifest=self._manifest(record)
        )

    async def close(self) -> None:
        await self._repository.close()

    async def _get_retrieval(
        self,
        *,
        actor: AuthenticatedSubject,
        retrieval_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> OperationalKnowledgeRetrievalResult:
        try:
            return await self._retrieval_source.get(
                actor=actor,
                retrieval_id=retrieval_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
        except OperationalKnowledgeRetrievalError as error:
            raise ProtectedModelContextError("protected_model_context_source_not_found") from error

    async def _reuse(
        self,
        claim: ProtectedModelContextClaim,
        *,
        browser_digest: str,
        request_binding_digest: str,
        objective_digest: str,
        authorization_context_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ProtectedModelContextResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_binding_digest
            or claim.objective_digest != objective_digest
        ):
            raise ProtectedModelContextError("protected_model_context_idempotency_conflict")
        record = await self._repository.get(context_id=claim.context_id)
        if record is None:
            raise ProtectedModelContextError("protected_model_context_already_claimed")
        if record.canonical_digest != self._digest(self._payload(record)):
            raise ProtectedModelContextError("protected_model_context_integrity_failed")
        package = await self._assembler.rehydrate(
            record=record,
            authorization_context_digest=authorization_context_digest,
        )
        if package.canonical_digest != record.context_package_digest:
            raise ProtectedModelContextError("protected_model_context_integrity_failed")
        await self._audit(
            actor,
            correlation_id,
            "protected_model_context_read",
            record.context_id,
            permission_id=AI_PROTECTED_MODEL_CONTEXT_READ,
        )
        return ProtectedModelContextResult(
            record=replace(record, reused=True), manifest=self._manifest(record)
        )

    def _verify_source(
        self,
        retrieval: OperationalKnowledgeRetrievalRecord,
        policy: ProtectedModelContextPolicySnapshot,
        *,
        retrieval_digest: str,
        policy_digest: str,
        now: datetime,
    ) -> None:
        later = (
            retrieval.model_context_available,
            retrieval.graph_updated,
            retrieval.scheduled,
            retrieval.workflow_continued,
            retrieval.execution_authorized,
            retrieval.deployment_approved,
            retrieval.infrastructure_mutation_performed,
        )
        if (
            retrieval.canonical_digest != retrieval_digest
            or retrieval.canonical_digest != self._digest(self._payload(retrieval))
            or retrieval.schema_version != policy.required_retrieval_schema
            or retrieval.instance_state != policy.required_retrieval_state
            or retrieval.instance_state != RETRIEVED_STATE
            or not retrieval.knowledge_retrieved
            or any(later)
            or now >= retrieval.expires_at
            or policy.canonical_digest != policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or policy.organization_id != retrieval.organization_id
            or policy.environment_id != retrieval.environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedModelContextError("protected_model_context_source_invalid")

    @staticmethod
    def _verify_receipt(
        receipt: ProtectedModelContextReceipt,
        instruction: ProtectedModelContextInstruction,
        policy: ProtectedModelContextPolicySnapshot,
        package: ProtectedModelContextPackage,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.assembler_id != policy.required_assembler_id
            or receipt.attested_by != policy.required_assembler_attestor_id
            or receipt.context_id != instruction.context_id
            or receipt.retrieval_id != instruction.retrieval_id
            or receipt.retrieval_digest != instruction.retrieval_digest
            or receipt.consumer_subject_digest != instruction.consumer_subject_digest
            or receipt.authorization_context_digest != instruction.authorization_context_digest
            or receipt.objective_digest != instruction.objective_digest
            or package.canonical_digest
            != GovernedProtectedModelContextService._digest(
                GovernedProtectedModelContextService._payload(package)
            )
            or receipt.context_package_digest != package.canonical_digest
            or receipt.included_evidence_count != len(package.evidence_units)
            or receipt.character_count != package.character_count
            or receipt.estimated_token_count != package.estimated_token_count
            or receipt.included_evidence_count > policy.maximum_evidence_items
            or receipt.character_count > policy.maximum_context_characters
            or receipt.estimated_token_count > policy.maximum_estimated_tokens
            or receipt.destination_profile_digest != policy.destination_profile_digest
            or receipt.expires_at != instruction.expires_at
            or receipt.canonical_digest
            != GovernedProtectedModelContextService._digest(
                GovernedProtectedModelContextService._payload(receipt)
            )
        ):
            raise ProtectedModelContextError("protected_model_context_receipt_invalid")

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise ProtectedModelContextError(
                "protected_model_context_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise ProtectedModelContextError("protected_model_context_source_not_found")

    @classmethod
    def _authorization_context_digest(
        cls,
        actor: AuthenticatedSubject,
        record: ProtectedModelContextRecord,
        policy: ProtectedModelContextPolicySnapshot,
    ) -> str:
        return cls._digest(
            [
                actor.organization_id,
                record.environment_id,
                record.classification,
                record.access_policy_id,
                record.purpose,
                policy.task_class,
                policy.safety_profile_digest,
                policy.destination_profile_digest,
                actor.role_ids,
            ]
        )

    @staticmethod
    def _manifest(record: ProtectedModelContextRecord) -> ProtectedModelContextManifest:
        return ProtectedModelContextManifest(
            context_id=record.context_id,
            retrieval_id=record.retrieval_id,
            task_class=record.task_class,
            output_schema_version=record.output_schema_version,
            classification=record.classification,
            included_evidence_count=record.included_evidence_count,
            character_count=record.character_count,
            estimated_token_count=record.estimated_token_count,
            maximum_context_characters=record.maximum_context_characters,
            maximum_estimated_tokens=record.maximum_estimated_tokens,
            outcome=record.outcome,
            evidence_set_digest=record.evidence_set_digest,
            citation_set_digest=record.citation_set_digest,
            safety_validation_digest=record.safety_validation_digest,
            context_package_digest=record.context_package_digest,
            assembled_at=record.assembled_at,
            expires_at=record.expires_at,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = AI_PROTECTED_MODEL_CONTEXT_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.protected-model-context",
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
                resource_type="resource.ai.protected-model-context",
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
        value: ProtectedModelContextPolicySnapshot
        | OperationalKnowledgeRetrievalRecord
        | ProtectedModelContextClaim
        | ProtectedModelContextPackage
        | ProtectedModelContextReceipt
        | ProtectedModelContextRecord,
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


def build_development_protected_model_context_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> ProtectedModelContextPolicySnapshot:
    digest = GovernedProtectedModelContextService._digest
    policy = ProtectedModelContextPolicySnapshot(
        policy_id="protected-model-context-policy.development",
        schema_version=MODEL_CONTEXT_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.protected-model-context-development-v1",
        required_retrieval_schema="atlas.operational-knowledge-retrieval.v1",
        required_retrieval_state=RETRIEVED_STATE,
        required_assembler_id="protected-model-context-assembler.synthetic",
        required_assembler_attestor_id="subject.protected-model-context-assembler-attestor",
        required_receipt_schema="atlas.protected-model-context-receipt.v1",
        protected_vault_id="protected-model-context-vault.development",
        task_class="task.grounded-operational-analysis",
        output_schema_version="atlas.grounded-operational-analysis-output.v1",
        context_profile_digest=digest(["context-profile.layered-v1"]),
        safety_profile_digest=digest(["safety-profile.untrusted-evidence-isolation-v1"]),
        budgeting_profile_digest=digest(["budget-profile.deterministic-four-char-v1"]),
        destination_profile_digest=digest(["destination-profile.local-openai-compatible-v1"]),
        browser_binding_key_digest=digest(["protected-model-context-browser-key"]),
        maximum_authentication_age_minutes=15,
        maximum_objective_characters=1_000,
        maximum_context_characters=8_000,
        maximum_estimated_tokens=2_000,
        maximum_evidence_items=5,
        retention_minutes=20,
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED,
        signed_by="subject.protected-model-context-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(GovernedProtectedModelContextService._payload(policy)),
    )
