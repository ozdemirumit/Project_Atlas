from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.ai.application.protected_candidate_risk_recovery_completion import (
    GovernedProtectedCandidateRiskRecoveryService,
)
from atlas.modules.ai.application.protected_candidate_risk_recovery_completion_ports import (
    ProtectedCandidateRiskRecoveryError,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_adjudication_ports import (
    ProtectedRecommendationAdjudicationError,
    ProtectedRecommendationAdjudicationPermissionAuthorizer,
    ProtectedRecommendationAdjudicationPolicySource,
    ProtectedRecommendationAdjudicationRepository,
    ProtectedRecommendationAdjudicationUncertainError,
    TrustedProtectedRecommendationAdjudicator,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryRecord,
    ProtectedCandidateRiskRecoveryReport,
    ProtectedOperationalEvidenceSnapshot,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationClaim,
    ProtectedRecommendationAdjudicationInstruction,
    ProtectedRecommendationAdjudicationManifest,
    ProtectedRecommendationAdjudicationPolicySnapshot,
    ProtectedRecommendationAdjudicationReceipt,
    ProtectedRecommendationAdjudicationRecord,
    ProtectedRecommendationAdjudicationReport,
    ProtectedRecommendationAdjudicationResult,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_RECOMMENDATION_ADJUDICATION_CREATE,
    AI_PROTECTED_RECOMMENDATION_ADJUDICATION_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

POLICY_SCHEMA = "atlas.protected-recommendation-adjudication-policy.v1"
CLAIM_SCHEMA = "atlas.protected-recommendation-adjudication-claim.v1"
RECORD_SCHEMA = "atlas.protected-recommendation-adjudication.v1"
SAFETY_NOTICE = (
    "Deterministic protected preference is decision support only; no candidate content, approval, "
    "workflow, review readiness, or operational authority is established."
)


class GovernedProtectedRecommendationAdjudicationService:
    def __init__(
        self,
        *,
        repository: ProtectedRecommendationAdjudicationRepository,
        completion_source: GovernedProtectedCandidateRiskRecoveryService,
        policy_source: ProtectedRecommendationAdjudicationPolicySource,
        permission_authorizer: ProtectedRecommendationAdjudicationPermissionAuthorizer,
        adjudicator: TrustedProtectedRecommendationAdjudicator,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._completion_source = completion_source
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
        completion_id: str,
        completion_digest: str,
        adjudication_policy_id: str,
        adjudication_policy_digest: str,
        purpose: str,
        preference_not_approval_acknowledged: bool,
        tie_or_no_support_acknowledged: bool,
        no_presentation_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProtectedRecommendationAdjudicationResult:
        self._require_human(actor)
        if not all(
            (
                preference_not_approval_acknowledged,
                tie_or_no_support_acknowledged,
                no_presentation_or_operational_authority_acknowledged,
            )
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_acknowledgement_required"
            )
        now = self._clock()
        policy = await self._policy_source.get_by_id(policy_id=adjudication_policy_id)
        if (
            policy is None
            or policy.policy_id != adjudication_policy_id
            or policy.canonical_digest != adjudication_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or policy.schema_version != POLICY_SCHEMA
            or policy.organization_id != actor.organization_id
            or policy.environment_id != self._environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_policy_invalid"
            )
        self._require_assurance(actor, policy)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            correlation_id=correlation_id,
        )
        subject_digest = self._digest([actor.subject_id, actor.organization_id])
        browser_digest = self._digest([policy.browser_binding_key_digest, browser_session_id])
        idempotency_digest = self._digest([subject_digest, idempotency_key])
        request_digest = self._digest(
            [
                completion_id,
                completion_digest,
                policy.canonical_digest,
                purpose,
                preference_not_approval_acknowledged,
                tie_or_no_support_acknowledged,
                no_presentation_or_operational_authority_acknowledged,
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
        await self._audit(
            actor,
            correlation_id,
            "protected_recommendation_adjudication_intent_recorded",
            completion_id,
        )
        adjudication_id = f"protected-recommendation-adjudication.{uuid4().hex}"
        claim = ProtectedRecommendationAdjudicationClaim(
            claim_id=f"claim.protected-recommendation-adjudication.{uuid4().hex}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            adjudication_id=adjudication_id,
            completion_id=completion_id,
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
        if not await self._repository.claim(claim):
            collision = await self._repository.get_claim_by_idempotency(
                claimed_by_subject_digest=subject_digest,
                idempotency_digest=idempotency_digest,
            )
            if collision is None:
                raise ProtectedRecommendationAdjudicationError(
                    "protected_recommendation_adjudication_already_claimed"
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
            actor,
            correlation_id,
            "protected_recommendation_adjudication_claimed",
            adjudication_id,
        )
        try:
            (
                completion,
                candidates,
                impact_report,
                completion_report,
                evidence,
            ) = await self._completion_source.rehydrate_for_adjudication(
                actor=actor,
                completion_id=completion_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
            self._verify_source(
                completion,
                completion_report,
                completion_digest,
                purpose,
                policy,
                now,
            )
            authorization_digest = self._digest(
                [
                    completion.consumer_subject_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    completion.canonical_digest,
                    completion_report.canonical_digest,
                ]
            )
            expires_at = min(
                completion.expires_at,
                completion_report.expires_at,
                evidence.expires_at,
                policy.expires_at,
                now + timedelta(minutes=policy.retention_minutes),
            )
            instruction = ProtectedRecommendationAdjudicationInstruction(
                adjudication_id=adjudication_id,
                completion_id=completion_id,
                completion_digest=completion_report.canonical_digest,
                candidate_set_id=completion.candidate_set_id,
                candidate_set_digest=completion.candidate_set_digest,
                adjudication_authorization_digest=authorization_digest,
                policy_id=policy.policy_id,
                policy_digest=policy.canonical_digest,
                required_dimensions=policy.required_dimensions,
                category_precedence=policy.category_precedence,
                allowed_categories=policy.allowed_categories,
                maximum_capability_class=policy.maximum_capability_class,
                maximum_candidate_count=policy.maximum_candidate_count,
                maximum_dimension_count=policy.maximum_dimension_count,
                maximum_exclusion_count=policy.maximum_exclusion_count,
                maximum_unknown_count=policy.maximum_unknown_count,
                maximum_output_bytes=policy.maximum_output_bytes,
                required_report_schema=policy.required_report_schema,
                preference_profile_digest=policy.preference_profile_digest,
                safety_profile_digest=policy.safety_profile_digest,
                requested_at=now,
                expires_at=expires_at,
            )
            receipt, report = await self._adjudicator.adjudicate(
                instruction,
                candidates,
                impact_report,
                completion_report,
                evidence,
            )
            self._verify_receipt(receipt, report, instruction, policy)
            record = self._record(
                claim,
                completion,
                policy,
                receipt,
                report,
                authorization_digest,
                purpose,
            )
            await self._audit(
                actor,
                correlation_id,
                "protected_recommendation_adjudication_completed",
                adjudication_id,
            )
            await self._repository.save(record)
        except ProtectedRecommendationAdjudicationError:
            raise
        except ProtectedCandidateRiskRecoveryError as error:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_source_invalid"
            ) from error
        except Exception as error:
            raise ProtectedRecommendationAdjudicationUncertainError(
                "protected_recommendation_adjudication_persistence_uncertain"
            ) from error
        return ProtectedRecommendationAdjudicationResult(
            record=record,
            manifest=self._manifest(record),
        )

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        adjudication_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedRecommendationAdjudicationResult:
        self._require_human(actor)
        record = await self._repository.get(adjudication_id=adjudication_id)
        if record is None:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.adjudication_policy_id)
        now = self._clock()
        if (
            policy is None
            or record.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.adjudication_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            )
        self._require_assurance(actor, policy)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        try:
            (
                completion,
                candidates,
                _,
                completion_report,
                _,
            ) = await self._completion_source.rehydrate_for_adjudication(
                actor=actor,
                completion_id=record.completion_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
            self._verify_source(
                completion,
                completion_report,
                record.completion_digest,
                record.purpose,
                policy,
                now,
            )
            authorization_digest = self._digest(
                [
                    completion.consumer_subject_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    completion.canonical_digest,
                    completion_report.canonical_digest,
                ]
            )
            receipt, report = await self._adjudicator.rehydrate(
                record=record,
                adjudication_authorization_digest=authorization_digest,
                candidate_set=candidates,
                completion_report=completion_report,
            )
            self._verify_receipt(
                receipt,
                report,
                self._instruction_from_record(record, policy, completion_report),
                policy,
            )
            self._verify_record(record, receipt, report, completion)
        except ProtectedRecommendationAdjudicationError:
            raise
        except Exception as error:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            ) from error
        await self._audit(
            actor,
            correlation_id,
            "protected_recommendation_adjudication_read",
            adjudication_id,
            permission_id=AI_PROTECTED_RECOMMENDATION_ADJUDICATION_READ,
        )
        return ProtectedRecommendationAdjudicationResult(
            record=replace(record, reused=True),
            manifest=self._manifest(record),
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
        ProtectedRecommendationAdjudicationResult,
        ProtectedRecommendationAdjudicationReport,
        ProtectedCandidateRiskRecoveryRecord,
        ProtectedRecommendationCandidateSet,
        ProtectedCandidateImpactReport,
        ProtectedCandidateRiskRecoveryReport,
        ProtectedOperationalEvidenceSnapshot,
    ]:
        self._require_human(actor)
        record = await self._repository.get(adjudication_id=adjudication_id)
        if record is None:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.adjudication_policy_id)
        now = self._clock()
        if (
            policy is None
            or record.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.adjudication_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            )
        self._require_assurance(actor, policy)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        try:
            (
                completion,
                candidates,
                impact_report,
                completion_report,
                evidence,
            ) = await self._completion_source.rehydrate_for_adjudication(
                actor=actor,
                completion_id=record.completion_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
            self._verify_source(
                completion,
                completion_report,
                record.completion_digest,
                record.purpose,
                policy,
                now,
            )
            authorization_digest = self._digest(
                [
                    completion.consumer_subject_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    completion.canonical_digest,
                    completion_report.canonical_digest,
                ]
            )
            receipt, report = await self._adjudicator.rehydrate(
                record=record,
                adjudication_authorization_digest=authorization_digest,
                candidate_set=candidates,
                completion_report=completion_report,
            )
            self._verify_receipt(
                receipt,
                report,
                self._instruction_from_record(record, policy, completion_report),
                policy,
            )
            self._verify_record(record, receipt, report, completion)
        except ProtectedRecommendationAdjudicationError:
            raise
        except Exception as error:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            ) from error
        result = ProtectedRecommendationAdjudicationResult(
            record=replace(record, reused=True),
            manifest=self._manifest(record),
        )
        return (
            result,
            report,
            completion,
            candidates,
            impact_report,
            completion_report,
            evidence,
        )

    async def get_record_for_presentation_authorization(
        self,
        *,
        actor: AuthenticatedSubject,
        adjudication_id: str,
        browser_session_id: str,
    ) -> ProtectedRecommendationAdjudicationRecord:
        self._require_human(actor)
        record = await self._repository.get(adjudication_id=adjudication_id)
        if record is None:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            )
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.adjudication_policy_id)
        now = self._clock()
        if (
            policy is None
            or record.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.adjudication_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            )
        self._require_assurance(actor, policy)
        return record

    @classmethod
    def _verify_source(
        cls,
        record: ProtectedCandidateRiskRecoveryRecord,
        report: ProtectedCandidateRiskRecoveryReport,
        expected_digest: str,
        purpose: str,
        policy: ProtectedRecommendationAdjudicationPolicySnapshot,
        now: datetime,
    ) -> None:
        if (
            record.canonical_digest != expected_digest
            or record.canonical_digest != cls._digest(cls._payload(record))
            or record.schema_version != policy.required_completion_schema
            or record.instance_state != policy.required_completion_state
            or record.purpose != purpose
            or now >= min(record.expires_at, report.expires_at)
            or report.completion_id != record.completion_id
            or report.canonical_digest != record.protected_report_digest
            or not all(
                (
                    record.service_impact_analyzed,
                    record.impact_complete,
                    record.interruption_established,
                    record.duration_established,
                    record.risk_completed,
                    record.recovery_completed,
                )
            )
            or any(
                (
                    record.recommendation_complete,
                    record.recommendation_presented,
                    record.recommendation_ready_for_review,
                    record.recommendation_approved,
                    record.workflow_created,
                    record.execution_authorized,
                    record.deployment_authorized,
                    record.infrastructure_mutated,
                )
            )
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_source_invalid"
            )

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ProtectedRecommendationAdjudicationReceipt,
        report: ProtectedRecommendationAdjudicationReport,
        instruction: ProtectedRecommendationAdjudicationInstruction,
        policy: ProtectedRecommendationAdjudicationPolicySnapshot,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.adjudicator_id != policy.required_adjudicator_id
            or receipt.attested_by != policy.required_adjudicator_attestor_id
            or receipt.adjudication_id != instruction.adjudication_id
            or receipt.completion_id != instruction.completion_id
            or receipt.completion_digest != instruction.completion_digest
            or receipt.adjudication_authorization_digest
            != instruction.adjudication_authorization_digest
            or receipt.policy_digest != policy.canonical_digest
            or report.schema_version != policy.required_report_schema
            or report.canonical_digest != cls._digest(cls._payload(report))
            or receipt.report_digest != report.canonical_digest
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or receipt.candidate_count != len(report.entries)
            or receipt.candidate_count != report.candidate_count
            or receipt.preferred_count > 1
            or any(
                entry.canonical_digest != cls._digest(cls._payload(entry))
                for entry in report.entries
            )
            or not all(
                (
                    receipt.source_verified,
                    receipt.complete_candidate_coverage_verified,
                    receipt.deterministic_policy_verified,
                    receipt.conservative_unknowns_verified,
                    receipt.tie_behavior_verified,
                    receipt.no_caller_preference_verified,
                    receipt.no_model_used,
                    receipt.cleanup_verified,
                    receipt.signature_verified,
                )
            )
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: ProtectedRecommendationAdjudicationClaim,
        completion: ProtectedCandidateRiskRecoveryRecord,
        policy: ProtectedRecommendationAdjudicationPolicySnapshot,
        receipt: ProtectedRecommendationAdjudicationReceipt,
        report: ProtectedRecommendationAdjudicationReport,
        authorization_digest: str,
        purpose: str,
    ) -> ProtectedRecommendationAdjudicationRecord:
        record = ProtectedRecommendationAdjudicationRecord(
            adjudication_id=claim.adjudication_id,
            schema_version=RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            completion_id=completion.completion_id,
            completion_digest=completion.canonical_digest,
            impact_analysis_id=completion.impact_analysis_id,
            candidate_set_id=completion.candidate_set_id,
            candidate_set_digest=completion.candidate_set_digest,
            presentation_id=completion.presentation_id,
            organization_id=completion.organization_id,
            environment_id=completion.environment_id,
            classification=completion.classification,
            consumer_subject_digest=completion.consumer_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            adjudication_policy_id=policy.policy_id,
            adjudication_policy_digest=policy.canonical_digest,
            adjudication_policy_version=policy.policy_version,
            adjudicator_id=receipt.adjudicator_id,
            adjudication_receipt_digest=receipt.canonical_digest,
            adjudication_authorization_digest=authorization_digest,
            protected_report_digest=report.canonical_digest,
            candidate_count=receipt.candidate_count,
            dimension_count=receipt.dimension_count,
            eligible_count=receipt.eligible_count,
            excluded_count=receipt.excluded_count,
            preferred_count=receipt.preferred_count,
            alternative_count=receipt.alternative_count,
            tie=receipt.tie,
            no_supportable_candidate=receipt.no_supportable_candidate,
            maximum_risk=completion.maximum_risk,
            interruption_possible_count=completion.interruption_possible_count,
            recovery_feasible_count=completion.recovery_feasible_count,
            gap_count=completion.gap_count,
            unknown_count=completion.unknown_count,
            comparison_digest=receipt.comparison_digest,
            eligibility_digest=receipt.eligibility_digest,
            exclusion_digest=receipt.exclusion_digest,
            preference_digest=receipt.preference_digest,
            safety_digest=receipt.safety_digest,
            cleanup_digest=receipt.cleanup_digest,
            byte_count=receipt.byte_count,
            adjudicated_at=report.completed_at,
            expires_at=report.expires_at,
            instance_state="protected_recommendation_adjudicated",
            purpose=purpose,
            safety_notice=SAFETY_NOTICE,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._payload(record)))

    @classmethod
    def _verify_record(
        cls,
        record: ProtectedRecommendationAdjudicationRecord,
        receipt: ProtectedRecommendationAdjudicationReceipt,
        report: ProtectedRecommendationAdjudicationReport,
        completion: ProtectedCandidateRiskRecoveryRecord,
    ) -> None:
        if (
            record.completion_digest != completion.canonical_digest
            or record.candidate_set_digest != completion.candidate_set_digest
            or record.adjudication_receipt_digest != receipt.canonical_digest
            or record.protected_report_digest != report.canonical_digest
            or record.comparison_digest != report.comparison_digest
            or record.eligibility_digest != report.eligibility_digest
            or record.exclusion_digest != report.exclusion_digest
            or record.preference_digest != report.preference_digest
            or record.safety_digest != report.safety_digest
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_integrity_failed"
            )

    @staticmethod
    def _instruction_from_record(
        record: ProtectedRecommendationAdjudicationRecord,
        policy: ProtectedRecommendationAdjudicationPolicySnapshot,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> ProtectedRecommendationAdjudicationInstruction:
        return ProtectedRecommendationAdjudicationInstruction(
            adjudication_id=record.adjudication_id,
            completion_id=record.completion_id,
            completion_digest=completion_report.canonical_digest,
            candidate_set_id=record.candidate_set_id,
            candidate_set_digest=record.candidate_set_digest,
            adjudication_authorization_digest=record.adjudication_authorization_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            required_dimensions=policy.required_dimensions,
            category_precedence=policy.category_precedence,
            allowed_categories=policy.allowed_categories,
            maximum_capability_class=policy.maximum_capability_class,
            maximum_candidate_count=policy.maximum_candidate_count,
            maximum_dimension_count=policy.maximum_dimension_count,
            maximum_exclusion_count=policy.maximum_exclusion_count,
            maximum_unknown_count=policy.maximum_unknown_count,
            maximum_output_bytes=policy.maximum_output_bytes,
            required_report_schema=policy.required_report_schema,
            preference_profile_digest=policy.preference_profile_digest,
            safety_profile_digest=policy.safety_profile_digest,
            requested_at=record.adjudicated_at,
            expires_at=record.expires_at,
        )

    async def _reuse(
        self,
        claim: ProtectedRecommendationAdjudicationClaim,
        browser_digest: str,
        request_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedRecommendationAdjudicationResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_idempotency_conflict"
            )
        return await self.get(
            actor=actor,
            adjudication_id=claim.adjudication_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_human_required"
            )

    @staticmethod
    def _require_assurance(
        actor: AuthenticatedSubject,
        policy: ProtectedRecommendationAdjudicationPolicySnapshot,
    ) -> None:
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_assurance_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_not_found"
            )

    @staticmethod
    def _manifest(
        record: ProtectedRecommendationAdjudicationRecord,
    ) -> ProtectedRecommendationAdjudicationManifest:
        fields = {
            name: getattr(record, name)
            for name in ProtectedRecommendationAdjudicationManifest.__dataclass_fields__
        }
        return ProtectedRecommendationAdjudicationManifest(**fields)

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = AI_PROTECTED_RECOMMENDATION_ADJUDICATION_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.protected-recommendation-adjudication",
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
                resource_type="resource.ai.protected-recommendation-adjudication",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    _digest = staticmethod(GovernedProtectedModelInvocationService._digest)
    _payload = staticmethod(GovernedProtectedModelInvocationService._payload)


