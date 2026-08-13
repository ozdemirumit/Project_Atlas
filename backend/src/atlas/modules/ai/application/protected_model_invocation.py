from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Any, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.ai.application.protected_model_invocation_ports import (
    ProtectedModelInvocationError,
    ProtectedModelInvocationPermissionAuthorizer,
    ProtectedModelInvocationPolicySource,
    ProtectedModelInvocationRepository,
    ProtectedModelInvocationUncertainError,
    TrustedProtectedModelGateway,
)
from atlas.modules.ai.domain.protected_model_invocation import (
    ProtectedModelInvocationClaim,
    ProtectedModelInvocationInstruction,
    ProtectedModelInvocationManifest,
    ProtectedModelInvocationPolicySnapshot,
    ProtectedModelInvocationReceipt,
    ProtectedModelInvocationRecord,
    ProtectedModelInvocationResult,
    ProtectedModelResponseDraft,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_MODEL_INVOCATION_CREATE,
    AI_PROTECTED_MODEL_INVOCATION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)
from atlas.modules.knowledge.application.model_context_assembly import (
    GovernedProtectedModelContextService,
)
from atlas.modules.knowledge.application.model_context_assembly_ports import (
    ProtectedModelContextError,
    TrustedProtectedModelContextAssembler,
)
from atlas.modules.knowledge.domain.model_context_assembly import (
    ASSEMBLED_STATE,
    ProtectedModelContextPackage,
    ProtectedModelContextRecord,
    ProtectedModelContextResult,
)

INVOCATION_POLICY_SCHEMA = "atlas.protected-model-invocation-policy.v1"
INVOCATION_CLAIM_SCHEMA = "atlas.protected-model-invocation-claim.v1"
INVOCATION_RECORD_SCHEMA = "atlas.protected-model-invocation.v1"


