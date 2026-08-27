from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from atlas.modules.rca.domain.models import RcaCase
from atlas.modules.recommendations.domain.models import (
    Applicability,
    ComparisonDimension,
    DurationEstimate,
    GovernanceRequirements,
    HumanReview,
    ImpactSummary,
    InterruptionEstimate,
    OptionState,
    PlanStep,
    PreferenceState,
    RecommendationArtifact,
    RecommendationCategory,
    RecommendationOption,
    RecommendationRequest,
    RecommendationState,
    RecoveryPlan,
    ReviewStatus,
    RiskDimension,
    RiskLevel,
)

SAFETY_NOTICE = (
    "Decision support only. Recommendation review or approval does not authorize Atlas to "
    "execute an infrastructure change."
)
_DATA_PROFILE = "configured_hitachi_read_only"


class ConfiguredHitachiRecommendationAssembler:
    """Builds the same five decision-support option categories as the synthetic assembler
    (investigate, escalate, defer, restoration planning, remediation planning) from a real
    `RcaCase` produced by `ConfiguredHitachiRcaAssembler`.

    Needs no connector access itself -- the source case is already real by the time it reaches
    here. What changes versus the synthetic version: evidence references are limited to what the
    real RCA case actually has (a hardware-health read and an inventory read; no peer-array
    signal, graph-path corroboration, or vendor guidance exist for a real case, so those slots are
    dropped rather than faked), and `Applicability.products` is left empty rather than guessing a
    vendor/model string from prose, since `RcaCase` carries no structured model field. See
    ATLAS-IMP-259.
    """

    def build(
        self,
        request: RecommendationRequest,
        source_case: RcaCase,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> RecommendationArtifact:
        if not source_case.hypotheses:
            raise ValueError("the source RCA case has no active finding to recommend against")
        evidence_by_type = {item.source_type: item.evidence_id for item in source_case.evidence}
        health = evidence_by_type.get("storage_hardware_health")
        inventory = evidence_by_type.get("storage_inventory")
        if health is None:
            raise ValueError("source RCA evidence is incomplete")

        affected = source_case.impact_scope.affected_entities
        possible_services = source_case.impact_scope.possibly_affected_services
        unaffected = source_case.impact_scope.explicitly_unaffected_entities
        applicability = Applicability(
            products=(),
            versions=(),
            environments=(environment_id,),
            targets=(request.target_id,),
            services=possible_services,
            valid_from=created_at,
            valid_until=created_at + timedelta(hours=4),
            limitations=(
                "No structured product or model identifier is carried on the source RCA case.",
                "Revalidate after target, health, policy, or RCA context changes.",
            ),
        )
        impact = ImpactSummary(
            affected_components=affected,
            possibly_affected_services=possible_services,
            explicitly_unaffected_entities=unaffected,
            blast_radius="Bounded to the exact storage target; downstream impact remains possible.",
            redundancy_effect="Reduced redundancy is plausible but not confirmed.",
            data_protection_effect=(
                "No data loss, corruption, or recoverability effect is confirmed."
            ),
            impact_confirmed=False,
            graph_maturity="D0-D1 dependency analysis; not a production digital twin.",
            gaps=source_case.impact_scope.limitations,
        )
        no_interruption = InterruptionEstimate(
            expected_mode="none expected from read-only evidence collection",
            worst_credible_mode="unknown if external systems are already degraded",
            expected_minutes=(0, 0),
            worst_credible_minutes=(0, 0),
            assumptions=("Allowlisted C1 connectors remain read-only and bounded.",),
            unknowns=("Current service state is not independently observed.",),
        )
        blocked_interruption = InterruptionEstimate(
            expected_mode="not estimated because the option is blocked",
            worst_credible_mode="partial or full service interruption remains possible",
            expected_minutes=(0, 0),
            worst_credible_minutes=(0, 0),
            assumptions=(),
            unknowns=(
                "Current redundancy, multipathing, maintenance-window, and service telemetry.",
            ),
        )
        options = (
            self._investigate(request, applicability, impact, no_interruption, health),
            self._escalate(request, applicability, impact, no_interruption, health),
            self._defer(request, applicability, impact, no_interruption, health, inventory),
            self._restoration_plan(request, applicability, impact, blocked_interruption, health),
            self._remediation_plan(request, applicability, impact, blocked_interruption, health),
        )[: request.max_options]
        option_ids = {option.option_id for option in options}
        preferred = (
            "recommendation.option.investigate"
            if "recommendation.option.investigate" in option_ids
            else None
        )
        excluded = tuple(
            option.option_id for option in options if option.state is OptionState.BLOCKED
        )
        comparisons = self._comparisons(options)
        return RecommendationArtifact(
            recommendation_id=f"rec_{uuid4().hex}",
            version=version,
            prior_version_id=prior_version_id,
            owner="Storage Operations",
            state=RecommendationState.READY_FOR_REVIEW,
            requested_by=requested_by,
            created_at=created_at,
            expires_at=created_at + timedelta(hours=4),
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            target_id=request.target_id,
            decision_question=request.decision_question,
            accountable_audience=request.accountable_audience,
            horizon=request.horizon,
            constraints=request.constraints,
            source_case_id=source_case.case_id,
            source_case_version=source_case.version,
            source_case_state=source_case.state.value,
            source_evidence=source_case.evidence,
            options=options,
            comparisons=comparisons,
            preferred_option_id=preferred,
            preference_rationale=(
                "The preferred option is bounded, read-only, reversible, supported by the current "
                "provisional RCA, and directly reduces the material evidence gap."
            ),
            policy_constraints=(
                "No Atlas execution authority is available.",
                "C3 or higher planning remains blocked until impact, rollback, and readiness "
                "are current.",
                "Human review is required before external handoff or change planning.",
            ),
            excluded_option_ids=excluded,
            human_review=HumanReview(
                status=ReviewStatus.PENDING,
                reviewer_id=None,
                reviewed_at=None,
                rationale=None,
            ),
            component_versions=(
                "recommendation-artifact.v1",
                "storage-recommendation-rules.v1",
                *source_case.component_versions,
            ),
            data_profile=_DATA_PROFILE,
            execution_authorized=False,
            safety_notice=SAFETY_NOTICE,
        )

    @staticmethod
    def _base_governance(*, approval: bool, itsm: bool, vendor: bool) -> GovernanceRequirements:
        return GovernanceRequirements(
            required_roles=("role.development.operator", "Storage Operations reviewer"),
            policy_references=("policy.recommendation.decision-support.v1",),
            approval_required=approval,
            itsm_record_required=itsm,
            vendor_support_required=vendor,
            human_handoff="An accountable human owns review, selection, and any external action.",
        )

    @staticmethod
    def _recovery(strategy: str, *, feasible: bool, gaps: tuple[str, ...] = ()) -> RecoveryPlan:
        return RecoveryPlan(
            strategy=strategy,
            rollback_feasible=feasible,
            point_of_no_return="None for C0/C1 options; unknown for blocked change planning.",
            trigger_conditions=(
                "Stop on scope, authorization, timeout, or contradictory evidence.",
            ),
            estimated_duration=DurationEstimate(0, 10, "Bounded planning estimate.", "low"),
            data_implications="No data state change is permitted by this artifact.",
            gaps=gaps,
        )

    def _investigate(
        self,
        request: RecommendationRequest,
        applicability: Applicability,
        impact: ImpactSummary,
        interruption: InterruptionEstimate,
        health: str,
    ) -> RecommendationOption:
        return RecommendationOption(
            option_id="recommendation.option.investigate",
            version=1,
            category=RecommendationCategory.INVESTIGATE,
            state=OptionState.VIABLE,
            preference=PreferenceState.PREFERRED,
            title="Collect current path, event, and service evidence",
            intended_outcome=(
                "Distinguish persistent path degradation from a transient observation."
            ),
            applicability=applicability,
            plan_steps=(
                PlanStep(
                    "step.investigate.path-events",
                    1,
                    "diagnosis",
                    "Collect one bounded current path and event snapshot.",
                    "hitachi.opscenter.storage.path-events.read",
                    "C1",
                    "Current scoped path state and related events.",
                    "Stop on timeout, stale data, scope mismatch, or output limit.",
                    False,
                ),
                PlanStep(
                    "step.investigate.repeat-health",
                    2,
                    "diagnosis",
                    "Repeat the exact target hardware-health observation.",
                    "hitachi.opscenter.storage.hardware.read",
                    "C1",
                    "A reproducible or absent warning on the same target.",
                    "Stop if the target or component mapping changes.",
                    False,
                ),
                PlanStep(
                    "step.investigate.service-health",
                    3,
                    "validation",
                    "Read authorized service telemetry for the same window.",
                    "atlas.telemetry.service-health.read",
                    "C1",
                    "Scoped service symptoms or an explicit absence of observed symptoms.",
                    "Stop if service mapping is stale or unauthorized.",
                    False,
                ),
            ),
            supporting_evidence=(health,),
            contradicting_evidence=(),
            assumptions=("The allowlisted connectors remain healthy and read-only.",),
            unknowns=("Current path, fabric, multipathing, and service state.",),
            confidence="supported",
            confidence_rationale="The option directly addresses the blocker in the source RCA.",
            risk_dimensions=(
                RiskDimension("availability", RiskLevel.LOW, "Read-only bounded collection."),
                RiskDimension("data", RiskLevel.LOW, "No write or recovery operation."),
                RiskDimension("uncertainty", RiskLevel.MODERATE, "Connector coverage is partial."),
            ),
            overall_risk=RiskLevel.LOW,
            impact=impact,
            duration=DurationEstimate(2, 5, "Three bounded reads with fixed timeouts.", "moderate"),
            interruption=interruption,
            preconditions=("Exact target authorization.", "Healthy audit and connector services."),
            success_criteria=("All three scoped reads return attributable current evidence.",),
            verification_criteria=("Evidence references resolve to the same target and window.",),
            stop_conditions=(
                "Any authorization, scope, freshness, timeout, or output-limit failure.",
            ),
            recovery=self._recovery(
                "Stop collection; no infrastructure rollback is required.", feasible=True
            ),
            governance=self._base_governance(approval=False, itsm=False, vendor=False),
            residual_risk=("Read-only results can remain inconclusive.",),
            policy_outcome="permitted_for_human_initiation",
            exclusion_reasons=(),
        )

    def _escalate(
        self,
        request: RecommendationRequest,
        applicability: Applicability,
        impact: ImpactSummary,
        interruption: InterruptionEstimate,
        health: str,
    ) -> RecommendationOption:
        return RecommendationOption(
            option_id="recommendation.option.escalate",
            version=1,
            category=RecommendationCategory.ESCALATE,
            state=OptionState.VIABLE,
            preference=PreferenceState.ALTERNATIVE,
            title="Prepare an attributable vendor escalation package",
            intended_outcome="Enable specialist review without exposing secrets or hidden targets.",
            applicability=applicability,
            plan_steps=(
                PlanStep(
                    "step.escalate.package",
                    1,
                    "preparation",
                    "Prepare a redacted evidence and version summary for human review.",
                    "atlas.vendor.support.package.prepare",
                    "C0",
                    "A non-secret draft support package.",
                    "Stop if classification or export policy cannot be satisfied.",
                    False,
                ),
            ),
            supporting_evidence=(health,),
            contradicting_evidence=(),
            assumptions=("A current support entitlement is independently verified by a human.",),
            unknowns=("Vendor entitlement, response time, and requested diagnostic scope.",),
            confidence="supported",
            confidence_rationale="Escalation is safe but may not reduce uncertainty as quickly.",
            risk_dimensions=(
                RiskDimension("availability", RiskLevel.LOW, "No target operation."),
                RiskDimension(
                    "security", RiskLevel.MODERATE, "Export requires review and redaction."
                ),
            ),
            overall_risk=RiskLevel.LOW,
            impact=impact,
            duration=DurationEstimate(10, 30, "Human package review is required.", "low"),
            interruption=interruption,
            preconditions=(
                "Classification and export review.",
                "Human verification of entitlement.",
            ),
            success_criteria=("A reviewer accepts the redacted package for external submission.",),
            verification_criteria=("No secret, credential, or unauthorized target is present.",),
            stop_conditions=("Stop on classification, ACL, or redaction failure.",),
            recovery=self._recovery(
                "Discard the draft package before external submission.", feasible=True
            ),
            governance=self._base_governance(approval=False, itsm=True, vendor=True),
            residual_risk=("Vendor response may require additional approved diagnostics.",),
            policy_outcome="permitted_for_human_handoff",
            exclusion_reasons=(),
        )

    def _defer(
        self,
        request: RecommendationRequest,
        applicability: Applicability,
        impact: ImpactSummary,
        interruption: InterruptionEstimate,
        health: str,
        inventory: str | None,
    ) -> RecommendationOption:
        return RecommendationOption(
            option_id="recommendation.option.defer",
            version=1,
            category=RecommendationCategory.DEFER_NO_ACTION,
            state=OptionState.VIABLE,
            preference=PreferenceState.ALTERNATIVE,
            title="Defer change and monitor explicit triggers",
            intended_outcome="Avoid premature change while keeping a bounded review trigger.",
            applicability=applicability,
            plan_steps=(
                PlanStep(
                    "step.defer.monitor",
                    1,
                    "monitoring",
                    "Continue the approved bounded hardware-health observation until expiry.",
                    "hitachi.opscenter.storage.hardware.read",
                    "C1",
                    "A current trigger or stable observation for human review.",
                    "Stop and escalate on critical state or service symptom.",
                    False,
                ),
            ),
            supporting_evidence=((inventory,) if inventory else ()),
            contradicting_evidence=(health,),
            assumptions=("Service state does not deteriorate before the next observation.",),
            unknowns=("Whether the warning will recur or worsen before the next observation.",),
            confidence="suspected",
            confidence_rationale=(
                "Deferral avoids change risk but accepts unresolved degradation risk; no "
                "independent peer signal is available to weigh against the current warning."
            ),
            risk_dimensions=(
                RiskDimension(
                    "availability", RiskLevel.MODERATE, "Reduced redundancy may persist."
                ),
                RiskDimension("uncertainty", RiskLevel.HIGH, "The mechanism remains unresolved."),
            ),
            overall_risk=RiskLevel.MODERATE,
            impact=impact,
            duration=DurationEstimate(0, 240, "Option expires with the artifact.", "moderate"),
            interruption=interruption,
            preconditions=("Monitoring remains current.", "Named human owner receives triggers."),
            success_criteria=("No escalation trigger occurs before expiry.",),
            verification_criteria=("Human review occurs at trigger or expiry.",),
            stop_conditions=("Critical warning, service symptom, or stale evidence.",),
            recovery=self._recovery(
                "Exit deferral and escalate for accountable review.", feasible=True
            ),
            governance=self._base_governance(approval=False, itsm=True, vendor=False),
            residual_risk=("A latent condition can progress between observations.",),
            policy_outcome="permitted_with_expiry_and_trigger",
            exclusion_reasons=(),
        )

    def _restoration_plan(
        self,
        request: RecommendationRequest,
        applicability: Applicability,
        impact: ImpactSummary,
        interruption: InterruptionEstimate,
        health: str,
    ) -> RecommendationOption:
        return RecommendationOption(
            option_id="recommendation.option.restoration-planning",
            version=1,
            category=RecommendationCategory.RESTORATION_PLANNING,
            state=OptionState.BLOCKED,
            preference=PreferenceState.INELIGIBLE,
            title="Prepare controller failover restoration planning",
            intended_outcome="Plan a human-governed restoration path if impact becomes active.",
            applicability=applicability,
            plan_steps=(
                PlanStep(
                    "step.restore.impact",
                    1,
                    "readiness",
                    "Recalculate current change impact and redundancy before planning.",
                    "atlas.graph.storage-impact.read",
                    "C1",
                    "A current impact and redundancy analysis.",
                    "Stop if topology or redundancy evidence remains incomplete.",
                    False,
                ),
                PlanStep(
                    "step.restore.failover-plan",
                    2,
                    "restoration-planning",
                    "Select an approved vendor failover procedure for human change planning.",
                    "hitachi.opscenter.storage.controller-failover.plan",
                    "C3",
                    "A reviewed conceptual plan, not an executable command.",
                    "Stop until impact, rollback, approval, and runbook applicability are current.",
                    False,
                ),
            ),
            supporting_evidence=(health,),
            contradicting_evidence=(),
            assumptions=(),
            unknowns=("Current redundancy, service impact, rollback path, and approved runbook.",),
            confidence="insufficient",
            confidence_rationale="Material readiness and impact inputs are missing.",
            risk_dimensions=(
                RiskDimension(
                    "availability", RiskLevel.CRITICAL, "Failover can interrupt service."
                ),
                RiskDimension("reversibility", RiskLevel.UNKNOWN, "Rollback is not established."),
                RiskDimension("uncertainty", RiskLevel.HIGH, "Impact inputs are incomplete."),
            ),
            overall_risk=RiskLevel.CRITICAL,
            impact=impact,
            duration=DurationEstimate(
                0, 0, "Blocked; no supported duration estimate.", "insufficient"
            ),
            interruption=interruption,
            preconditions=("Confirmed active impact.", "Current redundancy and rollback evidence."),
            success_criteria=("Not defined until an approved procedure is selected.",),
            verification_criteria=("Not defined until readiness is complete.",),
            stop_conditions=(
                "Do not enter implementation planning while exclusion reasons remain.",
            ),
            recovery=self._recovery(
                "No credible rollback is established.",
                feasible=False,
                gaps=("Point of no return and recovery duration are unknown.",),
            ),
            governance=self._base_governance(approval=True, itsm=True, vendor=True),
            residual_risk=("Service interruption and recovery exposure remain unknown.",),
            policy_outcome="blocked_pending_readiness",
            exclusion_reasons=(
                "No current service impact is confirmed.",
                "Rollback and recovery are not established.",
                "No reviewed applicable failover runbook is linked.",
                "The requested maximum viable capability class is C1.",
            ),
        )

    def _remediation_plan(
        self,
        request: RecommendationRequest,
        applicability: Applicability,
        impact: ImpactSummary,
        interruption: InterruptionEstimate,
        health: str,
    ) -> RecommendationOption:
        return RecommendationOption(
            option_id="recommendation.option.remediation-planning",
            version=1,
            category=RecommendationCategory.REMEDIATION_PLANNING,
            state=OptionState.BLOCKED,
            preference=PreferenceState.INELIGIBLE,
            title="Prepare permanent controller or path remediation planning",
            intended_outcome=(
                "Plan correction only after the causal mechanism is sufficiently supported."
            ),
            applicability=applicability,
            plan_steps=(
                PlanStep(
                    "step.remediate.validate",
                    1,
                    "readiness",
                    "Validate the path mechanism with current bounded evidence.",
                    "hitachi.opscenter.storage.path-events.read",
                    "C1",
                    "Evidence that raises, lowers, or rejects the leading hypothesis.",
                    "Stop if the result remains ambiguous.",
                    False,
                ),
                PlanStep(
                    "step.remediate.plan",
                    2,
                    "remediation-planning",
                    "Select an approved path or controller remediation procedure.",
                    "hitachi.opscenter.storage.path-remediation.plan",
                    "C3",
                    "A reviewed conceptual plan, not an executable command.",
                    "Stop until RCA, impact, rollback, and approval requirements are satisfied.",
                    False,
                ),
            ),
            supporting_evidence=(health,),
            contradicting_evidence=(),
            assumptions=(),
            unknowns=("Confirmed root cause, exact failing element, impact, and rollback.",),
            confidence="insufficient",
            confidence_rationale="The RCA is provisional and alternative explanations remain.",
            risk_dimensions=(
                RiskDimension(
                    "availability", RiskLevel.HIGH, "Remediation may disturb active paths."
                ),
                RiskDimension("data", RiskLevel.UNKNOWN, "Protection effects are not modeled."),
                RiskDimension("uncertainty", RiskLevel.HIGH, "Root cause is not confirmed."),
            ),
            overall_risk=RiskLevel.HIGH,
            impact=impact,
            duration=DurationEstimate(
                0, 0, "Blocked; no supported duration estimate.", "insufficient"
            ),
            interruption=interruption,
            preconditions=(
                "Sufficiently supported cause.",
                "Current impact and recovery evidence.",
            ),
            success_criteria=("Not defined until an approved procedure is selected.",),
            verification_criteria=("Not defined until readiness is complete.",),
            stop_conditions=(
                "Do not plan a state-changing correction from provisional RCA alone.",
            ),
            recovery=self._recovery(
                "No credible rollback is established.",
                feasible=False,
                gaps=("Recovery assets and data implications are unknown.",),
            ),
            governance=self._base_governance(approval=True, itsm=True, vendor=True),
            residual_risk=("Incorrect remediation could worsen availability or obscure evidence.",),
            policy_outcome="blocked_pending_causal_and_change_readiness",
            exclusion_reasons=(
                "Root cause is not confirmed.",
                "Change impact and rollback are incomplete.",
                "No reviewed applicable remediation runbook is linked.",
                "The requested maximum viable capability class is C1.",
            ),
        )

    @staticmethod
    def _comparisons(options: tuple[RecommendationOption, ...]) -> tuple[ComparisonDimension, ...]:
        def values(attribute: str) -> tuple[tuple[str, str], ...]:
            result: list[tuple[str, str]] = []
            for option in options:
                if attribute == "evidence":
                    value = f"{option.confidence}; {len(option.supporting_evidence)} supporting"
                elif attribute == "risk":
                    value = option.overall_risk.value
                elif attribute == "reversibility":
                    value = "credible" if option.recovery.rollback_feasible else "not established"
                elif attribute == "duration":
                    value = (
                        f"{option.duration.minimum_minutes}-{option.duration.maximum_minutes} min"
                    )
                else:
                    value = option.policy_outcome
                result.append((option.option_id, value))
            return tuple(result)

        return (
            ComparisonDimension(
                "evidence_strength",
                1,
                values("evidence"),
                "Applicability and evidence must be sufficient before preference.",
            ),
            ComparisonDimension(
                "risk_and_interruption",
                2,
                values("risk"),
                "Lower realistic worst-case risk is preferred when effectiveness is comparable.",
            ),
            ComparisonDimension(
                "reversibility",
                3,
                values("reversibility"),
                "Credible stop or recovery behavior is required for consequential use.",
            ),
            ComparisonDimension(
                "duration",
                4,
                values("duration"),
                "Ranges remain visible and are not treated as guarantees.",
            ),
            ComparisonDimension(
                "policy_and_readiness",
                5,
                values("policy"),
                "Deterministic policy and readiness exclusions override generated preference.",
            ),
        )
