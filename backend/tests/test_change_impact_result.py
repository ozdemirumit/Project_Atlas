from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.change_impact.domain.data_protection_service import (
    DataProtectionRecoverabilityAnalysis,
    ServiceImpactRecord,
)
from atlas.modules.change_impact.domain.dimensions import (
    ImpactDimension,
    ImpactDimensionAssessment,
    ImpactSeverity,
)
from atlas.modules.change_impact.domain.interruption_duration import (
    DurationEstimate,
    DurationModel,
    DurationPhase,
    InterruptionMode,
    InterruptionModeAssessment,
)
from atlas.modules.change_impact.domain.models import (
    ChangeCategory,
    ChangeRequest,
    ChangeStepSpec,
)
from atlas.modules.change_impact.domain.redundancy_capacity import (
    CapacityAndPerformanceAnalysis,
    CapacityEstimate,
    QuorumState,
    RedundancyAnalysis,
)
from atlas.modules.change_impact.domain.result import (
    ImpactComponentVersions,
    ImpactResult,
    ImpactResultSupersessionState,
    UnknownFactor,
    UnknownKind,
    blocks_recommendation_readiness,
)
from atlas.modules.change_impact.domain.scenario_risk import (
    RiskClassification,
    RiskLevel,
    Scenario,
    ScenarioKind,
)
from atlas.modules.change_impact.domain.snapshot import AnalysisSnapshot, EntityCurrentState
from atlas.modules.change_impact.domain.traversal import (
    AffectedItemClassification,
    DependencyTraversalResult,
    EdgeKind,
    ImpactCategory,
    TraversalDirection,
)
from atlas.modules.graph.domain.models import (
    EntityType,
    FreshnessState,
    GraphEntity,
    GraphEvidence,
    GraphSnapshot,
    ImpactPath,
    ImpactScope,
    StorageImpactResult,
)
from atlas.modules.runbook_engine.domain.risk_impact import DurationRange

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
REQUEST_ID = "change-request.example"
TARGET_ID = "target.controller-b"


def graph_entity(entity_id: str) -> GraphEntity:
    return GraphEntity(
        entity_id=entity_id,
        entity_type=EntityType.STORAGE_SYSTEM,
        display_name=entity_id,
        organization_id="organization.example",
        environment_id="environment.production",
        site_id="site.primary",
        domain_id="domain.storage",
        observed_at=NOW,
        valid_from=NOW,
        valid_to=None,
        freshness=FreshnessState.FRESH,
        confidence_basis="test fixture",
        evidence_references=("evidence.example",),
        classification=DataClassification.INTERNAL,
        allowed_principals=frozenset({"role.storage.operator"}),
    )


def change_request(**overrides: object) -> ChangeRequest:
    step = ChangeStepSpec(
        step_id="change-step.example",
        order=1,
        description="Fail over controller B to controller A.",
        connector_capability_id="capability.controller.failover",
        manual_procedure_reference=None,
        capability_class="C2",
    )
    defaults: dict[str, object] = {
        "request_id": REQUEST_ID,
        "proposed_change_version": 1,
        "purpose": "Apply a firmware update to controller B.",
        "expected_outcome": "Controller B runs the patched firmware with no data loss.",
        "change_category": ChangeCategory.SOFTWARE_FIRMWARE_DRIVER_OR_PATCH_UPDATE,
        "steps": (step,),
        "target_ids": (TARGET_ID,),
        "organization_id": "organization.example",
        "environment_id": "environment.production",
        "site_id": "site.primary",
        "parameters": (),
        "proposed_start": NOW + timedelta(days=1),
        "maintenance_window_start": NOW + timedelta(days=1),
        "maintenance_window_end": NOW + timedelta(days=1, hours=2),
        "deadline": NOW + timedelta(days=2),
        "preconditions": ("Controller A is healthy.",),
        "success_criteria": ("Controller B rejoins the cluster.",),
        "stop_conditions": ("Controller A reports a fault during failover.",),
        "rollback_plan": "Fail back to controller B's prior firmware image.",
        "current_incident_or_change_reference": None,
        "allowed_data_classes": ("topology", "health"),
        "required_freshness_seconds": 300,
        "requested_scenario_kinds": ("expected", "failure"),
        "audience": "storage-operations",
    }
    defaults.update(overrides)
    return ChangeRequest(**defaults)  # type: ignore[arg-type]


