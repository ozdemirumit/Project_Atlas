"""ATLAS-046 SS18: approval explanation.

Built directly from the already-governed `approvals.domain.models.ApprovalRecord`/`ApprovalPacket`
rather than a second capture of the same facts -- risk/impact is delegated to
`risk_impact.risk_impact_from_approval_packet` (SS16), reused rather than re-derived.

Two SS18 elements are not modeled anywhere in this codebase yet and are surfaced honestly here
rather than fabricated: an approval "stage and role required" concept (no workflow/stage model
exists on `ApprovalRecord` today -- it carries one flat `ApprovalState`, not a staged chain of
required roles), and a "revoke" action (`ApprovalOutcome` has APPROVE/REJECT/NEEDS_EVIDENCE/DEFER
only, no REVOKE).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.approvals.domain.models import (
    ApprovalOutcome,
    ApprovalPlanStep,
    ApprovalRecord,
    ApprovalState,
)
from atlas.modules.explainability.domain.risk_impact import (
    RiskImpactExplanation,
    RiskLabel,
    risk_impact_from_approval_packet,
)

_AVAILABLE_ACTIONS: dict[ApprovalState, tuple[ApprovalOutcome, ...]] = {
    ApprovalState.PENDING: (
        ApprovalOutcome.APPROVE,
        ApprovalOutcome.REJECT,
        ApprovalOutcome.NEEDS_EVIDENCE,
        ApprovalOutcome.DEFER,
    ),
    ApprovalState.NEEDS_EVIDENCE: (
        ApprovalOutcome.APPROVE,
        ApprovalOutcome.REJECT,
        ApprovalOutcome.DEFER,
    ),
    ApprovalState.DEFERRED: (
        ApprovalOutcome.APPROVE,
        ApprovalOutcome.REJECT,
        ApprovalOutcome.NEEDS_EVIDENCE,
    ),
    ApprovalState.APPROVED: (),
    ApprovalState.REJECTED: (),
    ApprovalState.EXPIRED: (),
}


def available_reviewer_actions_for(state: ApprovalState) -> tuple[ApprovalOutcome, ...]:
    """SS18: "how to reject, request evidence, defer, or revoke" -- a terminal state (approved,
    rejected, expired) has no further reviewer action available."""
    return _AVAILABLE_ACTIONS[state]


@dataclass(frozen=True, slots=True)
class ApprovalEvidenceReference:
    reference: str
    summary: str

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("an approval evidence reference requires a reference")
        if not self.summary.strip():
            raise ValueError("an approval evidence reference requires a summary")


@dataclass(frozen=True, slots=True)
class ApprovalExplanation:
    """SS18's approval view, minus the two gaps documented in this module's docstring."""

    requested_by: str
    purpose: str
    target_id: str
    bound_action: str
    plan_steps: tuple[ApprovalPlanStep, ...]
    risk_impact: RiskImpactExplanation
    evidence: tuple[ApprovalEvidenceReference, ...]
    recommendation_version: int
    option_version: int
    source_case_version: int
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    state: ApprovalState
    created_at: datetime
    expires_at: datetime
    execution_permitted: bool
    available_reviewer_actions: tuple[ApprovalOutcome, ...]

    def __post_init__(self) -> None:
        if not self.requested_by.strip():
            raise ValueError("an approval explanation requires who requested it")
        if not self.purpose.strip():
            raise ValueError("an approval explanation requires a purpose")
        if not self.bound_action.strip():
            raise ValueError("an approval explanation requires the bound action")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("approval explanation timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("approval expiry must follow creation")
        if self.execution_permitted:
            raise ValueError(
                "an approval explanation must never claim to permit execution -- approval alone"
                " never authorizes execution in this system"
            )


def explain_approval(record: ApprovalRecord, *, overall_risk: RiskLabel) -> ApprovalExplanation:
    packet = record.packet
    return ApprovalExplanation(
        requested_by=packet.requested_by,
        purpose=packet.purpose,
        target_id=packet.target_id,
        bound_action=packet.option_title,
        plan_steps=packet.plan_steps,
        risk_impact=risk_impact_from_approval_packet(packet, overall_risk=overall_risk),
        evidence=tuple(
            ApprovalEvidenceReference(reference=reference, summary=summary)
            for reference, summary in zip(
                packet.evidence_references, packet.evidence_summaries, strict=True
            )
        ),
        recommendation_version=packet.recommendation_version,
        option_version=packet.option_version,
        source_case_version=packet.source_case_version,
        assumptions=packet.assumptions,
        unknowns=packet.unknowns,
        state=record.state,
        created_at=record.created_at,
        expires_at=packet.expires_at,
        execution_permitted=False,
        available_reviewer_actions=available_reviewer_actions_for(record.state),
    )
