from __future__ import annotations

import pytest

from atlas.modules.mcp_plugin_sdk.domain.documentation_compatibility import (
    BreakingChangeDeclaration,
    BreakingChangeRequirement,
    CompatibilityMatrixEntry,
    DeprecationNotice,
    GeneratedDocumentation,
    SdkVersionRange,
    runtime_refuses_incompatible_packages_before_execution,
)


def documentation(**overrides: object) -> GeneratedDocumentation:
    defaults: dict[str, object] = {
        "connector_id": "connector.example.storage",
        "supported_products": ("Example Storage 6.1",),
        "configuration_examples": ("poll_interval_seconds: 60",),
        "required_target_permissions": ("permission.storage.read",),
        "network_flows": ("connector -> api.example-storage.vendor.com:443",),
        "capability_summaries": ("capability.inventory.read: reads volume inventory",),
        "health_and_troubleshooting_note": "Check endpoint resolution first.",
        "upgrade_downgrade_note": "Supports 1.x in-place upgrade.",
        "known_limitations": ("Does not support multi-tenant targets.",),
        "evidence_and_audit_behavior_note": "Every result carries an evidence reference.",
    }
    defaults.update(overrides)
    return GeneratedDocumentation(**defaults)  # type: ignore[arg-type]


def test_documentation_accepts_valid_state() -> None:
    assert documentation().connector_id == "connector.example.storage"


def test_documentation_requires_capability_summaries() -> None:
    with pytest.raises(ValueError, match="capability summaries"):
        documentation(capability_summaries=())


def test_documentation_rejects_secret_looking_example() -> None:
    with pytest.raises(ValueError, match="must be non-secret"):
        documentation(configuration_examples=("api_key: AKIAABCDEFGHIJKLMNOP",))


def test_compatibility_matrix_entry_requires_every_field() -> None:
    with pytest.raises(ValueError, match="requires language_runtime"):
        CompatibilityMatrixEntry(
            sdk_binding_version="1.0.0",
            atlas_runtime_version="1.2.0",
            runner_protocol_version="2.0",
            manifest_schema_version="1.0",
            language_runtime="",
            package_format="tar.gz",
        )


def test_breaking_change_declaration_requires_every_requirement() -> None:
    with pytest.raises(ValueError, match="every requirement"):
        BreakingChangeDeclaration(
            change_id="breaking-change.example",
            satisfied_requirements=frozenset({BreakingChangeRequirement.MAJOR_VERSION}),
        )


def test_breaking_change_declaration_accepts_full_set() -> None:
    declaration = BreakingChangeDeclaration(
        change_id="breaking-change.example",
        satisfied_requirements=frozenset(BreakingChangeRequirement),
    )
    assert declaration.change_id == "breaking-change.example"


def test_deprecation_notice_requires_a_warning() -> None:
    with pytest.raises(ValueError, match="build-time or test-time warnings"):
        DeprecationNotice(
            api_reference="api.legacy-config-loader",
            is_security_critical=False,
            removal_window_days=90,
            warning_emitted_at_build_time=False,
            warning_emitted_at_test_time=False,
        )


def test_deprecation_notice_accepts_build_time_warning_alone() -> None:
    notice = DeprecationNotice(
        api_reference="api.legacy-config-loader",
        is_security_critical=False,
        removal_window_days=90,
        warning_emitted_at_build_time=True,
        warning_emitted_at_test_time=False,
    )
    assert notice.removal_window_days == 90


def test_sdk_version_range_requires_both_bounds() -> None:
    with pytest.raises(ValueError, match="newest supported version"):
        SdkVersionRange(oldest_supported_sdk_version="1.0.0", newest_supported_sdk_version="")


def test_runtime_always_refuses_incompatible_packages() -> None:
    assert runtime_refuses_incompatible_packages_before_execution() is True
