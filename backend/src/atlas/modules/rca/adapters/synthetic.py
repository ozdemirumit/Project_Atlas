from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from atlas.core.classification import DataClassification
from atlas.modules.investigations.adapters.synthetic import SyntheticInvestigationAssembler
from atlas.modules.investigations.domain.models import InvestigationRequest
from atlas.modules.rca.domain.models import (
    CauseType,
    ConfirmationLevel,
    DiagnosticStep,
    HumanReview,
    ImpactScope,
    IncidentReference,
    NormalizedSymptom,
    ProvisionalCauseStatement,
    RcaCase,
    RcaCaseState,
    RcaCreateRequest,
    RcaFinding,
    RcaHypothesis,
    RcaSeverity,
    ReviewStatus,
)

FAULT_FAMILIES = (
    "storage_controller_or_path_degradation",
    "transient_or_observation_source_failure",
)
SAFETY_NOTICE = (
    "Decision support only. This provisional RCA does not confirm root cause, service impact, or "
    "remediation readiness and cannot authorize or execute an infrastructure change."
)


class SyntheticStorageRcaAssembler:
    def __init__(self) -> None:
        self._investigation_assembler = SyntheticInvestigationAssembler()

    def build(
        self,
        request: RcaCreateRequest,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> RcaCase:
        investigation = self._investigation_assembler.build(
            InvestigationRequest(
                target_id=request.target_id,
                question=f"Which bounded fault family best explains {request.actual_behavior}?",
                intended_decision="Select the safest discriminating evidence for provisional RCA.",
                window_start=request.window_start,
                window_end=request.window_end,
                max_evidence_records=request.max_evidence_records,
            ),
            requested_by=requested_by,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            created_at=created_at,
            version=version,
            prior_version_id=None,
        )
        model = "VSP One B28" if request.target_id.endswith("b28") else "VSP G400"
        component = "CTL01" if request.target_id.endswith("b28") else "capacity pool"
        possible_service = (
            "Enterprise Resource Planning"
            if request.target_id.endswith("b28")
            else "Analytics Processing Service"
        )
        unaffected_peer = "CTL02" if request.target_id.endswith("b28") else "peer capacity pool"
        health_evidence = "evidence.investigation.health.latest"
        peer_evidence = "evidence.investigation.peer.signal"
        graph_evidence = "evidence.investigation.graph.path"
        vendor_evidence = "evidence.investigation.vendor.guidance"

        path_step = self._diagnostic_step(
            step_id="diagnostic.path-events",
            question="Is the warning reproduced by current path or event evidence?",
            target_id=request.target_id,
            capability_id="hitachi.opscenter.storage.path-events.read",
            evidence_source="Hitachi Ops Center allowlisted read-only capability",
            expected_if_supported="Repeated path errors or degraded path state are present.",
            expected_if_not_supported="No related current path error or event sequence is present.",
            supported_branch="Increase support for controller or path degradation.",
            unsupported_branch="Weaken degradation and evaluate observation failure.",
            timeout_seconds=30,
            max_output_records=20,
        )
        service_step = self._diagnostic_step(
            step_id="diagnostic.service-telemetry",
            question="Does authorized service telemetry align with the warning window?",
            target_id=request.target_id,
            capability_id="atlas.telemetry.service-health.read",
            evidence_source="Atlas authorized service telemetry projection",
            expected_if_supported=(
                "A scoped latency or availability symptom aligns with the window."
            ),
            expected_if_not_supported="No scoped service symptom is observed in the same window.",
            supported_branch="Retain possible impact and continue dependency validation.",
            unsupported_branch="Do not infer service impact from graph reachability.",
            timeout_seconds=20,
            max_output_records=12,
        )
        repeat_step = self._diagnostic_step(
            step_id="diagnostic.repeat-health",
            question="Does a repeat bounded health read reproduce the warning?",
            target_id=request.target_id,
            capability_id="hitachi.opscenter.storage.hardware.read",
            evidence_source="Hitachi Ops Center allowlisted hardware-health capability",
            expected_if_supported="The same scoped component warning is reproduced.",
            expected_if_not_supported="The warning is absent from the repeat read.",
            supported_branch="Weaken transient observation failure.",
            unsupported_branch="Increase support for transient or observation-source failure.",
            timeout_seconds=15,
            max_output_records=8,
        )
        hypotheses = (
            RcaHypothesis(
                hypothesis_id="rca-hypothesis.controller-path-degradation",
                rank=1,
                fault_family=FAULT_FAMILIES[0],
                cause_type=CauseType.CONTRIBUTING_CAUSE,
                statement=(
                    f"A controller or path condition on {model} may be contributing to the warning."
                ),
                mechanism=(
                    "A degraded component or path could reduce redundancy and generate the "
                    "observed "
                    "warning before a confirmed service symptom appears."
                ),
                expected_affected_entities=(request.target_id, component),
                expected_unaffected_entities=(unaffected_peer,),
                expected_sequence=(
                    "Component or path condition begins.",
                    "The bounded health source observes a warning.",
                    "Related path events may appear if the condition persists.",
                ),
                supporting_evidence=(health_evidence, graph_evidence, vendor_evidence),
                contradicting_evidence=(peer_evidence,),
                missing_expected_observations=(
                    "Current host multipathing state.",
                    "Current SAN fabric and storage event sequence.",
                    "Time-aligned application telemetry.",
                ),
                confounders=(
                    "The graph snapshot is aging and does not model SAN redundancy.",
                    "The observation source may report a transient warning.",
                ),
                assumptions=(
                    "The health response maps to the same target and component in the case scope.",
                ),
                confirmation_level=ConfirmationLevel.SUPPORTED,
                confidence_rationale=(
                    "A current direct warning and applicable mechanism support the hypothesis, but "
                    "peer availability and missing independent path evidence prevent stronger "
                    "support."
                ),
                diagnostic_steps=(path_step, service_step),
            ),
            RcaHypothesis(
                hypothesis_id="rca-hypothesis.transient-observation",
                rank=2,
                fault_family=FAULT_FAMILIES[1],
                cause_type=CauseType.OBSERVATION_FAILURE,
                statement="The warning may be transient or specific to the observation source.",
                mechanism=(
                    "A short-lived state or collection limitation could produce a warning "
                    "without a "
                    "persistent infrastructure or service condition."
                ),
                expected_affected_entities=(component,),
                expected_unaffected_entities=(unaffected_peer, possible_service),
                expected_sequence=(
                    "A transient state or collection anomaly occurs.",
                    "One bounded source records the warning.",
                    "Repeat state and service telemetry remain normal.",
                ),
                supporting_evidence=(peer_evidence,),
                contradicting_evidence=(health_evidence,),
                missing_expected_observations=(
                    "A repeat health observation.",
                    "Observation-source health and parsing diagnostics.",
                ),
                confounders=("Peer availability does not prove the warned component is healthy.",),
                assumptions=("The peer signal is sufficiently independent for comparison.",),
                confirmation_level=ConfirmationLevel.SUSPECTED,
                confidence_rationale=(
                    "The available peer weakens an outage interpretation, but the direct warning "
                    "has "
                    "not been repeated or reconciled."
                ),
                diagnostic_steps=(repeat_step, service_step),
            ),
        )

        return RcaCase(
            case_id=f"rca_{uuid4().hex}",
            version=version,
            prior_version_id=prior_version_id,
            owner="Storage Operations",
            requested_by=requested_by,
            state=RcaCaseState.PROVISIONAL,
            severity=RcaSeverity.WARNING,
            created_at=created_at,
            updated_at=created_at,
            incident_references=(
                IncidentReference(
                    reference_type="incident",
                    reference_id=request.incident_id,
                    authority=(
                        "user-provided incident reference; ITSM linkage not yet authoritative"
                    ),
                ),
                IncidentReference(
                    reference_type="health_finding",
                    reference_id="finding.health.storage.warning",
                    authority="Project Atlas governed health-check artifact",
                ),
            ),
            user_report=request.user_report,
            expected_behavior=request.expected_behavior,
            actual_behavior=request.actual_behavior,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            target_id=request.target_id,
            window_start=request.window_start,
            window_end=request.window_end,
            fault_families=FAULT_FAMILIES,
            symptoms=(
                NormalizedSymptom(
                    symptom_id="symptom.storage.warning",
                    statement=request.actual_behavior,
                    first_observed_at=investigation.timeline[1].occurred_at,
                    current_state="observed warning; persistence and impact unknown",
                    evidence_references=(health_evidence,),
                ),
            ),
            impact_scope=ImpactScope(
                affected_entities=(request.target_id, component),
                possibly_affected_services=(possible_service,),
                explicitly_unaffected_entities=(unaffected_peer,),
                current_impact=(
                    "A component warning is observed. No service outage is confirmed; reduced "
                    "redundancy remains possible."
                ),
                business_criticality="Unknown until authoritative service mapping is reviewed.",
                impact_confirmed=False,
                limitations=(
                    "Graph reachability does not establish current service impact.",
                    "SAN redundancy and application telemetry are unavailable.",
                ),
            ),
            source_investigation_artifact_id=investigation.artifact_id,
            source_investigation_version=investigation.version,
            evidence=investigation.evidence,
            timeline=investigation.timeline,
            hypotheses=hypotheses,
            findings=(
                RcaFinding(
                    finding_id="rca-finding.warning-supported",
                    cause_type=CauseType.CONTRIBUTING_CAUSE,
                    statement=(
                        "A controller or path degradation mechanism is supported as a candidate "
                        "contributing condition, not a confirmed root cause."
                    ),
                    confirmation_level=ConfirmationLevel.SUPPORTED,
                    evidence_references=(health_evidence, vendor_evidence),
                    residual_uncertainty=(
                        "No current path, event-log, fabric, or service evidence confirms "
                        "mechanism.",
                    ),
                ),
            ),
            assumptions=investigation.assumptions,
            unknowns=investigation.unknowns,
            conflicts=investigation.conflicts,
            evidence_gaps=(
                "Current path and event-log evidence is missing.",
                "Current SAN fabric and host multipathing evidence is missing.",
                "Current authorized application telemetry is missing.",
                "No authoritative recent-change record is linked.",
            ),
            blocker=(
                "Safe evidence is insufficient to distinguish persistent path degradation from a "
                "transient observation failure."
            ),
            safest_next_step="Run the allowlisted C1 path/event and repeat-health reads.",
            provisional_statement=ProvisionalCauseStatement(
                statement=(
                    "No root cause is confirmed. Current evidence supports controller or path "
                    "degradation as the leading candidate contributing condition."
                ),
                confirmation_level=ConfirmationLevel.SUPPORTED,
                supporting_evidence=(health_evidence, graph_evidence, vendor_evidence),
                contradicting_evidence=(peer_evidence,),
                residual_uncertainty=(
                    "The warned state has not been reproduced.",
                    "A causal path to service impact is not observed.",
                ),
                alternatives_not_ruled_out=(
                    "Transient component state.",
                    "Observation-source or parsing limitation.",
                    "Independent downstream condition not represented in current evidence.",
                ),
                prevention_or_verification_implication=(
                    "Collect current path, event, and service evidence before remediation or "
                    "preventive-change planning."
                ),
            ),
            human_review=HumanReview(
                status=ReviewStatus.PENDING,
                reviewer_id=None,
                reviewed_at=None,
                decision_reason=None,
                domain_confirmation_criterion=None,
            ),
            component_versions=(
                "rca-case-contract.v1",
                "storage-fault-model.v1",
                *investigation.component_versions,
            ),
            data_profile="synthetic_lab",
            root_cause_confirmed=False,
            safety_notice=SAFETY_NOTICE,
        )

    @staticmethod
    def _diagnostic_step(
        *,
        step_id: str,
        question: str,
        target_id: str,
        capability_id: str,
        evidence_source: str,
        expected_if_supported: str,
        expected_if_not_supported: str,
        supported_branch: str,
        unsupported_branch: str,
        timeout_seconds: int,
        max_output_records: int,
    ) -> DiagnosticStep:
        return DiagnosticStep(
            step_id=step_id,
            question=question,
            target_id=target_id,
            scope=f"exact storage target {target_id}",
            capability_id=capability_id,
            capability_class="C1",
            evidence_source=evidence_source,
            preconditions=(
                "Exact target authorization remains valid.",
                "Connector and audit services are healthy.",
            ),
            expected_duration_seconds=timeout_seconds,
            expected_load="One bounded read-only request; no target state change.",
            max_output_records=max_output_records,
            expected_if_supported=expected_if_supported,
            expected_if_not_supported=expected_if_not_supported,
            timeout_seconds=timeout_seconds,
            stop_condition=(
                "Stop on timeout, authorization or scope failure, stale response, or output limit."
            ),
            required_role="role.development.operator",
            policy_reference="policy.rca.diagnostic.c1-read-only.v1",
            approval_required=False,
            classification=DataClassification.INTERNAL,
            retention="Retain evidence reference under the RCA case retention policy.",
            supported_branch=supported_branch,
            unsupported_branch=unsupported_branch,
        )
