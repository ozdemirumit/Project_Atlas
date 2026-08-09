from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_adjudication import (
    GovernedProtectedRecommendationAdjudicationService,
)
from atlas.modules.ai.application.protected_recommendation_adjudication_ports import (
    ProtectedRecommendationAdjudicationError,
)
from atlas.modules.ai.application.protected_recommendation_presentation_ports import (
    ProtectedRecommendationPresentationError,
    ProtectedRecommendationPresentationPermissionAuthorizer,
    ProtectedRecommendationPresentationPolicySource,
    ProtectedRecommendationPresentationRepository,
    ProtectedRecommendationPresentationUncertainError,
    TrustedProtectedRecommendationPresenter,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationRecord,
)
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    ProtectedPresentedRecommendation,
    ProtectedRecommendationPresentationClaim,
    ProtectedRecommendationPresentationInstruction,
    ProtectedRecommendationPresentationManifest,
    ProtectedRecommendationPresentationPolicySnapshot,
    ProtectedRecommendationPresentationReceipt,
    ProtectedRecommendationPresentationRecord,
    ProtectedRecommendationPresentationResult,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_RECOMMENDATION_PRESENTATION_CREATE,
    AI_PROTECTED_RECOMMENDATION_PRESENTATION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

POLICY_SCHEMA = "atlas.protected-recommendation-presentation-policy.v1"
CLAIM_SCHEMA = "atlas.protected-recommendation-presentation-claim.v1"
RECORD_SCHEMA = "atlas.protected-recommendation-presentation.v1"
SAFETY_NOTICE = (
    "Decision support only. Presentation is not approval, review readiness, workflow creation, "
    "execution authorization, or infrastructure mutation."
)


