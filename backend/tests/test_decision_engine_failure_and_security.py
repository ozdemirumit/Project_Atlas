from __future__ import annotations

import pytest

from atlas.modules.decision_engine.domain.failure_and_security import (
    DecisionFailureBehavior,
    DecisionFailureKind,
    SecurityPrivacyRequirement,
    evidence_and_model_output_are_trusted_by_default,
    is_cross_organization_or_environment_decision,
    required_behavior_for,
)


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            DecisionFailureKind.EVIDENCE_UNAVAILABLE,
            DecisionFailureBehavior.RETURN_INSUFFICIENT_EVIDENCE_AND_NEXT_STEP,
        ),
        (
            DecisionFailureKind.GRAPH_STALE_OR_INCOMPLETE,
            DecisionFailureBehavior.LIMIT_IMPACT_CLAIM_AND_IDENTIFY_UNKNOWN_BLAST_RADIUS,
        ),
        (
            DecisionFailureKind.AI_UNAVAILABLE,
            DecisionFailureBehavior.RETURN_DETERMINISTIC_FINDINGS_DEGRADED,
        ),
        (
            DecisionFailureKind.RULE_FAILURE,
            DecisionFailureBehavior.EXCLUDE_RULE_AND_DISCLOSE_INCOMPLETE,
        ),
        (
            DecisionFailureKind.CONFLICTING_EVIDENCE,
            DecisionFailureBehavior.PRESERVE_CONFLICT_AND_REDUCE_CONFIDENCE,
        ),
        (DecisionFailureKind.POLICY_UNAVAILABLE, DecisionFailureBehavior.DO_NOT_PRESENT_AS_ALLOWED),
        (
            DecisionFailureKind.OUTPUT_INVALID,
            DecisionFailureBehavior.BOUNDED_REPAIR_OR_FAIL_WITHOUT_PUBLISHING,
        ),
        (
            DecisionFailureKind.AUDIT_REQUIRED_BUT_UNAVAILABLE,
            DecisionFailureBehavior.FAIL_CLOSED_PER_TASK_POLICY,
        ),
    ],
)
def test_required_behavior_for_every_failure_kind(
    failure: DecisionFailureKind, expected: DecisionFailureBehavior
) -> None:
    assert required_behavior_for(failure) is expected


def test_every_failure_kind_has_a_required_behavior() -> None:
    for failure in DecisionFailureKind:
        required_behavior_for(failure)


def test_is_cross_organization_decision_true_for_different_organizations() -> None:
    assert (
        is_cross_organization_or_environment_decision(
            actor_organization_id="organization.a",
            actor_environment_id="environment.production",
            target_organization_id="organization.b",
            target_environment_id="environment.production",
        )
        is True
    )


def test_is_cross_environment_decision_true_for_different_environments() -> None:
    assert (
        is_cross_organization_or_environment_decision(
            actor_organization_id="organization.a",
            actor_environment_id="environment.production",
            target_organization_id="organization.a",
            target_environment_id="environment.staging",
        )
        is True
    )


def test_is_cross_organization_or_environment_decision_false_when_both_match() -> None:
    assert (
        is_cross_organization_or_environment_decision(
            actor_organization_id="organization.a",
            actor_environment_id="environment.production",
            target_organization_id="organization.a",
            target_environment_id="environment.production",
        )
        is False
    )


def test_evidence_and_model_output_are_never_trusted_by_default() -> None:
    assert evidence_and_model_output_are_trusted_by_default() is False


def test_security_privacy_requirement_has_eight_members() -> None:
    assert len(SecurityPrivacyRequirement) == 8
