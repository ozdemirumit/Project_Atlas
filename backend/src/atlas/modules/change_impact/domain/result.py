"""ATLAS-044 SS21/SS22: unknowns/conservative behavior and the impact result contract.

`ImpactResult` aggregates every earlier ATLAS-044 slice rather than re-capturing any of them,
matching the aggregator pattern established across this session (Reasoning's `ReasoningArtifact`,
Decision Engine's `DecisionRecord`, Runbook Engine's `RunbookHandoffView`, Explainability's
`InvestigationPresentation`). Version-linkage mirrors those same aggregators: version 1 cannot
carry a `prior_version_id`, every later version requires one. Beyond that shared shape, this
aggregator also cross-checks that every nested analysis was actually computed for the same change
request (and, where a single target applies, a target the change request actually names) --
nothing here established that guarantee for the aggregator's caller, so the aggregator enforces it
itself. `classification`/`retention_note` were added after SS28 (security and privacy) was read in
full -- "change details and impact reports carry classification and retention" -- extending this
still-in-progress subsystem's own earlier aggregator slice, the same way Policy Engine's slice 5
broadened `PolicyDecisionRequest` mid-subsystem when a later section revealed a real gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.modules.change_impact.domain.data_protection_service import (
    DataProtectionRecoverabilityAnalysis,
    ServiceImpactRecord,
)
from atlas.modules.change_impact.domain.dimensions import ImpactDimensionAssessment
from atlas.modules.change_impact.domain.interruption_duration import (
    DurationModel,
    InterruptionModeAssessment,
)
from atlas.modules.change_impact.domain.models import ChangeRequest
from atlas.modules.change_impact.domain.redundancy_capacity import (
    CapacityAndPerformanceAnalysis,
    RedundancyAnalysis,
)
from atlas.modules.change_impact.domain.scenario_risk import (
    RiskClassification,
    Scenario,
    ScenarioKind,
)
from atlas.modules.change_impact.domain.snapshot import AnalysisSnapshot
from atlas.modules.change_impact.domain.traversal import DependencyTraversalResult
from atlas.modules.identity.domain.models import validate_stable_identifier


class UnknownKind(StrEnum):
    """SS21's eight unknown kinds."""

    UNMAPPED_OR_INACCESSIBLE_DEPENDENCIES = "unmapped_or_inaccessible_dependencies"
    STALE_HEALTH_OR_CONFIGURATION = "stale_health_or_configuration"
    UNSUPPORTED_PRODUCT_COMBINATION = "unsupported_product_combination"
    UNVERIFIED_FAILOVER_OR_RESTORE = "unverified_failover_or_restore"
    MISSING_BUSINESS_SERVICE_MAPPING = "missing_business_service_mapping"
    INCOMPLETE_PLAN_OR_ROLLBACK = "incomplete_plan_or_rollback"
    CONCURRENT_ACTIVITY_OUTSIDE_ATLAS_VISIBILITY = "concurrent_activity_outside_atlas_visibility"
    VENDOR_BEHAVIOR_NOT_COVERED_BY_EVIDENCE = "vendor_behavior_not_covered_by_evidence"


@dataclass(frozen=True, slots=True)
class UnknownFactor:
    """SS21: "Atlas shows which impacts may be underestimated" is a required field, not an
    afterthought -- an unknown cannot be recorded without stating what it may be underestimating."""

    kind: UnknownKind
    description: str
    potentially_underestimated_impact_note: str
    is_critical: bool

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("an unknown factor requires a description")
        if not self.potentially_underestimated_impact_note.strip():
            raise ValueError(
                "an unknown factor requires a note on which impact it may be underestimating"
            )


def blocks_recommendation_readiness(unknowns: tuple[UnknownFactor, ...]) -> bool:
    """SS21: "policy may block recommendation readiness when critical unknowns remain.\""""
    return any(unknown.is_critical for unknown in unknowns)


@dataclass(frozen=True, slots=True)
class ImpactComponentVersions:
    graph_snapshot_id: str
    evidence_package_version: str
    model_version: str | None
    rule_version: str | None
    schema_version: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.graph_snapshot_id, "graph_snapshot_id")
        if not self.evidence_package_version.strip():
            raise ValueError("component versions require an evidence package version")
        if not self.schema_version.strip():
            raise ValueError("component versions require a schema version")