def build_development_protected_recommendation_adjudication_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> ProtectedRecommendationAdjudicationPolicySnapshot:
    policy = ProtectedRecommendationAdjudicationPolicySnapshot(
        policy_id="protected-recommendation-adjudication-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.protected-recommendation-adjudication-development-v1",
        required_completion_schema="atlas.protected-candidate-risk-recovery-completion.v1",
        required_completion_state="protected_candidate_risk_recovery_completed",
        required_report_schema="atlas.protected-recommendation-adjudication-report.v1",
        required_receipt_schema="atlas.protected-recommendation-adjudication-receipt.v1",
        required_adjudicator_id="protected-recommendation-adjudicator.synthetic",
        required_adjudicator_attestor_id=("subject.protected-recommendation-adjudicator-attestor"),
        required_dimensions=(
            "policy-eligibility",
            "evidence-applicability",
            "risk-and-uncertainty",
            "capability-class",
            "interruption",
            "recovery-and-reversibility",
            "work-duration",
            "evidence-value",
            "category-precedence",
        ),
        category_precedence=(
            "recommendation-category.investigate",
            "recommendation-category.escalate",
            "recommendation-category.defer-no-action",
        ),
        allowed_categories=(
            "recommendation-category.investigate",
            "recommendation-category.escalate",
            "recommendation-category.defer-no-action",
        ),
        maximum_capability_class="C1",
        maximum_candidate_count=5,
        maximum_dimension_count=12,
        maximum_exclusion_count=20,
        maximum_unknown_count=100,
        maximum_output_bytes=256 * 1024,
        retention_minutes=30,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        browser_binding_key_digest=GovernedProtectedModelInvocationService._digest(
            ["protected-recommendation-adjudication", "browser-binding", "v1"]
        ),
        preference_profile_digest=GovernedProtectedModelInvocationService._digest(
            ["policy-first", "lexicographic", "tie-preserving", "no-opaque-score"]
        ),
        safety_profile_digest=GovernedProtectedModelInvocationService._digest(
            ["no-presentation", "no-review-readiness", "no-approval", "no-operation"]
        ),
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=GovernedProtectedModelInvocationService._digest(
            GovernedProtectedModelInvocationService._payload(policy)
        ),
    )
