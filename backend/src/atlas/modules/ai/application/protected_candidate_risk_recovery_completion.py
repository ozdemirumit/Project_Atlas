from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.ai.application.protected_candidate_impact_enrichment import (
    GovernedProtectedCandidateImpactService,
)
from atlas.modules.ai.application.protected_candidate_impact_enrichment_ports import (
    ProtectedCandidateImpactError,
)
from atlas.modules.ai.application.protected_candidate_risk_recovery_completion_ports import (
    ProtectedCandidateRiskRecoveryError,
    ProtectedCandidateRiskRecoveryPermissionAuthorizer,
    ProtectedCandidateRiskRecoveryPolicySource,
    ProtectedCandidateRiskRecoveryRepository,
    ProtectedCandidateRiskRecoveryUncertainError,
    ProtectedOperationalEvidenceSource,
    TrustedProtectedCandidateRiskRecoveryAssessor,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactRecord,
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryClaim,
    ProtectedCandidateRiskRecoveryInstruction,
    ProtectedCandidateRiskRecoveryManifest,
    ProtectedCandidateRiskRecoveryPolicySnapshot,
    ProtectedCandidateRiskRecoveryReceipt,
    ProtectedCandidateRiskRecoveryRecord,
    ProtectedCandidateRiskRecoveryReport,
    ProtectedCandidateRiskRecoveryResult,
    ProtectedOperationalEvidenceSnapshot,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_CANDIDATE_RISK_RECOVERY_CREATE,
    AI_PROTECTED_CANDIDATE_RISK_RECOVERY_READ,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    SubjectKind,
    assurance_satisfies_policy,
)

POLICY_SCHEMA = "atlas.protected-candidate-risk-recovery-policy.v1"
CLAIM_SCHEMA = "atlas.protected-candidate-risk-recovery-claim.v1"
RECORD_SCHEMA = "atlas.protected-candidate-risk-recovery-completion.v1"
SAFETY_NOTICE = (
    "Risk, duration, interruption, and recovery are bounded decision-support estimates from "
    "verified evidence; they are not guarantees, preference, approval, or authority to act."
)


