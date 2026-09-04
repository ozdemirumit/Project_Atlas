from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atlas.modules.approvals.domain.models import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalPacket,
    ApprovalRecord,
    ApprovalState,
)
from atlas.modules.policy_engine.domain.approval_binding import validate_approval_binding
from atlas.modules.policy_engine.domain.models import PolicyApprovalStatus

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
DIGEST = "b" * 64


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
        "assumptions": (),
        "unknowns": (),
        "affected_components": ("controller-b",),
        "possibly_affected_services": (),
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


def approval_record(
    *,
    state: ApprovalState = ApprovalState.APPROVED,
    reviewer_id: str = "subject.reviewer",
    approval_packet: ApprovalPacket | None = None,
) -> ApprovalRecord:
    resolved_packet = approval_packet if approval_packet is not None else packet()
    decision = ApprovalDecision(
        decision_id="approval-decision.example",
        request_version=1,
        outcome=ApprovalOutcome.APPROVE,
        reviewer_id=reviewer_id,
        decided_at=NOW - timedelta(minutes=30),
        rationale="Matches a known, resolved fault pattern.",
    )
    return ApprovalRecord(
        request_id=resolved_packet.request_id,
        version=1,
        state=state,
        packet=resolved_packet,
        created_at=NOW - timedelta(hours=1),
        updated_at=NOW - timedelta(minutes=30),
        decisions=(decision,),
        execution_authorized=False,
    )


def test_no_approval_provided() -> None:
    status = validate_approval_binding(
        target_id="target.example",
        target_organization_id="organization.example",
        target_environment_id="environment.production",
        requesting_actor_id="subject.requester",
        approval=None,
        now=NOW,
    )
    assert status is PolicyApprovalStatus.NOT_PROVIDED


def test_a_matching_approved_record_is_valid() -> None:
    status = validate_approval_binding(
        target_id="target.example",
        target_organization_id="organization.example",
        target_environment_id="environment.production",
        requesting_actor_id="subject.requester",
        approval=approval_record(),
        now=NOW,
    )
    assert status is PolicyApprovalStatus.VALID


def test_an_approval_past_its_expires_at_is_expired() -> None:
    expired_packet = packet(expires_at=NOW - timedelta(minutes=1))
    status = validate_approval_binding(
        target_id="target.example",
        target_organization_id="organization.example",
        target_environment_id="environment.production",
        requesting_actor_id="subject.requester",
        approval=approval_record(approval_packet=expired_packet),
        now=NOW,
    )
    assert status is PolicyApprovalStatus.EXPIRED


def test_a_record_already_in_expired_state_is_expired_even_before_its_packet_expiry() -> None:
    status = validate_approval_binding(
        target_id="target.example",
        target_organization_id="organization.example",
        target_environment_id="environment.production",
        requesting_actor_id="subject.requester",
        approval=approval_record(state=ApprovalState.EXPIRED),
        now=NOW,
    )
    assert status is PolicyApprovalStatus.EXPIRED


def test_a_different_target_is_mismatched() -> None:
    status = validate_approval_binding(
        target_id="target.other",
        target_organization_id="organization.example",
        target_environment_id="environment.production",
        requesting_actor_id="subject.requester",
        approval=approval_record(),
        now=NOW,
    )
    assert status is PolicyApprovalStatus.MISMATCHED


def test_a_different_organization_is_mismatched() -> None:
    status = validate_approval_binding(
        target_id="target.example",
        target_organization_id="organization.other",
        target_environment_id="environment.production",
        requesting_actor_id="subject.requester",
        approval=approval_record(),
        now=NOW,
    )
    assert status is PolicyApprovalStatus.MISMATCHED


def test_a_different_environment_is_mismatched() -> None:
    status = validate_approval_binding(
        target_id="target.example",
        target_organization_id="organization.example",
        target_environment_id="environment.staging",
        requesting_actor_id="subject.requester",
        approval=approval_record(),
        now=NOW,
    )
    assert status is PolicyApprovalStatus.MISMATCHED


def test_the_requesting_actor_reviewing_their_own_approval_is_mismatched() -> None:
    status = validate_approval_binding(
        target_id="target.example",
        target_organization_id="organization.example",
        target_environment_id="environment.production",
        requesting_actor_id="subject.requester",
        approval=approval_record(reviewer_id="subject.requester"),
        now=NOW,
    )
    assert status is PolicyApprovalStatus.MISMATCHED


def test_a_non_approved_state_is_mismatched() -> None:
    for state in (
        ApprovalState.PENDING,
        ApprovalState.REJECTED,
        ApprovalState.NEEDS_EVIDENCE,
        ApprovalState.DEFERRED,
    ):
        status = validate_approval_binding(
            target_id="target.example",
            target_organization_id="organization.example",
            target_environment_id="environment.production",
            requesting_actor_id="subject.requester",
            approval=approval_record(state=state),
            now=NOW,
        )
        assert status is PolicyApprovalStatus.MISMATCHED, state
