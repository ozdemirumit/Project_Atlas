from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")

SCHEMA_SEMANTICS_CHECK_CODES = (
    "schema-semantics.source.accepted",
    "schema-semantics.archive.contract",
    "schema-semantics.inventory.contract",
    "schema-semantics.configuration.contract",
    "schema-semantics.capability.contracts",
)


class SchemaSemanticsLifecycle(StrEnum):
    VALIDATING = "validating"


class SchemaSemanticsOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class SchemaSemanticsCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class SchemaSemanticsSeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


class SchemaSemanticsFindingKind(StrEnum):
    CONFIGURATION = "configuration"
    CAPABILITY_INPUT = "capability_input"
    CAPABILITY_OUTPUT = "capability_output"


class SchemaPurpose(StrEnum):
    CONFIGURATION = "configuration"
    CAPABILITY_INPUT = "capability_input"
    CAPABILITY_OUTPUT = "capability_output"


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
class SchemaSemanticsFinding:
    rule_code: str
    kind: SchemaSemanticsFindingKind
    severity: SchemaSemanticsSeverity
    relative_path: str
    json_pointer: str
    evidence_fingerprint: str
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.rule_code, "schema semantics rule")
        if not _safe_path(self.relative_path):
            raise ValueError("Schema semantics finding path is invalid")
        if len(self.json_pointer) > 300 or (
            self.json_pointer and not self.json_pointer.startswith("/")
        ):
            raise ValueError("Schema semantics finding pointer is invalid")
        if _DIGEST.fullmatch(self.evidence_fingerprint) is None:
            raise ValueError("Schema semantics finding fingerprint is invalid")
        if self.severity is not SchemaSemanticsSeverity.ERROR:
            raise ValueError("Schema semantics findings must block promotion")
        if (
            not self.summary.strip()
            or len(self.summary) > 300
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Schema semantics finding text is invalid")


@dataclass(frozen=True, slots=True)
class SchemaSemanticsCheck:
    code: str
    state: SchemaSemanticsCheckState
    severity: SchemaSemanticsSeverity
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in SCHEMA_SEMANTICS_CHECK_CODES:
            raise ValueError("Schema semantics check code is invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 500
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Schema semantics check text is invalid")
        if (
            len(self.evidence_paths) > 500
            or len(self.evidence_paths) != len(set(self.evidence_paths))
            or any(not _safe_path(item) for item in self.evidence_paths)
        ):
            raise ValueError("Schema semantics check evidence is invalid")
        expected = (
            SchemaSemanticsSeverity.INFORMATIONAL
            if self.state is SchemaSemanticsCheckState.PASSED
            else SchemaSemanticsSeverity.ERROR
        )
        if self.severity is not expected:
            raise ValueError("Schema semantics check severity is invalid")


@dataclass(frozen=True, slots=True)
class SchemaSemanticsSummary:
    relative_path: str
    digest: str
    purpose: SchemaPurpose
    capability_id: str | None
    property_count: int
    required_count: int
    closed_object: bool
    semantically_complete: bool

    def __post_init__(self) -> None:
        if not _safe_path(self.relative_path) or _DIGEST.fullmatch(self.digest) is None:
            raise ValueError("Schema semantics summary identity is invalid")
        if self.purpose is SchemaPurpose.CONFIGURATION:
            if self.capability_id is not None:
                raise ValueError("Configuration schema cannot bind a capability")
        elif self.capability_id is None:
            raise ValueError("Capability schema requires a capability identifier")
        else:
            validate_stable_identifier(self.capability_id, "schema capability")
        if not 0 <= self.property_count <= 500 or not 0 <= self.required_count <= 500:
            raise ValueError("Schema semantics summary count is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageSchemaSemanticsValidation:
    validation_id: str
    schema_version: str
    version: int
    lifecycle: SchemaSemanticsLifecycle
    outcome: SchemaSemanticsOutcome
    source_content_policy_scan_id: str
    source_content_policy_scan_digest: str
    source_inventory_id: str
    source_inventory_digest: str
    source_validation_id: str
    source_validation_digest: str
    source_acquisition_id: str
    source_acquisition_digest: str
    source_handoff_id: str
    source_project_id: str
    source_acquired_by: str
    source_manifest_validated_by: str
    source_inventoried_by: str
    source_content_scanned_by: str
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
    inventory_digest: str
    content_scan_digest: str
    schemas: tuple[SchemaSemanticsSummary, ...]
    schema_set_digest: str
    findings: tuple[SchemaSemanticsFinding, ...]
    finding_set_digest: str
    semantic_validation_digest: str
    checks: tuple[SchemaSemanticsCheck, ...]
    limitations: tuple[str, ...]
    promotion_blocked: bool
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    validated_at: datetime
    secret_content_scan_completed: bool = True
    prohibited_content_scan_completed: bool = True
    schema_semantic_validation_completed: bool = True
    vulnerability_scan_completed: bool = False
    malware_scan_completed: bool = False
    license_scan_completed: bool = False
    static_code_validation_completed: bool = False
    permission_behavior_validation_completed: bool = False
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
            self.validation_id,
            self.schema_version,
            self.source_content_policy_scan_id,
            self.source_inventory_id,
            self.source_validation_id,
            self.source_acquisition_id,
            self.source_handoff_id,
            self.source_project_id,
            self.source_acquired_by,
            self.source_manifest_validated_by,
            self.source_inventoried_by,
            self.source_content_scanned_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
            self.organization_id,
            self.environment_id,
            self.validated_by,
            self.validation_profile,
            self.validator_version,
        )
        for value in identifiers:
            validate_stable_identifier(value, "schema semantics identifier")
        if self.version != 1 or self.lifecycle is not SchemaSemanticsLifecycle.VALIDATING:
            raise ValueError("Schema semantics version or lifecycle is invalid")
        for digest in (
            self.source_content_policy_scan_digest,
            self.source_inventory_digest,
            self.source_validation_digest,
            self.source_acquisition_digest,
            self.package_digest,
            self.inventory_digest,
            self.content_scan_digest,
            self.schema_set_digest,
            self.finding_set_digest,
            self.semantic_validation_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(digest) is None:
                raise ValueError("Schema semantics digest is invalid")
        source_actors = {
            self.source_acquired_by,
            self.source_manifest_validated_by,
            self.source_inventoried_by,
            self.source_content_scanned_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
        }
        if self.validated_by in source_actors:
            raise ValueError("Schema semantics validation violates separation of duties")
        if not self.schemas or self.schemas != tuple(
            sorted(self.schemas, key=lambda item: item.relative_path)
        ):
            raise ValueError("Schema semantics summaries are invalid")
        if (
            self.findings
            != tuple(
                sorted(
                    self.findings,
                    key=lambda item: (item.relative_path, item.json_pointer, item.rule_code),
                )
            )
            or len(self.findings) > 500
        ):
            raise ValueError("Schema semantics findings are invalid")
        if tuple(item.code for item in self.checks) != SCHEMA_SEMANTICS_CHECK_CODES:
            raise ValueError("Schema semantics check set is invalid")
        passed = all(item.state is SchemaSemanticsCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is SchemaSemanticsOutcome.PASSED):
            raise ValueError("Schema semantics outcome is inconsistent")
        if self.promotion_blocked != (self.outcome is SchemaSemanticsOutcome.FAILED):
            raise ValueError("Schema semantics promotion state is inconsistent")
        if not self.limitations or len(self.limitations) != len(set(self.limitations)):
            raise ValueError("Schema semantics limitations are invalid")
        if any(not item.strip() or len(item) > 500 for item in self.limitations):
            raise ValueError("Schema semantics limitation text is invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000 or self.validated_at.tzinfo is None:
            raise ValueError("Schema semantics package size or timestamp is invalid")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Schema semantics idempotency key is invalid")
        if not all(
            (
                self.secret_content_scan_completed,
                self.prohibited_content_scan_completed,
                self.schema_semantic_validation_completed,
            )
        ):
            raise ValueError("Schema semantics completion flags are invalid")
        if any(
            (
                self.vulnerability_scan_completed,
                self.malware_scan_completed,
                self.license_scan_completed,
                self.static_code_validation_completed,
                self.permission_behavior_validation_completed,
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
            raise ValueError("Schema semantics validation cannot grant later-stage authority")