class GovernedProtectedModelInvocationService:
    def __init__(
        self,
        *,
        repository: ProtectedModelInvocationRepository,
        context_source: GovernedProtectedModelContextService,
        context_vault: TrustedProtectedModelContextAssembler,
        policy_source: ProtectedModelInvocationPolicySource,
        permission_authorizer: ProtectedModelInvocationPermissionAuthorizer,
        gateway: TrustedProtectedModelGateway,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._context_source = context_source
        self._context_vault = context_vault
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._gateway = gateway
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        context_id: str,
        context_digest: str,
        invocation_policy_id: str,
        invocation_policy_digest: str,
        purpose: str,
        draft_untrusted_acknowledged: bool,
        citations_and_unknowns_acknowledged: bool,
        no_answer_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProtectedModelInvocationResult:
        self._require_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1_000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    draft_untrusted_acknowledged,
                    citations_and_unknowns_acknowledged,
                    no_answer_or_operational_authority_acknowledged,
                )
            )
        ):
            raise ProtectedModelInvocationError("protected_model_invocation_request_invalid")
        policy = await self._policy_source.get_by_id(policy_id=invocation_policy_id)
        if policy is None:
            raise ProtectedModelInvocationError("protected_model_invocation_source_not_found")
        context = await self._get_context(actor, context_id, browser_session_id, correlation_id)
        now = self._clock()
        self._verify_context(
            context.record, policy, context_digest, invocation_policy_digest, purpose, now
        )
        self._require_policy_assurance(actor, policy)
        self._require_scope(actor, context.record.organization_id, context.record.environment_id)
        if actor.subject_id in {
            policy.signed_by,
            policy.endpoint_owner_id,
            policy.endpoint_evaluator_id,
            policy.required_gateway_id,
            policy.required_gateway_attestor_id,
        }:
            raise ProtectedModelInvocationError(
                "protected_model_invocation_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=context.record.organization_id,
            environment_id=context.record.environment_id,
            correlation_id=correlation_id,
        )
        subject_digest = context.record.consumer_subject_digest
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        authorization_digest = self._authorization_digest(actor, context.record, policy)
        request_digest = self._digest(
            [
                context_id,
                context_digest,
                invocation_policy_digest,
                purpose,
                subject_digest,
                browser_digest,
                authorization_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, context_id, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=subject_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                browser_digest,
                request_digest,
                authorization_digest,
                actor,
                correlation_id,
            )
        seed = self._digest([context_id, subject_digest, idempotency_digest])
        invocation_id = f"protected-model-invocation.{seed[:24]}"
        claim = ProtectedModelInvocationClaim(
            claim_id=f"protected-model-invocation-claim.{seed[:24]}",
            schema_version=INVOCATION_CLAIM_SCHEMA,
            version=1,
            invocation_id=invocation_id,
            context_id=context_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            organization_id=context.record.organization_id,
            environment_id=context.record.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(actor, correlation_id, "protected_model_invocation_requested", context_id)
        if not await self._repository.claim(claim):
            raise ProtectedModelInvocationUncertainError(
                "protected_model_invocation_claim_uncertain"
            )
        await self._audit(
            actor, correlation_id, "protected_model_invocation_claimed", invocation_id
        )
        package = await self._context_vault.rehydrate(
            record=context.record,
            authorization_context_digest=context.record.authorization_context_digest,
        )
        if package.canonical_digest != context.record.context_package_digest:
            raise ProtectedModelInvocationError(
                "protected_model_invocation_context_integrity_failed"
            )
        expires_at = min(
            context.record.expires_at, now + timedelta(minutes=policy.retention_minutes)
        )
        instruction = ProtectedModelInvocationInstruction(
            invocation_id=invocation_id,
            context_id=context_id,
            context_digest=context.record.canonical_digest,
            context_package_digest=context.record.context_package_digest,
            organization_id=context.record.organization_id,
            environment_id=context.record.environment_id,
            consumer_subject_digest=subject_digest,
            authorization_context_digest=context.record.authorization_context_digest,
            invocation_authorization_digest=authorization_digest,
            endpoint_profile_id=policy.endpoint_profile_id,
            endpoint_profile_digest=policy.endpoint_profile_digest,
            model_id=policy.model_id,
            task_class=policy.task_class,
            output_schema_version=policy.output_schema_version,
            maximum_output_tokens=policy.maximum_output_tokens,
            timeout_seconds=policy.timeout_seconds,
            requested_at=now,
            expires_at=expires_at,
        )
        try:
            receipt, draft = await self._gateway.invoke(instruction, package)
            self._verify_receipt(receipt, draft, instruction, package, policy)
        except ProtectedModelInvocationError:
            raise
        except Exception as error:
            raise ProtectedModelInvocationUncertainError(
                "protected_model_invocation_outcome_uncertain"
            ) from error
        record = ProtectedModelInvocationRecord(
            invocation_id=invocation_id,
            schema_version=INVOCATION_RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            context_id=context_id,
            context_digest=context.record.canonical_digest,
            context_package_digest=context.record.context_package_digest,
            organization_id=context.record.organization_id,
            environment_id=context.record.environment_id,
            classification=context.record.classification,
            consumer_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            invocation_policy_id=policy.policy_id,
            invocation_policy_digest=policy.canonical_digest,
            invocation_policy_version=policy.policy_version,
            gateway_id=receipt.gateway_id,
            invocation_receipt_digest=receipt.canonical_digest,
            invocation_authorization_digest=authorization_digest,
            endpoint_profile_id=receipt.endpoint_profile_id,
            endpoint_profile_digest=receipt.endpoint_profile_digest,
            model_id=receipt.model_id,
            task_class=policy.task_class,
            response_schema_version=receipt.response_schema_version,
            protected_draft_reference=receipt.protected_draft_reference,
            protected_draft_digest=receipt.protected_draft_digest,
            draft_digest=receipt.draft_digest,
            citation_set_digest=receipt.citation_set_digest,
            output_safety_digest=receipt.output_safety_digest,
            input_tokens=receipt.input_tokens,
            output_tokens=receipt.output_tokens,
            maximum_output_tokens=policy.maximum_output_tokens,
            finish_reason=receipt.finish_reason,
            outcome=receipt.outcome,
            invoked_at=receipt.invoked_at,
            expires_at=receipt.expires_at,
            instance_state="protected_model_invoked",
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise ProtectedModelInvocationUncertainError(
                "protected_model_invocation_persistence_uncertain"
            )
        await self._audit(actor, correlation_id, "protected_model_invoked", invocation_id)
        return ProtectedModelInvocationResult(record=record, manifest=self._manifest(record, draft))

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        invocation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedModelInvocationResult:
        self._require_human(actor)
        record = await self._repository.get(invocation_id=invocation_id)
        if record is None or record.canonical_digest != self._digest(self._payload(record)):
            raise ProtectedModelInvocationError("protected_model_invocation_not_found")
        policy = await self._policy_source.get_by_id(policy_id=record.invocation_policy_id)
        if policy is None:
            raise ProtectedModelInvocationError("protected_model_invocation_not_found")
        context = await self._get_context(
            actor, record.context_id, browser_session_id, correlation_id
        )
        now = self._clock()
        self._verify_context(
            context.record,
            policy,
            record.context_digest,
            record.invocation_policy_digest,
            record.purpose,
            now,
        )
        self._require_policy_assurance(actor, policy)
        self._require_scope(actor, record.organization_id, record.environment_id)
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        authorization_digest = self._authorization_digest(actor, context.record, policy)
        if (
            browser_digest != record.browser_session_binding_digest
            or authorization_digest != record.invocation_authorization_digest
        ):
            raise ProtectedModelInvocationError("protected_model_invocation_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        draft = await self._gateway.rehydrate(
            record=record, invocation_authorization_digest=authorization_digest
        )
        if draft.canonical_digest != record.draft_digest:
            raise ProtectedModelInvocationError("protected_model_invocation_integrity_failed")
        await self._audit(
            actor,
            correlation_id,
            "protected_model_invocation_read",
            invocation_id,
            permission_id=AI_PROTECTED_MODEL_INVOCATION_READ,
        )
        return ProtectedModelInvocationResult(
            record=replace(record, reused=True), manifest=self._manifest(record, draft)
        )

    async def close(self) -> None:
        await self._repository.close()

    async def rehydrate_for_adjudication(
        self,
        *,
        actor: AuthenticatedSubject,
        invocation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> tuple[ProtectedModelInvocationResult, ProtectedModelResponseDraft]:
        """Rehydrate a draft only for a trusted downstream protected boundary."""
        result = await self.get(
            actor=actor,
            invocation_id=invocation_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        draft = await self._gateway.rehydrate(
            record=result.record,
            invocation_authorization_digest=result.record.invocation_authorization_digest,
        )
        if (
            draft.canonical_digest != result.record.draft_digest
            or draft.canonical_digest != self._digest(self._payload(draft))
        ):
            raise ProtectedModelInvocationError("protected_model_invocation_integrity_failed")
        await self._audit(
            actor,
            correlation_id,
            "protected_model_invocation_rehydrated_for_adjudication",
            invocation_id,
            permission_id=AI_PROTECTED_MODEL_INVOCATION_READ,
        )
        return result, draft

    async def _get_context(
        self,
        actor: AuthenticatedSubject,
        context_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedModelContextResult:
        try:
            return await self._context_source.get(
                actor=actor,
                context_id=context_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
        except ProtectedModelContextError as error:
            raise ProtectedModelInvocationError(
                "protected_model_invocation_source_not_found"
            ) from error

    def _verify_context(
        self,
        context: ProtectedModelContextRecord,
        policy: ProtectedModelInvocationPolicySnapshot,
        context_digest: str,
        policy_digest: str,
        purpose: str,
        now: datetime,
    ) -> None:
        if (
            context.canonical_digest != context_digest
            or context.canonical_digest != self._digest(self._payload(context))
            or context.instance_state != ASSEMBLED_STATE
            or not context.model_context_available
            or context.model_invoked
            or now >= context.expires_at
            or purpose != context.purpose
            or policy.canonical_digest != policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or policy.organization_id != context.organization_id
            or policy.environment_id != context.environment_id
            or policy.task_class != context.task_class
            or policy.output_schema_version != context.output_schema_version
            or policy.destination_profile_digest != context.destination_profile_digest
            or context.character_count > policy.maximum_context_characters
            or context.estimated_token_count > policy.maximum_context_tokens
            or not DataClassification(
                policy.classification_ceiling.removeprefix("classification.")
            ).permits(DataClassification(context.classification.removeprefix("classification.")))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedModelInvocationError("protected_model_invocation_source_invalid")

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ProtectedModelInvocationReceipt,
        draft: ProtectedModelResponseDraft,
        instruction: ProtectedModelInvocationInstruction,
        context: ProtectedModelContextPackage,
        policy: ProtectedModelInvocationPolicySnapshot,
    ) -> None:
        allowed_refs = {unit.evidence_reference_id for unit in context.evidence_units}
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.gateway_id != policy.required_gateway_id
            or receipt.attested_by != policy.required_gateway_attestor_id
            or receipt.invocation_id != instruction.invocation_id
            or receipt.context_id != instruction.context_id
            or receipt.context_digest != instruction.context_digest
            or receipt.context_package_digest != instruction.context_package_digest
            or receipt.authorization_context_digest != instruction.authorization_context_digest
            or receipt.endpoint_profile_id != policy.endpoint_profile_id
            or receipt.endpoint_profile_digest != policy.endpoint_profile_digest
            or receipt.model_id != policy.model_id
            or receipt.response_schema_version != policy.output_schema_version
            or draft.canonical_digest != cls._digest(cls._payload(draft))
            or receipt.draft_digest != draft.canonical_digest
            or not draft.summary.strip()
            or not draft.unknowns
            or not draft.citation_references
            or any(reference not in allowed_refs for reference in draft.citation_references)
            or receipt.citation_set_digest != cls._digest(draft.citation_references)
            or receipt.finish_reason not in policy.accepted_finish_reasons
            or receipt.output_tokens <= 0
            or receipt.output_tokens > policy.maximum_output_tokens
            or receipt.input_tokens > policy.maximum_context_tokens
            or receipt.expires_at != instruction.expires_at
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or not all(
                (
                    receipt.tools_disabled,
                    receipt.streaming_disabled,
                    receipt.schema_verified,
                    receipt.citations_verified,
                    receipt.output_safety_verified,
                    receipt.protected_vault_write_verified,
                    receipt.signature_verified,
                )
            )
        ):
            raise ProtectedModelInvocationError("protected_model_invocation_receipt_invalid")

    async def _reuse(
        self,
        claim: ProtectedModelInvocationClaim,
        browser_digest: str,
        request_digest: str,
        authorization_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ProtectedModelInvocationResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise ProtectedModelInvocationError("protected_model_invocation_idempotency_conflict")
        record = await self._repository.get(invocation_id=claim.invocation_id)
        if record is None or record.canonical_digest != self._digest(self._payload(record)):
            raise ProtectedModelInvocationError("protected_model_invocation_already_claimed")
        draft = await self._gateway.rehydrate(
            record=record, invocation_authorization_digest=authorization_digest
        )
        await self._audit(
            actor,
            correlation_id,
            "protected_model_invocation_read",
            record.invocation_id,
            permission_id=AI_PROTECTED_MODEL_INVOCATION_READ,
        )
        return ProtectedModelInvocationResult(
            record=replace(record, reused=True), manifest=self._manifest(record, draft)
        )

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ProtectedModelInvocationError("protected_model_invocation_human_required")

    @staticmethod
    def _require_policy_assurance(
        actor: AuthenticatedSubject, policy: ProtectedModelInvocationPolicySnapshot
    ) -> None:
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise ProtectedModelInvocationError(
                "protected_model_invocation_policy_assurance_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise ProtectedModelInvocationError("protected_model_invocation_source_not_found")

    @classmethod
    def _authorization_digest(
        cls,
        actor: AuthenticatedSubject,
        context: ProtectedModelContextRecord,
        policy: ProtectedModelInvocationPolicySnapshot,
    ) -> str:
        return cls._digest(
            [
                context.authorization_context_digest,
                actor.role_ids,
                policy.canonical_digest,
                policy.endpoint_profile_digest,
                policy.model_id,
            ]
        )

    @staticmethod
    def _manifest(
        record: ProtectedModelInvocationRecord, draft: ProtectedModelResponseDraft
    ) -> ProtectedModelInvocationManifest:
        return ProtectedModelInvocationManifest(
            invocation_id=record.invocation_id,
            context_id=record.context_id,
            endpoint_profile_id=record.endpoint_profile_id,
            model_id=record.model_id,
            task_class=record.task_class,
            response_schema_version=record.response_schema_version,
            citation_count=len(draft.citation_references),
            unknown_count=len(draft.unknowns),
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            maximum_output_tokens=record.maximum_output_tokens,
            finish_reason=record.finish_reason,
            outcome=record.outcome,
            draft_digest=record.draft_digest,
            citation_set_digest=record.citation_set_digest,
            output_safety_digest=record.output_safety_digest,
            invoked_at=record.invoked_at,
            expires_at=record.expires_at,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = AI_PROTECTED_MODEL_INVOCATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.protected-model-invocation",
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
                resource_type="resource.ai.protected-model-invocation",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    @classmethod
    def _payload(cls, value: Any) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(value))
        payload.pop("canonical_digest", None)
        payload.pop("reused", None)
        return payload

    @classmethod
    def _digest(cls, value: object) -> str:
        return sha256(
            json.dumps(
                cls._normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
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
        if isinstance(value, (list, tuple, set, frozenset)):
            return [cls._normalize(item) for item in value]
        return value


def build_development_protected_model_invocation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ProtectedModelInvocationPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = ProtectedModelInvocationPolicySnapshot(
        policy_id="protected-model-invocation-policy.development",
        schema_version=INVOCATION_POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.protected-model-invocation-development-v1",
        endpoint_profile_id="endpoint.model.synthetic-local",
        endpoint_profile_digest=digest(["endpoint.model.synthetic-local", "approved-v1"]),
        endpoint_owner_id="subject.model-endpoint-owner",
        endpoint_evaluator_id="subject.model-endpoint-evaluator",
        required_gateway_id="protected-model-gateway.synthetic",
        required_gateway_attestor_id="subject.protected-model-gateway-attestor",
        required_receipt_schema="atlas.protected-model-invocation-receipt.v1",
        protected_result_vault_id="protected-model-result-vault.development",
        model_id="atlas-local-synthetic",
        provider_type="openai_compatible",
        task_class="task.grounded-operational-analysis",
        output_schema_version="atlas.grounded-operational-analysis-output.v1",
        destination_profile_digest=digest(["destination-profile.local-openai-compatible-v1"]),
        classification_ceiling="classification.internal",
        network_boundary_digest=digest(["network-boundary.development-loopback"]),
        secret_reference_digest=digest(["secret.model.synthetic-reader"]),
        browser_binding_key_digest=digest(["protected-model-invocation-browser-key"]),
        maximum_authentication_age_minutes=15,
        maximum_context_characters=8_000,
        maximum_context_tokens=2_000,
        maximum_output_tokens=512,
        timeout_seconds=10,
        retention_minutes=15,
        accepted_finish_reasons=("stop",),
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        signed_by="subject.protected-model-invocation-policy-signer",
        signature_verified=True,
        endpoint_active=True,
        evaluation_approved=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
