from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_DEPENDENCY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")

INVENTORY_CHECK_CODES = (
    "inventory.source.accepted",
    "inventory.archive.contract",
    "inventory.content.classified",
    "inventory.project-metadata.contract",
    "inventory.dependencies.normalized",
)


class InventoryLifecycle(StrEnum):
    VALIDATING = "validating"


class InventoryOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class InventoryCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class InventorySeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


class PackageContentClass(StrEnum):
    PROVENANCE = "provenance"
    MANIFEST = "manifest"
    BUILD_METADATA = "build_metadata"
    DOCUMENTATION = "documentation"
    SOURCE = "source"
    CONFIGURATION_SCHEMA = "configuration_schema"
    CAPABILITY_SCHEMA = "capability_schema"
    CONTRACT_TEST = "contract_test"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class DependencyKind(StrEnum):
    BUILD = "build"
    RUNTIME = "runtime"


def _safe_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and len(value) <= 300
        and "\\" not in value
        and not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


@dataclass(frozen=True, slots=True)
class PackageFileEvidence:
    relative_path: str
    digest: str
    size_bytes: int
    content_class: PackageContentClass

    def __post_init__(self) -> None:
        if not _safe_path(self.relative_path) or _DIGEST.fullmatch(self.digest) is None:
            raise ValueError("Package file evidence path or digest is invalid")
        if not 1 <= self.size_bytes <= 1_000_000:
            raise ValueError("Package file evidence size is invalid")


@dataclass(frozen=True, slots=True)
class PackageDependencyEvidence:
    name: str
    version_constraint: str
    kind: DependencyKind
    source_path: str

    def __post_init__(self) -> None:
        if _DEPENDENCY_NAME.fullmatch(self.name) is None:
            raise ValueError("Package dependency name is invalid")
        if not self.version_constraint or len(self.version_constraint) > 200:
            raise ValueError("Package dependency constraint is invalid")
        if any(token in self.version_constraint for token in ("@", ";", "\\", "/")):
            raise ValueError("Package dependency constraint source is unsupported")
        if self.source_path != "pyproject.toml":
            raise ValueError("Package dependency evidence source is invalid")


