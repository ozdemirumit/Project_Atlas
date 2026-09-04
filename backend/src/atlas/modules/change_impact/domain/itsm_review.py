"""ATLAS-044 SS26/SS27: ITSM and approval integration, human review and override.

`ApprovalBinding` deliberately does not construct `approvals.domain.models.ApprovalPacket` itself
-- that type is built around a Recommendation Engine option (`recommendation_id`/`option_id`), and
ATLAS-044's own dependency note states "ATLAS-043 consumes impact for option comparison": Change
Impact feeds Recommendation Engine, which is the real producer of the option `ApprovalPacket`
wraps. This module instead records the exact binding facts SS26 requires an approval to pin
(version, target, plan, policy, window), for that downstream construction to reference verbatim.

`HumanCorrection` continues this session's "reference only, never mutates the source" pattern
(Decision Engine's `HumanReviewAction`, Explainability's `InvestigationAnnotation`/
`ChallengeOrCorrection`, Runbook Engine's `OperatorRecordedResult`) -- it names the new impact
result version a correction produced rather than carrying any field that could rewrite the
original.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


def itsm_approval_cures_stale_topology_or_failed_preconditions() -> bool:
    """SS26: "ITSM approval does not cure stale topology or failed preconditions.\""""
    return False


@dataclass(frozen=True, slots=True)
class ItsmAttachment:
    """SS26: "ATLAS-036 receives the immutable impact-report version or authorized reference.\""""

    impact_result_id: str
    impact_result_version: int
    itsm_change_record_reference: str
    attached_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.impact_result_id, "impact_result_id")
        if self.impact_result_version < 1:
            raise ValueError("an ITSM attachment requires a positive impact result version")
        if not self.itsm_change_record_reference.strip():
            raise ValueError("an ITSM attachment requires an ITSM change record reference")
        if self.attached_at.tzinfo is None:
            raise ValueError("attached_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ApprovalBinding:
    """SS26: "ATLAS-037 binds approval to that exact version, target, plan, policy, and window."
    `service_owner_acknowledged` and `technical_approval_granted` are two separate fields, not one
    merged flag -- "service-owner acknowledgement is distinct from technical approval where
    policy requires" as a structural property of the type's own shape."""

    impact_result_id: str
    impact_result_version: int
    target_ids: tuple[str, ...]
    plan_version: int
    policy_decision_reference: str
    maintenance_window_start: datetime
    maintenance_window_end: datetime
    service_owner_acknowledged: bool
    technical_approval_granted: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.impact_result_id, "impact_result_id")
        if self.impact_result_version < 1:
            raise ValueError("an approval binding requires a positive impact result version")
        if not self.target_ids:
            raise ValueError("an approval binding requires at least one target")
        if self.plan_version < 1:
            raise ValueError("an approval binding requires a positive plan version")
        if not self.policy_decision_reference.strip():
            raise ValueError("an approval binding requires a policy decision reference")
        if (
            self.maintenance_window_start.tzinfo is None
            or self.maintenance_window_end.tzinfo is None
        ):
            raise ValueError("the maintenance window must be timezone-aware")
        if self.maintenance_window_end < self.maintenance_window_start:
            raise ValueError("maintenance_window_end must not precede maintenance_window_start")

    @property
    def is_fully_approved(self) -> bool:
        return self.service_owner_acknowledged and self.technical_approval_granted


@dataclass(frozen=True, slots=True)
class ActualOutcomeRecord:
    """SS26: "actual impact and duration are imported for review and calibration." Feeds SS31's
    "estimated versus actual affected scope, duration, interruption, and rollback" evaluation."""

    impact_result_id: str
    actual_affected_entity_ids: tuple[str, ...]
    actual_interruption_mode: str | None
    actual_duration_minutes: int | None
    actual_service_impact_notes: tuple[str, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.impact_result_id, "impact_result_id")
        if self.actual_duration_minutes is not None and self.actual_duration_minutes < 0:
            raise ValueError("actual_duration_minutes must not be negative")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")


class HumanCorrectionKind(StrEnum):
    """SS27's six correctable elements."""

    ENTITY_MAPPING = "entity_mapping"
    SERVICE_OWNERSHIP = "service_ownership"
    ASSUMPTIONS = "assumptions"
    TIMING = "timing"
    SCENARIO = "scenario"
    HISTORICAL_COMPARISON = "historical_comparison"


@dataclass(frozen=True, slots=True)
class HumanCorrection:
    """SS27: "corrections create a new version with identity and rationale.\""""

    correction_id: str
    impact_result_id: str
    kind: HumanCorrectionKind
    corrected_by: str
    rationale: str
    resulting_impact_result_id: str
    resulting_impact_result_version: int
    corrected_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.correction_id, "correction_id")
        validate_stable_identifier(self.impact_result_id, "impact_result_id")
        validate_stable_identifier(self.resulting_impact_result_id, "resulting_impact_result_id")
        if not self.corrected_by.strip():
            raise ValueError("a human correction requires an identity")
        if not self.rationale.strip():
            raise ValueError("a human correction requires a rationale")
        if self.resulting_impact_result_version < 1:
            raise ValueError("a human correction requires a positive resulting version")
        if self.corrected_at.tzinfo is None:
            raise ValueError("corrected_at must be timezone-aware")


def accepting_residual_uncertainty_relabels_unknowns_as_safe_or_known() -> bool:
    """SS27: "Atlas preserves the unknowns and does not relabel them as safe or known.\""""
    return False


@dataclass(frozen=True, slots=True)
class ResidualUncertaintyAcceptance:
    """SS27: "a human may accept residual uncertainty through an authorized governance process."
    No field here can represent an unknown as resolved, safe, or known -- only that a named human,
    through a named process, accepted the risk of proceeding despite it."""

    impact_result_id: str
    accepted_by: str
    governance_process_reference: str
    accepted_unknowns_note: str
    accepted_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.impact_result_id, "impact_result_id")
        if not self.accepted_by.strip():
            raise ValueError("a residual uncertainty acceptance requires an identity")
        if not self.governance_process_reference.strip():
            raise ValueError(
                "a residual uncertainty acceptance requires a governance process reference"
            )
        if not self.accepted_unknowns_note.strip():
            raise ValueError("a residual uncertainty acceptance requires an unknowns note")
        if self.accepted_at.tzinfo is None:
            raise ValueError("accepted_at must be timezone-aware")
