from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.connectors.vendors.huawei_pacific.manifest import CLUSTER_NODE_CAPABILITY_ID
from atlas.modules.investigations.domain.models import EvidenceUnit, FreshnessState
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
    RcaFinding,
    RcaHypothesis,
    RcaSeverity,
    ReviewStatus,
)
from atlas.modules.recommendations.adapters.configured_huawei_pacific import (
    ConfiguredHuaweiPacificRecommendationAssembler,
)
from atlas.modules.recommendations.domain.models import RecommendationRequest

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
TARGET_ID = "asset.storage.real-cluster"
SCOPE = "organization.atlas.local/environment.development/site.local/" + TARGET_ID


def _evidence(evidence_id: str, source_type: str) -> EvidenceUnit:
    return EvidenceUnit(
        evidence_id=evidence_id,
        artifact_version="1",
        source_type=source_type,
        source_system="Huawei Pacific Cluster Manager",
        source_version="0.1.0",
        target_id=TARGET_ID,
        observed_at=NOW,
        applicable_from=NOW,
        applicable_to=None,
        freshness=FreshnessState.CURRENT,
        classification=DataClassification.INTERNAL,
        authorization_reference=SCOPE,
        collection_method="Huawei Pacific allowlisted C1 read",
        summary="A node reported a non-online running status.",
        integrity="Digest-only evidence from an allowlisted C1 cluster-manager response",
        completeness="A single current read.",
        quality_limitations=(),
        citation="Huawei Pacific read.",
    )


def _diagnostic_step(step_id: str) -> DiagnosticStep:
    return DiagnosticStep(
        step_id=step_id,
        question="Is the finding reproduced?",
        target_id=TARGET_ID,
        scope=f"exact storage target {TARGET_ID}",
        capability_id=CLUSTER_NODE_CAPABILITY_ID,
        capability_class="C1",
        evidence_source="Huawei Pacific allowlisted read-only capability",
        preconditions=("Exact target authorization remains valid.",),
        expected_duration_seconds=15,
        expected_load="One bounded read-only request.",
        max_output_records=8,
        expected_if_supported="Reproduced.",
        expected_if_not_supported="Absent.",
        timeout_seconds=15,
        stop_condition="Stop on timeout or scope failure.",
        required_role="role.development.operator",
        policy_reference="policy.rca.diagnostic.c1-read-only.v1",
        approval_required=False,
        classification=DataClassification.INTERNAL,
        retention="Retain evidence reference under the RCA case retention policy.",
        supported_branch="Increase support.",
        unsupported_branch="Weaken support.",
    )


