"""ATLAS-021 SS9/SS10: the manifest and configuration APIs.

`ConnectorManifestExtensions` wraps `connectors.domain.models.ConnectorPackageManifest` directly
for SS9's identity/publisher/compatibility/products/runtime/network-destination/capability
elements -- that type already models them -- and adds only what it does not yet carry (SDK
binding version, dependencies, configuration/secret schema references, permissions, health
checks, upgrade/migration support). SS9's "build fails when required safety metadata is absent"
is a construction-time guarantee: the extensions cannot be built without permission declarations
and health check references.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.connectors.domain.models import ConnectorPackageManifest
from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class ConnectorManifestExtensions:
    package: ConnectorPackageManifest
    sdk_binding_version: str
    dependencies: tuple[str, ...]
    configuration_schema_id: str
    secret_reference_schema_id: str
    network_protocols: tuple[str, ...]
    resource_declarations: tuple[str, ...]
    permission_declarations: tuple[str, ...]
    health_check_ids: tuple[str, ...]
    self_test_ids: tuple[str, ...]
    upgrade_support_note: str
    migration_support_note: str

    def __post_init__(self) -> None:
        if not self.sdk_binding_version.strip():
            raise ValueError("manifest extensions require an SDK binding version")
        validate_stable_identifier(self.configuration_schema_id, "configuration_schema_id")
        validate_stable_identifier(self.secret_reference_schema_id, "secret_reference_schema_id")
        if not self.permission_declarations:
            raise ValueError(
                "SS9: build fails when required safety metadata is absent -- permission "
                "declarations are required"
            )
        if not self.health_check_ids:
            raise ValueError(
                "SS9: build fails when required safety metadata is absent -- health checks "
                "are required"
            )
        if not self.upgrade_support_note.strip():
            raise ValueError("manifest extensions require an upgrade support note")
        if not self.migration_support_note.strip():
            raise ValueError("manifest extensions require a migration support note")


class ConfigFieldSensitivity(StrEnum):
    SENSITIVE = "sensitive"
    NON_SENSITIVE = "non_sensitive"


class ConfigRestartBehavior(StrEnum):
    """SS10: "restart or reload behavior.\""""

    NONE = "none"
    RELOAD = "reload"
    RESTART = "restart"


@dataclass(frozen=True, slots=True)
class ConfigFieldDeclaration:
    """SS10's declared elements. "Secret values cannot use ordinary configuration fields. The
    validator rejects common embedded credential patterns where feasible" reuses Guardrails'
    `detect_secret_patterns` on `default_value` -- the same enforcement Change Impact's
    `ChangeParameter` established for an identically-shaped rule."""

    name: str
    field_type: str
    purpose: str
    default_value: str | None
    required: bool
    allowed_values: tuple[str, ...]
    minimum: float | None
    maximum: float | None
    minimum_length: int | None
    maximum_length: int | None
    pattern: str | None
    environment_applicability: tuple[str, ...]
    target_applicability: tuple[str, ...]
    restart_behavior: ConfigRestartBehavior
    sensitivity: ConfigFieldSensitivity
    deprecated: bool
    deprecation_migration_note: str | None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("a configuration field requires a name")
        if not self.field_type.strip():
            raise ValueError("a configuration field requires a type")
        if not self.purpose.strip():
            raise ValueError("a configuration field requires a purpose")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        if (
            self.minimum_length is not None
            and self.maximum_length is not None
            and self.minimum_length > self.maximum_length
        ):
            raise ValueError("minimum_length must not exceed maximum_length")
        if self.deprecated and self.deprecation_migration_note is None:
            raise ValueError("a deprecated configuration field requires a migration note")
        if not self.deprecated and self.deprecation_migration_note is not None:
            raise ValueError("deprecation_migration_note is only meaningful for a deprecated field")
        if self.default_value is not None and detect_secret_patterns(self.default_value):
            raise ValueError("SS10: secret values cannot use ordinary configuration fields")
