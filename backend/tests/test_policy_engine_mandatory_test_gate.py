from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.policy_engine.domain.lifecycle import (
    PolicyMandatoryTestFailureError,
    require_mandatory_tests_pass,
)
from atlas.modules.policy_engine.domain.models import (
    ConnectorTrustState,
    PolicyApprovalStatus,
    PolicyDecisionOutcome,
    PolicyDecisionRequest,
)
from atlas.modules.policy_engine.domain.policy_set import (
    PolicyLifecycleState,
    PolicySet,
    PolicySetLayer,
    PolicySetScope,
)
from atlas.modules.policy_engine.domain.rule import PolicyRule
from atlas.modules.policy_engine.domain.simulation import SimulationCase, simulate_policy

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
DIGEST = "e" * 64


def allow_all_policy_set() -> PolicySet:
    return PolicySet(
        set_id="policy-set.allow-all",
        version=1,
        layer=PolicySetLayer.PLATFORM,
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        scope=PolicySetScope(),
        rule_document_digest=DIGEST,
        effective_from=NOW - timedelta(days=1),
        rules=(
            PolicyRule(
                rule_id="policy-rule.allow-all",
                effect=PolicyDecisionOutcome.ALLOW,
                conditions=(),
                summary="Allow everything.",
            ),
        ),
    )


def deny_all_policy_set() -> PolicySet:
    return PolicySet(
        set_id="policy-set.deny-all",
        version=1,
        layer=PolicySetLayer.PLATFORM,
        lifecycle_state=PolicyLifecycleState.ACTIVE,
        scope=PolicySetScope(),
        rule_document_digest=DIGEST,
        effective_from=NOW - timedelta(days=1),
        rules=(
            PolicyRule(
                rule_id="policy-rule.deny-all",
                effect=PolicyDecisionOutcome.DENY,
                conditions=(),
                summary="Deny everything.",
            ),
        ),
    )


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


def test_a_mandatory_case_failing_blocks_activation() -> None:
    case = SimulationCase(
        case_id="case.mandatory-deny",
        request=request(),
        expected_outcome=PolicyDecisionOutcome.DENY,
        mandatory=True,
    )
    # allow_all_policy_set contradicts the mandatory deny expectation -- the case fails.
    result = simulate_policy((case,), (allow_all_policy_set(),), decided_at=NOW)
    with pytest.raises(PolicyMandatoryTestFailureError) as excinfo:
        require_mandatory_tests_pass(PolicyLifecycleState.ACTIVE, result)
    assert excinfo.value.failing_case_ids == ("case.mandatory-deny",)


def test_a_passing_mandatory_case_does_not_block_activation() -> None:
    case = SimulationCase(
        case_id="case.mandatory-deny",
        request=request(),
        expected_outcome=PolicyDecisionOutcome.DENY,
        mandatory=True,
    )
    result = simulate_policy((case,), (deny_all_policy_set(),), decided_at=NOW)
    require_mandatory_tests_pass(PolicyLifecycleState.ACTIVE, result)


def test_a_non_mandatory_case_failing_does_not_block_activation() -> None:
    case = SimulationCase(
        case_id="case.exploratory",
        request=request(),
        expected_outcome=PolicyDecisionOutcome.DENY,
        mandatory=False,
    )
    result = simulate_policy((case,), (allow_all_policy_set(),), decided_at=NOW)
    assert result.passed is False
    # Not mandatory, so it does not raise even though the case itself failed.
    require_mandatory_tests_pass(PolicyLifecycleState.ACTIVE, result)


def test_scheduled_is_gated_the_same_as_active() -> None:
    case = SimulationCase(
        case_id="case.mandatory-deny",
        request=request(),
        expected_outcome=PolicyDecisionOutcome.DENY,
        mandatory=True,
    )
    result = simulate_policy((case,), (allow_all_policy_set(),), decided_at=NOW)
    with pytest.raises(PolicyMandatoryTestFailureError):
        require_mandatory_tests_pass(PolicyLifecycleState.SCHEDULED, result)


@pytest.mark.parametrize(
    "state",
    [
        PolicyLifecycleState.DRAFT,
        PolicyLifecycleState.VALIDATING,
        PolicyLifecycleState.SIMULATION,
        PolicyLifecycleState.REVIEW,
        PolicyLifecycleState.APPROVED,
        PolicyLifecycleState.SUSPENDED,
        PolicyLifecycleState.DEPRECATED,
        PolicyLifecycleState.RETIRED,
    ],
)
def test_non_activating_states_are_never_gated(state: PolicyLifecycleState) -> None:
    case = SimulationCase(
        case_id="case.mandatory-deny",
        request=request(),
        expected_outcome=PolicyDecisionOutcome.DENY,
        mandatory=True,
    )
    result = simulate_policy((case,), (allow_all_policy_set(),), decided_at=NOW)
    assert result.passed is False
    require_mandatory_tests_pass(state, result)


def test_multiple_mandatory_failures_are_all_reported() -> None:
    cases = (
        SimulationCase(
            case_id="case.one",
            request=request(operation_id="operation.one"),
            expected_outcome=PolicyDecisionOutcome.DENY,
            mandatory=True,
        ),
        SimulationCase(
            case_id="case.two",
            request=request(operation_id="operation.two"),
            expected_outcome=PolicyDecisionOutcome.DENY,
            mandatory=True,
        ),
    )
    result = simulate_policy(cases, (allow_all_policy_set(),), decided_at=NOW)
    with pytest.raises(PolicyMandatoryTestFailureError) as excinfo:
        require_mandatory_tests_pass(PolicyLifecycleState.ACTIVE, result)
    assert set(excinfo.value.failing_case_ids) == {"case.one", "case.two"}
