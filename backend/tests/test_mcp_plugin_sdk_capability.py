from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    IdempotencyClass,
    SideEffect,
)
from atlas.modules.mcp_plugin_sdk.domain.capability import (
    CancellationBehavior,
    CapabilityDefinition,
    HandlerComplianceCheck,
    HandlerComplianceReport,
    HandlerRule,
    is_consistent_with_manifest,
)


def manifest() -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="capability.inventory.read",
        version="1.0.0",
        description="Read storage inventory.",
        capability_class=CapabilityClass.C1_READ_ONLY,
        side_effects=frozenset({SideEffect.READ}),
        target_types=("target.storage.array",),
        timeout_seconds=30,
        idempotency=IdempotencyClass.SAFE,
    )


def definition(**overrides: object) -> CapabilityDefinition:
    defaults: dict[str, object] = {
        "manifest": manifest(),
        "input_schema_id": "schema.input.inventory-read",
        "output_schema_id": "schema.output.inventory-read",
        "permission_declarations": ("permission.storage.read",),
        "cancellation_behavior": CancellationBehavior.COOPERATIVE_CHECKPOINTED,
        "max_concurrency": 4,
        "rate_limit_per_minute": 60,
        "preconditions": ("Target is reachable.",),
        "required_result_evidence_fields": ("observed_at", "vendor_version"),
        "error_mapping_ids": ("error-mapping.timeout",),
        "test_scenario_ids": ("scenario.normal", "scenario.timeout"),
    }
    defaults.update(overrides)
    return CapabilityDefinition(**defaults)  # type: ignore[arg-type]


def test_definition_accepts_valid_state() -> None:
    assert definition().max_concurrency == 4


def test_definition_requires_permission_declarations() -> None:
    with pytest.raises(ValueError, match="permission declarations"):
        definition(permission_declarations=())


def test_definition_requires_test_scenarios() -> None:
    with pytest.raises(ValueError, match="test scenarios"):
        definition(test_scenario_ids=())


def test_definition_rejects_non_positive_concurrency() -> None:
    with pytest.raises(ValueError, match="max_concurrency must be positive"):
        definition(max_concurrency=0)


def test_is_consistent_with_manifest_true_when_present() -> None:
    assert (
        is_consistent_with_manifest(
            definition(), manifest_capability_ids=frozenset({"capability.inventory.read"})
        )
        is True
    )


def test_is_consistent_with_manifest_false_when_absent() -> None:
    assert is_consistent_with_manifest(definition(), manifest_capability_ids=frozenset()) is False


def full_report(
    override: dict[HandlerRule, bool] | None = None,
) -> HandlerComplianceReport:
    results = {rule: True for rule in HandlerRule}
    if override is not None:
        results.update(override)
    checks = tuple(
        HandlerComplianceCheck(rule=rule, passed=passed, detail="checked")
        for rule, passed in results.items()
    )
    return HandlerComplianceReport(capability_id="capability.inventory.read", checks=checks)


def test_handler_compliance_report_requires_every_rule() -> None:
    with pytest.raises(ValueError, match="every handler rule"):
        HandlerComplianceReport(
            capability_id="capability.inventory.read",
            checks=(
                HandlerComplianceCheck(
                    rule=HandlerRule.NEVER_CALLS_LLM_OR_POLICY_ENGINE_DIRECTLY,
                    passed=True,
                    detail="checked",
                ),
            ),
        )


def test_handler_compliance_report_rejects_duplicate_rule() -> None:
    checks = (
        HandlerComplianceCheck(
            rule=HandlerRule.NEVER_CALLS_LLM_OR_POLICY_ENGINE_DIRECTLY,
            passed=True,
            detail="checked",
        ),
    ) * 2
    with pytest.raises(ValueError, match="must not repeat a rule"):
        HandlerComplianceReport(capability_id="capability.inventory.read", checks=checks)


def test_all_rules_satisfied_true_when_all_pass() -> None:
    assert full_report().all_rules_satisfied is True


def test_all_rules_satisfied_false_when_one_fails() -> None:
    report = full_report({HandlerRule.NEVER_CREATES_NESTED_SHELL_FOR_CLI_OPERATIONS: False})
    assert report.all_rules_satisfied is False
