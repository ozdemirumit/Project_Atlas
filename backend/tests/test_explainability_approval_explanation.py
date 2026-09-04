from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.approvals.domain.models import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalPacket,
    ApprovalRecord,
    ApprovalState,
)
from atlas.modules.explainability.domain.approval_explanation import (
    ApprovalExplanation,
    available_reviewer_actions_for,
    explain_approval,
)
from atlas.modules.explainability.domain.risk_impact import RiskLabel, RiskLevel

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


def packet(**overrides: object) -> ApprovalPacket:
    defaults: dict[str, object] = {
        "request_id": "approval-request.example",
        "packet_version": 1,
        "canonicalization_version": "atlas.approval-packet.v1",
        "canonical_digest": DIGEST,
        "requested_by": "subject.requester",
        "purpose": "Restart a degraded storage controller.",
        "created_at": NOW - timedelta(hours=1),
        "expires_at": NOW + timedelta(hours=1),
        "organization_id": "organization.example",
        "environment_id": "environment.production",
        "site_id": "site.example",
        "target_id": "target.example",
        "recommendation_id": "recommendation.example",
        "recommendation_version": 1,
        "source_case_id": "case.example",
        "source_case_version": 1,
        "option_id": "option.example",
        "option_version": 1,
        "option_title": "Restart controller B.",
        "option_category": "remediation",
        "option_confidence": "high",
        "confidence_rationale": "Matches a known, resolved fault pattern.",
        "overall_risk": "low",
        "risk_rationales": ("Read-only diagnostics preceded this option.",),
        "evidence_references": ("evidence.example",),
        "evidence_summaries": ("Controller B reports degraded state.",),
        "alternatives": (),
        "assumptions": ("The redundant path remains healthy throughout.",),
        "unknowns": ("Whether the firmware bug also affects controller A.",),
        "affected_components": ("controller-b",),
        "possibly_affected_services": ("service.file-shares",),
        "blast_radius": "single-controller",
        "impact_confirmed": True,
        "graph_maturity": "complete",
        "impact_gaps": (),
        "duration_minimum_minutes": 1,
        "duration_maximum_minutes": 5,
        "duration_basis": "vendor-documented restart time",
        "interruption_expected_mode": "none",
        "interruption_worst_credible_mode": "brief-path-failover",
        "interruption_expected_minutes": (0, 0),
        "interruption_worst_credible_minutes": (0, 1),
        "interruption_unknowns": (),
        "plan_steps": (),
        "preconditions": (),
        "success_criteria": ("Controller B reports healthy.",),
        "verification_criteria": ("Controller B reports healthy.",),
        "stop_conditions": (),
        "recovery_strategy": "Failback to controller A if restart fails.",
        "rollback_feasible": True,
        "recovery_duration_minimum_minutes": 1,
        "recovery_duration_maximum_minutes": 5,
        "recovery_gaps": (),
        "policy_constraints": (),
        "execution_authorized": False,
    }
    defaults.update(overrides)
    return ApprovalPacket(**defaults)  # type: ignore[arg-type]


def record(**overrides: object) -> ApprovalRecord:
    defaults: dict[str, object] = {
        "request_id": "approval-request.example",
        "version": 1,
        "state": ApprovalState.PENDING,
        "packet": packet(),
        "created_at": NOW - timedelta(hours=1),
        "updated_at": NOW - timedelta(hours=1),
        "decisions": (),
        "execution_authorized": False,
    }
    defaults.update(overrides)
    return ApprovalRecord(**defaults)  # type: ignore[arg-type]


def risk_label(**overrides: object) -> RiskLabel:
    defaults: dict[str, object] = {
        "level": RiskLevel.LOW,
        "rationale": "Single-controller restart with a confirmed healthy redundant path.",
    }
    defaults.update(overrides)
    return RiskLabel(**defaults)  # type: ignore[arg-type]


def test_explain_approval_surfaces_who_why_and_bound_action() -> None:
    explanation = explain_approval(record(), overall_risk=risk_label())
    assert explanation.requested_by == "subject.requester"
    assert explanation.purpose == "Restart a degraded storage controller."
    assert explanation.target_id == "target.example"
    assert explanation.bound_action == "Restart controller B."


