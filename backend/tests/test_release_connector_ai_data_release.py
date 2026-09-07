from __future__ import annotations

import pytest

from atlas.modules.release.domain.connector_ai_data_release import (
    AiModelRelease,
    ConnectorRelease,
    DataSchemaRelease,
    connector_suspension_requires_republishing_platform_artifacts,
    connector_upgrade_or_rollback_can_change_target_or_credential_scope,
    deleted_or_restricted_data_can_reappear,
    restore_into_incompatible_release_is_permitted,
    silent_model_substitution_is_permitted,
)
from atlas.modules.release.domain.versioning import SemanticVersion


def connector_version() -> SemanticVersion:
    return SemanticVersion(
        major=1,
        minor=0,
        patch=0,
        prerelease_label=None,
        prerelease_number=None,
        build_metadata=None,
    )


def connector_release(**overrides: object) -> ConnectorRelease:
    defaults: dict[str, object] = {
        "connector_package_reference": "connector.example.storage:v1.0.0",
        "connector_version": connector_version(),
        "platform_compatibility": ">=1.4.0",
        "sdk_compatibility": "sdk-1.0.x",
        "capability_compatibility": ("capability.inventory.read",),
        "vendor_product_compatibility": ("Example Storage 6.1",),
        "expands_capability_or_permission": False,
        "capability_class_and_safety_review_reference": "review.connector.example.storage",
        "signed": True,
        "scanned": True,
        "simulated": True,
        "vendor_lab_tested": True,
        "platform_release_matrix_reference": "compat-matrix.1.5.0",
    }
    defaults.update(overrides)
    return ConnectorRelease(**defaults)  # type: ignore[arg-type]


def test_connector_release_requires_signed() -> None:
    with pytest.raises(ValueError, match="package is signed"):
        connector_release(signed=False)


def test_connector_release_requires_scanned() -> None:
    with pytest.raises(ValueError, match="scanned"):
        connector_release(scanned=False)


def test_connector_release_accepts_valid_state() -> None:
    assert connector_release().connector_package_reference == "connector.example.storage:v1.0.0"


def test_connector_suspension_never_requires_republishing_platform_artifacts() -> None:
    assert connector_suspension_requires_republishing_platform_artifacts() is False


def test_connector_upgrade_never_changes_target_or_credential_scope() -> None:
    assert connector_upgrade_or_rollback_can_change_target_or_credential_scope() is False


def ai_model_release(**overrides: object) -> AiModelRelease:
    defaults: dict[str, object] = {
        "update_reference": "model-update.root-cause-agent.v2",
        "version": "2.0.0",
        "immutable_package_reference": "model-package.root-cause-agent.v2",
        "dataset_and_evaluation_version_reference": "eval-dataset.v3",
        "baseline_comparison_reference": "baseline-comparison.v1-to-v2",
        "safety_gate_references": ("gate.prompt-injection", "gate.invariant"),
        "domain_and_human_review_reference": "review.root-cause-agent.v2",
        "canary_or_shadow_plan_reference": None,
        "schema_compatibility_reference": "schema-compat.root-cause-output.v1",
        "rollback_target_reference": "model-package.root-cause-agent.v1",
    }
    defaults.update(overrides)
    return AiModelRelease(**defaults)  # type: ignore[arg-type]


def test_ai_model_release_requires_safety_gates() -> None:
    with pytest.raises(ValueError, match="safety gates"):
        ai_model_release(safety_gate_references=())


def test_ai_model_release_accepts_valid_state() -> None:
    assert ai_model_release().version == "2.0.0"


def test_silent_model_substitution_never_permitted() -> None:
    assert silent_model_substitution_is_permitted() is False


def data_schema_release(**overrides: object) -> DataSchemaRelease:
    defaults: dict[str, object] = {
        "supported_source_schema_versions": ("0179", "0180"),
        "target_schema_version": "0181",
        "migration_test_reference": "migration-test.0181",
        "backup_and_restore_readiness_reference": "backup-readiness.1.5.0",
        "expand_contract_stage": None,
        "expand_contract_completion_state": None,
        "is_destructive": False,
        "deprecation_and_usage_evidence_reference": None,
        "derived_rebuild_references": (),
    }
    defaults.update(overrides)
    return DataSchemaRelease(**defaults)  # type: ignore[arg-type]


def test_data_schema_release_accepts_valid_state() -> None:
    assert data_schema_release().target_schema_version == "0181"


def test_data_schema_release_rejects_partial_expand_contract_state() -> None:
    with pytest.raises(ValueError, match="must be given together"):
        data_schema_release(expand_contract_stage="expand")


def test_data_schema_release_destructive_requires_deprecation_evidence() -> None:
    with pytest.raises(ValueError, match="deprecation and usage evidence"):
        data_schema_release(is_destructive=True, deprecation_and_usage_evidence_reference=None)


def test_deleted_data_can_never_reappear() -> None:
    assert deleted_or_restricted_data_can_reappear() is False


def test_restore_into_incompatible_release_never_permitted() -> None:
    assert restore_into_incompatible_release_is_permitted() is False