class ImpactResultSupersessionState(StrEnum):
    """SS25 speaks of results being "recalculated or invalidated," not "expired" -- a different
    vocabulary from `decision_engine.domain.record.DecisionSupersessionState`, so this is its own
    enum rather than a reuse."""

    CURRENT = "current"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


@dataclass(frozen=True, slots=True)
class ImpactResult:
    """SS22's thirteen declared elements."""

    result_id: str
    version: int
    prior_version_id: str | None
    created_at: datetime
    change_request: ChangeRequest
    target_summary: str
    snapshot: AnalysisSnapshot
    analysis_scope_note: str
    traversal: DependencyTraversalResult
    service_impacts: tuple[ServiceImpactRecord, ...]
    redundancy: RedundancyAnalysis
    capacity: CapacityAndPerformanceAnalysis
    data_protection: DataProtectionRecoverabilityAnalysis
    dimension_assessments: tuple[ImpactDimensionAssessment, ...]
    scenarios: tuple[Scenario, ...]
    interruption_modes: tuple[InterruptionModeAssessment, ...]
    duration_model: DurationModel
    risk_classification: RiskClassification
    validation_requirements: tuple[str, ...]
    rollback_and_recovery_impact_note: str
    unknowns: tuple[UnknownFactor, ...]
    assumptions: tuple[str, ...]
    conflict_notes: tuple[str, ...]
    overall_confidence: str
    policy_approval_itsm_owner_requirements: tuple[str, ...]
    component_versions: ImpactComponentVersions
    supersession_state: ImpactResultSupersessionState
    superseded_by_result_id: str | None
    classification: DataClassification
    retention_note: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.result_id, "result_id")
        if self.version < 1:
            raise ValueError("an impact result requires a positive version")
        if self.version == 1 and self.prior_version_id is not None:
            raise ValueError("version 1 of an impact result cannot have a prior version")
        if self.version > 1 and self.prior_version_id is None:
            raise ValueError("an impact result beyond version 1 requires prior_version_id")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if not self.target_summary.strip():
            raise ValueError("an impact result requires a target summary")
        if not self.analysis_scope_note.strip():
            raise ValueError("an impact result requires an analysis scope note")
        if not self.scenarios:
            raise ValueError("an impact result requires at least one scenario")
        if ScenarioKind.EXPECTED not in {scenario.kind for scenario in self.scenarios}:
            raise ValueError("an impact result requires at least the expected scenario")
        if not self.rollback_and_recovery_impact_note.strip():
            raise ValueError("an impact result requires a rollback and recovery impact note")
        if not self.overall_confidence.strip():
            raise ValueError("an impact result requires an overall confidence")
        if not self.retention_note.strip():
            raise ValueError(
                'an impact result requires a retention note -- SS28: "change details and '
                'impact reports carry classification and retention"'
            )

        request_id = self.change_request.request_id
        for label, change_request_id in (
            ("snapshot", self.snapshot.change_request_id),
            ("traversal", self.traversal.change_request_id),
            ("redundancy", self.redundancy.change_request_id),
            ("capacity", self.capacity.change_request_id),
            ("data_protection", self.data_protection.change_request_id),
            ("duration_model", self.duration_model.change_request_id),
            ("risk_classification", self.risk_classification.change_request_id),
        ):
            if change_request_id != request_id:
                raise ValueError(
                    f"{label} was computed for a different change request than this result"
                )
        for label, target_entity_id in (
            ("redundancy", self.redundancy.target_entity_id),
            ("capacity", self.capacity.target_entity_id),
            ("data_protection", self.data_protection.target_entity_id),
            ("duration_model", self.duration_model.target_entity_id),
        ):
            if target_entity_id not in self.change_request.target_ids:
                raise ValueError(f"{label} targets an entity the change request does not name")

        is_superseded = self.supersession_state is ImpactResultSupersessionState.SUPERSEDED
        if is_superseded and self.superseded_by_result_id is None:
            raise ValueError("a superseded impact result requires the result that superseded it")
        if not is_superseded and self.superseded_by_result_id is not None:
            raise ValueError("superseded_by_result_id is only meaningful for a SUPERSEDED result")