def _active_finding_case() -> RcaCase:
    health = _evidence("evidence.rca.health.real1", "storage_hardware_health")
    inventory = _evidence("evidence.rca.inventory.real1", "storage_inventory")
    hypothesis = RcaHypothesis(
        hypothesis_id="rca-hypothesis.controller-path-degradation",
        rank=1,
        fault_family="storage_controller_or_path_degradation",
        cause_type=CauseType.CONTRIBUTING_CAUSE,
        statement="A node condition may be contributing to the finding.",
        mechanism="A faulty node could reduce cluster redundancy.",
        expected_affected_entities=(TARGET_ID,),
        expected_unaffected_entities=(),
        expected_sequence=("Condition begins.", "Finding observed."),
        supporting_evidence=(health.evidence_id,),
        contradicting_evidence=(),
        missing_expected_observations=("A repeat health read.",),
        confounders=("No CMDB or hypervisor mapping exists in this environment.",),
        assumptions=("The health response maps to the same target.",),
        confirmation_level=ConfirmationLevel.SUPPORTED,
        confidence_rationale="A current direct finding supports the hypothesis.",
        diagnostic_steps=(_diagnostic_step("diagnostic.node-events"),),
    )
    return RcaCase(
        case_id="rca_real1",
        version=1,
        prior_version_id=None,
        owner="Storage Operations",
        requested_by="subject.development.operator",
        state=RcaCaseState.PROVISIONAL,
        severity=RcaSeverity.CRITICAL,
        created_at=NOW,
        updated_at=NOW,
        incident_references=(
            IncidentReference(
                reference_type="incident", reference_id="INC-1", authority="user-provided"
            ),
        ),
        user_report="A node reports a non-online running status.",
        expected_behavior="Cluster nodes remain online.",
        actual_behavior="A node reports a non-online running status.",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        site_id="site.local",
        target_id=TARGET_ID,
        window_start=NOW - timedelta(hours=24),
        window_end=NOW,
        fault_families=("storage_controller_or_path_degradation",),
        symptoms=(
            NormalizedSymptom(
                symptom_id="symptom.storage.finding",
                statement="A node reports a non-online running status.",
                first_observed_at=NOW,
                current_state="observed finding",
                evidence_references=(health.evidence_id,),
            ),
        ),
        impact_scope=ImpactScope(
            affected_entities=(TARGET_ID,),
            possibly_affected_services=(),
            explicitly_unaffected_entities=(),
            current_impact="A node finding is observed.",
            business_criticality="Unknown -- no service mapping is available.",
            impact_confirmed=False,
            limitations=("No CMDB or hypervisor mapping exists in this environment.",),
        ),
        source_investigation_artifact_id="investigation.rca.real1",
        source_investigation_version=1,
        evidence=(health, inventory),
        timeline=(),
        hypotheses=(hypothesis,),
        findings=(
            RcaFinding(
                finding_id="rca-finding.finding-supported",
                cause_type=CauseType.CONTRIBUTING_CAUSE,
                statement="A node condition is supported as a candidate contributing cause.",
                confirmation_level=ConfirmationLevel.SUPPORTED,
                evidence_references=(health.evidence_id,),
                residual_uncertainty=("No repeat read confirms persistence.",),
            ),
        ),
        assumptions=("The connector's read reflects the cluster's current state.",),
        unknowns=("Whether the finding is persistent or transient.",),
        conflicts=(),
        evidence_gaps=("Current node event-log evidence is missing.",),
        blocker="Safe evidence is insufficient to distinguish degradation from a transient state.",
        safest_next_step="Run the allowlisted C1 node-event and repeat cluster-node reads.",
        provisional_statement=ProvisionalCauseStatement(
            statement="No root cause is confirmed.",
            confirmation_level=ConfirmationLevel.SUPPORTED,
            supporting_evidence=(health.evidence_id,),
            contradicting_evidence=(),
            residual_uncertainty=("The finding has not been reproduced.",),
            alternatives_not_ruled_out=("Transient node state.",),
            prevention_or_verification_implication="Collect current node event evidence.",
        ),
        human_review=HumanReview(
            status=ReviewStatus.PENDING,
            reviewer_id=None,
            reviewed_at=None,
            decision_reason=None,
            domain_confirmation_criterion=None,
        ),
        component_versions=("rca-case-contract.v1", "huawei-pacific-connector.0.1.0"),
        data_profile="configured_huawei_pacific_read_only",
        root_cause_confirmed=False,
        safety_notice="Decision support only.",
    )


def _request() -> RecommendationRequest:
    return RecommendationRequest(
        source_case_id="rca_real1",
        source_case_version=1,
        target_id=TARGET_ID,
        decision_question="What should be done about the current finding?",
        accountable_audience="Storage Operations",
        horizon="next maintenance window",
        constraints=(),
        maximum_capability_class="C1",
        max_options=5,
    )


def test_build_populates_options_from_real_evidence_only() -> None:
    assembler = ConfiguredHuaweiPacificRecommendationAssembler()
    case = _active_finding_case()

    artifact = assembler.build(
        _request(),
        case,
        requested_by="subject.development.operator",
        organization_id=case.organization_id,
        environment_id=case.environment_id,
        site_id=case.site_id,
        created_at=NOW,
        version=1,
        prior_version_id=None,
    )

    assert artifact.data_profile == "configured_huawei_pacific_read_only"
    assert len(artifact.options) == 5
    evidence_ids = {item.evidence_id for item in artifact.source_evidence}
    referenced = {
        reference
        for option in artifact.options
        for reference in (*option.supporting_evidence, *option.contradicting_evidence)
    }
    assert referenced <= evidence_ids
    assert "evidence.investigation.peer.signal" not in referenced
    assert "evidence.investigation.graph.path" not in referenced
    assert "evidence.investigation.vendor.guidance" not in referenced
    investigate = next(
        option
        for option in artifact.options
        if option.option_id == "recommendation.option.investigate"
    )
    assert investigate.applicability.products == ()
    assert any(
        step.capability_id == CLUSTER_NODE_CAPABILITY_ID
        for option in artifact.options
        for step in option.plan_steps
    )
    assert artifact.execution_authorized is False


def test_build_raises_without_an_active_finding() -> None:
    assembler = ConfiguredHuaweiPacificRecommendationAssembler()
    case = _active_finding_case()
    empty_case = replace(case, hypotheses=())

    with pytest.raises(ValueError, match="no active finding"):
        assembler.build(
            _request(),
            empty_case,
            requested_by="subject.development.operator",
            organization_id=case.organization_id,
            environment_id=case.environment_id,
            site_id=case.site_id,
            created_at=NOW,
            version=1,
            prior_version_id=None,
        )
