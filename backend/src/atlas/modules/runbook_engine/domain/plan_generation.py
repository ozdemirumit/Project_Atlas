"""ATLAS-045 SS22: interpretation and plan generation.

SS22: "material adaptation creates a derived plan and does not alter the source runbook." This is
already structurally guaranteed rather than something this module has to re-enforce:
`RunbookVersionMetadata` (slice 1) is `frozen=True`, so nothing in this codebase can mutate a
runbook version at all -- `DerivedPlan` only ever references its source by ID/version, and that
reference can never itself change the thing it points to.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class PlanOutputKind(StrEnum):
    """SS22's five plan output kinds."""

    HUMAN_CHECKLIST = "human_checklist"
    INCIDENT_DIAGNOSTIC_PLAN = "incident_diagnostic_plan"
    TARGET_SPECIFIC_RECOMMENDATION_PLAN = "target_specific_recommendation_plan"
    WORKFLOW_DRAFT = "workflow_draft"
    APPROVAL_PACKET_INPUT = "approval_packet_input"


_REQUIRES_POLICY_DECISION_BINDING = frozenset(
    {PlanOutputKind.APPROVAL_PACKET_INPUT, PlanOutputKind.WORKFLOW_DRAFT}
)


def requires_policy_decision_binding(kind: PlanOutputKind) -> bool:
    """An ATLAS-037 approval packet input and an ATLAS-023 workflow draft both bind consequential
    action to a target, so both require a resolved policy decision before they can be produced --
    a human checklist or diagnostic plan does not."""
    return kind in _REQUIRES_POLICY_DECISION_BINDING


@dataclass(frozen=True, slots=True)
class DerivedPlan:
    """SS22: "interpretation binds a runbook version to current targets, parameters, evidence,
    graph, policy, and impact analysis.\""""

    plan_id: str
    kind: PlanOutputKind
    source_runbook_id: str
    source_version_id: str
    target_id: str
    bound_parameters: tuple[tuple[str, str], ...]
    bound_evidence_references: tuple[str, ...]
    bound_policy_decision_id: str | None
    bound_impact_analysis_reference: str | None
    created_at: datetime
    created_by: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.plan_id, "plan_id")
        validate_stable_identifier(self.source_runbook_id, "source_runbook_id")
        validate_stable_identifier(self.source_version_id, "source_version_id")
        validate_stable_identifier(self.target_id, "target_id")
        if not self.created_by.strip():
            raise ValueError("a derived plan requires who created it")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if requires_policy_decision_binding(self.kind) and self.bound_policy_decision_id is None:
            raise ValueError(f"a {self.kind.value} plan requires a bound policy decision")
