from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.policy_engine.domain.default_capability_policies import (
    DEFAULT_CAPABILITY_POLICY_SET_ID,
    DEFAULT_CAPABILITY_RULES,
    default_capability_policy_set,
)
from atlas.modules.policy_engine.domain.evaluation import evaluate_policy
from atlas.modules.policy_engine.domain.models import (
    ConnectorTrustState,
    PolicyApprovalStatus,
    PolicyDecisionOutcome,
    PolicyDecisionRequest,
)
from atlas.modules.policy_engine.domain.rule import compute_rule_document_digest

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


def decide(policy_request: PolicyDecisionRequest) -> PolicyDecisionOutcome:
    policy_set = default_capability_policy_set(effective_from=NOW - timedelta(days=1))
    decision = evaluate_policy(
        policy_request,
        (policy_set,),
        decision_id="policy-decision.example",
        decided_at=NOW,
    )
    return decision.outcome


def test_c0_is_allowed() -> None:
    assert decide(request(capability_class=CapabilityClass.C0_INFORMATIONAL)) is (
        PolicyDecisionOutcome.ALLOW
    )


def test_c1_is_allowed_through_a_trusted_connector() -> None:
    assert (
        decide(
            request(
                capability_class=CapabilityClass.C1_READ_ONLY,
                connector_trust=ConnectorTrustState.TRUSTED,
            )
        )
        is PolicyDecisionOutcome.ALLOW
    )


def test_c1_is_denied_by_default_through_an_untrusted_connector() -> None:
    # No allow rule matches (connector not trusted) and no deny rule matches either -- SS3's
    # deny-by-default applies since nothing explicitly grants the operation.
    assert (
        decide(
            request(
                capability_class=CapabilityClass.C1_READ_ONLY,
                connector_trust=ConnectorTrustState.UNTRUSTED,
            )
        )
        is PolicyDecisionOutcome.DENY
    )


def test_c2_requires_additional_evidence() -> None:
    assert decide(request(capability_class=CapabilityClass.C2_DIAGNOSTIC)) is (
        PolicyDecisionOutcome.REQUIRE_ADDITIONAL_EVIDENCE
    )


def test_c3_is_denied_without_a_valid_approval() -> None:
    for status in (
        PolicyApprovalStatus.NOT_REQUIRED,
        PolicyApprovalStatus.NOT_PROVIDED,
    ):
        outcome = decide(
            request(capability_class=CapabilityClass.C3_CONTROLLED_CHANGE, approval_status=status)
        )
        assert outcome is PolicyDecisionOutcome.DENY, status


def test_c3_is_allowed_with_a_valid_approval() -> None:
    assert (
        decide(
            request(
                capability_class=CapabilityClass.C3_CONTROLLED_CHANGE,
                approval_status=PolicyApprovalStatus.VALID,
            )
        )
        is PolicyDecisionOutcome.ALLOW
    )


def test_c4_is_denied_without_a_valid_approval() -> None:
    assert (
        decide(
            request(
                capability_class=CapabilityClass.C4_SERVICE_IMPACTING,
                approval_status=PolicyApprovalStatus.NOT_PROVIDED,
            )
        )
        is PolicyDecisionOutcome.DENY
    )


def test_c4_is_allowed_with_a_valid_approval() -> None:
    assert (
        decide(
            request(
                capability_class=CapabilityClass.C4_SERVICE_IMPACTING,
                approval_status=PolicyApprovalStatus.VALID,
            )
        )
        is PolicyDecisionOutcome.ALLOW
    )


def test_c5_requires_manual_execution_even_when_not_autonomous() -> None:
    assert (
        decide(
            request(capability_class=CapabilityClass.C5_DESTRUCTIVE, execution_is_autonomous=False)
        )
        is PolicyDecisionOutcome.REQUIRE_MANUAL_EXECUTION
    )


def test_autonomous_c5_is_denied_before_the_default_matrix_is_even_consulted() -> None:
    # The non-overridable minimum catches this first (slice 1); the default matrix never runs.
    assert (
        decide(
            request(capability_class=CapabilityClass.C5_DESTRUCTIVE, execution_is_autonomous=True)
        )
        is PolicyDecisionOutcome.DENY
    )


def test_the_default_policy_set_is_platform_layer_active_and_universally_scoped() -> None:
    policy_set = default_capability_policy_set(effective_from=NOW)
    assert policy_set.set_id == DEFAULT_CAPABILITY_POLICY_SET_ID
    assert policy_set.rules == DEFAULT_CAPABILITY_RULES


def test_the_rule_document_digest_is_deterministic() -> None:
    first = compute_rule_document_digest(DEFAULT_CAPABILITY_RULES)
    second = compute_rule_document_digest(DEFAULT_CAPABILITY_RULES)
    assert first == second
    assert len(first) == 64


def test_a_different_rule_set_produces_a_different_digest() -> None:
    digest = compute_rule_document_digest(DEFAULT_CAPABILITY_RULES)
    digest_without_last_rule = compute_rule_document_digest(DEFAULT_CAPABILITY_RULES[:-1])
    assert digest != digest_without_last_rule


@pytest.mark.parametrize("capability_class", list(CapabilityClass))
def test_every_capability_class_has_at_least_one_default_rule(
    capability_class: CapabilityClass,
) -> None:
    matching = [
        r
        for r in DEFAULT_CAPABILITY_RULES
        if any(
            c.field.value == "capability_class" and capability_class.value in c.values
            for c in r.conditions
        )
    ]
    assert matching, f"{capability_class} has no default rule"