class GovernedProtectedRecommendationPresentationService:
    def __init__(
        self,
        *,
        repository: ProtectedRecommendationPresentationRepository,
        adjudication_source: GovernedProtectedRecommendationAdjudicationService,
        policy_source: ProtectedRecommendationPresentationPolicySource,
        permission_authorizer: ProtectedRecommendationPresentationPermissionAuthorizer,
        presenter: TrustedProtectedRecommendationPresenter,
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
        decision_support_only_acknowledged: bool,
        tie_or_no_support_acknowledged: bool,
        no_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProtectedRecommendationPresentationResult:
        self._require_human(actor)
        if not all(
            (
                decision_support_only_acknowledged,
                tie_or_no_support_acknowledged,
                no_operational_authority_acknowledged,
            )
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_acknowledgement_required"
            )
        now = self._clock()
        policy = await self._policy_source.get_by_id(policy_id=presentation_policy_id)
        if (
            policy is None
            or policy.canonical_digest != presentation_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or policy.schema_version != POLICY_SCHEMA
            or policy.organization_id != actor.organization_id
            or policy.environment_id != self._environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_policy_invalid"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            correlation_id=correlation_id,
        )
        source = await self._adjudication_source.get_record_for_presentation_authorization(
            actor=actor,
            adjudication_id=adjudication_id,
            browser_session_id=browser_session_id,
        )
        self._verify_adjudication(source, policy, adjudication_digest, purpose, now)
        subject_digest = self._digest([actor.subject_id, actor.organization_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        idempotency_digest = self._digest([subject_digest, idempotency_key])
        request_digest = self._digest(
            [
                adjudication_id,
                adjudication_digest,
                policy.canonical_digest,
                purpose,
                decision_support_only_acknowledged,
                tie_or_no_support_acknowledged,
                no_operational_authority_acknowledged,
            ]
        )
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
        presentation_id = f"protected-recommendation-presentation.{uuid4().hex}"
        claim = ProtectedRecommendationPresentationClaim(
            claim_id=f"claim.protected-recommendation-presentation.{uuid4().hex}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            presentation_id=presentation_id,
            adjudication_id=adjudication_id,
            claimed_by_subject_digest=subject_digest,
            browser_session_binding_digest=browser_digest,
            request_binding_digest=request_digest,
            idempotency_digest=idempotency_digest,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            claimed_at=now,
            canonical_digest="0" * 64,
        )
        claim = replace(claim, canonical_digest=self._digest(self._payload(claim)))
        await self._audit(
            actor,
            correlation_id,
            "protected_recommendation_presentation_intent_recorded",
            adjudication_id,
        )
        if not await self._repository.claim(claim):
            collision = await self._repository.get_claim_by_idempotency(
                claimed_by_subject_digest=subject_digest,
                idempotency_digest=idempotency_digest,
            )
            if collision is None:
                raise ProtectedRecommendationPresentationError(
                    "protected_recommendation_presentation_already_claimed"
                )
            return await self._reuse(
                collision,
                browser_digest,
                request_digest,
                actor,
                browser_session_id,
                correlation_id,
            )
        await self._audit(
            actor, correlation_id, "protected_recommendation_presentation_claimed", presentation_id
        )
        try:
            (
                adjudication,
                adjudication_report,
                completion,
                candidates,
                impact_report,
                completion_report,
                evidence,
            ) = await self._adjudication_source.rehydrate_for_presentation(
                actor=actor,
                adjudication_id=adjudication_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
            self._verify_adjudication(
                adjudication.record, policy, adjudication_digest, purpose, now
            )
            authorization_digest = self._digest(
                [
                    adjudication.record.adjudication_authorization_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    adjudication_report.canonical_digest,
                ]
            )
            expires_at = min(
                adjudication.record.expires_at,
                adjudication_report.expires_at,
                completion.expires_at,
                candidates.expires_at,
                impact_report.expires_at,
                completion_report.expires_at,
                evidence.expires_at,
                policy.expires_at,
                now + timedelta(minutes=policy.retention_minutes),
            )
            instruction = ProtectedRecommendationPresentationInstruction(
                presentation_id=presentation_id,
                adjudication_id=adjudication_id,
                adjudication_digest=adjudication.record.canonical_digest,
                adjudication_report_digest=adjudication_report.canonical_digest,
                completion_digest=completion.canonical_digest,
                candidate_set_digest=candidates.canonical_digest,
                impact_report_digest=impact_report.canonical_digest,
                completion_report_digest=completion_report.canonical_digest,
                organization_id=adjudication.record.organization_id,
                environment_id=adjudication.record.environment_id,
                consumer_subject_digest=adjudication.record.consumer_subject_digest,
                presentation_authorization_digest=authorization_digest,
                policy_id=policy.policy_id,
                policy_digest=policy.canonical_digest,
                media_type=policy.media_type,
                maximum_option_count=policy.maximum_option_count,
                maximum_steps_per_option=policy.maximum_steps_per_option,
                maximum_text_items_per_option=policy.maximum_text_items_per_option,
                maximum_output_bytes=policy.maximum_output_bytes,
                rendering_profile_digest=policy.rendering_profile_digest,
                prohibited_output_profile_digest=policy.prohibited_output_profile_digest,
                requested_at=now,
                expires_at=expires_at,
            )
            receipt, recommendation = await self._presenter.present(
                instruction,
                adjudication_report,
                candidates,
                impact_report,
                completion_report,
            )
            self._verify_receipt(receipt, recommendation, instruction, policy)
            record = self._record(
                claim,
                adjudication.record,
                policy,
                receipt,
                authorization_digest,
                purpose,
            )
            await self._repository.save(record)
            await self._audit(
                actor,
                correlation_id,
                "protected_recommendation_presentation_completed",
                presentation_id,
            )
        except ProtectedRecommendationPresentationError:
            raise
        except ProtectedRecommendationAdjudicationError as error:
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_source_invalid"
            ) from error
        except Exception as error:
            raise ProtectedRecommendationPresentationUncertainError(
                "protected_recommendation_presentation_persistence_uncertain"
            ) from error
        return ProtectedRecommendationPresentationResult(
            record=record,
            manifest=self._manifest(record),
            recommendation=recommendation,
        )

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        presentation_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedRecommendationPresentationResult:
        self._require_human(actor)
        record = await self._repository.get(presentation_id=presentation_id)
        if record is None:
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.presentation_policy_id)
        now = self._clock()
        if (
            policy is None
            or record.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.presentation_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_not_found"
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        try:
            (
                adjudication,
                adjudication_report,
                _,
                candidates,
                impact_report,
                completion_report,
                _,
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
                record.purpose,
                now,
            )
            authorization_digest = self._digest(
                [
                    adjudication.record.adjudication_authorization_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    adjudication_report.canonical_digest,
                ]
            )
            recommendation = await self._presenter.rehydrate(
                record=record,
                presentation_authorization_digest=authorization_digest,
                adjudication_report=adjudication_report,
                candidate_set=candidates,
                impact_report=impact_report,
                completion_report=completion_report,
            )
            self._verify_recommendation(record, recommendation)
        except ProtectedRecommendationPresentationError:
            raise
        except Exception as error:
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_not_found"
            ) from error
        await self._audit(
            actor,
            correlation_id,
            "protected_recommendation_presentation_read",
            presentation_id,
            permission_id=AI_PROTECTED_RECOMMENDATION_PRESENTATION_READ,
        )
        return ProtectedRecommendationPresentationResult(
            record=replace(record, reused=True),
            manifest=self._manifest(record),
            recommendation=recommendation,
        )

    async def close(self) -> None:
        await self._repository.close()

    @classmethod
    def _verify_adjudication(
        cls,
        record: ProtectedRecommendationAdjudicationRecord,
        policy: ProtectedRecommendationPresentationPolicySnapshot,
        expected_digest: str,
        purpose: str,
        now: datetime,
    ) -> None:
        if (
            record.canonical_digest != expected_digest
            or record.canonical_digest != cls._digest(cls._payload(record))
            or record.schema_version != policy.required_adjudication_schema
            or record.instance_state != policy.required_adjudication_state
            or record.purpose != purpose
            or now >= record.expires_at
            or not record.recommendation_complete
            or record.recommendation_presented
            or record.recommendation_ready_for_review
            or record.recommendation_approved
            or record.workflow_created
            or record.execution_authorized
            or record.deployment_authorized
            or record.infrastructure_mutated
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_source_invalid"
            )

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ProtectedRecommendationPresentationReceipt,
        recommendation: ProtectedPresentedRecommendation,
        instruction: ProtectedRecommendationPresentationInstruction,
        policy: ProtectedRecommendationPresentationPolicySnapshot,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.presenter_id != policy.required_presenter_id
            or receipt.attested_by != policy.required_presenter_attestor_id
            or receipt.presentation_id != instruction.presentation_id
            or receipt.adjudication_id != instruction.adjudication_id
            or receipt.adjudication_digest != instruction.adjudication_digest
            or receipt.presentation_authorization_digest
            != instruction.presentation_authorization_digest
            or receipt.policy_digest != policy.canonical_digest
            or receipt.recommendation_digest != recommendation.canonical_digest
            or receipt.byte_count != recommendation.byte_count
            or receipt.option_count != len(recommendation.options)
            or receipt.outcome != recommendation.outcome
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or recommendation.canonical_digest != cls._digest(cls._payload(recommendation))
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: ProtectedRecommendationPresentationClaim,
        adjudication: ProtectedRecommendationAdjudicationRecord,
        policy: ProtectedRecommendationPresentationPolicySnapshot,
        receipt: ProtectedRecommendationPresentationReceipt,
        authorization_digest: str,
        purpose: str,
    ) -> ProtectedRecommendationPresentationRecord:
        record = ProtectedRecommendationPresentationRecord(
            presentation_id=claim.presentation_id,
            schema_version=RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            adjudication_id=adjudication.adjudication_id,
            adjudication_digest=adjudication.canonical_digest,
            completion_id=adjudication.completion_id,
            candidate_set_id=adjudication.candidate_set_id,
            impact_analysis_id=adjudication.impact_analysis_id,
            organization_id=adjudication.organization_id,
            environment_id=adjudication.environment_id,
            classification=adjudication.classification,
            consumer_subject_digest=adjudication.consumer_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            presentation_policy_id=policy.policy_id,
            presentation_policy_digest=policy.canonical_digest,
            presentation_policy_version=policy.policy_version,
            presenter_id=receipt.presenter_id,
            presentation_receipt_digest=receipt.canonical_digest,
            presentation_authorization_digest=authorization_digest,
            recommendation_digest=receipt.recommendation_digest,
            source_binding_digest=receipt.source_binding_digest,
            rendering_digest=receipt.rendering_digest,
            cleanup_digest=receipt.cleanup_digest,
            outcome=receipt.outcome,
            option_count=receipt.option_count,
            preferred_count=receipt.preferred_count,
            evidence_reference_count=receipt.evidence_reference_count,
            unknown_count=receipt.unknown_count,
            byte_count=receipt.byte_count,
            media_type=policy.media_type,
            presented_at=receipt.presented_at,
            expires_at=receipt.expires_at,
            instance_state="protected_recommendation_presented",
            purpose=purpose,
            safety_notice=SAFETY_NOTICE,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._payload(record)))

    @staticmethod
    def _verify_recommendation(
        record: ProtectedRecommendationPresentationRecord,
        recommendation: ProtectedPresentedRecommendation,
    ) -> None:
        if (
            recommendation.canonical_digest != record.recommendation_digest
            or recommendation.outcome != record.outcome
            or len(recommendation.options) != record.option_count
            or recommendation.byte_count != record.byte_count
            or recommendation.media_type != record.media_type
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_integrity_failed"
            )

    async def _reuse(
        self,
        claim: ProtectedRecommendationPresentationClaim,
        browser_digest: str,
        request_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedRecommendationPresentationResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_idempotency_conflict"
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
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_not_found"
            )

    @staticmethod
    def _manifest(
        record: ProtectedRecommendationPresentationRecord,
    ) -> ProtectedRecommendationPresentationManifest:
        return ProtectedRecommendationPresentationManifest(
            presentation_id=record.presentation_id,
            adjudication_id=record.adjudication_id,
            completion_id=record.completion_id,
            candidate_set_id=record.candidate_set_id,
            impact_analysis_id=record.impact_analysis_id,
            outcome=record.outcome,
            option_count=record.option_count,
            preferred_count=record.preferred_count,
            evidence_reference_count=record.evidence_reference_count,
            unknown_count=record.unknown_count,
            byte_count=record.byte_count,
            media_type=record.media_type,
            recommendation_digest=record.recommendation_digest,
            source_binding_digest=record.source_binding_digest,
            rendering_digest=record.rendering_digest,
            presented_at=record.presented_at,
            expires_at=record.expires_at,
            safety_notice=record.safety_notice,
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = AI_PROTECTED_RECOMMENDATION_PRESENTATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.protected-recommendation-presentation",
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
                resource_type="resource.ai.protected-recommendation-presentation",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    _digest = staticmethod(GovernedProtectedModelInvocationService._digest)
    _payload = staticmethod(GovernedProtectedModelInvocationService._payload)


def build_development_protected_recommendation_presentation_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ProtectedRecommendationPresentationPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = ProtectedRecommendationPresentationPolicySnapshot(
        policy_id="protected-recommendation-presentation-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.protected-recommendation-presentation-development-v1",
        required_adjudication_schema="atlas.protected-recommendation-adjudication.v1",
        required_adjudication_state="protected_recommendation_adjudicated",
        required_presenter_id="protected-recommendation-presenter.synthetic",
        required_presenter_attestor_id="subject.protected-recommendation-presenter-attestor",
        required_receipt_schema="atlas.protected-recommendation-presentation-receipt.v1",
        media_type="text/plain",
        maximum_option_count=5,
        maximum_steps_per_option=10,
        maximum_text_items_per_option=25,
        maximum_output_bytes=65_536,
        retention_minutes=10,
        browser_binding_key_digest=digest(["protected-recommendation-presentation-browser-key"]),
        rendering_profile_digest=digest(["rendering-profile.inert-recommendation-v1"]),
        prohibited_output_profile_digest=digest(
            ["prohibited-output.no-identifiers-tools-operations-v1"]
        ),
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
