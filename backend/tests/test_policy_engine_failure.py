from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.policy_engine.domain import failure as failure_module
from atlas.modules.policy_engine.domain.failure import (
    PolicyFailureReason,
    deny_for_failure,
    evaluate_policy_safely,
)
from atlas.modules.policy_engine.domain.models import (
    ConnectorTrustState,
    PolicyApprovalStatus,
    PolicyDecisionOutcome,
    PolicyDecisionRequest,
)
from atlas.modules.policy_engine.domain.policy_set import PolicySet

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def request(**overrides: object) -> PolicyDecisionRequest:
    defaults: dict[str, object] = {
        "decision_request_id": "policy-decision-request.example",
        "correlation_id": "correlation.example",
        "requested_at": NOW,
        "operation_id": "operation.storage.health.read",
        "is_authenticated": True,
        "is_authorized_for_scope": True,
        "actor_id": "subject.example",
        "actor_is_ai": False,
        "actor_organization_id": "organization.example",
        "actor_environment_id": "environment.production",
        "target_organization_id": "organization.example",
        "target_environment_id": "environment.production",
        "target_id": "target.example",
        "capability_class": CapabilityClass.C1_READ_ONLY,
        "connector_trust": ConnectorTrustState.TRUSTED,
        "approval_status": PolicyApprovalStatus.NOT_REQUIRED,
        "context_contains_secret": False,
        "operation_is_infrastructure_execution": False,
        "operation_is_approval": False,
        "execution_is_autonomous": False,
        "audit_required": False,
        "audit_persistence_available": True,
        "cross_boundary_explicitly_permitted": False,
    }
    defaults.update(overrides)
    return PolicyDecisionRequest(**defaults)  # type: ignore[arg-type]


def test_deny_for_failure_is_always_a_deny_with_exactly_one_reason() -> None:
    for reason in PolicyFailureReason:
        decision = deny_for_failure(
            reason,
            decision_id="policy-decision.example",
            decided_at=NOW,
            decision_request_id="policy-decision-request.example",
            correlation_id="correlation.example",
            actor_id="subject.example",
            operation_id="operation.example",
        )
        assert decision.outcome is PolicyDecisionOutcome.DENY, reason
        assert len(decision.reasons) == 1
        assert decision.reasons[0].summary.strip()


@pytest.mark.asyncio
async def test_a_policy_store_failure_resolves_to_a_store_unavailable_deny() -> None:
    async def failing_resolve() -> tuple[PolicySet, ...]:
        raise ConnectionError("policy store is down")

    decision = await evaluate_policy_safely(
        resolve_policy_sets=failing_resolve,
        request=request(),
        decision_id="policy-decision.example",
        decided_at=NOW,
    )
    assert decision.outcome is PolicyDecisionOutcome.DENY
    assert "policy store" in decision.reasons[0].summary.lower()


@pytest.mark.asyncio
async def test_a_successful_resolution_evaluates_normally() -> None:
    async def empty_resolve() -> tuple[PolicySet, ...]:
        return ()

    decision = await evaluate_policy_safely(
        resolve_policy_sets=empty_resolve,
        request=request(),
        decision_id="policy-decision.example",
        decided_at=NOW,
    )
    # No policy sets resolved -> deny-by-default (evaluate_policy's own SS3 behavior), not a
    # failure path -- this is a real evaluated decision, distinguishable from a failure deny by
    # its reason text.
    assert decision.outcome is PolicyDecisionOutcome.DENY
    assert "denies by default" in decision.reasons[0].summary


@pytest.mark.asyncio
async def test_an_evaluation_error_resolves_to_an_evaluation_error_deny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def empty_resolve() -> tuple[PolicySet, ...]:
        return ()

    def raising_evaluate_policy(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("unexpected evaluation failure")

    monkeypatch.setattr(failure_module, "evaluate_policy", raising_evaluate_policy)

    decision = await evaluate_policy_safely(
        resolve_policy_sets=empty_resolve,
        request=request(),
        decision_id="policy-decision.example",
        decided_at=NOW,
    )
    assert decision.outcome is PolicyDecisionOutcome.DENY
    assert "evaluation failed" in decision.reasons[0].summary.lower()


@pytest.mark.asyncio
async def test_a_non_authenticated_request_still_denies_through_the_normal_path() -> None:
    async def empty_resolve() -> tuple[PolicySet, ...]:
        return ()

    decision = await evaluate_policy_safely(
        resolve_policy_sets=empty_resolve,
        request=request(is_authenticated=False),
        decision_id="policy-decision.example",
        decided_at=NOW,
    )
    assert decision.outcome is PolicyDecisionOutcome.DENY
    assert decision.non_overridable_rule_references
