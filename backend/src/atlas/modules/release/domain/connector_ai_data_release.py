"""ATLAS-059 SS28/SS29/SS30: connector releases, AI and model releases, and data/schema
releases.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.release.domain.versioning import SemanticVersion


@dataclass(frozen=True, slots=True)
class ConnectorRelease:
    """SS28's declared elements."""

    connector_package_reference: str
    connector_version: SemanticVersion
    platform_compatibility: str
    sdk_compatibility: str
    capability_compatibility: tuple[str, ...]
    vendor_product_compatibility: tuple[str, ...]
    expands_capability_or_permission: bool
    capability_class_and_safety_review_reference: str
    signed: bool
    scanned: bool
    simulated: bool
    vendor_lab_tested: bool
    platform_release_matrix_reference: str

    def __post_init__(self) -> None:
        if not self.connector_package_reference.strip():
            raise ValueError("a connector release requires a package reference")
        if not self.platform_compatibility.strip():
            raise ValueError("a connector release requires platform compatibility")
        if not self.sdk_compatibility.strip():
            raise ValueError("a connector release requires SDK compatibility")
        if not self.capability_compatibility:
            raise ValueError("a connector release requires capability compatibility")
        if not self.vendor_product_compatibility:
            raise ValueError("a connector release requires vendor product compatibility")
        if not self.capability_class_and_safety_review_reference.strip():
            raise ValueError("a connector release requires a capability class and safety review")
        if not self.signed:
            raise ValueError("SS28: package is signed")
        if not self.scanned:
            raise ValueError("SS28: package is ... scanned")
        if not self.platform_release_matrix_reference.strip():
            raise ValueError("a connector release requires a platform release matrix reference")


def connector_suspension_requires_republishing_platform_artifacts() -> bool:
    """SS28: "connector can be suspended without republishing platform artifacts.\""""
    return False


def connector_upgrade_or_rollback_can_change_target_or_credential_scope() -> bool:
    """SS28: "upgrade and rollback preserve target and credential scope.\""""
    return False


@dataclass(frozen=True, slots=True)
class AiModelRelease:
    """SS29's declared elements."""

    update_reference: str
    version: str
    immutable_package_reference: str
    dataset_and_evaluation_version_reference: str
    baseline_comparison_reference: str
    safety_gate_references: tuple[str, ...]
    domain_and_human_review_reference: str | None
    canary_or_shadow_plan_reference: str | None
    schema_compatibility_reference: str
    rollback_target_reference: str

    def __post_init__(self) -> None:
        if not self.update_reference.strip():
            raise ValueError("an AI/model release requires an update reference")
        if not self.version.strip():
            raise ValueError("an AI/model release requires an independent version")
        if not self.immutable_package_reference.strip():
            raise ValueError("an AI/model release requires an immutable package reference")
        if not self.dataset_and_evaluation_version_reference.strip():
            raise ValueError("an AI/model release requires a dataset and evaluation version")
        if not self.baseline_comparison_reference.strip():
            raise ValueError("an AI/model release requires a baseline comparison")
        if not self.safety_gate_references:
            raise ValueError(
                "SS29: prompt-injection, DLP, tool, refusal, and invariant safety gates"
            )
        if not self.schema_compatibility_reference.strip():
            raise ValueError(
                "an AI/model release requires compatible output/artifact/audit schemas"
            )
        if not self.rollback_target_reference.strip():
            raise ValueError("an AI/model release requires a rollback target")


def silent_model_substitution_is_permitted() -> bool:
    """SS29: "silent model substitution is prohibited.\""""
    return False


@dataclass(frozen=True, slots=True)
class DataSchemaRelease:
    """SS30's declared elements."""

    supported_source_schema_versions: tuple[str, ...]
    target_schema_version: str
    migration_test_reference: str
    backup_and_restore_readiness_reference: str
    expand_contract_stage: str | None
    expand_contract_completion_state: str | None
    is_destructive: bool
    deprecation_and_usage_evidence_reference: str | None
    derived_rebuild_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.supported_source_schema_versions:
            raise ValueError("a data/schema release requires supported source schema versions")
        if not self.target_schema_version.strip():
            raise ValueError("a data/schema release requires a target schema version")
        if not self.migration_test_reference.strip():
            raise ValueError("a data/schema release requires a migration test reference")
        if not self.backup_and_restore_readiness_reference.strip():
            raise ValueError("a data/schema release requires backup and restore readiness")
        if (self.expand_contract_stage is None) != (self.expand_contract_completion_state is None):
            raise ValueError(
                "expand-and-contract stage and completion state must be given together"
            )
        if self.is_destructive and self.deprecation_and_usage_evidence_reference is None:
            raise ValueError("SS30: destructive changes require deprecation and usage evidence")


def deleted_or_restricted_data_can_reappear() -> bool:
    """SS30: "deleted and restricted data cannot reappear.\""""
    return False


def restore_into_incompatible_release_is_permitted() -> bool:
    """SS30: "restore into incompatible release is blocked.\""""
    return False
