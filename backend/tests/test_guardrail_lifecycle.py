from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.guardrails.domain.lifecycle import (
    GuardrailDeploymentMode,
    GuardrailLifecycleRecord,
    GuardrailLifecycleStage,
    an_invariant_class_guardrail_is_deployed_indefinitely_in_observe_only_mode,
    is_valid_guardrail_lifecycle_transition,
)
from atlas.modules.guardrails.domain.models import GuardrailClass

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _record(**overrides: object) -> GuardrailLifecycleRecord:
    values: dict[str, object] = {
        "rule_id": "rule.injection.instruction-override",
        "rule_version": 1,
        "guardrail_class": GuardrailClass.POLICY_CONFIGURABLE,
        "stage": GuardrailLifecycleStage.DRAFT,
        "deployment_mode": None,
        "owner": "subject.security-engineer.primary",
        "threat": "Instruction override via retrieved content.",
        "scope": "All retrieval-augmented prompts.",
        "behavior": "Blocks content matching known override patterns.",
        "false_positive_risk": "Low; pattern is narrowly scoped.",
        "updated_at": NOW,
        "updated_by": "subject.security-engineer.primary",
    }
    values.update(overrides)
    return GuardrailLifecycleRecord(**values)  # type: ignore[arg-type]


def test_absolute_rule_is_false() -> None:
    assert an_invariant_class_guardrail_is_deployed_indefinitely_in_observe_only_mode() is False


def test_diagram_transitions_are_valid() -> None:
    assert (
        is_valid_guardrail_lifecycle_transition(
            GuardrailLifecycleStage.DRAFT, GuardrailLifecycleStage.IMPLEMENTED
        )
        is True
    )
    assert (
        is_valid_guardrail_lifecycle_transition(
            GuardrailLifecycleStage.MONITORED, GuardrailLifecycleStage.RETIRED
        )
        is True
    )


def test_undiagrammed_transitions_are_rejected() -> None:
    assert (
        is_valid_guardrail_lifecycle_transition(
            GuardrailLifecycleStage.DRAFT, GuardrailLifecycleStage.DEPLOYED
        )
        is False
    )
    assert (
        is_valid_guardrail_lifecycle_transition(
            GuardrailLifecycleStage.RETIRED, GuardrailLifecycleStage.DRAFT
        )
        is False
    )


def test_deployed_stage_requires_a_deployment_mode() -> None:
    with pytest.raises(ValueError, match="requires a deployment mode"):
        _record(stage=GuardrailLifecycleStage.DEPLOYED, deployment_mode=None)


def test_undeployed_stage_forbids_a_deployment_mode() -> None:
    with pytest.raises(ValueError, match="only a deployed guardrail"):
        _record(
            stage=GuardrailLifecycleStage.DRAFT,
            deployment_mode=GuardrailDeploymentMode.OBSERVE,
        )


def test_invariant_class_can_only_deploy_in_enforce_mode() -> None:
    with pytest.raises(ValueError, match="only ever be deployed in enforce mode"):
        _record(
            guardrail_class=GuardrailClass.INVARIANT,
            stage=GuardrailLifecycleStage.DEPLOYED,
            deployment_mode=GuardrailDeploymentMode.OBSERVE,
        )
    record = _record(
        guardrail_class=GuardrailClass.INVARIANT,
        stage=GuardrailLifecycleStage.DEPLOYED,
        deployment_mode=GuardrailDeploymentMode.ENFORCE,
    )
    assert record.deployment_mode is GuardrailDeploymentMode.ENFORCE


def test_non_invariant_class_permits_staged_rollout() -> None:
    record = _record(
        stage=GuardrailLifecycleStage.DEPLOYED,
        deployment_mode=GuardrailDeploymentMode.OBSERVE,
    )
    assert record.deployment_mode is GuardrailDeploymentMode.OBSERVE
