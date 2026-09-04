from __future__ import annotations

import pytest

from atlas.modules.ai_agents.domain.lifecycle_security import (
    IsolatedGenerationEnvironment,
    ModelUpgradeEvaluation,
    ModelUpgradeEvaluationDimension,
    NetworkDestinationAllowlist,
    ProductionRunReference,
    PromptTemplateVersion,
    RollbackTarget,
    TemplateKind,
    agents_run_with_infrastructure_credentials,
    security_review_agent_output_replaces_deterministic_enforcement,
)


def test_prompt_template_version_requires_review() -> None:
    with pytest.raises(ValueError, match="reviewed as behavior changes"):
        PromptTemplateVersion(
            template_id="prompt-template.system",
            kind=TemplateKind.SYSTEM,
            version=2,
            reviewed_as_behavior_change=False,
        )


def test_prompt_template_version_accepts_reviewed_change() -> None:
    version = PromptTemplateVersion(
        template_id="prompt-template.system",
        kind=TemplateKind.SYSTEM,
        version=2,
        reviewed_as_behavior_change=True,
    )
    assert version.version == 2


def full_evaluation(
    override: dict[ModelUpgradeEvaluationDimension, bool] | None = None,
) -> tuple[tuple[ModelUpgradeEvaluationDimension, bool], ...]:
    results = {dimension: True for dimension in ModelUpgradeEvaluationDimension}
    if override is not None:
        results.update(override)
    return tuple(results.items())


def test_model_upgrade_evaluation_requires_every_dimension() -> None:
    with pytest.raises(ValueError, match="every evaluation dimension"):
        ModelUpgradeEvaluation(
            from_model_id="model.v2",
            to_model_id="model.v3",
            dimension_results=((ModelUpgradeEvaluationDimension.SAFETY, True),),
        )


def test_model_upgrade_evaluation_passed_true_when_all_pass() -> None:
    evaluation = ModelUpgradeEvaluation(
        from_model_id="model.v2", to_model_id="model.v3", dimension_results=full_evaluation()
    )
    assert evaluation.passed is True


def test_model_upgrade_evaluation_passed_false_when_one_fails() -> None:
    dimension_results = full_evaluation({ModelUpgradeEvaluationDimension.LATENCY: False})
    evaluation = ModelUpgradeEvaluation(
        from_model_id="model.v2", to_model_id="model.v3", dimension_results=dimension_results
    )
    assert evaluation.passed is False


def test_production_run_reference_requires_prompt_references() -> None:
    with pytest.raises(ValueError, match="prompt template references"):
        ProductionRunReference(
            run_id="agent-run.example",
            model_id="model.v3",
            model_version="3.0.1",
            prompt_template_references=(),
        )


def test_rollback_target_requires_validated_compatible_combination() -> None:
    with pytest.raises(ValueError, match="validated compatible combination"):
        RollbackTarget(combination_id="combination.example", is_validated_compatible=False)


def test_agents_never_run_with_infrastructure_credentials() -> None:
    assert agents_run_with_infrastructure_credentials() is False


def test_security_review_agent_output_never_replaces_deterministic_enforcement() -> None:
    assert security_review_agent_output_replaces_deterministic_enforcement() is False


def test_network_destination_allowlist_requires_at_least_one_host() -> None:
    with pytest.raises(ValueError, match="at least one host"):
        NetworkDestinationAllowlist(allowed_hosts=frozenset())


def test_network_destination_allowlist_is_allowed() -> None:
    allowlist = NetworkDestinationAllowlist(allowed_hosts=frozenset({"api.vendor.example"}))
    assert allowlist.is_allowed("api.vendor.example") is True
    assert allowlist.is_allowed("evil.example") is False


def test_isolated_generation_environment_rejects_production_secrets() -> None:
    with pytest.raises(ValueError, match="no production secrets"):
        IsolatedGenerationEnvironment(
            environment_id="environment.builder", has_production_secrets=True
        )
