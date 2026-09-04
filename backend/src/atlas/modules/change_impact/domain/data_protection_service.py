"""ATLAS-044 SS13/SS14: data protection/recoverability and service/business impact.

SS13's own closing line -- "backup existence alone does not make a destructive change safe" --
gets a concrete call site the same way this session has repeatedly given absolute prose rules one:
a hardcoded function with no parameters to override. `ServiceImpactRecord` (SS14) is a new type,
not a reuse of `change_impact.domain.snapshot.ServiceCriticalityRecord` -- that type is raw
observed criticality/ownership captured at snapshot time; this one is the actual per-service
analysis result (expected impact mode, interruption range, confidence) computed from it.

SS14's "hidden or unauthorized service details are summarized without leaking names or
relationships" is not given a redaction function here: `supporting_graph_path_entity_ids` can only
ever reference entities the caller already pulled from an access-filtered
`graph.domain.models.GraphSnapshot`/`change_impact.domain.snapshot.AnalysisSnapshot` (both carry
`allowed_principals` per entity), so access control is already enforced upstream of this type
rather than needing a second mechanism here.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.identity.domain.models import validate_stable_identifier


def backup_existence_alone_makes_a_destructive_change_safe() -> bool:
    """SS13: "backup existence alone does not make a destructive change safe.\""""
    return False


@dataclass(frozen=True, slots=True)
class DataProtectionRecoverabilityAnalysis:
    change_request_id: str
    target_entity_id: str
    backup_recency: str
    backup_status: str
    backup_scope: str
    backup_immutable: bool
    relevant_restore_evidence_reference: str | None
    replication_mode: str | None
    replication_lag_seconds: float | None
    replication_consistency: str | None
    replication_failover_state: str | None
    snapshot_and_retention_consequences: tuple[str, ...]
    write_ordering_and_consistency_notes: str
    split_brain_or_divergence_risk: str | None
    recovery_point_objective_seconds: int | None
    recovery_time_objective_seconds: int | None
    point_of_no_return_description: str | None
    is_rollback_available: bool
    is_recovery_available: bool
    legal_hold_or_retention_constraint: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.change_request_id, "change_request_id")
        validate_stable_identifier(self.target_entity_id, "target_entity_id")
        if not self.backup_recency.strip():
            raise ValueError("a data protection analysis requires backup recency")
        if not self.backup_status.strip():
            raise ValueError("a data protection analysis requires backup status")
        if not self.backup_scope.strip():
            raise ValueError("a data protection analysis requires backup scope")
        if not self.write_ordering_and_consistency_notes.strip():
            raise ValueError("a data protection analysis requires write ordering notes")
        if self.replication_lag_seconds is not None and self.replication_lag_seconds < 0:
            raise ValueError("replication_lag_seconds must not be negative")
        if (
            self.recovery_point_objective_seconds is not None
            and self.recovery_point_objective_seconds < 0
        ):
            raise ValueError("recovery_point_objective_seconds must not be negative")
        if (
            self.recovery_time_objective_seconds is not None
            and self.recovery_time_objective_seconds < 0
        ):
            raise ValueError("recovery_time_objective_seconds must not be negative")
        if not self.is_rollback_available and not self.is_recovery_available:
            raise ValueError(
                "a destructive change with neither rollback nor recovery available must be "
                "flagged explicitly, not silently modeled as safe"
            )


@dataclass(frozen=True, slots=True)
class ServiceImpactRecord:
    """SS14's per-service report."""

    service_id: str
    service_name: str
    owner: str
    criticality: str
    supporting_graph_path_entity_ids: tuple[str, ...]
    expected_impact_mode: str
    affected_function: str
    user_or_location_scope: str | None
    expected_interruption_minimum_minutes: int
    expected_interruption_maximum_minutes: int
    worst_credible_interruption_minimum_minutes: int
    worst_credible_interruption_maximum_minutes: int
    degradation_and_recovery_dependencies: tuple[str, ...]
    relevant_sla_or_calendar_context: str | None
    confidence: str
    is_confidence_reduced_by_missing_service_mapping: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.service_id, "service_id")
        if not self.service_name.strip():
            raise ValueError("a service impact record requires a service name")
        if not self.owner.strip():
            raise ValueError("a service impact record requires an owner")
        if not self.criticality.strip():
            raise ValueError("a service impact record requires a criticality")
        if not self.supporting_graph_path_entity_ids:
            raise ValueError("a service impact record requires a supporting graph path")
        if not self.expected_impact_mode.strip():
            raise ValueError("a service impact record requires an expected impact mode")
        for field_name, minimum, maximum in (
            (
                "expected_interruption",
                self.expected_interruption_minimum_minutes,
                self.expected_interruption_maximum_minutes,
            ),
            (
                "worst_credible_interruption",
                self.worst_credible_interruption_minimum_minutes,
                self.worst_credible_interruption_maximum_minutes,
            ),
        ):
            if minimum < 0 or maximum < 0:
                raise ValueError(f"{field_name} minutes must not be negative")
            if minimum > maximum:
                raise ValueError(f"{field_name} minimum must not exceed maximum")
        if not self.confidence.strip():
            raise ValueError("a service impact record requires a confidence")