def test_explain_approval_surfaces_evidence_with_summaries() -> None:
    explanation = explain_approval(record(), overall_risk=risk_label())
    assert len(explanation.evidence) == 1
    assert explanation.evidence[0].reference == "evidence.example"
    assert explanation.evidence[0].summary == "Controller B reports degraded state."


def test_explain_approval_surfaces_assumptions_and_unknowns() -> None:
    explanation = explain_approval(record(), overall_risk=risk_label())
    assert explanation.assumptions == ("The redundant path remains healthy throughout.",)
    assert explanation.unknowns == ("Whether the firmware bug also affects controller A.",)


def test_explain_approval_never_permits_execution() -> None:
    explanation = explain_approval(record(), overall_risk=risk_label())
    assert explanation.execution_permitted is False


def test_explain_approval_carries_the_risk_impact_explanation() -> None:
    explanation = explain_approval(record(), overall_risk=risk_label())
    assert explanation.risk_impact.affected_components == ("controller-b",)
    assert explanation.risk_impact.overall_risk.level is RiskLevel.LOW


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            ApprovalState.PENDING,
            (
                ApprovalOutcome.APPROVE,
                ApprovalOutcome.REJECT,
                ApprovalOutcome.NEEDS_EVIDENCE,
                ApprovalOutcome.DEFER,
            ),
        ),
        (
            ApprovalState.NEEDS_EVIDENCE,
            (ApprovalOutcome.APPROVE, ApprovalOutcome.REJECT, ApprovalOutcome.DEFER),
        ),
        (
            ApprovalState.DEFERRED,
            (ApprovalOutcome.APPROVE, ApprovalOutcome.REJECT, ApprovalOutcome.NEEDS_EVIDENCE),
        ),
        (ApprovalState.APPROVED, ()),
        (ApprovalState.REJECTED, ()),
        (ApprovalState.EXPIRED, ()),
    ],
)
def test_available_reviewer_actions_for_every_state(
    state: ApprovalState, expected: tuple[ApprovalOutcome, ...]
) -> None:
    assert available_reviewer_actions_for(state) == expected


def test_a_terminal_state_carries_no_available_actions_in_the_explanation() -> None:
    explanation = explain_approval(
        record(
            state=ApprovalState.APPROVED,
            decisions=(
                ApprovalDecision(
                    decision_id="decision.example",
                    request_version=1,
                    outcome=ApprovalOutcome.APPROVE,
                    reviewer_id="subject.reviewer",
                    decided_at=NOW,
                    rationale="Matches known-good remediation pattern.",
                ),
            ),
        ),
        overall_risk=risk_label(),
    )
    assert explanation.available_reviewer_actions == ()


def _explanation(**overrides: object) -> ApprovalExplanation:
    base = explain_approval(record(), overall_risk=risk_label())
    defaults: dict[str, object] = {
        "requested_by": base.requested_by,
        "purpose": base.purpose,
        "target_id": base.target_id,
        "bound_action": base.bound_action,
        "plan_steps": base.plan_steps,
        "risk_impact": base.risk_impact,
        "evidence": base.evidence,
        "recommendation_version": base.recommendation_version,
        "option_version": base.option_version,
        "source_case_version": base.source_case_version,
        "assumptions": base.assumptions,
        "unknowns": base.unknowns,
        "state": base.state,
        "created_at": base.created_at,
        "expires_at": base.expires_at,
        "execution_permitted": base.execution_permitted,
        "available_reviewer_actions": base.available_reviewer_actions,
    }
    defaults.update(overrides)
    return ApprovalExplanation(**defaults)  # type: ignore[arg-type]


def test_rejects_blank_requested_by() -> None:
    with pytest.raises(ValueError, match="who requested"):
        _explanation(requested_by="   ")


def test_rejects_blank_purpose() -> None:
    with pytest.raises(ValueError, match="purpose"):
        _explanation(purpose="   ")


def test_rejects_blank_bound_action() -> None:
    with pytest.raises(ValueError, match="bound action"):
        _explanation(bound_action="   ")


def test_rejects_expiry_before_creation() -> None:
    with pytest.raises(ValueError, match="expiry must follow creation"):
        _explanation(expires_at=NOW - timedelta(hours=2))


def test_rejects_execution_permitted_true() -> None:
    with pytest.raises(ValueError, match="never authorizes execution"):
        _explanation(execution_permitted=True)
