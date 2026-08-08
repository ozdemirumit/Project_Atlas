from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.ai.application.protected_answer_presentation_ports import (
    ProtectedAnswerPresentationError,
    ProtectedAnswerPresentationPermissionAuthorizer,
    ProtectedAnswerPresentationPolicySource,
    ProtectedAnswerPresentationRepository,
    ProtectedAnswerPresentationUncertainError,
    TrustedProtectedAnswerPresenter,
)
from atlas.modules.ai.application.protected_draft_adjudication import (
    GovernedProtectedDraftAdjudicationService,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_answer_presentation import (
    ProtectedAnswerPresentationClaim,
    ProtectedAnswerPresentationInstruction,
    ProtectedAnswerPresentationManifest,
    ProtectedAnswerPresentationPolicySnapshot,
    ProtectedAnswerPresentationReceipt,
    ProtectedAnswerPresentationRecord,
    ProtectedAnswerPresentationResult,
    ProtectedPresentedAnswer,
)
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationRecord,
    ProtectedDraftAdjudicationReport,
    ProtectedDraftAdjudicationResult,
)
from atlas.modules.ai.domain.protected_model_invocation import (
    ProtectedModelInvocationResult,
    ProtectedModelResponseDraft,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_ANSWER_PRESENTATION_CREATE,
    AI_PROTECTED_ANSWER_PRESENTATION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage

ProtectedAnswerPresentationSourceBundle = tuple[
    ProtectedAnswerPresentationResult,
    ProtectedDraftAdjudicationResult,
    ProtectedDraftAdjudicationReport,
    ProtectedModelInvocationResult,
    ProtectedModelResponseDraft,
    ProtectedModelContextPackage,
]

POLICY_SCHEMA = "atlas.protected-answer-presentation-policy.v1"
CLAIM_SCHEMA = "atlas.protected-answer-presentation-claim.v1"
RECORD_SCHEMA = "atlas.protected-answer-presentation.v1"


class GovernedProtectedAnswerPresentationService:
    def __init__(
        self,
        *,
        repository: ProtectedAnswerPresentationRepository,
        adjudication_source: GovernedProtectedDraftAdjudicationService,
        policy_source: ProtectedAnswerPresentationPolicySource,
        permission_authorizer: ProtectedAnswerPresentationPermissionAuthorizer,
        presenter: TrustedProtectedAnswerPresenter,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._adjudication_source = adjudication_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._presenter = presenter
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        adjudication_id: str,
        adjudication_digest: str,
        presentation_policy_id: str,
        presentation_policy_digest: str,
        purpose: str,
        decision_support_acknowledged: bool,
        citations_and_unknowns_acknowledged: bool,
        no_recommendation_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProtectedAnswerPresentationResult:
        self._require_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1_000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    decision_support_acknowledged,
                    citations_and_unknowns_acknowledged,
                    no_recommendation_or_operational_authority_acknowledged,
                )
            )
        ):
            raise ProtectedAnswerPresentationError("protected_answer_presentation_request_invalid")
        policy = await self._policy_source.get_by_id(policy_id=presentation_policy_id)
        if policy is None:
            raise ProtectedAnswerPresentationError("protected_answer_presentation_source_not_found")
        adjudication_record = (
            await self._adjudication_source.get_record_for_presentation_authorization(
                actor=actor, adjudication_id=adjudication_id
            )
        )
        now = self._clock()
        self._verify_adjudication(
            adjudication_record,
            policy,
            adjudication_digest,
            presentation_policy_digest,
            purpose,
            now,
        )
        self._require_scope(
            actor, adjudication_record.organization_id, adjudication_record.environment_id
        )
        if actor.subject_id in {
            policy.signed_by,
            policy.required_presenter_id,
            policy.required_presenter_attestor_id,
        }:
            raise ProtectedAnswerPresentationError(
                "protected_answer_presentation_actor_separation_required"
            )
        subject_digest = adjudication_record.consumer_subject_digest
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        authorization_digest = self._digest(
            [
                adjudication_record.adjudication_authorization_digest,
                actor.role_ids,
                policy.canonical_digest,
            ]
        )
        request_digest = self._digest(
            [
                adjudication_id,
                adjudication_digest,
                policy.canonical_digest,
                purpose,
                subject_digest,
                browser_digest,
                authorization_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, adjudication_id, idempotency_key])
        existing = await self._repository.get_claim_by_idempotency(
            claimed_by_subject_digest=subject_digest,
            idempotency_digest=idempotency_digest,
        )
        if existing is not None:
            return await self._reuse(
                existing,
                browser_digest,
                request_digest,
                actor,
                browser_session_id,
                correlation_id,
            )
        if await self._repository.get_claim_by_adjudication(adjudication_id=adjudication_id):
            raise ProtectedAnswerPresentationError("protected_answer_presentation_already_claimed")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=adjudication_record.organization_id,
            environment_id=adjudication_record.environment_id,
            correlation_id=correlation_id,
        )
        (
            adjudication,
            report,
            invocation,
            draft,
            context,
        ) = await self._adjudication_source.rehydrate_for_presentation(
            actor=actor,
            adjudication_id=adjudication_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        self._verify_adjudication(
            adjudication.record,
            policy,
            adjudication_digest,
            presentation_policy_digest,
            purpose,
            now,
        )
        self._verify_invocation_schema(invocation.record.response_schema_version, policy)
        seed = self._digest([adjudication_id, subject_digest, idempotency_digest])
        presentation_id = f"protected-answer-presentation.{seed[:24]}"
        claim = ProtectedAnswerPresentationClaim(
            claim_id=f"protected-answer-presentation-claim.{seed[:24]}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            presentation_id=presentation_id,
            adjudication_id=adjudication_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            organization_id=adjudication.record.organization_id,
            environment_id=adjudication.record.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor, correlation_id, "protected_answer_presentation_requested", adjudication_id
        )
        if not await self._repository.claim(claim):
            raise ProtectedAnswerPresentationUncertainError(
                "protected_answer_presentation_claim_uncertain"
            )
        await self._audit(
            actor, correlation_id, "protected_answer_presentation_claimed", presentation_id
        )
        expires_at = min(
            adjudication.record.expires_at,
            invocation.record.expires_at,
            now + timedelta(minutes=policy.retention_minutes),
        )
        instruction = ProtectedAnswerPresentationInstruction(
            presentation_id=presentation_id,
            adjudication_id=adjudication_id,
            adjudication_digest=adjudication.record.canonical_digest,
            invocation_id=adjudication.record.invocation_id,
            invocation_digest=adjudication.record.invocation_digest,
            context_id=adjudication.record.context_id,
            context_digest=adjudication.record.context_digest,
            context_package_digest=invocation.record.context_package_digest,
            draft_digest=adjudication.record.draft_digest,
            report_digest=adjudication.record.report_digest,
            organization_id=adjudication.record.organization_id,
            environment_id=adjudication.record.environment_id,
            consumer_subject_digest=subject_digest,
            presentation_authorization_digest=authorization_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            rendering_profile_digest=policy.rendering_profile_digest,
            prohibited_output_profile_digest=policy.prohibited_output_profile_digest,
            media_type=policy.media_type,
            maximum_summary_characters=policy.maximum_summary_characters,
            maximum_citation_count=policy.maximum_citation_count,
            maximum_unknown_count=policy.maximum_unknown_count,
            maximum_output_bytes=policy.maximum_output_bytes,
            requested_at=now,
            expires_at=expires_at,
        )
        try:
            receipt, answer = await self._presenter.present(instruction, report, draft, context)
            self._verify_receipt(receipt, answer, instruction, policy)
        except ProtectedAnswerPresentationError:
            raise
        except Exception as error:
            raise ProtectedAnswerPresentationUncertainError(
                "protected_answer_presentation_outcome_uncertain"
            ) from error
        await self._audit(actor, correlation_id, "protected_answer_content_read", presentation_id)
        record = ProtectedAnswerPresentationRecord(
            presentation_id=presentation_id,
            schema_version=RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            adjudication_id=adjudication_id,
            adjudication_digest=adjudication.record.canonical_digest,
            invocation_id=adjudication.record.invocation_id,
            invocation_digest=adjudication.record.invocation_digest,
            context_id=adjudication.record.context_id,
            context_digest=adjudication.record.context_digest,
            context_package_digest=invocation.record.context_package_digest,
            organization_id=adjudication.record.organization_id,
            environment_id=adjudication.record.environment_id,
            classification=adjudication.record.classification,
            consumer_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            presentation_policy_id=policy.policy_id,
            presentation_policy_digest=policy.canonical_digest,
            presentation_policy_version=policy.policy_version,
            presenter_id=receipt.presenter_id,
            presentation_receipt_digest=receipt.canonical_digest,
            presentation_authorization_digest=authorization_digest,
            draft_digest=adjudication.record.draft_digest,
            report_digest=adjudication.record.report_digest,
            answer_digest=answer.canonical_digest,
            citation_set_digest=receipt.citation_set_digest,
            unknown_set_digest=receipt.unknown_set_digest,
            source_binding_digest=receipt.source_binding_digest,
            rendering_digest=receipt.rendering_digest,
            cleanup_digest=receipt.cleanup_digest,
            summary_character_count=receipt.summary_character_count,
            citation_count=receipt.citation_count,
            unknown_count=receipt.unknown_count,
            byte_count=receipt.byte_count,
            media_type=policy.media_type,
            presented_at=receipt.presented_at,
            expires_at=expires_at,
            instance_state="protected_answer_presented",
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        await self._audit(
            actor, correlation_id, "protected_answer_presentation_completed", presentation_id
        )
        try:
            await self._repository.save(record)
        except Exception as error:
            raise ProtectedAnswerPresentationUncertainError(
                "protected_answer_presentation_persistence_uncertain"
            ) from error
        return ProtectedAnswerPresentationResult(
            record=record, manifest=self._manifest(record), answer=answer
        )

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        presentation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedAnswerPresentationResult:
        bundle = await self.rehydrate_for_recommendation(
            actor=actor,
            presentation_id=presentation_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        result = bundle[0]
        await self._audit(
            actor,
            correlation_id,
            "protected_answer_presentation_read",
            presentation_id,
            permission_id=AI_PROTECTED_ANSWER_PRESENTATION_READ,
        )
        return result

    async def rehydrate_for_recommendation(
        self,
        *,
        actor: AuthenticatedSubject,
        presentation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedAnswerPresentationSourceBundle:
        self._require_human(actor)
        record = await self._repository.get(presentation_id=presentation_id)
        if record is None:
            raise ProtectedAnswerPresentationError("protected_answer_presentation_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.presentation_policy_id)
        if policy is None:
            raise ProtectedAnswerPresentationError("protected_answer_presentation_not_found")
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        now = self._clock()
        if (
            record.browser_session_binding_digest != browser_digest
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.presentation_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedAnswerPresentationError("protected_answer_presentation_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        (
            adjudication,
            report,
            invocation,
            draft,
            context,
        ) = await self._adjudication_source.rehydrate_for_presentation(
            actor=actor,
            adjudication_id=record.adjudication_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        self._verify_adjudication(
            adjudication.record,
            policy,
            record.adjudication_digest,
            record.presentation_policy_digest,
            record.purpose,
            now,
        )
        self._verify_invocation_schema(invocation.record.response_schema_version, policy)
        authorization_digest = self._digest(
            [
                adjudication.record.adjudication_authorization_digest,
                actor.role_ids,
                policy.canonical_digest,
            ]
        )
        self._verify_record(record, adjudication.record, invocation.record.context_package_digest)
        answer = await self._presenter.rehydrate(
            record=record,
            presentation_authorization_digest=authorization_digest,
            report=report,
            draft=draft,
            context=context,
        )
        self._verify_answer(record, answer)
        result = ProtectedAnswerPresentationResult(
            record=replace(record, reused=True),
            manifest=self._manifest(record),
            answer=answer,
        )
        return result, adjudication, report, invocation, draft, context

    async def get_record_for_recommendation_authorization(
        self,
        *,
        actor: AuthenticatedSubject,
        presentation_id: str,
        browser_session_id: str,
    ) -> ProtectedAnswerPresentationRecord:
        self._require_human(actor)
        record = await self._repository.get(presentation_id=presentation_id)
        if record is None:
            raise ProtectedAnswerPresentationError("protected_answer_presentation_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.presentation_policy_id)
        if policy is None:
            raise ProtectedAnswerPresentationError("protected_answer_presentation_not_found")
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        now = self._clock()
        if (
            record.browser_session_binding_digest != browser_digest
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.presentation_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedAnswerPresentationError("protected_answer_presentation_not_found")
        return record

    async def close(self) -> None:
        await self._repository.close()

    def _verify_adjudication(
        self,
        record: ProtectedDraftAdjudicationRecord,
        policy: ProtectedAnswerPresentationPolicySnapshot,
        adjudication_digest: str,
        policy_digest: str,
        purpose: str,
        now: datetime,
    ) -> None:
        if (
            record.canonical_digest != adjudication_digest
            or record.canonical_digest != self._digest(self._payload(record))
            or record.schema_version != policy.required_adjudication_schema
            or record.instance_state != policy.required_adjudication_state
            or record.outcome != policy.required_adjudication_outcome
            or not record.model_draft_adjudicated
            or record.answer_generated
            or now >= record.expires_at
            or purpose != record.purpose
            or policy.canonical_digest != policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or policy.organization_id != record.organization_id
            or policy.environment_id != record.environment_id
            or not DataClassification(
                policy.classification_ceiling.removeprefix("classification.")
            ).permits(DataClassification(record.classification.removeprefix("classification.")))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedAnswerPresentationError("protected_answer_presentation_source_invalid")

    @staticmethod
    def _verify_invocation_schema(
        response_schema_version: str,
        policy: ProtectedAnswerPresentationPolicySnapshot,
    ) -> None:
        if response_schema_version != policy.required_draft_schema:
            raise ProtectedAnswerPresentationError("protected_answer_presentation_source_invalid")

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ProtectedAnswerPresentationReceipt,
        answer: ProtectedPresentedAnswer,
        instruction: ProtectedAnswerPresentationInstruction,
        policy: ProtectedAnswerPresentationPolicySnapshot,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.presenter_id != policy.required_presenter_id
            or receipt.attested_by != policy.required_presenter_attestor_id
            or receipt.presentation_id != instruction.presentation_id
            or receipt.adjudication_id != instruction.adjudication_id
            or receipt.adjudication_digest != instruction.adjudication_digest
            or receipt.invocation_digest != instruction.invocation_digest
            or receipt.draft_digest != instruction.draft_digest
            or receipt.report_digest != instruction.report_digest
            or receipt.policy_digest != policy.canonical_digest
            or answer.canonical_digest != cls._digest(cls._payload(answer))
            or receipt.answer_digest != answer.canonical_digest
            or receipt.summary_character_count != len(answer.summary)
            or receipt.citation_count != len(answer.citation_references)
            or receipt.unknown_count != len(answer.unknowns)
            or receipt.byte_count != answer.byte_count
            or receipt.expires_at != instruction.expires_at
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or not all(
                (
                    receipt.source_verified,
                    receipt.eligible_outcome_verified,
                    receipt.content_verified,
                    receipt.inert_rendering_verified,
                    receipt.no_model_used,
                    receipt.cleanup_verified,
                    receipt.signature_verified,
                )
            )
        ):
            raise ProtectedAnswerPresentationError("protected_answer_presentation_receipt_invalid")

    @staticmethod
    def _verify_record(
        record: ProtectedAnswerPresentationRecord,
        adjudication: ProtectedDraftAdjudicationRecord,
        context_package_digest: str,
    ) -> None:
        if (
            record.adjudication_digest != adjudication.canonical_digest
            or record.consumer_subject_digest != adjudication.consumer_subject_digest
            or record.invocation_digest != adjudication.invocation_digest
            or record.context_digest != adjudication.context_digest
            or record.context_package_digest != context_package_digest
            or record.draft_digest != adjudication.draft_digest
            or record.report_digest != adjudication.report_digest
            or adjudication.outcome != "adjudication-outcome.eligible"
        ):
            raise ProtectedAnswerPresentationError("protected_answer_presentation_integrity_failed")

    @staticmethod
    def _verify_answer(
        record: ProtectedAnswerPresentationRecord, answer: ProtectedPresentedAnswer
    ) -> None:
        if (
            answer.canonical_digest != record.answer_digest
            or len(answer.summary) != record.summary_character_count
            or len(answer.citation_references) != record.citation_count
            or len(answer.unknowns) != record.unknown_count
            or answer.byte_count != record.byte_count
            or answer.media_type != record.media_type
        ):
            raise ProtectedAnswerPresentationError("protected_answer_presentation_integrity_failed")

    async def _reuse(
        self,
        claim: ProtectedAnswerPresentationClaim,
        browser_digest: str,
        request_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedAnswerPresentationResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise ProtectedAnswerPresentationError(
                "protected_answer_presentation_idempotency_conflict"
            )
        return await self.get(
            actor=actor,
            presentation_id=claim.presentation_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level is not AssuranceLevel.HARDWARE_BACKED
        ):
            raise ProtectedAnswerPresentationError(
                "protected_answer_presentation_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise ProtectedAnswerPresentationError("protected_answer_presentation_not_found")

    @staticmethod
    def _manifest(record: ProtectedAnswerPresentationRecord) -> ProtectedAnswerPresentationManifest:
        return ProtectedAnswerPresentationManifest(
            presentation_id=record.presentation_id,
            adjudication_id=record.adjudication_id,
            invocation_id=record.invocation_id,
            context_id=record.context_id,
            summary_character_count=record.summary_character_count,
            citation_count=record.citation_count,
            unknown_count=record.unknown_count,
            byte_count=record.byte_count,
            media_type=record.media_type,
            answer_digest=record.answer_digest,
            citation_set_digest=record.citation_set_digest,
            unknown_set_digest=record.unknown_set_digest,
            source_binding_digest=record.source_binding_digest,
            rendering_digest=record.rendering_digest,
            cleanup_digest=record.cleanup_digest,
            presented_at=record.presented_at,
            expires_at=record.expires_at,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = AI_PROTECTED_ANSWER_PRESENTATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.protected-answer-presentation",
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
                resource_type="resource.ai.protected-answer-presentation",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    _digest = staticmethod(GovernedProtectedModelInvocationService._digest)
    _payload = staticmethod(GovernedProtectedModelInvocationService._payload)


def build_development_protected_answer_presentation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ProtectedAnswerPresentationPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = ProtectedAnswerPresentationPolicySnapshot(
        policy_id="protected-answer-presentation-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.protected-answer-presentation-development-v1",
        required_adjudication_schema="atlas.protected-draft-adjudication.v1",
        required_adjudication_state="protected_model_draft_adjudicated",
        required_adjudication_outcome="adjudication-outcome.eligible",
        required_draft_schema="atlas.grounded-operational-analysis-output.v1",
        required_presenter_id="protected-answer-presenter.synthetic",
        required_presenter_attestor_id="subject.protected-answer-presenter-attestor",
        required_receipt_schema="atlas.protected-answer-presentation-receipt.v1",
        media_type="text/plain",
        rendering_profile_digest=digest(["rendering-profile.inert-answer-v1"]),
        prohibited_output_profile_digest=digest(
            ["prohibited-output.no-secrets-tools-operations-v1"]
        ),
        browser_binding_key_digest=digest(["protected-answer-presentation-browser-key"]),
        classification_ceiling="classification.internal",
        maximum_authentication_age_minutes=15,
        maximum_summary_characters=2_000,
        maximum_citation_count=25,
        maximum_unknown_count=25,
        maximum_output_bytes=16_384,
        retention_minutes=10,
        signed_by="subject.protected-answer-presentation-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