def analysis_snapshot() -> AnalysisSnapshot:
    graph_snapshot = GraphSnapshot(
        snapshot_id="snapshot.graph.example",
        schema_version="1.0",
        organization_id="organization.example",
        environment_id="environment.production",
        site_id="site.primary",
        generated_at=NOW,
        freshness=FreshnessState.FRESH,
        completeness="partial",
        entities=(graph_entity(TARGET_ID),),
        relationships=(),
        observations=(),
        evidence=(
            GraphEvidence(
                reference="evidence.example",
                source="hitachi_ops_center",
                source_version="1.0",
                observed_at=NOW,
                freshness=FreshnessState.FRESH,
                trust_basis="vendor API",
                classification=DataClassification.INTERNAL,
            ),
        ),
        known_gaps=(),
        data_profile="configured_test_read_only",
    )
    return AnalysisSnapshot(
        snapshot_id="snapshot.change-impact.example",
        change_request_id=REQUEST_ID,
        generated_at=NOW,
        graph_snapshot=graph_snapshot,
        entity_current_states=(
            EntityCurrentState(
                entity_id=TARGET_ID,
                health_status="healthy",
                active_alert_count=0,
                capacity_used_percent=62.5,
                load_percent=40.0,
                latency_ms=3.2,
                in_maintenance=False,
                firmware_version="6.1.0",
                compatibility_status="supported",
                support_status="in_support",
            ),
        ),
        service_criticality=(),
        data_protection_states=(),
        recent_and_concurrent_change_references=(),
    )


def traversal() -> DependencyTraversalResult:
    graph_impact = StorageImpactResult(
        snapshot_id="graph-snapshot.example",
        snapshot_generated_at=NOW,
        start_entity_id=TARGET_ID,
        max_depth=3,
        freshness=FreshnessState.FRESH,
        completeness="complete",
        entities=(graph_entity(TARGET_ID), graph_entity("target.host-01")),
        relationships=(),
        paths=(
            ImpactPath(
                scope=ImpactScope.DIRECT,
                entity_ids=(TARGET_ID, "target.host-01"),
                relationship_ids=("relationship.controller-host",),
                evidence_references=("evidence.example",),
            ),
        ),
        evidence=(),
        direct_entity_ids=(TARGET_ID, "target.host-01"),
        possible_entity_ids=(),
        technical_service_ids=("service.file-shares",),
        business_service_ids=(),
        unknowns=(),
        known_gaps=(),
        outage_confirmed=False,
        digital_twin_maturity="d0",
        data_profile="synthetic_lab",
        safety_notice="Decision support only.",
    )
    return DependencyTraversalResult(
        traversal_id="traversal.example",
        change_request_id=REQUEST_ID,
        graph_impact=graph_impact,
        direction=TraversalDirection.DOWNSTREAM,
        classifications=(
            AffectedItemClassification(
                entity_id="target.host-01",
                impact_category=ImpactCategory.FIRST_ORDER,
                edge_kinds=(EdgeKind.OBSERVED,),
            ),
        ),
        inaccessible_or_missing_subgraph_notes=(),
    )


def service_impact() -> ServiceImpactRecord:
    return ServiceImpactRecord(
        service_id="service.file-shares",
        service_name="Enterprise File Shares",
        owner="storage-team",
        criticality="high",
        supporting_graph_path_entity_ids=(TARGET_ID, "target.host-01"),
        expected_impact_mode="intermittent",
        affected_function="SMB write availability",
        user_or_location_scope="site.primary",
        expected_interruption_minimum_minutes=2,
        expected_interruption_maximum_minutes=5,
        worst_credible_interruption_minimum_minutes=5,
        worst_credible_interruption_maximum_minutes=30,
        degradation_and_recovery_dependencies=("target.controller-a",),
        relevant_sla_or_calendar_context="SLA permits 15 minutes of degradation per month.",
        confidence="moderate",
        is_confidence_reduced_by_missing_service_mapping=False,
    )


