from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_CHECK_CODE = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")
_SCHEMA_ID = re.compile(r"^atlas://generated/[A-Za-z0-9_.:/-]{1,300}$")

VALIDATION_CHECK_CODES = (
    "validation.source.accepted",
    "validation.archive.contract",
    "validation.manifest.contract",
    "validation.schemas.contract",
)


class PackageValidationLifecycle(StrEnum):
    VALIDATING = "validating"


class PackageValidationOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class PackageValidationCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class PackageValidationSeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


class ValidatedSchemaPurpose(StrEnum):
    CONFIGURATION = "configuration"
    CAPABILITY_INPUT = "capability_input"
    CAPABILITY_OUTPUT = "capability_output"


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and len(value) <= 300
        and "\\" not in value
        and not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


@dataclass(frozen=True, slots=True)
class PackageValidationCheck:
    code: str
    state: PackageValidationCheckState
    severity: PackageValidationSeverity
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str

    def __post_init__(self) -> None:
        if _CHECK_CODE.fullmatch(self.code) is None:
            raise ValueError("Package validation check code is invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 500
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Package validation check text is invalid")
        if (
            len(self.evidence_paths) > 100
            or len(self.evidence_paths) != len(set(self.evidence_paths))
            or any(not _safe_relative_path(item) for item in self.evidence_paths)
        ):
            raise ValueError("Package validation evidence paths are invalid")
        if self.state is PackageValidationCheckState.PASSED:
            if self.severity is not PackageValidationSeverity.INFORMATIONAL:
                raise ValueError("Passed package validation check severity is invalid")
        elif self.severity is not PackageValidationSeverity.ERROR:
            raise ValueError("Failed package validation check severity is invalid")


@dataclass(frozen=True, slots=True)
class ValidatedSchemaEvidence:
    relative_path: str
    digest: str
    schema_id: str
    purpose: ValidatedSchemaPurpose
    capability_id: str | None = None

    def __post_init__(self) -> None:
        if not _safe_relative_path(self.relative_path) or _DIGEST.fullmatch(self.digest) is None:
            raise ValueError("Validated schema evidence path or digest is invalid")
        if _SCHEMA_ID.fullmatch(self.schema_id) is None:
            raise ValueError("Validated schema evidence identifier is invalid")
        if self.purpose is ValidatedSchemaPurpose.CONFIGURATION:
            if self.capability_id is not None:
                raise ValueError("Configuration schema cannot bind a capability")
        elif self.capability_id is None:
            raise ValueError("Capability schema requires a capability identifier")
        if self.capability_id is not None:
            validate_stable_identifier(self.capability_id, "validated schema capability id")


@dataclass(frozen=True, slots=True)
class ConnectorPackageValidation:
    validation_id: str
    schema_version: str
    version: int
    lifecycle: PackageValidationLifecycle
    outcome: PackageValidationOutcome
    source_acquisition_id: str
    source_acquisition_digest: str
    source_handoff_id: str
    source_handoff_digest: str
    source_project_id: str
    source_acquired_by: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    validated_by: str
    validation_profile: str
    validator_version: str
    package_digest: str
    package_size_bytes: int
    manifest_path: str
    manifest_digest: str | None
    capability_ids: tuple[str, ...]
    schema_evidence: tuple[ValidatedSchemaEvidence, ...]
    checks: tuple[PackageValidationCheck, ...]
    limitations: tuple[str, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    validated_at: datetime
    source_integrity_accepted: bool = True
    manifest_schema_validation_completed: bool = True
    dependency_scan_completed: bool = False
    vulnerability_scan_completed: bool = False
    malware_scan_completed: bool = False
    secret_content_scan_completed: bool = False
    license_scan_completed: bool = False
    static_code_validation_completed: bool = False
    contract_validation_completed: bool = False
    runner_validation_completed: bool = False
    lab_validation_completed: bool = False
    package_signed: bool = False
    publisher_attested: bool = False
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
        for value, name in (
            (self.validation_id, "package validation id"),
            (self.schema_version, "package validation schema version"),
            (self.source_acquisition_id, "source acquisition id"),
            (self.source_handoff_id, "source handoff id"),
            (self.source_project_id, "source project id"),
            (self.source_acquired_by, "source acquisition operator id"),
            (self.source_custodied_by, "source custodian id"),
            (self.source_domain_reviewed_by, "source domain reviewer id"),
            (self.source_security_reviewed_by, "source security reviewer id"),
            (self.source_lab_operated_by, "source lab operator id"),
            (self.organization_id, "package validation organization id"),
            (self.environment_id, "package validation environment id"),
            (self.validated_by, "package validation operator id"),
            (self.validation_profile, "package validation profile"),
            (self.validator_version, "package validator version"),
        ):
            validate_stable_identifier(value, name)
        if self.version != 1 or self.lifecycle is not PackageValidationLifecycle.VALIDATING:
            raise ValueError("Package validation version or lifecycle is invalid")
        for value in (
            self.source_acquisition_digest,
            self.source_handoff_digest,
            self.package_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Package validation digest is invalid")
        if self.manifest_digest is not None and _DIGEST.fullmatch(self.manifest_digest) is None:
            raise ValueError("Package validation manifest digest is invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000:
            raise ValueError("Package validation package size is invalid")
        if self.manifest_path != "atlas-connector.yaml":
            raise ValueError("Package validation manifest path is invalid")
        if self.validated_by in {
            self.source_acquired_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
        }:
            raise ValueError("Package validation violates separation of duties")
        if not self.capability_ids or self.capability_ids != tuple(
            sorted(set(self.capability_ids))
        ):
            raise ValueError("Package validation capabilities are invalid")
        for capability_id in self.capability_ids:
            validate_stable_identifier(capability_id, "package validation capability id")
        if len({item.relative_path for item in self.schema_evidence}) != len(self.schema_evidence):
            raise ValueError("Package validation schema evidence is duplicated")
        if tuple(item.code for item in self.checks) != VALIDATION_CHECK_CODES:
            raise ValueError("Package validation check inventory is invalid")
        passed = all(item.state is PackageValidationCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is PackageValidationOutcome.PASSED):
            raise ValueError("Package validation outcome is inconsistent")
        manifest_passed = self.checks[2].state is PackageValidationCheckState.PASSED
        schemas_passed = self.checks[3].state is PackageValidationCheckState.PASSED
        if manifest_passed and self.manifest_digest is None:
            raise ValueError("Passed package manifest validation requires evidence")
        if schemas_passed and not self.schema_evidence:
            raise ValueError("Passed package schema validation requires evidence")
        if (
            not self.limitations
            or len(self.limitations) > 30
            or len(self.limitations) != len(set(self.limitations))
            or any(not value.strip() or len(value) > 500 for value in self.limitations)
        ):
            raise ValueError("Package validation limitations are invalid")
        if self.validated_at.tzinfo is None or not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Package validation timestamp or idempotency key is invalid")
        if not self.source_integrity_accepted or not self.manifest_schema_validation_completed:
            raise ValueError("Package validation prerequisite flags are invalid")
        if any(
            (
                self.dependency_scan_completed,
                self.vulnerability_scan_completed,
                self.malware_scan_completed,
                self.secret_content_scan_completed,
                self.license_scan_completed,
                self.static_code_validation_completed,
                self.contract_validation_completed,
                self.runner_validation_completed,
                self.lab_validation_completed,
                self.package_signed,
                self.publisher_attested,
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
            raise ValueError("Package validation cannot grant later-stage authority")
