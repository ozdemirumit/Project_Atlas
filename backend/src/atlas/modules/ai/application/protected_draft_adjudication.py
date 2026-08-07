from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.ai.application.protected_draft_adjudication_ports import (
    ProtectedDraftAdjudicationError,
    ProtectedDraftAdjudicationPermissionAuthorizer,
    ProtectedDraftAdjudicationPolicySource,
    ProtectedDraftAdjudicationRepository,
    ProtectedDraftAdjudicationUncertainError,
    TrustedProtectedDraftAdjudicator,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationClaim,
    ProtectedDraftAdjudicationInstruction,
    ProtectedDraftAdjudicationManifest,
    ProtectedDraftAdjudicationPolicySnapshot,
    ProtectedDraftAdjudicationReceipt,
    ProtectedDraftAdjudicationRecord,
    ProtectedDraftAdjudicationReport,
    ProtectedDraftAdjudicationResult,
)
from atlas.modules.ai.domain.protected_model_invocation import (
    ProtectedModelInvocationRecord,
    ProtectedModelInvocationResult,
    ProtectedModelResponseDraft,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_DRAFT_ADJUDICATION_CREATE,
    AI_PROTECTED_DRAFT_ADJUDICATION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.application.model_context_assembly import (
    GovernedProtectedModelContextService,
)
from atlas.modules.knowledge.application.model_context_assembly_ports import (
    TrustedProtectedModelContextAssembler,
)
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage

POLICY_SCHEMA = "atlas.protected-draft-adjudication-policy.v1"
CLAIM_SCHEMA = "atlas.protected-draft-adjudication-claim.v1"
RECORD_SCHEMA = "atlas.protected-draft-adjudication.v1"


class GovernedProtectedDraftAdjudicationService:
    def __init__(
        self,
        *,
        repository: ProtectedDraftAdjudicationRepository,
        invocation_source: GovernedProtectedModelInvocationService,
        context_source: GovernedProtectedModelContextService,
        context_vault: TrustedProtectedModelContextAssembler,
        policy_source: ProtectedDraftAdjudicationPolicySource,
        permission_authorizer: ProtectedDraftAdjudicationPermissionAuthorizer,
        adjudicator: TrustedProtectedDraftAdjudicator,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._invocation_source = invocation_source
        self._context_source = context_source
        self._context_vault = context_vault
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._adjudicator = adjudicator
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        invocation_id: str,
        invocation_digest: str,
        adjudication_policy_id: str,
        adjudication_policy_digest: str,
        purpose: str,
        draft_untrusted_acknowledged: bool,
        no_content_presentation_acknowledged: bool,
        no_answer_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProtectedDraftAdjudicationResult:
        self._require_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1_000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    draft_untrusted_acknowledged,
                    no_content_presentation_acknowledged,
                    no_answer_or_operational_authority_acknowledged,
                )
            )
        ):
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_request_invalid")
        policy = await self._policy_source.get_by_id(policy_id=adjudication_policy_id)
        if policy is None:
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_source_not_found")
        invocation, draft = await self._invocation_source.rehydrate_for_adjudication(
            actor=actor,
            invocation_id=invocation_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        now = self._clock()
        self._verify_invocation(
            invocation.record, policy, invocation_digest, adjudication_policy_digest, purpose, now
        )
        self._require_scope(
            actor, invocation.record.organization_id, invocation.record.environment_id
        )
        if actor.subject_id in {
            policy.signed_by,
            policy.required_adjudicator_id,
            policy.required_adjudicator_attestor_id,
        }:
            raise ProtectedDraftAdjudicationError(
                "protected_draft_adjudication_actor_separation_required"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=invocation.record.organization_id,
            environment_id=invocation.record.environment_id,
            correlation_id=correlation_id,
        )
        context = await self._context_source.get(
            actor=actor,
            context_id=invocation.record.context_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        package = await self._context_vault.rehydrate(
            record=context.record,
            authorization_context_digest=context.record.authorization_context_digest,
        )
        if package.canonical_digest != invocation.record.context_package_digest:
            raise ProtectedDraftAdjudicationError(
                "protected_draft_adjudication_context_integrity_failed"
            )
        subject_digest = invocation.record.consumer_subject_digest
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        authorization_digest = self._digest(
            [
                invocation.record.invocation_authorization_digest,
                actor.role_ids,
                policy.canonical_digest,
            ]
        )
        request_digest = self._digest(
            [
                invocation_id,
                invocation_digest,
                policy.canonical_digest,
                purpose,
                subject_digest,
                browser_digest,
                authorization_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, invocation_id, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=subject_digest, idempotency_digest=idempotency_digest
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
        seed = self._digest([invocation_id, subject_digest, idempotency_digest])
        adjudication_id = f"protected-draft-adjudication.{seed[:24]}"
        claim = ProtectedDraftAdjudicationClaim(
            claim_id=f"protected-draft-adjudication-claim.{seed[:24]}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            adjudication_id=adjudication_id,
            invocation_id=invocation_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            organization_id=invocation.record.organization_id,
            environment_id=invocation.record.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor, correlation_id, "protected_draft_adjudication_requested", invocation_id
        )
        if not await self._repository.claim(claim):
            raise ProtectedDraftAdjudicationUncertainError(
                "protected_draft_adjudication_claim_uncertain"
            )
        expires_at = min(
            invocation.record.expires_at, now + timedelta(minutes=policy.retention_minutes)
        )
        instruction = ProtectedDraftAdjudicationInstruction(
            adjudication_id=adjudication_id,
            invocation_id=invocation_id,
            invocation_digest=invocation.record.canonical_digest,
            context_id=invocation.record.context_id,
            context_digest=invocation.record.context_digest,
            context_package_digest=invocation.record.context_package_digest,
            draft_digest=invocation.record.draft_digest,
            citation_set_digest=invocation.record.citation_set_digest,
            output_safety_digest=invocation.record.output_safety_digest,
            organization_id=invocation.record.organization_id,
            environment_id=invocation.record.environment_id,
            consumer_subject_digest=subject_digest,
            adjudication_authorization_digest=authorization_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            validation_profile_digest=policy.validation_profile_digest,
            prohibited_output_profile_digest=policy.prohibited_output_profile_digest,
            minimum_citation_count=policy.minimum_citation_count,
            minimum_unknown_count=policy.minimum_unknown_count,
            maximum_summary_characters=policy.maximum_summary_characters,
            requested_at=now,
            expires_at=expires_at,
        )
        try:
            receipt, report = await self._adjudicator.adjudicate(instruction, draft, package)
            self._verify_receipt(receipt, report, instruction, policy)
        except ProtectedDraftAdjudicationError:
            raise
        except Exception as error:
            raise ProtectedDraftAdjudicationUncertainError(
                "protected_draft_adjudication_outcome_uncertain"
            ) from error
        record = ProtectedDraftAdjudicationRecord(
            adjudication_id=adjudication_id,
            schema_version=RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            invocation_id=invocation_id,
            invocation_digest=invocation.record.canonical_digest,
            context_id=invocation.record.context_id,
            context_digest=invocation.record.context_digest,
            organization_id=invocation.record.organization_id,
            environment_id=invocation.record.environment_id,
            classification=invocation.record.classification,
            consumer_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            adjudication_policy_id=policy.policy_id,
            adjudication_policy_digest=policy.canonical_digest,
            adjudication_policy_version=policy.policy_version,
            adjudicator_id=receipt.adjudicator_id,
            adjudication_receipt_digest=receipt.canonical_digest,
            adjudication_authorization_digest=authorization_digest,
            draft_digest=receipt.draft_digest,
            protected_report_reference=receipt.protected_report_reference,
            protected_report_digest=receipt.protected_report_digest,
            report_digest=receipt.report_digest,
            check_set_digest=receipt.check_set_digest,
            citation_coverage_digest=receipt.citation_coverage_digest,
            unknown_preservation_digest=receipt.unknown_preservation_digest,
            prohibited_output_digest=receipt.prohibited_output_digest,
            check_count=receipt.check_count,
            citation_count=receipt.citation_count,
            unknown_count=receipt.unknown_count,
            outcome=receipt.outcome,
            adjudicated_at=receipt.adjudicated_at,
            expires_at=receipt.expires_at,
            instance_state="protected_model_draft_adjudicated",
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        if not await self._repository.add(record):
            raise ProtectedDraftAdjudicationUncertainError(
                "protected_draft_adjudication_persistence_uncertain"
            )
        await self._audit(
            actor, correlation_id, "protected_model_draft_adjudicated", adjudication_id
        )
        return ProtectedDraftAdjudicationResult(record=record, manifest=self._manifest(record))

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        adjudication_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedDraftAdjudicationResult:
        self._require_human(actor)
        record = await self._repository.get(adjudication_id=adjudication_id)
        if record is None or record.canonical_digest != self._digest(self._payload(record)):
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_not_found")
        policy = await self._policy_source.get_by_id(policy_id=record.adjudication_policy_id)
        if policy is None:
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_not_found")
        invocation, _ = await self._invocation_source.rehydrate_for_adjudication(
            actor=actor,
            invocation_id=record.invocation_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        self._verify_invocation(
            invocation.record,
            policy,
            record.invocation_digest,
            record.adjudication_policy_digest,
            record.purpose,
            self._clock(),
        )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        authorization_digest = self._digest(
            [
                invocation.record.invocation_authorization_digest,
                actor.role_ids,
                policy.canonical_digest,
            ]
        )
        if (
            browser_digest != record.browser_session_binding_digest
            or authorization_digest != record.adjudication_authorization_digest
        ):
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        report = await self._adjudicator.rehydrate(
            record=record, adjudication_authorization_digest=authorization_digest
        )
        if report.canonical_digest != record.report_digest:
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_integrity_failed")
        await self._audit(
            actor,
            correlation_id,
            "protected_draft_adjudication_read",
            adjudication_id,
            permission_id=AI_PROTECTED_DRAFT_ADJUDICATION_READ,
        )
        return ProtectedDraftAdjudicationResult(
            record=replace(record, reused=True), manifest=self._manifest(record)
        )

    async def close(self) -> None:
        await self._repository.close()

    async def rehydrate_for_presentation(
        self,
        *,
        actor: AuthenticatedSubject,
        adjudication_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> tuple[
        ProtectedDraftAdjudicationResult,
        ProtectedDraftAdjudicationReport,
        ProtectedModelInvocationResult,
        ProtectedModelResponseDraft,
        ProtectedModelContextPackage,
    ]:
        adjudication = await self.get(
            actor=actor,
            adjudication_id=adjudication_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        invocation, draft = await self._invocation_source.rehydrate_for_adjudication(
            actor=actor,
            invocation_id=adjudication.record.invocation_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        context = await self._context_source.get(
            actor=actor,
            context_id=adjudication.record.context_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        package = await self._context_vault.rehydrate(
            record=context.record,
            authorization_context_digest=context.record.authorization_context_digest,
        )
        authorization_digest = self._digest(
            [
                invocation.record.invocation_authorization_digest,
                actor.role_ids,
                adjudication.record.adjudication_policy_digest,
            ]
        )
        report = await self._adjudicator.rehydrate(
            record=adjudication.record,
            adjudication_authorization_digest=authorization_digest,
        )
        if (
            invocation.record.canonical_digest != adjudication.record.invocation_digest
            or draft.canonical_digest != adjudication.record.draft_digest
            or package.canonical_digest != invocation.record.context_package_digest
            or report.canonical_digest != adjudication.record.report_digest
            or report.outcome != adjudication.record.outcome
        ):
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_integrity_failed")
        return adjudication, report, invocation, draft, package

    async def get_record_for_presentation_authorization(
        self, *, actor: AuthenticatedSubject, adjudication_id: str
    ) -> ProtectedDraftAdjudicationRecord:
        self._require_human(actor)
        record = await self._repository.get(adjudication_id=adjudication_id)
        if record is None or record.canonical_digest != self._digest(self._payload(record)):
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        return record

    def _verify_invocation(
        self,
        record: ProtectedModelInvocationRecord,
        policy: ProtectedDraftAdjudicationPolicySnapshot,
        invocation_digest: str,
        policy_digest: str,
        purpose: str,
        now: datetime,
    ) -> None:
        if (
            record.canonical_digest != invocation_digest
            or record.canonical_digest != self._digest(self._payload(record))
            or record.schema_version != policy.required_invocation_schema
            or record.instance_state != policy.required_invocation_state
            or not record.model_invoked
            or not record.protected_draft_available
            or record.answer_generated
            or now >= record.expires_at
            or purpose != record.purpose
            or policy.canonical_digest != policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or policy.organization_id != record.organization_id
            or policy.environment_id != record.environment_id
            or policy.required_draft_schema != record.response_schema_version
            or not DataClassification(
                policy.classification_ceiling.removeprefix("classification.")
            ).permits(DataClassification(record.classification.removeprefix("classification.")))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_source_invalid")

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ProtectedDraftAdjudicationReceipt,
        report: ProtectedDraftAdjudicationReport,
        instruction: ProtectedDraftAdjudicationInstruction,
        policy: ProtectedDraftAdjudicationPolicySnapshot,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.adjudicator_id != policy.required_adjudicator_id
            or receipt.attested_by != policy.required_adjudicator_attestor_id
            or receipt.adjudication_id != instruction.adjudication_id
            or receipt.invocation_id != instruction.invocation_id
            or receipt.invocation_digest != instruction.invocation_digest
            or receipt.context_digest != instruction.context_digest
            or receipt.draft_digest != instruction.draft_digest
            or receipt.policy_digest != policy.canonical_digest
            or report.canonical_digest != cls._digest(cls._payload(report))
            or receipt.report_digest != report.canonical_digest
            or receipt.outcome != report.outcome
            or receipt.check_count != len(report.check_codes)
            or receipt.citation_count != report.citation_count
            or receipt.unknown_count != report.unknown_count
            or receipt.expires_at != instruction.expires_at
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or not all(
                (
                    receipt.no_model_used,
                    receipt.protected_vault_write_verified,
                    receipt.signature_verified,
                )
            )
        ):
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_receipt_invalid")

    async def _reuse(
        self,
        claim: ProtectedDraftAdjudicationClaim,
        browser_digest: str,
        request_digest: str,
        authorization_digest: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> ProtectedDraftAdjudicationResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise ProtectedDraftAdjudicationError(
                "protected_draft_adjudication_idempotency_conflict"
            )
        record = await self._repository.get(adjudication_id=claim.adjudication_id)
        if record is None or record.canonical_digest != self._digest(self._payload(record)):
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_already_claimed")
        report = await self._adjudicator.rehydrate(
            record=record, adjudication_authorization_digest=authorization_digest
        )
        if report.canonical_digest != record.report_digest:
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_integrity_failed")
        await self._audit(
            actor,
            correlation_id,
            "protected_draft_adjudication_read",
            record.adjudication_id,
            permission_id=AI_PROTECTED_DRAFT_ADJUDICATION_READ,
        )
        return ProtectedDraftAdjudicationResult(
            record=replace(record, reused=True), manifest=self._manifest(record)
        )

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise ProtectedDraftAdjudicationError(
                "protected_draft_adjudication_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_source_not_found")

    @staticmethod
    def _manifest(record: ProtectedDraftAdjudicationRecord) -> ProtectedDraftAdjudicationManifest:
        return ProtectedDraftAdjudicationManifest(
            adjudication_id=record.adjudication_id,
            invocation_id=record.invocation_id,
            context_id=record.context_id,
            outcome=record.outcome,
            check_count=record.check_count,
            citation_count=record.citation_count,
            unknown_count=record.unknown_count,
            report_digest=record.report_digest,
            check_set_digest=record.check_set_digest,
            citation_coverage_digest=record.citation_coverage_digest,
            unknown_preservation_digest=record.unknown_preservation_digest,
            prohibited_output_digest=record.prohibited_output_digest,
            adjudicated_at=record.adjudicated_at,
            expires_at=record.expires_at,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = AI_PROTECTED_DRAFT_ADJUDICATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.protected-draft-adjudication",
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
                resource_type="resource.ai.protected-draft-adjudication",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    _digest = staticmethod(GovernedProtectedModelInvocationService._digest)
    _payload = staticmethod(GovernedProtectedModelInvocationService._payload)


def build_development_protected_draft_adjudication_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ProtectedDraftAdjudicationPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = ProtectedDraftAdjudicationPolicySnapshot(
        policy_id="protected-draft-adjudication-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.protected-draft-adjudication-development-v1",
        required_invocation_schema="atlas.protected-model-invocation.v1",
        required_invocation_state="protected_model_invoked",
        required_draft_schema="atlas.grounded-operational-analysis-output.v1",
        required_adjudicator_id="protected-draft-adjudicator.synthetic",
        required_adjudicator_attestor_id="subject.protected-draft-adjudicator-attestor",
        required_receipt_schema="atlas.protected-draft-adjudication-receipt.v1",
        protected_vault_id="protected-draft-adjudication-vault.development",
        validation_profile_digest=digest(["validation-profile.draft-adjudication-v1"]),
        prohibited_output_profile_digest=digest(
            ["prohibited-output.no-secrets-tools-operations-v1"]
        ),
        browser_binding_key_digest=digest(["protected-draft-adjudication-browser-key"]),
        classification_ceiling="classification.internal",
        maximum_authentication_age_minutes=15,
        maximum_summary_characters=2_000,
        minimum_citation_count=1,
        minimum_unknown_count=1,
        retention_minutes=10,
        signed_by="subject.protected-draft-adjudication-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