def redundancy() -> RedundancyAnalysis:
    return RedundancyAnalysis(
        change_request_id=REQUEST_ID,
        target_entity_id=TARGET_ID,
        normal_redundancy_level="dual_controller",
        maintenance_redundancy_level="single_controller",
        removed_by_change_entity_ids=(TARGET_ID,),
        existing_degraded_or_failed_entity_ids=(),
        failover_eligibility="eligible",
        failover_readiness="ready",
        recent_failover_test_evidence_reference="evidence.failover-test.2026-08",
        shared_fate_notes=(),
        quorum_state=QuorumState(
            quorum_state="healthy",
            witness_state="reachable",
            replication_state="synchronized",
            synchronization_state="in_sync",
        ),
        remaining_path_capacity_summary="Controller A can absorb full load for 4 hours.",
        single_points_of_failure_created_entity_ids=("target.controller-a",),
        evidence_references=("evidence.health-check.2026-09-04",),
    )


def capacity() -> CapacityAndPerformanceAnalysis:
    return CapacityAndPerformanceAnalysis(
        change_request_id=REQUEST_ID,
        target_entity_id=TARGET_ID,
        estimates=(
            CapacityEstimate(
                metric="iops",
                unit="iops",
                formula="current_iops * (1 + failover_load_factor)",
                assumptions=("failover_load_factor derived from last 30 days peak",),
                minimum_estimate=8000.0,
                maximum_estimate=12000.0,
                telemetry_available=True,
            ),
        ),
        workload_concurrency_notes="Batch backup job runs concurrently at 02:00 UTC.",
        business_peak_period_notes="Avoid month-end close, 2026-09-30.",
        rate_limit_and_vendor_threshold_notes=("Vendor caps failover IOPS burst at 15000.",),
        performance_effect_of_validation_and_rollback=(
            "Post-failover validation adds roughly 5% read latency for ten minutes."
        ),
        measurement_coverage="90% of volumes have five-minute telemetry.",
        measurement_age_seconds=120,
        aggregation_limitations=("Latency is averaged, not p99.",),
    )


def data_protection() -> DataProtectionRecoverabilityAnalysis:
    return DataProtectionRecoverabilityAnalysis(
        change_request_id=REQUEST_ID,
        target_entity_id=TARGET_ID,
        backup_recency="6 hours ago",
        backup_status="current",
        backup_scope="full volume",
        backup_immutable=True,
        relevant_restore_evidence_reference="evidence.restore-test.2026-08",
        replication_mode="synchronous",
        replication_lag_seconds=0.0,
        replication_consistency="consistent",
        replication_failover_state="ready",
        snapshot_and_retention_consequences=(),
        write_ordering_and_consistency_notes="Application-consistent snapshots enabled.",
        split_brain_or_divergence_risk=None,
        recovery_point_objective_seconds=0,
        recovery_time_objective_seconds=900,
        point_of_no_return_description=None,
        is_rollback_available=True,
        is_recovery_available=True,
        legal_hold_or_retention_constraint=None,
    )


def duration_model() -> DurationModel:
    return DurationModel(
        change_request_id=REQUEST_ID,
        target_entity_id=TARGET_ID,
        estimates=(
            DurationEstimate(
                phase=DurationPhase.TRANSITION,
                duration_range=DurationRange(minimum_minutes=1, maximum_minutes=5),
                basis="Median of the last 12 controller failovers in this environment.",
                comparable_outcome_references=("change.controller-failover.2026-06-01",),
                vendor_guidance_reference="vendor.doc.failover-timing",
                extending_factors=("Concurrent backup job in progress.",),
            ),
        ),
    )


