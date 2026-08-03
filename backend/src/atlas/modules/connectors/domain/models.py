from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass

_STABLE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
_SEMANTIC_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _validate_identifier(value: str, field_name: str) -> None:
    if not _STABLE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field_name} is not a valid stable identifier")


def _validate_semantic_version(value: str, field_name: str) -> None:
    if not _SEMANTIC_VERSION.fullmatch(value):
        raise ValueError(f"{field_name} must use semantic versioning")


class SideEffect(StrEnum):
    NONE = "none"
    READ = "read"
    DIAGNOSTIC = "diagnostic"
    WRITE = "write"
    SERVICE_IMPACTING = "service_impacting"
    DESTRUCTIVE = "destructive"


class IdempotencyClass(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    SAFE = "safe"
    KEYED = "keyed"
    UNSAFE = "unsafe"


class PackageLifecycle(StrEnum):
    QUARANTINED = "quarantined"
    REGISTERED = "registered"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class InstanceLifecycle(StrEnum):
    DISABLED = "disabled"
    ENABLED = "enabled"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class ConnectorHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    capability_id: str
    version: str
    description: str
    capability_class: CapabilityClass
    side_effects: frozenset[SideEffect]
    target_types: tuple[str, ...]
    timeout_seconds: int
    idempotency: IdempotencyClass

    def __post_init__(self) -> None:
        _validate_identifier(self.capability_id, "capability_id")
        _validate_semantic_version(self.version, "capability version")
        if not self.description.strip():
            raise ValueError("capability description must not be empty")
        if not self.side_effects:
            raise ValueError("capability side effects must be declared")
        if SideEffect.NONE in self.side_effects and len(self.side_effects) != 1:
            raise ValueError("the none side effect cannot be combined with other effects")
        if not self.target_types:
            raise ValueError("at least one target type is required")
        for target_type in self.target_types:
            _validate_identifier(target_type, "target_type")
        if not 1 <= self.timeout_seconds <= 300:
            raise ValueError("capability timeout must be between 1 and 300 seconds")


@dataclass(frozen=True, slots=True)
class ConnectorPackageManifest:
    package_id: str
    connector_id: str
    display_name: str
    publisher: str
    owner: str
    package_version: str
    atlas_compatibility: str
    runtime: str
    entry_point: str
    digest_sha256: str
    supported_products: tuple[str, ...]
    network_destinations: tuple[str, ...]
    capabilities: tuple[CapabilityManifest, ...]
    generated: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.package_id, "package_id")
        _validate_identifier(self.connector_id, "connector_id")
        _validate_semantic_version(self.package_version, "package_version")
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if not self.publisher.strip() or not self.owner.strip():
            raise ValueError("publisher and owner must not be empty")
        if not self.atlas_compatibility.strip():
            raise ValueError("atlas_compatibility must not be empty")
        _validate_identifier(self.runtime, "runtime")
        if not self.entry_point.strip():
            raise ValueError("entry_point must not be empty")
        if not _SHA256.fullmatch(self.digest_sha256):
            raise ValueError("digest_sha256 must be a lowercase SHA-256 digest")
        if not self.supported_products:
            raise ValueError("at least one supported product is required")
        if not self.capabilities:
            raise ValueError("at least one capability is required")
        capability_ids = [item.capability_id for item in self.capabilities]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("capability identifiers must be unique within a package")

    @property
    def version_reference(self) -> str:
        return f"{self.package_id}:v{self.package_version}"


@dataclass(frozen=True, slots=True)
class RegisteredPackage:
    manifest: ConnectorPackageManifest
    lifecycle: PackageLifecycle
    registered_at: datetime
    registered_by: str
    validation_report: ConnectorValidationReport

    def __post_init__(self) -> None:
        if self.registered_at.tzinfo is None:
            raise ValueError("registered_at must be timezone-aware")
        _validate_identifier(self.registered_by, "registered_by")


@dataclass(frozen=True, slots=True)
class ConnectorInstance:
    instance_id: str
    package_id: str
    package_version: str
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    enabled_capability_ids: frozenset[str]
    secret_reference_ids: tuple[str, ...]
    lifecycle: InstanceLifecycle
    health: ConnectorHealth
    configuration_revision: int
    created_at: datetime
    created_by: str

    def __post_init__(self) -> None:
        for field_name in (
            "instance_id",
            "package_id",
            "organization_id",
            "environment_id",
            "site_id",
            "target_id",
            "created_by",
        ):
            _validate_identifier(str(getattr(self, field_name)), field_name)
        _validate_semantic_version(self.package_version, "package_version")
        for capability_id in self.enabled_capability_ids:
            _validate_identifier(capability_id, "enabled_capability_id")
        for secret_reference_id in self.secret_reference_ids:
            _validate_identifier(secret_reference_id, "secret_reference_id")
        if self.configuration_revision < 1:
            raise ValueError("configuration_revision must be positive")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ConnectorValidationReport:
    report_id: str
    package_reference: str
    validated_at: datetime
    findings: tuple[ValidationFinding, ...]

    def __post_init__(self) -> None:
        _validate_identifier(self.report_id, "report_id")
        if self.validated_at.tzinfo is None:
            raise ValueError("validated_at must be timezone-aware")

    @property
    def passed(self) -> bool:
        return not self.findings
