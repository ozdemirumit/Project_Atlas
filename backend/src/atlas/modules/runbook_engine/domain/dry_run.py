"""ATLAS-045 SS23: dry-run and simulation.

SS23 defers simulation-claim strength to "ATLAS-044 maturity levels," but ATLAS-044 (Change
Impact) has no built domain model anywhere in this codebase yet -- unlike Policy Engine,
Guardrails, and Explainability, it was not one of the four subsystems targeted this session.
`SimulationMaturityLevel` is therefore a local definition scoped to this module's own dry-run
claims, not an import of an ATLAS-044 type that does not exist -- `approvals.ApprovalPacket`'s
own `graph_maturity: str` field shows this codebase already tracks maturity as a loose string
elsewhere, so a locally-scoped enum here is a strict improvement, not a new inconsistency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class SimulationMaturityLevel(StrEnum):
    """A four-level scale for how strongly a dry-run's claims can be trusted."""

    UNVALIDATED = "unvalidated"
    STRUCTURAL_ONLY = "structural_only"
    LAB_VALIDATED = "lab_validated"
    PRODUCTION_OBSERVED = "production_observed"


class DryRunCheckKind(StrEnum):
    """SS23's eight named dry-run checks."""

    TARGET_RESOLUTION_AND_SCOPE = "target_resolution_and_scope"
    PARAMETER_TYPES_AND_REQUIRED_VALUES = "parameter_types_and_required_values"
    CONNECTOR_CAPABILITY_AVAILABILITY_AND_TRUST = "connector_capability_availability_and_trust"
    PERMISSION_POLICY_APPROVAL_AND_WINDOW = "permission_policy_approval_and_window"
    PRECONDITION_QUERY_AVAILABILITY = "precondition_query_availability"
    BRANCH_AND_TERMINAL_STATE_REACHABILITY = "branch_and_terminal_state_reachability"
    EXPECTED_ARTIFACTS_LOGS_AUDIT_AND_ITSM = "expected_artifacts_logs_audit_and_itsm"
    TARGET_SPECIFIC_IMPACT_AND_ROLLBACK_REFERENCES = (
        "target_specific_impact_and_rollback_references"
    )


class DryRunCheckResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class DryRunCheck:
    kind: DryRunCheckKind
    result: DryRunCheckResult
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("a dry-run check requires a detail statement")


@dataclass(frozen=True, slots=True)
class DryRunReport:
    """SS23: "dry-run does not prove vendor behavior." `maturity_level` makes that limitation an
    explicit, checkable field on every report rather than an implicit disclaimer a caller has to
    remember."""

    report_id: str
    plan_id: str
    checks: tuple[DryRunCheck, ...]
    maturity_level: SimulationMaturityLevel
    performed_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.report_id, "report_id")
        validate_stable_identifier(self.plan_id, "plan_id")
        if not self.checks:
            raise ValueError("a dry-run report requires at least one check")
        kinds = tuple(check.kind for check in self.checks)
        if len(set(kinds)) != len(kinds):
            raise ValueError("a dry-run report cannot evaluate the same check kind twice")
        if self.performed_at.tzinfo is None:
            raise ValueError("performed_at must be timezone-aware")

    @property
    def is_infrastructure_changing(self) -> bool:
        """SS23: "dry-run validates without changing infrastructure." Always `False` -- there is
        no field on this object through which an infrastructure mutation could be recorded."""
        return False

    @property
    def all_checks_passed(self) -> bool:
        return all(check.result is DryRunCheckResult.PASSED for check in self.checks)
