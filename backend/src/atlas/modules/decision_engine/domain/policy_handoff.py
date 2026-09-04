"""ATLAS-024 SS16: policy handoff.

Reuses Policy Engine's `PolicyDecisionRequest`/`PolicyDecision` directly for the actual policy
evaluation -- SS16's "capability and class," "exact target," "environment," and "approval state"
are already `PolicyDecisionRequest`'s own fields. This module adds only what SS16 asks for beyond
that request shape: candidate/plan version, exact parameters, evidence/impact references, time
window, change record, and proposed safeguards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.policy_engine.domain.models import PolicyDecision, PolicyDecisionRequest


@dataclass(frozen=True, slots=True)
class PolicyHandoffRequest:
    candidate_id: str
    plan_version: int
    policy_request: PolicyDecisionRequest
    exact_parameters: tuple[tuple[str, str], ...]
    evidence_references: tuple[str, ...]
    impact_references: tuple[str, ...]
    time_window_start: datetime
    time_window_end: datetime
    change_record_reference: str | None
    proposed_safeguards: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.candidate_id, "candidate_id")
        if self.plan_version < 1:
            raise ValueError("a policy handoff request requires a positive plan version")
        if self.time_window_start.tzinfo is None or self.time_window_end.tzinfo is None:
            raise ValueError("the time window must be timezone-aware")
        if self.time_window_end < self.time_window_start:
            raise ValueError("time_window_end must not precede time_window_start")


@dataclass(frozen=True, slots=True)
class PolicyHandoffRecord:
    """SS16: "Policy returns allow, deny, or conditions. The Decision Engine records the outcome
    but cannot alter it." Frozen, and carries the real `PolicyDecision` verbatim -- there is no
    field through which this record could represent an outcome other than what Policy Engine
    actually returned."""

    request: PolicyHandoffRequest
    decision: PolicyDecision
    recorded_at: datetime

    def __post_init__(self) -> None:
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
