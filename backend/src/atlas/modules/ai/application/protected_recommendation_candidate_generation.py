from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.ai.application.protected_answer_presentation import (
    GovernedProtectedAnswerPresentationService,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation_ports import (
    ProtectedRecommendationCandidateError,
    ProtectedRecommendationCandidatePermissionAuthorizer,
    ProtectedRecommendationCandidatePolicySource,
    ProtectedRecommendationCandidateRepository,
    ProtectedRecommendationCandidateUncertainError,
    TrustedProtectedRecommendationCandidateGenerator,
)
from atlas.modules.ai.domain.protected_answer_presentation import (
    ProtectedAnswerPresentationRecord,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateClaim,
    ProtectedRecommendationCandidateInstruction,
    ProtectedRecommendationCandidateManifest,
    ProtectedRecommendationCandidatePolicySnapshot,
    ProtectedRecommendationCandidateReceipt,
    ProtectedRecommendationCandidateRecord,
    ProtectedRecommendationCandidateResult,
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_RECOMMENDATION_CANDIDATE_CREATE,
    AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

POLICY_SCHEMA = "atlas.protected-recommendation-candidate-policy.v1"
CLAIM_SCHEMA = "atlas.protected-recommendation-candidate-claim.v1"
RECORD_SCHEMA = "atlas.protected-recommendation-candidate-set.v1"


class GovernedProtectedRecommendationCandidateService:
    def __init__(
        self,
        *,
        repository: ProtectedRecommendationCandidateRepository,
        presentation_source: GovernedProtectedAnswerPresentationService,
        policy_source: ProtectedRecommendationCandidatePolicySource,
        permission_authorizer: ProtectedRecommendationCandidatePermissionAuthorizer,
        generator: TrustedProtectedRecommendationCandidateGenerator,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._presentation_source = presentation_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._generator = generator
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        presentation_id: str,
        presentation_digest: str,
        generation_policy_id: str,
        generation_policy_digest: str,
        purpose: str,
        incomplete_candidates_acknowledged: bool,
        impact_and_recovery_unverified_acknowledged: bool,
        no_recommendation_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProtectedRecommendationCandidateResult:
        self._require_human(actor)
        purpose = purpose.strip()
        if (
            not 20 <= len(purpose) <= 1_000
            or not 16 <= len(browser_session_id) <= 256
            or not 8 <= len(idempotency_key) <= 128
            or not all(
                (
                    incomplete_candidates_acknowledged,
                    impact_and_recovery_unverified_acknowledged,
                    no_recommendation_or_operational_authority_acknowledged,
                )
            )
        ):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_request_invalid"
            )
        policy = await self._policy_source.get_by_id(policy_id=generation_policy_id)
        if policy is None:
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_source_not_found"
            )
        presentation = await self._presentation_source.get_record_for_recommendation_authorization(
            actor=actor,
            presentation_id=presentation_id,
            browser_session_id=browser_session_id,
        )
        now = self._clock()
        self._verify_presentation(
            presentation,
            policy,
            presentation_digest,
            generation_policy_digest,
            purpose,
            now,
        )
        self._require_scope(actor, presentation.organization_id, presentation.environment_id)
        if actor.subject_id in {
            policy.signed_by,
            policy.required_generator_id,
            policy.required_generator_attestor_id,
        }:
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_actor_separation_required"
            )
        subject_digest = presentation.consumer_subject_digest
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        authorization_digest = self._digest(
            [
                presentation.presentation_authorization_digest,
                actor.role_ids,
                policy.canonical_digest,
            ]
        )
        request_digest = self._digest(
            [
                presentation_id,
                presentation_digest,
                policy.canonical_digest,
                purpose,
                subject_digest,
                browser_digest,
                authorization_digest,
            ]
        )
        idempotency_digest = self._digest([subject_digest, presentation_id, idempotency_key])
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
        if await self._repository.get_claim_by_presentation(presentation_id=presentation_id):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_already_claimed"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            correlation_id=correlation_id,
        )
        seed = self._digest([presentation_id, subject_digest, idempotency_digest])
        candidate_set_id = f"protected-recommendation-candidates.{seed[:24]}"
        claim = ProtectedRecommendationCandidateClaim(
            claim_id=f"protected-recommendation-candidate-claim.{seed[:24]}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            candidate_set_id=candidate_set_id,
            presentation_id=presentation_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            organization_id=presentation.organization_id,
            environment_id=presentation.environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor, correlation_id, "protected_recommendation_candidate_requested", presentation_id
        )
        if not await self._repository.claim(claim):
            raise ProtectedRecommendationCandidateUncertainError(
                "protected_recommendation_candidate_claim_uncertain"
            )
        await self._audit(
            actor,
            correlation_id,
            "protected_recommendation_candidate_claimed",
            candidate_set_id,
        )
        try:
            (
                presented,
                adjudication,
                report,
                invocation,
                draft,
                context,
            ) = await self._presentation_source.rehydrate_for_recommendation(
                actor=actor,
                presentation_id=presentation_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
        except Exception as error:
            raise ProtectedRecommendationCandidateUncertainError(
                "protected_recommendation_candidate_source_uncertain"
            ) from error
        self._verify_presentation(
            presented.record,
            policy,
            presentation_digest,
            generation_policy_digest,
            purpose,
            now,
        )
        self._verify_source_lineage(
            presented.record,
            adjudication.record.canonical_digest,
            invocation.record.context_package_digest,
            draft.canonical_digest,
            report.canonical_digest,
            presented.answer.canonical_digest,
        )
        await self._audit(
            actor,
            correlation_id,
            "protected_recommendation_candidate_source_read",
            candidate_set_id,
        )
        expires_at = min(
            presented.record.expires_at,
            adjudication.record.expires_at,
            invocation.record.expires_at,
            now + timedelta(minutes=policy.retention_minutes),
        )
        instruction = ProtectedRecommendationCandidateInstruction(
            candidate_set_id=candidate_set_id,
            presentation_id=presentation_id,
            presentation_digest=presented.record.canonical_digest,
            answer_digest=presented.record.answer_digest,
            adjudication_id=presented.record.adjudication_id,
            adjudication_digest=presented.record.adjudication_digest,
            invocation_id=presented.record.invocation_id,
            invocation_digest=presented.record.invocation_digest,
            context_id=presented.record.context_id,
            context_digest=presented.record.context_digest,
            context_package_digest=presented.record.context_package_digest,
            draft_digest=presented.record.draft_digest,
            report_digest=presented.record.report_digest,
            organization_id=presented.record.organization_id,
            environment_id=presented.record.environment_id,
            consumer_subject_digest=subject_digest,
            generation_authorization_digest=authorization_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            required_candidate_set_schema=policy.required_candidate_set_schema,
            required_categories=policy.required_categories,
            allowed_capability_ids=policy.allowed_capability_ids,
            maximum_capability_class=policy.maximum_capability_class,
            maximum_candidate_count=policy.maximum_candidate_count,
            maximum_steps_per_candidate=policy.maximum_steps_per_candidate,
            maximum_title_characters=policy.maximum_title_characters,
            maximum_outcome_characters=policy.maximum_outcome_characters,
            maximum_text_items_per_candidate=policy.maximum_text_items_per_candidate,
            maximum_output_bytes=policy.maximum_output_bytes,
            prohibited_output_profile_digest=policy.prohibited_output_profile_digest,
            requested_at=now,
            expires_at=expires_at,
        )
        try:
            receipt, candidate_set = await self._generator.generate(
                instruction, presented.answer, report, draft, context
            )
            self._verify_receipt(receipt, candidate_set, instruction, policy)
        except ProtectedRecommendationCandidateError:
            raise
        except Exception as error:
            raise ProtectedRecommendationCandidateUncertainError(
                "protected_recommendation_candidate_outcome_uncertain"
            ) from error
        categories = tuple(candidate.category for candidate in candidate_set.candidates)
        record = ProtectedRecommendationCandidateRecord(
            candidate_set_id=candidate_set_id,
            schema_version=RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            presentation_id=presentation_id,
            presentation_digest=presented.record.canonical_digest,
            answer_digest=presented.record.answer_digest,
            adjudication_id=presented.record.adjudication_id,
            adjudication_digest=presented.record.adjudication_digest,
            invocation_id=presented.record.invocation_id,
            invocation_digest=presented.record.invocation_digest,
            context_id=presented.record.context_id,
            context_digest=presented.record.context_digest,
            context_package_digest=presented.record.context_package_digest,
            draft_digest=presented.record.draft_digest,
            report_digest=presented.record.report_digest,
            organization_id=presented.record.organization_id,
            environment_id=presented.record.environment_id,
            classification=presented.record.classification,
            consumer_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            generation_policy_id=policy.policy_id,
            generation_policy_digest=policy.canonical_digest,
            generation_policy_version=policy.policy_version,
            generator_id=receipt.generator_id,
            generation_receipt_digest=receipt.canonical_digest,
            generation_authorization_digest=authorization_digest,
            candidate_content_digest=candidate_set.canonical_digest,
            source_binding_digest=receipt.source_binding_digest,
            citation_set_digest=receipt.citation_set_digest,
            unknown_set_digest=receipt.unknown_set_digest,
            safety_digest=receipt.safety_digest,
            cleanup_digest=receipt.cleanup_digest,
            candidate_categories=categories,
            maximum_capability_class=policy.maximum_capability_class,
            candidate_count=receipt.candidate_count,
            step_count=receipt.step_count,
            citation_count=receipt.citation_count,
            unknown_count=receipt.unknown_count,
            byte_count=receipt.byte_count,
            generated_at=receipt.generated_at,
            expires_at=expires_at,
            instance_state="protected_recommendation_candidates_generated",
            purpose=purpose,
            canonical_digest="0" * 64,
        )
        record = replace(record, canonical_digest=self._digest(self._payload(record)))
        await self._audit(
            actor,
            correlation_id,
            "protected_recommendation_candidate_completed",
            candidate_set_id,
        )
        try:
            await self._repository.save(record)
        except Exception as error:
            raise ProtectedRecommendationCandidateUncertainError(
                "protected_recommendation_candidate_persistence_uncertain"
            ) from error
        return ProtectedRecommendationCandidateResult(
            record=record, manifest=self._manifest(record)
        )

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        candidate_set_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedRecommendationCandidateResult:
        self._require_human(actor)
        record = await self._repository.get(candidate_set_id=candidate_set_id)
        if record is None:
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.generation_policy_id)
        if policy is None:
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_not_found"
            )
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        now = self._clock()
        if (
            record.browser_session_binding_digest != browser_digest
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.generation_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        try:
            (
                presented,
                adjudication,
                report,
                invocation,
                draft,
                context,
            ) = await self._presentation_source.rehydrate_for_recommendation(
                actor=actor,
                presentation_id=record.presentation_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
        except Exception as error:
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_not_found"
            ) from error
        self._verify_presentation(
            presented.record,
            policy,
            record.presentation_digest,
            record.generation_policy_digest,
            record.purpose,
            now,
        )
        self._verify_source_lineage(
            presented.record,
            adjudication.record.canonical_digest,
            invocation.record.context_package_digest,
            draft.canonical_digest,
            report.canonical_digest,
            presented.answer.canonical_digest,
        )
        authorization_digest = self._digest(
            [
                presented.record.presentation_authorization_digest,
                actor.role_ids,
                policy.canonical_digest,
            ]
        )
        receipt, candidate_set = await self._generator.rehydrate(
            record=record,
            generation_authorization_digest=authorization_digest,
            answer=presented.answer,
            report=report,
            draft=draft,
            context=context,
        )
        instruction = self._instruction_from_record(record, policy)
        self._verify_receipt(receipt, candidate_set, instruction, policy)
        self._verify_record(record, candidate_set, presented.record)
        await self._audit(
            actor,
            correlation_id,
            "protected_recommendation_candidate_read",
            candidate_set_id,
            permission_id=AI_PROTECTED_RECOMMENDATION_CANDIDATE_READ,
        )
        reused = replace(record, reused=True)
        return ProtectedRecommendationCandidateResult(
            record=reused, manifest=self._manifest(record)
        )

    async def close(self) -> None:
        await self._repository.close()

    def _verify_presentation(
        self,
        record: ProtectedAnswerPresentationRecord,
        policy: ProtectedRecommendationCandidatePolicySnapshot,
        presentation_digest: str,
        policy_digest: str,
        purpose: str,
        now: datetime,
    ) -> None:
        if (
            record.canonical_digest != presentation_digest
            or record.canonical_digest != self._digest(self._payload(record))
            or record.schema_version != policy.required_presentation_schema
            or record.instance_state != policy.required_presentation_state
            or not record.answer_presented
            or record.recommendation_generated
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
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_source_invalid"
            )

    @staticmethod
    def _verify_source_lineage(
        presentation: ProtectedAnswerPresentationRecord,
        adjudication_digest: str,
        context_package_digest: str,
        draft_digest: str,
        report_digest: str,
        answer_digest: str,
    ) -> None:
        if (
            presentation.adjudication_digest != adjudication_digest
            or presentation.context_package_digest != context_package_digest
            or presentation.draft_digest != draft_digest
            or presentation.report_digest != report_digest
            or presentation.answer_digest != answer_digest
        ):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_integrity_failed"
            )

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ProtectedRecommendationCandidateReceipt,
        candidate_set: ProtectedRecommendationCandidateSet,
        instruction: ProtectedRecommendationCandidateInstruction,
        policy: ProtectedRecommendationCandidatePolicySnapshot,
    ) -> None:
        categories = tuple(candidate.category for candidate in candidate_set.candidates)
        allowed_order = {"C0": 0, "C1": 1}
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.generator_id != policy.required_generator_id
            or receipt.attested_by != policy.required_generator_attestor_id
            or receipt.candidate_set_id != instruction.candidate_set_id
            or receipt.presentation_id != instruction.presentation_id
            or receipt.presentation_digest != instruction.presentation_digest
            or receipt.generation_authorization_digest
            != instruction.generation_authorization_digest
            or receipt.policy_digest != policy.canonical_digest
            or candidate_set.schema_version != policy.required_candidate_set_schema
            or candidate_set.canonical_digest != cls._digest(cls._payload(candidate_set))
            or receipt.candidate_set_digest != candidate_set.canonical_digest
            or candidate_set.presentation_digest != instruction.presentation_digest
            or candidate_set.answer_digest != instruction.answer_digest
            or categories != policy.required_categories
            or receipt.candidate_count != len(candidate_set.candidates)
            or receipt.step_count
            != sum(len(candidate.steps) for candidate in candidate_set.candidates)
            or receipt.byte_count != candidate_set.byte_count
            or receipt.expires_at != instruction.expires_at
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or any(
                candidate.canonical_digest != cls._digest(cls._payload(candidate))
                or len(candidate.steps) > policy.maximum_steps_per_candidate
                or any(step.executable_by_atlas for step in candidate.steps)
                or any(
                    allowed_order[step.capability_class]
                    > allowed_order[policy.maximum_capability_class]
                    or (
                        step.capability_id is not None
                        and step.capability_id not in policy.allowed_capability_ids
                    )
                    for step in candidate.steps
                )
                for candidate in candidate_set.candidates
            )
            or not all(
                (
                    receipt.source_verified,
                    receipt.diversity_verified,
                    receipt.citations_verified,
                    receipt.unknowns_preserved,
                    receipt.capability_boundary_verified,
                    receipt.non_executable_verified,
                    receipt.no_preference_assigned,
                    receipt.no_model_used,
                    receipt.cleanup_verified,
                    receipt.signature_verified,
                )
            )
        ):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_receipt_invalid"
            )

    @staticmethod
    def _verify_record(
        record: ProtectedRecommendationCandidateRecord,
        candidate_set: ProtectedRecommendationCandidateSet,
        presentation: ProtectedAnswerPresentationRecord,
    ) -> None:
        if (
            record.presentation_digest != presentation.canonical_digest
            or record.consumer_subject_digest != presentation.consumer_subject_digest
            or record.answer_digest != presentation.answer_digest
            or record.candidate_content_digest != candidate_set.canonical_digest
            or record.source_binding_digest != candidate_set.source_binding_digest
            or record.citation_set_digest != candidate_set.citation_set_digest
            or record.unknown_set_digest != candidate_set.unknown_set_digest
            or record.safety_digest != candidate_set.safety_digest
            or record.candidate_categories
            != tuple(candidate.category for candidate in candidate_set.candidates)
        ):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_integrity_failed"
            )

    def _instruction_from_record(
        self,
        record: ProtectedRecommendationCandidateRecord,
        policy: ProtectedRecommendationCandidatePolicySnapshot,
    ) -> ProtectedRecommendationCandidateInstruction:
        return ProtectedRecommendationCandidateInstruction(
            candidate_set_id=record.candidate_set_id,
            presentation_id=record.presentation_id,
            presentation_digest=record.presentation_digest,
            answer_digest=record.answer_digest,
            adjudication_id=record.adjudication_id,
            adjudication_digest=record.adjudication_digest,
            invocation_id=record.invocation_id,
            invocation_digest=record.invocation_digest,
            context_id=record.context_id,
            context_digest=record.context_digest,
            context_package_digest=record.context_package_digest,
            draft_digest=record.draft_digest,
            report_digest=record.report_digest,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            consumer_subject_digest=record.consumer_subject_digest,
            generation_authorization_digest=record.generation_authorization_digest,
            policy_id=record.generation_policy_id,
            policy_digest=record.generation_policy_digest,
            required_candidate_set_schema=policy.required_candidate_set_schema,
            required_categories=policy.required_categories,
            allowed_capability_ids=policy.allowed_capability_ids,
            maximum_capability_class=record.maximum_capability_class,
            maximum_candidate_count=record.candidate_count,
            maximum_steps_per_candidate=policy.maximum_steps_per_candidate,
            maximum_title_characters=policy.maximum_title_characters,
            maximum_outcome_characters=policy.maximum_outcome_characters,
            maximum_text_items_per_candidate=policy.maximum_text_items_per_candidate,
            maximum_output_bytes=record.byte_count,
            prohibited_output_profile_digest=policy.prohibited_output_profile_digest,
            requested_at=record.generated_at,
            expires_at=record.expires_at,
        )

    async def _reuse(
        self,
        claim: ProtectedRecommendationCandidateClaim,
        browser_digest: str,
        request_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedRecommendationCandidateResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_idempotency_conflict"
            )
        return await self.get(
            actor=actor,
            candidate_set_id=claim.candidate_set_id,
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
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_not_found"
            )

    @staticmethod
    def _manifest(
        record: ProtectedRecommendationCandidateRecord,
    ) -> ProtectedRecommendationCandidateManifest:
        return ProtectedRecommendationCandidateManifest(
            candidate_set_id=record.candidate_set_id,
            presentation_id=record.presentation_id,
            adjudication_id=record.adjudication_id,
            invocation_id=record.invocation_id,
            context_id=record.context_id,
            candidate_categories=record.candidate_categories,
            maximum_capability_class=record.maximum_capability_class,
            candidate_count=record.candidate_count,
            step_count=record.step_count,
            citation_count=record.citation_count,
            unknown_count=record.unknown_count,
            byte_count=record.byte_count,
            candidate_content_digest=record.candidate_content_digest,
            source_binding_digest=record.source_binding_digest,
            citation_set_digest=record.citation_set_digest,
            unknown_set_digest=record.unknown_set_digest,
            safety_digest=record.safety_digest,
            cleanup_digest=record.cleanup_digest,
            generated_at=record.generated_at,
            expires_at=record.expires_at,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = AI_PROTECTED_RECOMMENDATION_CANDIDATE_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.protected-recommendation-candidate-generation",
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
                resource_type="resource.ai.protected-recommendation-candidate-set",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    _digest = staticmethod(GovernedProtectedModelInvocationService._digest)
    _payload = staticmethod(GovernedProtectedModelInvocationService._payload)


def build_development_protected_recommendation_candidate_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ProtectedRecommendationCandidatePolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = ProtectedRecommendationCandidatePolicySnapshot(
        policy_id="protected-recommendation-candidate-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.protected-recommendation-candidate-development-v1",
        required_presentation_schema="atlas.protected-answer-presentation.v1",
        required_presentation_state="protected_answer_presented",
        required_candidate_set_schema="atlas.protected-recommendation-candidate-content.v1",
        required_receipt_schema="atlas.protected-recommendation-candidate-receipt.v1",
        required_generator_id="protected-recommendation-candidate-generator.synthetic",
        required_generator_attestor_id=(
            "subject.protected-recommendation-candidate-generator-attestor"
        ),
        required_categories=(
            "recommendation-category.investigate",
            "recommendation-category.escalate",
            "recommendation-category.defer-no-action",
        ),
        allowed_capability_ids=(
            "hitachi.opscenter.storage.hardware.read",
            "atlas.vendor.support.package.prepare",
        ),
        maximum_capability_class="C1",
        maximum_authentication_age_minutes=15,
        maximum_candidate_count=3,
        maximum_steps_per_candidate=3,
        maximum_title_characters=200,
        maximum_outcome_characters=1_000,
        maximum_text_items_per_candidate=25,
        maximum_output_bytes=65_536,
        retention_minutes=10,
        prohibited_output_profile_digest=digest(
            ["prohibited-output.no-secrets-tools-operations-preference-v1"]
        ),
        browser_binding_key_digest=digest(["protected-recommendation-candidate-browser-key"]),
        classification_ceiling="classification.internal",
        signed_by="subject.protected-recommendation-candidate-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