def risk_classification() -> RiskClassification:
    return RiskClassification(
        change_request_id=REQUEST_ID,
        capability_class="C2",
        service_criticality_and_blast_radius_note="One high-criticality service affected.",
        interruption_mode_and_duration_note="Performance degradation, 2-10 minutes.",
        data_and_security_consequence_note="No data or security consequence expected.",
        starting_health_and_redundancy_note="Both controllers healthy at start.",
        reversibility_and_recovery_evidence_note="Rollback available, tested 2026-08.",
        plan_complexity_and_manual_dependency_note="Single automated step, no manual work.",
        evidence_freshness_and_graph_completeness_note="Graph snapshot is 3 minutes old.",
        risk_level=RiskLevel.MODERATE,
    )


def impact_result(**overrides: object) -> ImpactResult:
    defaults: dict[str, object] = {
        "result_id": "impact-result.example",
        "version": 1,
        "prior_version_id": None,
        "created_at": NOW,
        "change_request": change_request(),
        "target_summary": "Controller B, storage.example organization.",
        "snapshot": analysis_snapshot(),
        "analysis_scope_note": "Single storage system, production environment.",
        "traversal": traversal(),
        "service_impacts": (service_impact(),),
        "redundancy": redundancy(),
        "capacity": capacity(),
        "data_protection": data_protection(),
        "dimension_assessments": (
            ImpactDimensionAssessment(
                dimension=ImpactDimension.AVAILABILITY,
                severity=ImpactSeverity.MODERATE,
                rationale="Controller B failover causes a brief path interruption.",
                affected_entity_ids=(TARGET_ID,),
            ),
        ),
        "scenarios": (
            Scenario(
                scenario_id="scenario.expected",
                kind=ScenarioKind.EXPECTED,
                description="Controller B fails over cleanly to controller A within 5 minutes.",
                assumptions=("Controller A is healthy at start.",),
                confidence="high",
            ),
        ),
        "interruption_modes": (
            InterruptionModeAssessment(
                mode=InterruptionMode.PERFORMANCE_DEGRADATION,
                trigger="Controller B failover redirects load to controller A.",
                affected_scope_entity_ids=("target.controller-a",),
                duration_range=DurationRange(minimum_minutes=2, maximum_minutes=10),
                detection="Latency alert on controller A.",
                recovery_expectation="Latency returns to baseline once controller B rejoins.",
            ),
        ),
        "duration_model": duration_model(),
        "risk_classification": risk_classification(),
        "validation_requirements": ("Domain owner review required for C2 changes.",),
        "rollback_and_recovery_impact_note": (
            "Rollback returns controller B to its prior firmware within 10 minutes."
        ),
        "unknowns": (),
        "assumptions": ("No other change is scheduled during the maintenance window.",),
        "conflict_notes": (),
        "overall_confidence": "moderate",
        "policy_approval_itsm_owner_requirements": ("storage-team approval required.",),
        "component_versions": ImpactComponentVersions(
            graph_snapshot_id="snapshot.graph.example",
            evidence_package_version="evidence-package.example:v1",
            model_version="model.v3",
            rule_version="rule.v1",
            schema_version="impact-result.v1",
        ),
        "supersession_state": ImpactResultSupersessionState.CURRENT,
        "superseded_by_result_id": None,
        "classification": DataClassification.INTERNAL,
        "retention_note": "Retained 180 days per infrastructure change record policy.",
    }
    defaults.update(overrides)
    return ImpactResult(**defaults)  # type: ignore[arg-type]


def test_impact_result_accepts_valid_state() -> None:
    assert impact_result().result_id == "impact-result.example"


def test_impact_result_requires_expected_scenario() -> None:
    non_expected = Scenario(
        scenario_id="scenario.no-change",
        kind=ScenarioKind.NO_CHANGE,
        description="Nothing changes.",
        assumptions=("No action is taken.",),
        confidence="high",
    )
    with pytest.raises(ValueError, match="at least the expected scenario"):
        impact_result(scenarios=(non_expected,))


