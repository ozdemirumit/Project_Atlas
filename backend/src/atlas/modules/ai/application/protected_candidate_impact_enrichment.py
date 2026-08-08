from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.ai.application.protected_candidate_impact_enrichment_ports import (
    ProtectedCandidateImpactError,
    ProtectedCandidateImpactPermissionAuthorizer,
    ProtectedCandidateImpactPolicySource,
    ProtectedCandidateImpactRepository,
    ProtectedCandidateImpactUncertainError,
    TrustedProtectedCandidateImpactAnalyzer,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation import (
    GovernedProtectedRecommendationCandidateService,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation_ports import (
    ProtectedRecommendationCandidateError,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactClaim,
    ProtectedCandidateImpactInstruction,
    ProtectedCandidateImpactManifest,
    ProtectedCandidateImpactPolicySnapshot,
    ProtectedCandidateImpactReceipt,
    ProtectedCandidateImpactRecord,
    ProtectedCandidateImpactReport,
    ProtectedCandidateImpactResult,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateRecord,
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.authorization.application.bootstrap import (
    AI_PROTECTED_CANDIDATE_IMPACT_CREATE,
    AI_PROTECTED_CANDIDATE_IMPACT_READ,
)
from atlas.modules.graph.application.engine import (
    GraphAccessContext,
    GraphImpactError,
    InMemoryGraphImpactAnalyzer,
)
from atlas.modules.graph.domain.models import StorageImpactResult
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

POLICY_SCHEMA = "atlas.protected-candidate-impact-policy.v1"
CLAIM_SCHEMA = "atlas.protected-candidate-impact-claim.v1"
RECORD_SCHEMA = "atlas.protected-candidate-impact-analysis.v1"
SAFETY_NOTICE = (
    "Dependencies show modeled reachability only; no outage, interruption, duration, risk, "
    "recovery, recommendation, or operational authority is established."
)


class GovernedProtectedCandidateImpactService:
    def __init__(
        self,
        *,
        repository: ProtectedCandidateImpactRepository,
        candidate_source: GovernedProtectedRecommendationCandidateService,
        policy_source: ProtectedCandidateImpactPolicySource,
        permission_authorizer: ProtectedCandidateImpactPermissionAuthorizer,
        graph_analyzer: InMemoryGraphImpactAnalyzer,
        analyzer: TrustedProtectedCandidateImpactAnalyzer,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str = "site.local",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._candidate_source = candidate_source
        self._policy_source = policy_source
        self._permission_authorizer = permission_authorizer
        self._graph_analyzer = graph_analyzer
        self._analyzer = analyzer
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        candidate_set_id: str,
        candidate_set_digest: str,
        impact_policy_id: str,
        impact_policy_digest: str,
        purpose: str,
        reachability_not_outage_acknowledged: bool,
        impact_provisional_acknowledged: bool,
        no_recommendation_or_operational_authority_acknowledged: bool,
        browser_session_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProtectedCandidateImpactResult:
        self._require_human(actor)
        if not all(
            (
                reachability_not_outage_acknowledged,
                impact_provisional_acknowledged,
                no_recommendation_or_operational_authority_acknowledged,
            )
        ):
            raise ProtectedCandidateImpactError(
                "protected_candidate_impact_acknowledgement_required"
            )
        now = self._clock()
        policy = await self._policy_source.get_by_id(policy_id=impact_policy_id)
        if (
            policy is None
            or policy.policy_id != impact_policy_id
            or policy.canonical_digest != impact_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or policy.schema_version != POLICY_SCHEMA
            or policy.organization_id != actor.organization_id
            or policy.environment_id != self._environment_id
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_policy_invalid")
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
                candidate_set_id,
                candidate_set_digest,
                policy.canonical_digest,
                purpose,
                reachability_not_outage_acknowledged,
                impact_provisional_acknowledged,
                no_recommendation_or_operational_authority_acknowledged,
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
            "protected_candidate_impact_intent_recorded",
            candidate_set_id,
        )
        impact_analysis_id = f"protected-candidate-impact.{uuid4().hex}"
        claim = ProtectedCandidateImpactClaim(
            claim_id=f"claim.protected-candidate-impact.{uuid4().hex}",
            schema_version=CLAIM_SCHEMA,
            version=1,
            impact_analysis_id=impact_analysis_id,
            candidate_set_id=candidate_set_id,
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
                raise ProtectedCandidateImpactError("protected_candidate_impact_already_claimed")
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
            "protected_candidate_impact_claimed",
            impact_analysis_id,
        )
        try:
            source_record, candidate_set = await self._candidate_source.rehydrate_for_impact(
                actor=actor,
                candidate_set_id=candidate_set_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
            self._verify_candidate_source(
                source_record,
                candidate_set,
                candidate_set_digest,
                purpose,
                policy,
                now,
            )
            graph_result = self._analyze_graph(actor, source_record, policy)
            graph_digest = self._digest(self._payload(graph_result))
            self._verify_graph(graph_result, graph_digest, policy)
            impact_authorization_digest = self._digest(
                [
                    source_record.consumer_subject_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    graph_digest,
                ]
            )
            expires_at = min(
                source_record.expires_at,
                policy.expires_at,
                now + timedelta(minutes=policy.retention_minutes),
            )
            instruction = ProtectedCandidateImpactInstruction(
                impact_analysis_id=impact_analysis_id,
                candidate_set_id=candidate_set_id,
                candidate_set_digest=candidate_set.canonical_digest,
                candidate_source_binding_digest=candidate_set.source_binding_digest,
                impact_authorization_digest=impact_authorization_digest,
                policy_id=policy.policy_id,
                policy_digest=policy.canonical_digest,
                graph_snapshot_id=graph_result.snapshot_id,
                graph_snapshot_digest=graph_digest,
                start_entity_id=policy.start_entity_id,
                maximum_depth=policy.maximum_depth,
                maximum_candidate_count=policy.maximum_candidate_count,
                maximum_path_count=policy.maximum_path_count,
                maximum_entity_count=policy.maximum_entity_count,
                maximum_service_count=policy.maximum_service_count,
                maximum_gap_count=policy.maximum_gap_count,
                maximum_unknown_count=policy.maximum_unknown_count,
                maximum_output_bytes=policy.maximum_output_bytes,
                required_report_schema=policy.required_report_schema,
                safety_profile_digest=policy.safety_profile_digest,
                requested_at=now,
                expires_at=expires_at,
            )
            receipt, report = await self._analyzer.analyze(instruction, candidate_set, graph_result)
            self._verify_receipt(receipt, report, instruction, policy, candidate_set)
            record = self._record(
                claim,
                source_record,
                policy,
                receipt,
                report,
                impact_authorization_digest,
                purpose,
            )
            await self._audit(
                actor,
                correlation_id,
                "protected_candidate_impact_analyzed",
                impact_analysis_id,
            )
            await self._repository.save(record)
        except ProtectedCandidateImpactError:
            raise
        except ProtectedRecommendationCandidateError as error:
            raise ProtectedCandidateImpactError(
                "protected_candidate_impact_source_invalid"
            ) from error
        except GraphImpactError as error:
            raise ProtectedCandidateImpactError(
                "protected_candidate_impact_graph_unavailable"
            ) from error
        except Exception as error:
            raise ProtectedCandidateImpactUncertainError(
                "protected_candidate_impact_persistence_uncertain"
            ) from error
        return ProtectedCandidateImpactResult(record=record, manifest=self._manifest(record))

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        impact_analysis_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedCandidateImpactResult:
        self._require_human(actor)
        record = await self._repository.get(impact_analysis_id=impact_analysis_id)
        if record is None:
            raise ProtectedCandidateImpactError("protected_candidate_impact_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.impact_policy_id)
        now = self._clock()
        if (
            policy is None
            or record.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.impact_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        try:
            source_record, candidate_set = await self._candidate_source.rehydrate_for_impact(
                actor=actor,
                candidate_set_id=record.candidate_set_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
            self._verify_candidate_source(
                source_record,
                candidate_set,
                record.candidate_set_digest,
                record.purpose,
                policy,
                now,
            )
            graph_result = self._analyze_graph(actor, source_record, policy)
            self._verify_graph(graph_result, record.graph_snapshot_digest, policy)
            impact_authorization_digest = self._digest(
                [
                    source_record.consumer_subject_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    record.graph_snapshot_digest,
                ]
            )
            receipt, report = await self._analyzer.rehydrate(
                record=record,
                impact_authorization_digest=impact_authorization_digest,
                candidate_set=candidate_set,
                graph_result=graph_result,
            )
            instruction = self._instruction_from_record(record, policy)
            self._verify_receipt(receipt, report, instruction, policy, candidate_set)
            self._verify_record(record, receipt, report, source_record)
        except ProtectedCandidateImpactError:
            raise
        except ProtectedRecommendationCandidateError as error:
            raise ProtectedCandidateImpactError("protected_candidate_impact_not_found") from error
        except Exception as error:
            raise ProtectedCandidateImpactError("protected_candidate_impact_not_found") from error
        await self._audit(
            actor,
            correlation_id,
            "protected_candidate_impact_read",
            impact_analysis_id,
            permission_id=AI_PROTECTED_CANDIDATE_IMPACT_READ,
        )
        reused = replace(record, reused=True)
        return ProtectedCandidateImpactResult(record=reused, manifest=self._manifest(record))

    async def rehydrate_for_risk_recovery(
        self,
        *,
        actor: AuthenticatedSubject,
        impact_analysis_id: str,
        browser_session_id: str,
        correlation_id: str,
    ) -> tuple[
        ProtectedCandidateImpactRecord,
        ProtectedRecommendationCandidateSet,
        ProtectedCandidateImpactReport,
    ]:
        self._require_human(actor)
        record = await self._repository.get(impact_analysis_id=impact_analysis_id)
        if record is None:
            raise ProtectedCandidateImpactError("protected_candidate_impact_not_found")
        self._require_scope(actor, record.organization_id, record.environment_id)
        policy = await self._policy_source.get_by_id(policy_id=record.impact_policy_id)
        now = self._clock()
        if (
            policy is None
            or record.browser_session_binding_digest
            != self._digest([policy.browser_binding_key_digest, browser_session_id])
            or record.canonical_digest != self._digest(self._payload(record))
            or now >= record.expires_at
            or policy.canonical_digest != record.impact_policy_digest
            or policy.canonical_digest != self._digest(self._payload(policy))
            or not policy.issued_at <= now < policy.expires_at
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_not_found")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            correlation_id=correlation_id,
        )
        try:
            source_record, candidate_set = await self._candidate_source.rehydrate_for_impact(
                actor=actor,
                candidate_set_id=record.candidate_set_id,
                browser_session_id=browser_session_id,
                correlation_id=correlation_id,
            )
            self._verify_candidate_source(
                source_record,
                candidate_set,
                record.candidate_set_digest,
                record.purpose,
                policy,
                now,
            )
            graph_result = self._analyze_graph(actor, source_record, policy)
            self._verify_graph(graph_result, record.graph_snapshot_digest, policy)
            authorization_digest = self._digest(
                [
                    source_record.consumer_subject_digest,
                    actor.role_ids,
                    policy.canonical_digest,
                    record.graph_snapshot_digest,
                ]
            )
            receipt, report = await self._analyzer.rehydrate(
                record=record,
                impact_authorization_digest=authorization_digest,
                candidate_set=candidate_set,
                graph_result=graph_result,
            )
            self._verify_receipt(
                receipt,
                report,
                self._instruction_from_record(record, policy),
                policy,
                candidate_set,
            )
            self._verify_record(record, receipt, report, source_record)
        except ProtectedCandidateImpactError:
            raise
        except Exception as error:
            raise ProtectedCandidateImpactError("protected_candidate_impact_not_found") from error
        await self._audit(
            actor,
            correlation_id,
            "protected_candidate_impact_rehydrated_for_risk_recovery",
            impact_analysis_id,
            permission_id=AI_PROTECTED_CANDIDATE_IMPACT_READ,
        )
        return record, candidate_set, report

    async def close(self) -> None:
        await self._repository.close()

    def _analyze_graph(
        self,
        actor: AuthenticatedSubject,
        source: ProtectedRecommendationCandidateRecord,
        policy: ProtectedCandidateImpactPolicySnapshot,
    ) -> StorageImpactResult:
        return self._graph_analyzer.analyze(
            start_entity_id=policy.start_entity_id,
            max_depth=policy.maximum_depth,
            access=GraphAccessContext(
                organization_id=source.organization_id,
                environment_id=source.environment_id,
                site_id=self._site_id,
                principals=frozenset((actor.subject_id, *actor.role_ids, *actor.group_ids)),
                classification_ceiling=DataClassification(
                    policy.classification_ceiling.removeprefix("classification.")
                ),
            ),
        )

    @classmethod
    def _verify_candidate_source(
        cls,
        record: ProtectedRecommendationCandidateRecord,
        candidate_set: ProtectedRecommendationCandidateSet,
        expected_digest: str,
        purpose: str,
        policy: ProtectedCandidateImpactPolicySnapshot,
        now: datetime,
    ) -> None:
        if (
            record.candidate_set_id != candidate_set.candidate_set_id
            or record.candidate_content_digest != candidate_set.canonical_digest
            or candidate_set.canonical_digest != expected_digest
            or candidate_set.canonical_digest != cls._digest(cls._payload(candidate_set))
            or candidate_set.schema_version != policy.required_candidate_set_schema
            or record.instance_state != policy.required_candidate_state
            or record.purpose != purpose
            or now >= min(record.expires_at, candidate_set.expires_at)
            or not record.recommendation_candidates_generated
            or record.service_impact_analyzed
            or record.recommendation_complete
            or record.recommendation_presented
            or record.recommendation_ready_for_review
            or record.recommendation_approved
            or record.workflow_created
            or record.execution_authorized
            or record.deployment_authorized
            or record.infrastructure_mutated
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_source_invalid")

    @classmethod
    def _verify_graph(
        cls,
        result: StorageImpactResult,
        expected_digest: str,
        policy: ProtectedCandidateImpactPolicySnapshot,
    ) -> None:
        if (
            result.snapshot_id != policy.required_graph_snapshot_id
            or result.start_entity_id != policy.start_entity_id
            or result.max_depth != policy.maximum_depth
            or cls._digest(cls._payload(result)) != expected_digest
            or result.outage_confirmed
            or result.data_profile != "synthetic_lab"
            or not result.paths
            or not result.known_gaps
            or not result.unknowns
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_graph_invalid")

    @classmethod
    def _verify_receipt(
        cls,
        receipt: ProtectedCandidateImpactReceipt,
        report: ProtectedCandidateImpactReport,
        instruction: ProtectedCandidateImpactInstruction,
        policy: ProtectedCandidateImpactPolicySnapshot,
        candidate_set: ProtectedRecommendationCandidateSet,
    ) -> None:
        if (
            receipt.schema_version != policy.required_receipt_schema
            or receipt.analyzer_id != policy.required_analyzer_id
            or receipt.attested_by != policy.required_analyzer_attestor_id
            or receipt.impact_analysis_id != instruction.impact_analysis_id
            or receipt.candidate_set_id != candidate_set.candidate_set_id
            or receipt.candidate_set_digest != candidate_set.canonical_digest
            or receipt.impact_authorization_digest != instruction.impact_authorization_digest
            or receipt.policy_digest != policy.canonical_digest
            or receipt.graph_snapshot_id != instruction.graph_snapshot_id
            or receipt.graph_snapshot_digest != instruction.graph_snapshot_digest
            or report.schema_version != policy.required_report_schema
            or report.canonical_digest != cls._digest(cls._payload(report))
            or receipt.report_digest != report.canonical_digest
            or receipt.canonical_digest != cls._digest(cls._payload(receipt))
            or receipt.candidate_count != len(candidate_set.candidates) == len(report.entries)
            or tuple(entry.candidate_id for entry in report.entries)
            != tuple(candidate.candidate_id for candidate in candidate_set.candidates)
            or any(
                entry.canonical_digest != cls._digest(cls._payload(entry))
                or entry.outage_confirmed
                or entry.interruption_established
                or entry.duration_established
                or entry.risk_completed
                or entry.recovery_completed
                for entry in report.entries
            )
            or not all(
                (
                    receipt.candidate_source_verified,
                    receipt.graph_snapshot_verified,
                    receipt.bounded_traversal_verified,
                    receipt.complete_candidate_coverage_verified,
                    receipt.unknowns_preserved,
                    receipt.no_outage_claim_verified,
                    receipt.no_preference_assigned,
                    receipt.no_model_used,
                    receipt.cleanup_verified,
                    receipt.signature_verified,
                )
            )
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_receipt_invalid")

    @classmethod
    def _record(
        cls,
        claim: ProtectedCandidateImpactClaim,
        source: ProtectedRecommendationCandidateRecord,
        policy: ProtectedCandidateImpactPolicySnapshot,
        receipt: ProtectedCandidateImpactReceipt,
        report: ProtectedCandidateImpactReport,
        impact_authorization_digest: str,
        purpose: str,
    ) -> ProtectedCandidateImpactRecord:
        record = ProtectedCandidateImpactRecord(
            impact_analysis_id=claim.impact_analysis_id,
            schema_version=RECORD_SCHEMA,
            version=1,
            claim_id=claim.claim_id,
            candidate_set_id=source.candidate_set_id,
            candidate_set_digest=source.candidate_content_digest,
            candidate_source_binding_digest=source.source_binding_digest,
            presentation_id=source.presentation_id,
            answer_digest=source.answer_digest,
            adjudication_id=source.adjudication_id,
            invocation_id=source.invocation_id,
            context_id=source.context_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
            classification=source.classification,
            consumer_subject_digest=source.consumer_subject_digest,
            browser_session_binding_digest=claim.browser_session_binding_digest,
            impact_policy_id=policy.policy_id,
            impact_policy_digest=policy.canonical_digest,
            impact_policy_version=policy.policy_version,
            analyzer_id=receipt.analyzer_id,
            analysis_receipt_digest=receipt.canonical_digest,
            impact_authorization_digest=impact_authorization_digest,
            protected_report_digest=report.canonical_digest,
            graph_snapshot_id=report.graph_snapshot_id,
            graph_snapshot_digest=report.graph_snapshot_digest,
            graph_snapshot_generated_at=report.graph_snapshot_generated_at,
            graph_freshness=report.graph_freshness,
            graph_completeness=report.graph_completeness,
            graph_maturity=report.graph_maturity,
            coverage_digest=receipt.coverage_digest,
            graph_gap_digest=report.graph_gap_digest,
            unknown_digest=report.unknown_digest,
            safety_digest=report.safety_digest,
            cleanup_digest=receipt.cleanup_digest,
            candidate_count=receipt.candidate_count,
            path_count=receipt.path_count,
            modeled_entity_count=receipt.modeled_entity_count,
            technical_service_count=receipt.technical_service_count,
            business_service_count=receipt.business_service_count,
            gap_count=receipt.gap_count,
            unknown_count=receipt.unknown_count,
            byte_count=receipt.byte_count,
            analyzed_at=report.analyzed_at,
            expires_at=report.expires_at,
            instance_state="protected_candidate_service_impact_analyzed",
            purpose=purpose,
            safety_notice=SAFETY_NOTICE,
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=cls._digest(cls._payload(record)))

    @classmethod
    def _verify_record(
        cls,
        record: ProtectedCandidateImpactRecord,
        receipt: ProtectedCandidateImpactReceipt,
        report: ProtectedCandidateImpactReport,
        source: ProtectedRecommendationCandidateRecord,
    ) -> None:
        if (
            record.candidate_set_digest != source.candidate_content_digest
            or record.candidate_source_binding_digest != source.source_binding_digest
            or record.analysis_receipt_digest != receipt.canonical_digest
            or record.protected_report_digest != report.canonical_digest
            or record.graph_snapshot_digest != report.graph_snapshot_digest
            or record.coverage_digest != receipt.coverage_digest
            or record.graph_gap_digest != report.graph_gap_digest
            or record.unknown_digest != report.unknown_digest
            or record.safety_digest != report.safety_digest
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_integrity_failed")

    @staticmethod
    def _instruction_from_record(
        record: ProtectedCandidateImpactRecord,
        policy: ProtectedCandidateImpactPolicySnapshot,
    ) -> ProtectedCandidateImpactInstruction:
        return ProtectedCandidateImpactInstruction(
            impact_analysis_id=record.impact_analysis_id,
            candidate_set_id=record.candidate_set_id,
            candidate_set_digest=record.candidate_set_digest,
            candidate_source_binding_digest=record.candidate_source_binding_digest,
            impact_authorization_digest=record.impact_authorization_digest,
            policy_id=policy.policy_id,
            policy_digest=policy.canonical_digest,
            graph_snapshot_id=record.graph_snapshot_id,
            graph_snapshot_digest=record.graph_snapshot_digest,
            start_entity_id=policy.start_entity_id,
            maximum_depth=policy.maximum_depth,
            maximum_candidate_count=policy.maximum_candidate_count,
            maximum_path_count=policy.maximum_path_count,
            maximum_entity_count=policy.maximum_entity_count,
            maximum_service_count=policy.maximum_service_count,
            maximum_gap_count=policy.maximum_gap_count,
            maximum_unknown_count=policy.maximum_unknown_count,
            maximum_output_bytes=policy.maximum_output_bytes,
            required_report_schema=policy.required_report_schema,
            safety_profile_digest=policy.safety_profile_digest,
            requested_at=record.analyzed_at,
            expires_at=record.expires_at,
        )

    async def _reuse(
        self,
        claim: ProtectedCandidateImpactClaim,
        browser_digest: str,
        request_digest: str,
        actor: AuthenticatedSubject,
        browser_session_id: str,
        correlation_id: str,
    ) -> ProtectedCandidateImpactResult:
        if (
            claim.browser_session_binding_digest != browser_digest
            or claim.request_binding_digest != request_digest
        ):
            raise ProtectedCandidateImpactError("protected_candidate_impact_idempotency_conflict")
        return await self.get(
            actor=actor,
            impact_analysis_id=claim.impact_analysis_id,
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
            raise ProtectedCandidateImpactError(
                "protected_candidate_impact_enterprise_human_hardware_mfa_required"
            )

    def _require_scope(
        self, actor: AuthenticatedSubject, organization_id: str, environment_id: str
    ) -> None:
        if actor.organization_id != organization_id or environment_id != self._environment_id:
            raise ProtectedCandidateImpactError("protected_candidate_impact_not_found")

    @staticmethod
    def _manifest(record: ProtectedCandidateImpactRecord) -> ProtectedCandidateImpactManifest:
        return ProtectedCandidateImpactManifest(
            impact_analysis_id=record.impact_analysis_id,
            candidate_set_id=record.candidate_set_id,
            presentation_id=record.presentation_id,
            graph_snapshot_id=record.graph_snapshot_id,
            graph_snapshot_digest=record.graph_snapshot_digest,
            graph_snapshot_generated_at=record.graph_snapshot_generated_at,
            graph_freshness=record.graph_freshness,
            graph_completeness=record.graph_completeness,
            graph_maturity=record.graph_maturity,
            candidate_count=record.candidate_count,
            path_count=record.path_count,
            modeled_entity_count=record.modeled_entity_count,
            technical_service_count=record.technical_service_count,
            business_service_count=record.business_service_count,
            gap_count=record.gap_count,
            unknown_count=record.unknown_count,
            coverage_digest=record.coverage_digest,
            graph_gap_digest=record.graph_gap_digest,
            unknown_digest=record.unknown_digest,
            safety_digest=record.safety_digest,
            analyzed_at=record.analyzed_at,
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
        permission_id: str = AI_PROTECTED_CANDIDATE_IMPACT_CREATE,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.protected-candidate-impact-enrichment",
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
                resource_type="resource.ai.protected-candidate-impact-analysis",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    _digest = staticmethod(GovernedProtectedModelInvocationService._digest)
    _payload = staticmethod(GovernedProtectedModelInvocationService._payload)


def build_development_protected_candidate_impact_policy(
    *, organization_id: str, environment_id: str, issued_at: datetime, expires_at: datetime
) -> ProtectedCandidateImpactPolicySnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    policy = ProtectedCandidateImpactPolicySnapshot(
        policy_id="protected-candidate-impact-policy.development",
        schema_version=POLICY_SCHEMA,
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        policy_version="policy-version.protected-candidate-impact-development-v1",
        required_candidate_set_schema="atlas.protected-recommendation-candidate-content.v1",
        required_candidate_state="protected_recommendation_candidates_generated",
        required_graph_schema="1.0",
        required_graph_snapshot_id="snapshot.graph.lab.001",
        required_report_schema="atlas.protected-candidate-impact-report.v1",
        required_receipt_schema="atlas.protected-candidate-impact-receipt.v1",
        required_analyzer_id="protected-candidate-impact-analyzer.synthetic",
        required_analyzer_attestor_id="subject.protected-candidate-impact-analyzer-attestor",
        start_entity_id="asset.storage.lab.b28",
        maximum_depth=5,
        maximum_candidate_count=3,
        maximum_path_count=20,
        maximum_entity_count=50,
        maximum_service_count=20,
        maximum_gap_count=20,
        maximum_unknown_count=20,
        maximum_output_bytes=262_144,
        retention_minutes=10,
        classification_ceiling="classification.internal",
        browser_binding_key_digest=digest(["protected-candidate-impact-browser-key"]),
        safety_profile_digest=digest(["reachability-not-outage-no-authority-v1"]),
        signed_by="subject.protected-candidate-impact-policy-signer",
        signature_verified=True,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(
        policy, canonical_digest=digest(GovernedProtectedModelInvocationService._payload(policy))
    )
