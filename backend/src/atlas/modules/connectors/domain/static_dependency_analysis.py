from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")

STATIC_DEPENDENCY_CHECK_CODES = (
    "static-dependency.source.accepted",
    "static-dependency.archive.contract",
    "static-dependency.source.structure",
    "static-dependency.import.graph",
    "static-dependency.metadata.hygiene",
)


class StaticDependencyLifecycle(StrEnum):
    VALIDATING = "validating"


class StaticDependencyOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class StaticDependencyCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class StaticDependencySeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


class StaticDependencyCategory(StrEnum):
    SOURCE_STRUCTURE = "source_structure"
    IMPORT_GRAPH = "import_graph"
    EXCEPTION_HANDLING = "exception_handling"
    STATE_MANAGEMENT = "state_management"
    TYPE_CONTRACT = "type_contract"
    COMPLEXITY = "complexity"
    DEPENDENCY_METADATA = "dependency_metadata"
    DEPENDENCY_LOCK = "dependency_lock"


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
class StaticDependencyFinding:
    rule_code: str
    category: StaticDependencyCategory
    severity: StaticDependencySeverity
    relative_path: str
    line_number: int
    evidence_fingerprint: str
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.rule_code, "static dependency rule")
        if not _safe_path(self.relative_path) or not 0 <= self.line_number <= 1_000_000:
            raise ValueError("Static dependency finding location is invalid")
        if _DIGEST.fullmatch(self.evidence_fingerprint) is None:
            raise ValueError("Static dependency finding fingerprint is invalid")
        if self.severity is not StaticDependencySeverity.ERROR:
            raise ValueError("Static dependency findings must block promotion")
        if (
            not self.summary.strip()
            or len(self.summary) > 300
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Static dependency finding text is invalid")


@dataclass(frozen=True, slots=True)
class StaticDependencyCheck:
    code: str
    state: StaticDependencyCheckState
    severity: StaticDependencySeverity
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in STATIC_DEPENDENCY_CHECK_CODES:
            raise ValueError("Static dependency check code is invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 500
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Static dependency check text is invalid")
        if (
            len(self.evidence_paths) > 500
            or len(self.evidence_paths) != len(set(self.evidence_paths))
            or any(not _safe_path(item) for item in self.evidence_paths)
        ):
            raise ValueError("Static dependency check evidence is invalid")
        expected = (
            StaticDependencySeverity.INFORMATIONAL
            if self.state is StaticDependencyCheckState.PASSED
            else StaticDependencySeverity.ERROR
        )
        if self.severity is not expected:
            raise ValueError("Static dependency check severity is invalid")


@dataclass(frozen=True, slots=True)
class StaticSourceSummary:
    source_file_count: int
    module_count: int
    function_count: int
    import_count: int
    external_import_count: int
    unresolved_import_count: int
    source_set_digest: str

    def __post_init__(self) -> None:
        counts = (
            self.source_file_count,
            self.module_count,
            self.function_count,
            self.import_count,
            self.external_import_count,
            self.unresolved_import_count,
        )
        if any(not 0 <= value <= 100_000 for value in counts) or self.source_file_count < 1:
            raise ValueError("Static source summary counts are invalid")
        if _DIGEST.fullmatch(self.source_set_digest) is None:
            raise ValueError("Static source summary digest is invalid")


@dataclass(frozen=True, slots=True)
class DependencyHygieneSummary:
    runtime_dependency_count: int
    build_dependency_count: int
    imported_dependency_count: int
    dependency_lock_present: bool
    dependency_lock_required: bool
    dependency_set_digest: str
    metadata_consistent: bool
    imports_reconciled: bool
    deterministic_constraints: bool

    def __post_init__(self) -> None:
        counts = (
            self.runtime_dependency_count,
            self.build_dependency_count,
            self.imported_dependency_count,
        )
        if any(not 0 <= value <= 10_000 for value in counts):
            raise ValueError("Dependency hygiene counts are invalid")
        if _DIGEST.fullmatch(self.dependency_set_digest) is None:
            raise ValueError("Dependency hygiene digest is invalid")
        if self.dependency_lock_required != (self.runtime_dependency_count > 0):
            raise ValueError("Dependency lock requirement is inconsistent")


@dataclass(frozen=True, slots=True)
class ConnectorPackageStaticDependencyAnalysis:
    analysis_id: str
    schema_version: str
    version: int
    lifecycle: StaticDependencyLifecycle
    outcome: StaticDependencyOutcome
    source_authority_behavior_validation_id: str
    source_authority_behavior_validation_digest: str
    source_schema_semantics_validation_id: str
    source_content_policy_scan_id: str
    source_inventory_id: str
    source_validation_id: str
    source_acquisition_id: str
    source_handoff_id: str
    source_project_id: str
    source_acquired_by: str
    source_manifest_validated_by: str
    source_inventoried_by: str
    source_content_scanned_by: str
    source_schema_validated_by: str
    source_authority_validated_by: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    analyzed_by: str
    analysis_profile: str
    analyzer_version: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    source_summary: StaticSourceSummary
    dependency_summary: DependencyHygieneSummary
    findings: tuple[StaticDependencyFinding, ...]
    finding_set_digest: str
    analysis_digest: str
    checks: tuple[StaticDependencyCheck, ...]
    limitations: tuple[str, ...]
    promotion_blocked: bool
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    analyzed_at: datetime
    secret_content_scan_completed: bool = True
    prohibited_content_scan_completed: bool = True
    schema_semantic_validation_completed: bool = True
    permission_behavior_validation_completed: bool = True
    static_code_validation_completed: bool = True
    vulnerability_scan_completed: bool = False
    malware_scan_completed: bool = False
    license_scan_completed: bool = False
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
            self.analysis_id,
            self.schema_version,
            self.source_authority_behavior_validation_id,
            self.source_schema_semantics_validation_id,
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
            self.source_schema_validated_by,
            self.source_authority_validated_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
            self.organization_id,
            self.environment_id,
            self.analyzed_by,
            self.analysis_profile,
            self.analyzer_version,
        )
        for value in identifiers:
            validate_stable_identifier(value, "static dependency identifier")
        if self.version != 1 or self.lifecycle is not StaticDependencyLifecycle.VALIDATING:
            raise ValueError("Static dependency version or lifecycle is invalid")
        for digest in (
            self.source_authority_behavior_validation_digest,
            self.package_digest,
            self.inventory_digest,
            self.finding_set_digest,
            self.analysis_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(digest) is None:
                raise ValueError("Static dependency digest is invalid")
        source_actors = {
            self.source_acquired_by,
            self.source_manifest_validated_by,
            self.source_inventoried_by,
            self.source_content_scanned_by,
            self.source_schema_validated_by,
            self.source_authority_validated_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
        }
        if self.analyzed_by in source_actors:
            raise ValueError("Static dependency analysis violates separation of duties")
        if (
            self.findings
            != tuple(
                sorted(
                    self.findings,
                    key=lambda item: (item.relative_path, item.line_number, item.rule_code),
                )
            )
            or len(self.findings) > 500
        ):
            raise ValueError("Static dependency findings are invalid")
        if tuple(item.code for item in self.checks) != STATIC_DEPENDENCY_CHECK_CODES:
            raise ValueError("Static dependency check set is invalid")
        passed = all(item.state is StaticDependencyCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is StaticDependencyOutcome.PASSED):
            raise ValueError("Static dependency outcome is inconsistent")
        if self.promotion_blocked != (self.outcome is StaticDependencyOutcome.FAILED):
            raise ValueError("Static dependency promotion state is inconsistent")
        if not self.limitations or len(self.limitations) != len(set(self.limitations)):
            raise ValueError("Static dependency limitations are invalid")
        if any(not item.strip() or len(item) > 500 for item in self.limitations):
            raise ValueError("Static dependency limitation text is invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000 or self.analyzed_at.tzinfo is None:
            raise ValueError("Static dependency package size or timestamp is invalid")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Static dependency idempotency key is invalid")
        if not all(
            (
                self.secret_content_scan_completed,
                self.prohibited_content_scan_completed,
                self.schema_semantic_validation_completed,
                self.permission_behavior_validation_completed,
                self.static_code_validation_completed,
            )
        ):
            raise ValueError("Static dependency completion flags are invalid")
        if any(
            (
                self.vulnerability_scan_completed,
                self.malware_scan_completed,
                self.license_scan_completed,
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
            raise ValueError("Static dependency analysis cannot grant later-stage authority")
