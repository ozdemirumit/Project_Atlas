from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.approvals.domain.models import ApprovalPacket
from atlas.modules.explainability.domain.risk_impact import (
    RiskImpactExplanation,
    RiskLabel,
    RiskLevel,
    risk_impact_from_approval_packet,
)

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
        "unknowns": (),
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
        "preconditions": ("Redundant path confirmed healthy.",),
        "success_criteria": ("Controller B reports healthy.",),
        "verification_criteria": ("Controller B reports healthy.",),
        "stop_conditions": ("Redundant path reports degraded.",),
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


def risk_label(**overrides: object) -> RiskLabel:
    defaults: dict[str, object] = {
        "level": RiskLevel.LOW,
        "rationale": "Single-controller restart with a confirmed healthy redundant path.",
    }
    defaults.update(overrides)
    return RiskLabel(**defaults)  # type: ignore[arg-type]


def test_risk_label_requires_a_rationale() -> None:
    with pytest.raises(ValueError, match="rationale"):
        risk_label(rationale="   ")


def test_risk_impact_from_approval_packet_renders_the_packets_fields() -> None:
    explanation = risk_impact_from_approval_packet(packet(), overall_risk=risk_label())
    assert explanation.affected_components == ("controller-b",)
    assert explanation.affected_services == ("service.file-shares",)
    assert explanation.overall_risk.level is RiskLevel.LOW
    assert explanation.assumptions == ("The redundant path remains healthy throughout.",)
    assert explanation.graph_gaps == ()
    assert explanation.preconditions == ("Redundant path confirmed healthy.",)
    assert explanation.stop_conditions == ("Redundant path reports degraded.",)
    assert explanation.rollback_feasible is True


def _explanation(**overrides: object) -> RiskImpactExplanation:
    defaults: dict[str, object] = {
        "affected_components": ("controller-b",),
        "affected_services": (),
        "overall_risk": risk_label(),
        "interruption_expected_mode": "none",
        "interruption_worst_credible_mode": "brief-path-failover",
        "duration_minimum_minutes": 1,
        "duration_maximum_minutes": 5,
        "recovery_duration_minimum_minutes": 1,
        "recovery_duration_maximum_minutes": 5,
        "assumptions": (),
        "graph_gaps": (),
        "preconditions": (),
        "stop_conditions": (),
        "rollback_feasible": True,
    }
    defaults.update(overrides)
    return RiskImpactExplanation(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_explanation_constructs_cleanly() -> None:
    example = _explanation()
    assert example.overall_risk.level is RiskLevel.LOW


def test_rejects_duration_minimum_exceeding_maximum() -> None:
    with pytest.raises(ValueError, match="duration_minimum_minutes"):
        _explanation(duration_minimum_minutes=10, duration_maximum_minutes=5)


def test_rejects_negative_duration_minutes() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        _explanation(duration_minimum_minutes=-1)


def test_rejects_recovery_duration_minimum_exceeding_maximum() -> None:
    with pytest.raises(ValueError, match="recovery_duration_minimum_minutes"):
        _explanation(recovery_duration_minimum_minutes=10, recovery_duration_maximum_minutes=5)


def test_rejects_negative_recovery_duration_minutes() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        _explanation(recovery_duration_minimum_minutes=-1)


def test_rejects_blank_interruption_expected_mode() -> None:
    with pytest.raises(ValueError, match="expected interruption mode"):
        _explanation(interruption_expected_mode="   ")


def test_rejects_blank_interruption_worst_credible_mode() -> None:
    with pytest.raises(ValueError, match="worst-credible interruption mode"):
        _explanation(interruption_worst_credible_mode="   ")


def test_assumptions_and_gaps_may_be_empty() -> None:
    example = _explanation(assumptions=(), graph_gaps=())
    assert example.assumptions == ()
    assert example.graph_gaps == ()