def test_impact_result_rejects_mismatched_sub_analysis_request_id() -> None:
    mismatched = redundancy()
    other = RedundancyAnalysis(
        change_request_id="change-request.other",
        target_entity_id=mismatched.target_entity_id,
        normal_redundancy_level=mismatched.normal_redundancy_level,
        maintenance_redundancy_level=mismatched.maintenance_redundancy_level,
        removed_by_change_entity_ids=mismatched.removed_by_change_entity_ids,
        existing_degraded_or_failed_entity_ids=mismatched.existing_degraded_or_failed_entity_ids,
        failover_eligibility=mismatched.failover_eligibility,
        failover_readiness=mismatched.failover_readiness,
        recent_failover_test_evidence_reference=(
            mismatched.recent_failover_test_evidence_reference
        ),
        shared_fate_notes=mismatched.shared_fate_notes,
        quorum_state=mismatched.quorum_state,
        remaining_path_capacity_summary=mismatched.remaining_path_capacity_summary,
        single_points_of_failure_created_entity_ids=(
            mismatched.single_points_of_failure_created_entity_ids
        ),
        evidence_references=mismatched.evidence_references,
    )
    with pytest.raises(ValueError, match="different change request"):
        impact_result(redundancy=other)


def test_impact_result_rejects_target_entity_not_named_by_change_request() -> None:
    mismatched = capacity()
    other = CapacityAndPerformanceAnalysis(
        change_request_id=mismatched.change_request_id,
        target_entity_id="target.not-in-request",
        estimates=mismatched.estimates,
        workload_concurrency_notes=mismatched.workload_concurrency_notes,
        business_peak_period_notes=mismatched.business_peak_period_notes,
        rate_limit_and_vendor_threshold_notes=mismatched.rate_limit_and_vendor_threshold_notes,
        performance_effect_of_validation_and_rollback=(
            mismatched.performance_effect_of_validation_and_rollback
        ),
        measurement_coverage=mismatched.measurement_coverage,
        measurement_age_seconds=mismatched.measurement_age_seconds,
        aggregation_limitations=mismatched.aggregation_limitations,
    )
    with pytest.raises(ValueError, match="entity the change request does not name"):
        impact_result(capacity=other)


def test_impact_result_version_1_forbids_prior_version_id() -> None:
    with pytest.raises(ValueError, match="cannot have a prior version"):
        impact_result(version=1, prior_version_id="impact-result.previous")


def test_impact_result_version_2_requires_prior_version_id() -> None:
    with pytest.raises(ValueError, match="requires prior_version_id"):
        impact_result(version=2, prior_version_id=None)


def test_impact_result_superseded_requires_successor_id() -> None:
    with pytest.raises(ValueError, match="requires the result that superseded it"):
        impact_result(supersession_state=ImpactResultSupersessionState.SUPERSEDED)


def test_impact_result_requires_retention_note() -> None:
    with pytest.raises(ValueError, match="requires a retention note"):
        impact_result(retention_note="")


def test_unknown_factor_requires_underestimation_note() -> None:
    with pytest.raises(ValueError, match="underestimating"):
        UnknownFactor(
            kind=UnknownKind.STALE_HEALTH_OR_CONFIGURATION,
            description="Health data is 2 hours old.",
            potentially_underestimated_impact_note="",
            is_critical=False,
        )


def test_blocks_recommendation_readiness_true_for_critical_unknown() -> None:
    critical = UnknownFactor(
        kind=UnknownKind.MISSING_BUSINESS_SERVICE_MAPPING,
        description="Service mapping for this volume is missing.",
        potentially_underestimated_impact_note="Business impact may be understated.",
        is_critical=True,
    )
    assert blocks_recommendation_readiness((critical,)) is True


def test_blocks_recommendation_readiness_false_without_critical_unknowns() -> None:
    non_critical = UnknownFactor(
        kind=UnknownKind.STALE_HEALTH_OR_CONFIGURATION,
        description="Health data is 2 hours old.",
        potentially_underestimated_impact_note="Redundancy state may be understated.",
        is_critical=False,
    )
    assert blocks_recommendation_readiness((non_critical,)) is False