class GovernedProtectedCandidateRiskRecoveryService:
    def __init__(
        self,
        *,
        repository: ProtectedCandidateRiskRecoveryRepository,
        impact_source: GovernedProtectedCandidateImpactService,
        policy_source: ProtectedCandidateRiskRecoveryPolicySource,
        evidence_source: ProtectedOperationalEvidenceSource,
        permission_authorizer: ProtectedCandidateRiskRecoveryPermissionAuthorizer,
        assessor: TrustedProtectedCandidateRiskRecoveryAssessor,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._impact_source = impact_source
        self._policy_source = policy_source
        self._evidence_source = evidence_source
        self._permission_authorizer = permission_authorizer
        self._assessor = assessor
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        impact_analysis_id: str,
        impact_digest: str,
        completion_policy_id: str,
        completion_policy_digest: str,
        purpose: str,
        estimates_not_guarantees_acknowledged: bool,
        unknowns_cannot_lower_risk_acknowledged: bool,
        no_preference_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProtectedCandidateRiskRecoveryResult:
        self._require_human(actor)
        if not all(
            (
                estimates_not_guarantees_acknowledged,
                unknowns_cannot_lower_risk_acknowledged,
                no_preference_or_operational_authority_acknowledged,
            )
        ):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_acknowledgement_required"
            )
        now = self._clock()
        policy = await self._policy_source.get_by_id(policy_id=completion_policy_id)
        if (
            policy is None
            or policy.policy_id != completion_policy_id
            or policy.canonical_digest != completion_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or policy.schema_version != POLICY_SCHEMA
            or policy.organization_id != actor.organization_id
            or policy.environment_id != self._environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_policy_invalid"
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
                impact_analysis_id,
                impact_digest,
                policy.canonical_digest,
                purpose,
                estimates_not_guarantees_acknowledged,
                unknowns_cannot_lower_risk_acknowledged,
                no_preference_or_operational_authority_acknowledged,
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
            "protected_candidate_risk_recovery_intent_recorded",
            impact_analysis_id,
        )
        completion_id = f"protected-candidate-risk-recovery.{uuid4().hex}"
        claim = ProtectedCandidateRiskRecoveryClaim(
            claim_id=f"claim.protected-candidate-risk-recovery.{uuid4().hex}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            completion_id=completion_id,
            impact_analysis_id=impact_analysis_id,
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
                raise ProtectedCandidateRiskRecoveryError(
                    "protected_candidate_risk_recovery_already_claimed"
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
            "protected_candidate_risk_recovery_claimed",
            completion_id,
        )
        try:
            (
                impact_record,
                candidate_set,
                impact_report,
            ) = await self._impact_source.rehydrate_for_risk_recovery(
                actor=actor,
                impact_analysis_id=impact_analysis_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
            self._verify_impact_source(
                impact_record,
                candidate_set,
                impact_report,
                impact_digest,
                purpose,
                policy,
                now,
            )
            evidence = await self._evidence_source.get_by_id(
                snapshot_id=policy.required_evidence_snapshot_id
            )
            self._verify_evidence(evidence, impact_record, policy, now)
            assert evidence is not None
            authorization_digest = self._digest(
                [
                    impact_record.consumer_subject_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    impact_record.canonical_digest,
                    evidence.canonical_digest,
                ]
            )
            expires_at = min(
                impact_record.expires_at,
                impact_report.expires_at,
                policy.expires_at,
                evidence.expires_at,
                now + timedelta(minutes=policy.retention_minutes),
            )
            instruction = ProtectedCandidateRiskRecoveryInstruction(
                completion_id=completion_id,
                impact_analysis_id=impact_analysis_id,
                impact_digest=impact_report.canonical_digest,
                candidate_set_id=impact_record.candidate_set_id,
                candidate_set_digest=candidate_set.canonical_digest,
                completion_authorization_digest=authorization_digest,
                policy_id=policy.policy_id,
                policy_digest=policy.canonical_digest,
                evidence_snapshot_id=evidence.snapshot_id,
                evidence_snapshot_digest=evidence.canonical_digest,
                required_risk_dimensions=policy.required_risk_dimensions,
                maximum_candidate_count=policy.maximum_candidate_count,
                maximum_evidence_item_count=policy.maximum_evidence_item_count,
                maximum_gap_count=policy.maximum_gap_count,
                maximum_unknown_count=policy.maximum_unknown_count,
                maximum_duration_minutes=policy.maximum_duration_minutes,
                maximum_output_bytes=policy.maximum_output_bytes,
                required_report_schema=policy.required_report_schema,
                risk_floor_profile_digest=policy.risk_floor_profile_digest,
                safety_profile_digest=policy.safety_profile_digest,
                requested_at=now,
                expires_at=expires_at,
            )
            receipt, report = await self._assessor.complete(
                instruction,
                candidate_set,
                impact_report,
                evidence,
            )
            self._verify_receipt(
                receipt,
                report,
                instruction,
                policy,
                candidate_set,
                impact_report,
                evidence,
            )
            record = self._record(
                claim,
                impact_record,
                policy,
                evidence,
                receipt,
                report,
                authorization_digest,
                purpose,
            )
            await self._audit(
                actor,
                correlation_id,
                "protected_candidate_risk_recovery_completed",
                completion_id,
            )
            await self._repository.save(record)
        except ProtectedCandidateRiskRecoveryError:
            raise
        except ProtectedCandidateImpactError as error:
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_source_invalid"
            ) from error
        except Exception as error:
            raise ProtectedCandidateRiskRecoveryUncertainError(
                "protected_candidate_risk_recovery_persistence_uncertain"
            ) from error
        return ProtectedCandidateRiskRecoveryResult(
            record=record,
            manifest=self._manifest(record),
        )

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        completion_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedCandidateRiskRecoveryResult:
        self._require_human(actor)
        record = await self._repository.get(completion_id=completion_id)
        if record is None:
            raise ProtectedCandidateRiskRecoveryError("protected_candidate_risk_recovery_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.completion_policy_id)
        now = self._clock()
        if (
            policy is None
            or record.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.completion_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedCandidateRiskRecoveryError("protected_candidate_risk_recovery_not_found")
        self._require_assurance(actor, policy)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        try:
            (
                impact_record,
                candidate_set,
                impact_report,
            ) = await self._impact_source.rehydrate_for_risk_recovery(
                actor=actor,
                impact_analysis_id=record.impact_analysis_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
            self._verify_impact_source(
                impact_record,
                candidate_set,
                impact_report,
                record.impact_digest,
                record.purpose,
                policy,
                now,
            )
            evidence = await self._evidence_source.get_by_id(
                snapshot_id=record.evidence_snapshot_id
            )
            self._verify_evidence(evidence, impact_record, policy, now)
            assert evidence is not None
            authorization_digest = self._digest(
                [
                    impact_record.consumer_subject_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    impact_record.canonical_digest,
                    evidence.canonical_digest,
                ]
            )
            receipt, report = await self._assessor.rehydrate(
                record=record,
                completion_authorization_digest=authorization_digest,
                candidate_set=candidate_set,
                impact_report=impact_report,
                evidence_snapshot=evidence,
            )
            self._verify_receipt(
                receipt,
                report,
                self._instruction_from_record(record, policy, impact_report),
                policy,
                candidate_set,
                impact_report,
                evidence,
            )
            self._verify_record(record, receipt, report, impact_record, evidence)
        except ProtectedCandidateRiskRecoveryError:
            raise
        except Exception as error:
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_not_found"
            ) from error
        await self._audit(
            actor,
            correlation_id,
            "protected_candidate_risk_recovery_read",
            completion_id,
            permission_id=AI_PROTECTED_CANDIDATE_RISK_RECOVERY_READ,
        )
        reused = replace(record, reused=True)
        return ProtectedCandidateRiskRecoveryResult(
            record=reused,
            manifest=self._manifest(record),
        )

    async def rehydrate_for_adjudication(
        self,
        *,
        actor: AuthenticatedSubject,
        completion_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> tuple[
        ProtectedCandidateRiskRecoveryRecord,
        ProtectedRecommendationCandidateSet,
        ProtectedCandidateImpactReport,
        ProtectedCandidateRiskRecoveryReport,
        ProtectedOperationalEvidenceSnapshot,
    ]:
        await self.get(
            actor=actor,
            completion_id=completion_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        record = await self._repository.get(completion_id=completion_id)
        if record is None:
            raise ProtectedCandidateRiskRecoveryError("protected_candidate_risk_recovery_not_found")
        policy = await self._policy_source.get_by_id(policy_id=record.completion_policy_id)
        if policy is None:
            raise ProtectedCandidateRiskRecoveryError("protected_candidate_risk_recovery_not_found")
        (
            impact_record,
            candidate_set,
            impact_report,
        ) = await self._impact_source.rehydrate_for_risk_recovery(
            actor=actor,
            impact_analysis_id=record.impact_analysis_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )
        evidence = await self._evidence_source.get_by_id(snapshot_id=record.evidence_snapshot_id)
        self._verify_evidence(evidence, impact_record, policy, self._clock())
        assert evidence is not None
        authorization_digest = self._digest(
            [
                impact_record.consumer_subject_digest,
                actor.role_ids,
                policy.canonical_digest,
                impact_record.canonical_digest,
                evidence.canonical_digest,
            ]
        )
        receipt, report = await self._assessor.rehydrate(
            record=record,
            completion_authorization_digest=authorization_digest,
            candidate_set=candidate_set,
            impact_report=impact_report,
            evidence_snapshot=evidence,
        )
        self._verify_receipt(
            receipt,
            report,
            self._instruction_from_record(record, policy, impact_report),
            policy,
            candidate_set,
            impact_report,
            evidence,
        )
        self._verify_record(record, receipt, report, impact_record, evidence)
        await self._audit(
            actor,
            correlation_id,
            "protected_candidate_risk_recovery_rehydrated_for_adjudication",
            completion_id,
            permission_id=AI_PROTECTED_CANDIDATE_RISK_RECOVERY_READ,
        )
        return record, candidate_set, impact_report, report, evidence

    async def close(self) -> None:
        await self._repository.close()

    @classmethod
    def _verify_impact_source(
        cls,
        record: ProtectedCandidateImpactRecord,
        candidate_set: ProtectedRecommendationCandidateSet,
        report: ProtectedCandidateImpactReport,
        expected_digest: str,
        purpose: str,
        policy: ProtectedCandidateRiskRecoveryPolicySnapshot,
        now: datetime,
    ) -> None:
        if (
            record.canonical_digest != expected_digest
            or record.canonical_digest != cls._digest(cls._payload(record))
            or record.schema_version != policy.required_impact_schema
            or record.instance_state != policy.required_impact_state
            or record.purpose != purpose
            or now >= min(record.expires_at, report.expires_at, candidate_set.expires_at)
            or report.impact_analysis_id != record.impact_analysis_id
            or report.canonical_digest != record.protected_report_digest
            or report.candidate_set_digest != candidate_set.canonical_digest
            or not record.service_impact_analyzed
            or any(
                (
                    record.impact_complete,
                    record.outage_confirmed,
                    record.interruption_established,
                    record.duration_established,
                    record.risk_completed,
                    record.recovery_completed,
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
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_source_invalid"
            )

    @classmethod
    def _verify_evidence(
        cls,
        evidence: ProtectedOperationalEvidenceSnapshot | None,
        impact: ProtectedCandidateImpactRecord,
        policy: ProtectedCandidateRiskRecoveryPolicySnapshot,
        now: datetime,
    ) -> None:
        if (
            evidence is None
            or evidence.snapshot_id != policy.required_evidence_snapshot_id
            or evidence.schema_version != policy.required_evidence_schema
            or evidence.organization_id != impact.organization_id
            or evidence.environment_id != impact.environment_id
            or evidence.classification != impact.classification
            or evidence.canonical_digest != cls._digest(cls._payload(evidence))
            or not evidence.generated_at <= now < evidence.expires_at
            or not evidence.items
            or not evidence.gaps
            or not evidence.unknowns
            or len(evidence.items) > policy.maximum_evidence_item_count
        ):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_evidence_invalid"
            )

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ProtectedCandidateRiskRecoveryReceipt,
        report: ProtectedCandidateRiskRecoveryReport,
        instruction: ProtectedCandidateRiskRecoveryInstruction,
        policy: ProtectedCandidateRiskRecoveryPolicySnapshot,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        evidence: ProtectedOperationalEvidenceSnapshot,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.assessor_id != policy.required_assessor_id
            or receipt.attested_by != policy.required_assessor_attestor_id
            or receipt.completion_id != instruction.completion_id
            or receipt.impact_analysis_id != impact_report.impact_analysis_id
            or receipt.impact_digest != impact_report.canonical_digest
            or receipt.candidate_set_id != candidate_set.candidate_set_id
            or receipt.candidate_set_digest != candidate_set.canonical_digest
            or receipt.completion_authorization_digest
            != instruction.completion_authorization_digest
            or receipt.policy_digest != policy.canonical_digest
            or receipt.evidence_snapshot_id != evidence.snapshot_id
            or receipt.evidence_snapshot_digest != evidence.canonical_digest
            or report.schema_version != policy.required_report_schema
            or report.canonical_digest != cls._digest(cls._payload(report))
            or receipt.report_digest != report.canonical_digest
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or receipt.candidate_count != len(candidate_set.candidates) == len(report.entries)
            or receipt.evidence_item_count != len(evidence.items)
            or tuple(entry.candidate_id for entry in report.entries)
            != tuple(candidate.candidate_id for candidate in candidate_set.candidates)
            or any(
                entry.canonical_digest != cls._digest(cls._payload(entry))
                or not all(
                    (
                        entry.impact_complete,
                        entry.interruption_established,
                        entry.duration_established,
                        entry.risk_completed,
                        entry.recovery_completed,
                    )
                )
                or any((entry.preferred, entry.ready_for_review, entry.execution_authorized))
                for entry in report.entries
            )
            or not all(
                (
                    receipt.source_verified,
                    receipt.evidence_verified,
                    receipt.complete_candidate_coverage_verified,
                    receipt.conservative_risk_floor_verified,
                    receipt.ranges_bounded_verified,
                    receipt.recovery_coverage_verified,
                    receipt.no_preference_assigned,
                    receipt.no_model_used,
                    receipt.cleanup_verified,
                    receipt.signature_verified,
                )
            )
        ):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_receipt_invalid"
            )

    @classmethod
    def _record(
        cls,
        claim: ProtectedCandidateRiskRecoveryClaim,
        impact: ProtectedCandidateImpactRecord,
        policy: ProtectedCandidateRiskRecoveryPolicySnapshot,
        evidence: ProtectedOperationalEvidenceSnapshot,
        receipt: ProtectedCandidateRiskRecoveryReceipt,
        report: ProtectedCandidateRiskRecoveryReport,
        authorization_digest: str,
        purpose: str,
    ) -> ProtectedCandidateRiskRecoveryRecord:
        record = ProtectedCandidateRiskRecoveryRecord(
            completion_id=claim.completion_id,
            schema_version=RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            impact_analysis_id=impact.impact_analysis_id,
            impact_digest=impact.canonical_digest,
            candidate_set_id=impact.candidate_set_id,
            candidate_set_digest=impact.candidate_set_digest,
            presentation_id=impact.presentation_id,
            answer_digest=impact.answer_digest,
            adjudication_id=impact.adjudication_id,
            invocation_id=impact.invocation_id,
            context_id=impact.context_id,
            organization_id=impact.organization_id,
            environment_id=impact.environment_id,
            classification=impact.classification,
            consumer_subject_digest=impact.consumer_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            completion_policy_id=policy.policy_id,
            completion_policy_digest=policy.canonical_digest,
            completion_policy_version=policy.policy_version,
            assessor_id=receipt.assessor_id,
            completion_receipt_digest=receipt.canonical_digest,
            completion_authorization_digest=authorization_digest,
            protected_report_digest=report.canonical_digest,
            evidence_snapshot_id=evidence.snapshot_id,
            evidence_snapshot_digest=evidence.canonical_digest,
            evidence_snapshot_generated_at=evidence.generated_at,
            evidence_freshness=evidence.freshness,
            evidence_completeness=evidence.completeness,
            evidence_coverage_digest=evidence.coverage_digest,
            coverage_digest=receipt.coverage_digest,
            risk_digest=receipt.risk_digest,
            duration_digest=receipt.duration_digest,
            interruption_digest=receipt.interruption_digest,
            recovery_digest=receipt.recovery_digest,
            unknown_digest=receipt.unknown_digest,
            safety_digest=receipt.safety_digest,
            cleanup_digest=receipt.cleanup_digest,
            candidate_count=receipt.candidate_count,
            evidence_item_count=receipt.evidence_item_count,
            low_risk_count=receipt.low_risk_count,
            moderate_risk_count=receipt.moderate_risk_count,
            high_risk_count=receipt.high_risk_count,
            critical_risk_count=receipt.critical_risk_count,
            unknown_risk_count=receipt.unknown_risk_count,
            maximum_risk=receipt.maximum_risk,
            interruption_possible_count=receipt.interruption_possible_count,
            recovery_feasible_count=receipt.recovery_feasible_count,
            recovery_unknown_count=receipt.recovery_unknown_count,
            recovery_blocked_count=receipt.recovery_blocked_count,
            work_minimum_minutes=receipt.work_minimum_minutes,
            work_maximum_minutes=receipt.work_maximum_minutes,
            interruption_minimum_minutes=receipt.interruption_minimum_minutes,
            interruption_maximum_minutes=receipt.interruption_maximum_minutes,
            recovery_minimum_minutes=receipt.recovery_minimum_minutes,
            recovery_maximum_minutes=receipt.recovery_maximum_minutes,
            gap_count=receipt.gap_count,
            unknown_count=receipt.unknown_count,
            byte_count=receipt.byte_count,
            completed_at=report.completed_at,
            expires_at=report.expires_at,
            instance_state="protected_candidate_risk_recovery_completed",
            purpose=purpose,
            safety_notice=SAFETY_NOTICE,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._payload(record)))

    @classmethod
    def _verify_record(
        cls,
        record: ProtectedCandidateRiskRecoveryRecord,
        receipt: ProtectedCandidateRiskRecoveryReceipt,
        report: ProtectedCandidateRiskRecoveryReport,
        impact: ProtectedCandidateImpactRecord,
        evidence: ProtectedOperationalEvidenceSnapshot,
    ) -> None:
        if (
            record.impact_digest != impact.canonical_digest
            or record.candidate_set_digest != impact.candidate_set_digest
            or record.evidence_snapshot_digest != evidence.canonical_digest
            or record.evidence_coverage_digest != evidence.coverage_digest
            or record.completion_receipt_digest != receipt.canonical_digest
            or record.protected_report_digest != report.canonical_digest
            or record.coverage_digest != receipt.coverage_digest
            or record.risk_digest != report.risk_digest
            or record.duration_digest != report.duration_digest
            or record.interruption_digest != report.interruption_digest
            or record.recovery_digest != report.recovery_digest
            or record.unknown_digest != report.unknown_digest
            or record.safety_digest != report.safety_digest
        ):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_integrity_failed"
            )

    @staticmethod
    def _instruction_from_record(
        record: ProtectedCandidateRiskRecoveryRecord,
        policy: ProtectedCandidateRiskRecoveryPolicySnapshot,
        impact_report: ProtectedCandidateImpactReport,
    ) -> ProtectedCandidateRiskRecoveryInstruction:
        return ProtectedCandidateRiskRecoveryInstruction(
            completion_id=record.completion_id,
            impact_analysis_id=record.impact_analysis_id,
            impact_digest=impact_report.canonical_digest,
            candidate_set_id=record.candidate_set_id,
            candidate_set_digest=record.candidate_set_digest,
            completion_authorization_digest=record.completion_authorization_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            evidence_snapshot_id=record.evidence_snapshot_id,
            evidence_snapshot_digest=record.evidence_snapshot_digest,
            required_risk_dimensions=policy.required_risk_dimensions,
            maximum_candidate_count=policy.maximum_candidate_count,
            maximum_evidence_item_count=policy.maximum_evidence_item_count,
            maximum_gap_count=policy.maximum_gap_count,
            maximum_unknown_count=policy.maximum_unknown_count,
            maximum_duration_minutes=policy.maximum_duration_minutes,
            maximum_output_bytes=policy.maximum_output_bytes,
            required_report_schema=policy.required_report_schema,
            risk_floor_profile_digest=policy.risk_floor_profile_digest,
            safety_profile_digest=policy.safety_profile_digest,
            requested_at=record.completed_at,
            expires_at=record.expires_at,
        )

    async def _reuse(
        self,
        claim: ProtectedCandidateRiskRecoveryClaim,
        browser_digest: str,
        request_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedCandidateRiskRecoveryResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_idempotency_conflict"
            )
        return await self.get(
            actor=actor,
            completion_id=claim.completion_id,
            browser_session_id=browser_session_id,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_human_required"
            )

    @staticmethod
    def _require_assurance(
        actor: AuthenticatedSubject,
        policy: ProtectedCandidateRiskRecoveryPolicySnapshot,
    ) -> None:
        if not assurance_satisfies_policy(actor.assurance_level, policy.required_assurance_level):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_assurance_required"
            )

    def _require_scope(
        self,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise ProtectedCandidateRiskRecoveryError("protected_candidate_risk_recovery_not_found")

    @staticmethod
    def _manifest(
        record: ProtectedCandidateRiskRecoveryRecord,
    ) -> ProtectedCandidateRiskRecoveryManifest:
        fields = {
            name: getattr(record, name)
            for name in ProtectedCandidateRiskRecoveryManifest.__dataclass_fields__
        }
        return ProtectedCandidateRiskRecoveryManifest(**fields)

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        *,
        permission_id: str = AI_PROTECTED_CANDIDATE_RISK_RECOVERY_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.protected-candidate-risk-recovery-completion",
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
                resource_type="resource.ai.protected-candidate-risk-recovery-completion",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    _digest = staticmethod(GovernedProtectedModelInvocationService._digest)
    _payload = staticmethod(GovernedProtectedModelInvocationService._payload)


def build_development_protected_candidate_risk_recovery_policy(
    *,
    organization_id: str,
    environment_id: str,
    issued_at: datetime,
    expires_at: datetime,
) -> ProtectedCandidateRiskRecoveryPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = ProtectedCandidateRiskRecoveryPolicySnapshot(
        policy_id="protected-candidate-risk-recovery-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.protected-candidate-risk-recovery-development-v1",
        required_impact_schema="atlas.protected-candidate-impact-analysis.v1",
        required_impact_state="protected_candidate_service_impact_analyzed",
        required_evidence_schema="atlas.protected-operational-evidence-snapshot.v1",
        required_evidence_snapshot_id="snapshot.operational-evidence.lab.001",
        required_report_schema="atlas.protected-candidate-risk-recovery-report.v1",
        required_receipt_schema="atlas.protected-candidate-risk-recovery-receipt.v1",
        required_assessor_id="protected-candidate-risk-recovery-assessor.synthetic",
        required_assessor_attestor_id=(
            "subject.protected-candidate-risk-recovery-assessor-attestor"
        ),
        required_risk_dimensions=(
            "availability",
            "data",
            "security",
            "performance",
            "operational-complexity",
            "reversibility",
            "evidence-uncertainty",
        ),
        maximum_candidate_count=3,
        maximum_evidence_item_count=20,
        maximum_gap_count=100,
        maximum_unknown_count=100,
        maximum_duration_minutes=480,
        maximum_output_bytes=524_288,
        retention_minutes=10,
        required_assurance_level=AssuranceLevel.SINGLE_FACTOR,
        classification_ceiling="classification.internal",
        browser_binding_key_digest=digest(["protected-candidate-risk-recovery-browser-key"]),
        risk_floor_profile_digest=digest(["conservative-risk-floor-v1"]),
        safety_profile_digest=digest(["bounded-estimates-no-preference-no-authority-v1"]),
        signed_by="subject.protected-candidate-risk-recovery-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy,
        canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy)),
    )
