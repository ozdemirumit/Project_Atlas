from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorPackageManifest,
    IdempotencyClass,
    SideEffect,
)
from atlas.modules.mcp_plugin_sdk.domain.manifest_config import (
    ConfigFieldDeclaration,
    ConfigFieldSensitivity,
    ConfigRestartBehavior,
    ConnectorManifestExtensions,
)


def capability() -> CapabilityManifest:
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


def package() -> ConnectorPackageManifest:
    return ConnectorPackageManifest(
        package_id="connector.example.storage",
        connector_id="connector.example.storage",
        display_name="Example Storage Connector",
        publisher="Project Atlas",
        owner="Platform Engineering",
        package_version="1.0.0",
        atlas_compatibility=">=0.1.0,<0.2.0",
        runtime="python3.12",
        entry_point="atlas_connector_example.main",
        digest_sha256="a" * 64,
        supported_products=("Example Storage 6.1",),
        network_destinations=("api.example-storage.vendor.com",),
        capabilities=(capability(),),
    )


def extensions(**overrides: object) -> ConnectorManifestExtensions:
    defaults: dict[str, object] = {
        "package": package(),
        "sdk_binding_version": "1.0.0",
        "dependencies": ("httpx>=0.27",),
        "configuration_schema_id": "schema.config.example-storage",
        "secret_reference_schema_id": "schema.secret.example-storage",
        "network_protocols": ("https",),
        "resource_declarations": ("resource.storage.array",),
        "permission_declarations": ("permission.storage.read",),
        "health_check_ids": ("health-check.endpoint-resolution",),
        "self_test_ids": ("self-test.authentication",),
        "upgrade_support_note": "Supports in-place upgrade from 1.x to 1.y.",
        "migration_support_note": "No configuration migration required within 1.x.",
    }
    defaults.update(overrides)
    return ConnectorManifestExtensions(**defaults)  # type: ignore[arg-type]


def config_field(**overrides: object) -> ConfigFieldDeclaration:
    defaults: dict[str, object] = {
        "name": "poll_interval_seconds",
        "field_type": "integer",
        "purpose": "How often to poll the target for health observations.",
        "default_value": "60",
        "required": False,
        "allowed_values": (),
        "minimum": 10.0,
        "maximum": 3600.0,
        "minimum_length": None,
        "maximum_length": None,
        "pattern": None,
        "environment_applicability": ("production", "staging"),
        "target_applicability": ("target.storage.array",),
        "restart_behavior": ConfigRestartBehavior.RELOAD,
        "sensitivity": ConfigFieldSensitivity.NON_SENSITIVE,
        "deprecated": False,
        "deprecation_migration_note": None,
    }
    defaults.update(overrides)
    return ConfigFieldDeclaration(**defaults)  # type: ignore[arg-type]


def test_extensions_accepts_valid_state() -> None:
    assert extensions().sdk_binding_version == "1.0.0"


def test_extensions_requires_permission_declarations() -> None:
    with pytest.raises(ValueError, match="permission declarations are required"):
        extensions(permission_declarations=())


def test_extensions_requires_health_check_ids() -> None:
    with pytest.raises(ValueError, match="health checks are required"):
        extensions(health_check_ids=())


def test_config_field_accepts_valid_state() -> None:
    assert config_field().name == "poll_interval_seconds"


def test_config_field_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="minimum must not exceed maximum"):
        config_field(minimum=100.0, maximum=10.0)


def test_config_field_deprecated_requires_migration_note() -> None:
    with pytest.raises(ValueError, match="requires a migration note"):
        config_field(deprecated=True, deprecation_migration_note=None)


def test_config_field_migration_note_only_for_deprecated() -> None:
    with pytest.raises(ValueError, match="only meaningful for a deprecated field"):
        config_field(deprecated=False, deprecation_migration_note="Use new_field instead.")


def test_config_field_rejects_secret_looking_default_value() -> None:
    with pytest.raises(ValueError, match="cannot use ordinary configuration fields"):
        config_field(default_value="AKIAABCDEFGHIJKLMNOP")


def test_config_field_accepts_sensitive_non_secret_default() -> None:
    field = config_field(
        name="internal_hostname",
        default_value="storage-internal.example.local",
        sensitivity=ConfigFieldSensitivity.SENSITIVE,
    )
    assert field.sensitivity is ConfigFieldSensitivity.SENSITIVE
