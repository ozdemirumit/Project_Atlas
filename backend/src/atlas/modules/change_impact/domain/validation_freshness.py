"""ATLAS-044 SS24/SS25: validation and review, freshness and recalculation.

`ValidationCheck` gives SS24's eight-item checklist a real, enumerable shape rather than free-form
prose review notes -- each check is a named, individually pass/fail item, so "domain and service
owners review consequential analyses before formal approval" has a concrete artifact to review.
`RecalculationTrigger` (SS25) is the structural home for plan-step analysis's own deferred
"reordering requires a new plan and impact version" and "parameter or target changes invalidate
affected analysis" rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ValidationCheckKind(StrEnum):
    """SS24's eight automated validation checks."""

    EVERY_TARGET_RESOLVES_TO_CURRENT_AUTHORIZED_INVENTORY = (
        "every_target_resolves_to_current_authorized_inventory"
    )
    GRAPH_TRAVERSAL_IS_BOUNDED_AND_CITES_RELATIONSHIP_PATHS = (
        "graph_traversal_is_bounded_and_cites_relationship_paths"
    )
    REQUIRED_IMPACT_DIMENSIONS_AND_SCENARIOS_ARE_PRESENT = (
        "required_impact_dimensions_and_scenarios_are_present"
    )
    UNITS_RANGES_FORMULAS_AND_TIMESTAMPS_ARE_CONSISTENT = (
        "units_ranges_formulas_and_timestamps_are_consistent"
    )
    HIDDEN_ENTITIES_ARE_NOT_LEAKED = "hidden_entities_are_not_leaked"
    POLICY_REQUIRED_SERVICE_OWNERS_AND_APPROVALS_ARE_IDENTIFIED = (
        "policy_required_service_owners_and_approvals_are_identified"
    )
    PLAN_AND_ROLLBACK_VERSIONS_MATCH_THE_RECOMMENDATION = (
        "plan_and_rollback_versions_match_the_recommendation"
    )
    CRITICAL_UNKNOWNS_PREVENT_UNSUPPORTED_SAFETY_CLAIMS = (
        "critical_unknowns_prevent_unsupported_safety_claims"
    )


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    kind: ValidationCheckKind
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("a validation check requires a detail")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """SS24's automated checklist, plus "domain and service owners review consequential analyses
    before formal approval" as an explicit, required-when-consequential review record."""

    impact_result_id: str
    checks: tuple[ValidationCheck, ...]
    is_consequential: bool
    domain_owner_reviewed: bool
    service_owner_reviewed: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.impact_result_id, "impact_result_id")
        if not self.checks:
            raise ValueError("a validation report requires at least one check")
        kinds = [check.kind for check in self.checks]
        if len(kinds) != len(set(kinds)):
            raise ValueError("a validation report must not repeat a check kind")

    @property
    def all_checks_passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def is_ready_for_formal_approval(self) -> bool:
        """SS24: "domain and service owners review consequential analyses before formal
        approval." A non-consequential analysis needs only its automated checks to pass."""
        if not self.all_checks_passed:
            return False
        if not self.is_consequential:
            return True
        return self.domain_owner_reviewed and self.service_owner_reviewed


class RecalculationTrigger(StrEnum):
    """SS25's six recalculation/invalidation trigger categories."""

    TARGET_PARAMETER_PLAN_ORDER_OR_ROLLBACK_CHANGE = (
        "target_parameter_plan_order_or_rollback_change"
    )
    TOPOLOGY_HEALTH_CAPACITY_REDUNDANCY_PROTECTION_OR_SERVICE_MAPPING_CHANGE = (
        "topology_health_capacity_redundancy_protection_or_service_mapping_change"
    )
    NEW_INCIDENT_ALERT_MAINTENANCE_OR_CONFLICTING_CHANGE = (
        "new_incident_alert_maintenance_or_conflicting_change"
    )
    PRODUCT_CONNECTOR_RUNBOOK_RULE_OR_SIMULATION_VERSION_CHANGE = (
        "product_connector_runbook_rule_or_simulation_version_change"
    )
    CHANGE_WINDOW_OR_BUSINESS_CALENDAR_CHANGE = "change_window_or_business_calendar_change"
    EVIDENCE_EXCEEDS_RISK_BASED_FRESHNESS_LIMIT = "evidence_exceeds_risk_based_freshness_limit"


@dataclass(frozen=True, slots=True)
class RecalculationEvent:
    """SS25: "the result shows which sections changed and why" -- `changed_section_notes` is
    required, not optional, so a recalculation can never be recorded without stating what
    changed."""

    impact_result_id: str
    trigger: RecalculationTrigger
    detail: str
    changed_section_notes: tuple[str, ...]
    is_invalidation: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.impact_result_id, "impact_result_id")
        if not self.detail.strip():
            raise ValueError("a recalculation event requires a detail")
        if not self.changed_section_notes:
            raise ValueError("a recalculation event requires which sections changed and why")