@dataclass(frozen=True, slots=True)
class PackageInventoryCheck:
    code: str
    state: InventoryCheckState
    severity: InventorySeverity
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in INVENTORY_CHECK_CODES:
            raise ValueError("Package inventory check code is invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 500
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Package inventory check text is invalid")
        if (
            len(self.evidence_paths) > 500
            or len(self.evidence_paths) != len(set(self.evidence_paths))
            or any(not _safe_path(item) for item in self.evidence_paths)
        ):
            raise ValueError("Package inventory check evidence is invalid")
        expected = (
            InventorySeverity.INFORMATIONAL
            if self.state is InventoryCheckState.PASSED
            else InventorySeverity.ERROR
        )
        if self.severity is not expected:
            raise ValueError("Package inventory check severity is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageSupplyChainInventory:
    inventory_id: str
    schema_version: str
    version: int
    lifecycle: InventoryLifecycle
    outcome: InventoryOutcome
    source_validation_id: str
    source_validation_digest: str
    source_acquisition_id: str
    source_acquisition_digest: str
    source_handoff_id: str
    source_project_id: str
    source_acquired_by: str
    source_validated_by: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    inventoried_by: str
    inventory_profile: str
    inspector_version: str
    package_digest: str
    package_size_bytes: int
    files: tuple[PackageFileEvidence, ...]
    dependencies: tuple[PackageDependencyEvidence, ...]
    inventory_digest: str
    dependency_set_digest: str
    runtime_dependency_count: int
    build_dependency_count: int
    dependency_lock_present: bool
    checks: tuple[PackageInventoryCheck, ...]
    limitations: tuple[str, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    inventoried_at: datetime
    content_inventory_completed: bool = True
    dependency_inventory_completed: bool = True
    vulnerability_scan_completed: bool = False
    malware_scan_completed: bool = False
    secret_content_scan_completed: bool = False
    prohibited_content_scan_completed: bool = False
    license_scan_completed: bool = False
    static_code_validation_completed: bool = False
    contract_validation_completed: bool = False
    runner_validation_completed: bool = False
    lab_validation_completed: bool = False
    package_signed: bool = False
    publisher_attested: bool = False
    connector_rejected: bool = False
    connector_registered: bool = False
    connector_approved: bool = False
    connector_installed: bool = False
    connector_enabled: bool = False
    target_configured: bool = False
    credentials_resolved: bool = False
    runtime_trust_granted: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            (self.inventory_id, "inventory id"),
            (self.schema_version, "inventory schema"),
            (self.source_validation_id, "source validation id"),
            (self.source_acquisition_id, "source acquisition id"),
            (self.source_handoff_id, "source handoff id"),
            (self.source_project_id, "source project id"),
            (self.source_acquired_by, "source acquisition actor"),
            (self.source_validated_by, "source validation actor"),
            (self.source_custodied_by, "source custodian"),
            (self.source_domain_reviewed_by, "source domain reviewer"),
            (self.source_security_reviewed_by, "source security reviewer"),
            (self.source_lab_operated_by, "source lab operator"),
            (self.organization_id, "inventory organization"),
            (self.environment_id, "inventory environment"),
            (self.inventoried_by, "inventory actor"),
            (self.inventory_profile, "inventory profile"),
            (self.inspector_version, "inspector version"),
        )
        for value, label in identifiers:
            validate_stable_identifier(value, label)
        if self.version != 1 or self.lifecycle is not InventoryLifecycle.VALIDATING:
            raise ValueError("Package inventory version or lifecycle is invalid")
        for digest in (
            self.source_validation_digest,
            self.source_acquisition_digest,
            self.package_digest,
            self.inventory_digest,
            self.dependency_set_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(digest) is None:
                raise ValueError("Package inventory digest is invalid")
        if self.inventoried_by in {
            self.source_acquired_by,
            self.source_validated_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
        }:
            raise ValueError("Package inventory violates separation of duties")
        if not self.files or self.files != tuple(
            sorted(self.files, key=lambda item: item.relative_path)
        ):
            raise ValueError("Package file inventory order is invalid")
        paths = [item.relative_path for item in self.files]
        if len(paths) != len(set(paths)) or len({item.casefold() for item in paths}) != len(paths):
            raise ValueError("Package file inventory paths are duplicated")
        if self.dependencies != tuple(
            sorted(self.dependencies, key=lambda item: (item.kind, item.name))
        ):
            raise ValueError("Package dependency inventory order is invalid")
        if self.runtime_dependency_count != sum(
            item.kind is DependencyKind.RUNTIME for item in self.dependencies
        ) or self.build_dependency_count != sum(
            item.kind is DependencyKind.BUILD for item in self.dependencies
        ):
            raise ValueError("Package dependency counts are inconsistent")
        if tuple(item.code for item in self.checks) != INVENTORY_CHECK_CODES:
            raise ValueError("Package inventory check set is invalid")
        passed = all(item.state is InventoryCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is InventoryOutcome.PASSED):
            raise ValueError("Package inventory outcome is inconsistent")
        if not self.limitations or len(self.limitations) != len(set(self.limitations)):
            raise ValueError("Package inventory limitations are invalid")
        if any(not item.strip() or len(item) > 500 for item in self.limitations):
            raise ValueError("Package inventory limitation text is invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000 or self.inventoried_at.tzinfo is None:
            raise ValueError("Package inventory size or timestamp is invalid")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Package inventory idempotency key is invalid")
        if not self.content_inventory_completed or not self.dependency_inventory_completed:
            raise ValueError("Package inventory completion flags are invalid")
        if any(
            (
                self.vulnerability_scan_completed,
                self.malware_scan_completed,
                self.secret_content_scan_completed,
                self.prohibited_content_scan_completed,
                self.license_scan_completed,
                self.static_code_validation_completed,
                self.contract_validation_completed,
                self.runner_validation_completed,
                self.lab_validation_completed,
                self.package_signed,
                self.publisher_attested,
                self.connector_rejected,
                self.connector_registered,
                self.connector_approved,
                self.connector_installed,
                self.connector_enabled,
                self.target_configured,
                self.credentials_resolved,
                self.runtime_trust_granted,
                self.execution_authorized,
                self.deployment_approved,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("Package inventory cannot grant later-stage authority")
