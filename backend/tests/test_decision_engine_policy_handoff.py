from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.decision_engine.domain.policy_handoff import (
    PolicyHandoffRecord,
    PolicyHandoffRequest,
)
from atlas.modules.policy_engine.domain.models import (
    ConnectorTrustState,
    PolicyApprovalStatus,
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyDecisionRequest,
    PolicyReason,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def policy_request(**overrides: object) -> PolicyDecisionRequest:
    defaults: dict[str, object] = {
        "decision_request_id": "policy-decision-request.example",
        "correlation_id": "correlation.example",
        "requested_at": NOW,
        "operation_id": "operation.restart-controller",
        "is_authenticated": True,
        "is_authorized_for_scope": True,
        "actor_id": "subject.requester",
        "actor_is_ai": False,
        "actor_organization_id": "organization.example",
        "actor_environment_id": "environment.production",
        "target_organization_id": "organization.example",
        "target_environment_id": "environment.production",
        "target_id": "target.example",
        "capability_class": CapabilityClass.C3_CONTROLLED_CHANGE,
        "connector_trust": ConnectorTrustState.TRUSTED,
        "approval_status": PolicyApprovalStatus.NOT_REQUIRED,
        "context_contains_secret": False,
        "operation_is_infrastructure_execution": False,
        "operation_is_approval": False,
        "execution_is_autonomous": False,
        "audit_required": True,
        "audit_persistence_available": True,
        "cross_boundary_explicitly_permitted": False,
    }
    defaults.update(overrides)
    return PolicyDecisionRequest(**defaults)  # type: ignore[arg-type]


def request(**overrides: object) -> PolicyHandoffRequest:
    defaults: dict[str, object] = {
        "candidate_id": "decision-candidate.example",
        "plan_version": 1,
        "policy_request": policy_request(),
        "exact_parameters": (("controller_id", "controller-b"),),
        "evidence_references": ("evidence.example",),
        "impact_references": ("decision-impact-assessment.example",),
        "time_window_start": NOW,
        "time_window_end": NOW + timedelta(hours=1),
        "change_record_reference": None,
        "proposed_safeguards": ("Dry-run validation before execution.",),
    }
    defaults.update(overrides)
    return PolicyHandoffRequest(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_request_constructs_cleanly() -> None:
    example = request()
    assert example.plan_version == 1


def test_rejects_non_positive_plan_version() -> None:
    with pytest.raises(ValueError, match="positive plan version"):
        request(plan_version=0)


def test_rejects_naive_time_window() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        request(time_window_start=NOW.replace(tzinfo=None))


def test_rejects_time_window_end_before_start() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        request(time_window_start=NOW, time_window_end=NOW - timedelta(hours=1))


def policy_decision(**overrides: object) -> PolicyDecision:
    defaults: dict[str, object] = {
        "decision_id": "policy-decision.example",
        "decided_at": NOW,
        "outcome": PolicyDecisionOutcome.REQUIRE_APPROVAL,
        "reasons": (),
        "decision_request_id": "policy-decision-request.example",
        "correlation_id": "correlation.example",
        "actor_id": "subject.requester",
        "operation_id": "operation.restart-controller",
        "non_overridable_rule_references": (),
        "evaluated_policy_set_versions": (),
        "additional_conditions": (),
    }
    defaults.update(overrides)
    return PolicyDecision(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_record_constructs_cleanly() -> None:
    example = PolicyHandoffRecord(request=request(), decision=policy_decision(), recorded_at=NOW)
    assert example.decision.outcome is PolicyDecisionOutcome.REQUIRE_APPROVAL


def test_record_rejects_naive_recorded_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PolicyHandoffRecord(
            request=request(), decision=policy_decision(), recorded_at=NOW.replace(tzinfo=None)
        )


def test_record_carries_the_real_policy_decision_verbatim() -> None:
    decision = policy_decision(
        outcome=PolicyDecisionOutcome.DENY,
        reasons=(PolicyReason(summary="No policy rule permits this operation."),),
    )
    example = PolicyHandoffRecord(request=request(), decision=decision, recorded_at=NOW)
    assert example.decision is decision


def test_record_is_frozen() -> None:
    example = PolicyHandoffRecord(request=request(), decision=policy_decision(), recorded_at=NOW)
    with pytest.raises(AttributeError):
        example.decision = policy_decision(outcome=PolicyDecisionOutcome.ALLOW)  # type: ignore[misc]
