from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_RULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_CATEGORY = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")

CONTRACT_CHECK_CODES = (
    "contract.source.accepted",
    "contract.archive.contract",
    "contract.manifest.binding",
    "contract.schemas.binding",
    "contract.handlers.binding",
    "contract.tests.synthetic",
    "contract.coverage.complete",
)


class ContractLifecycle(StrEnum):
    VALIDATING = "validating"


class ContractOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ContractCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ContractCheckSeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


class ContractSeverity(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContractArtifactScope(StrEnum):
    MANIFEST = "manifest"
    CONFIGURATION_SCHEMA = "configuration_schema"
    CAPABILITY_SCHEMA = "capability_schema"
    HANDLER = "handler"
    CONTRACT_TEST = "contract_test"
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    COVERAGE = "coverage"


@dataclass(frozen=True, slots=True)
class ContractFinding:
    rule_id: str
    category: str
    severity: ContractSeverity
    artifact_scope: ContractArtifactScope
    subject_fingerprint: str
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        if _RULE_ID.fullmatch(self.rule_id) is None or _CATEGORY.fullmatch(self.category) is None:
            raise ValueError("Contract finding identity is invalid")
        if _DIGEST.fullmatch(self.subject_fingerprint) is None:
            raise ValueError("Contract finding fingerprint is invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 300
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Contract finding text is invalid")


@dataclass(frozen=True, slots=True)
class ContractCheck:
    code: str
    state: ContractCheckState
    severity: ContractCheckSeverity
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in CONTRACT_CHECK_CODES:
            raise ValueError("Contract check code is invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 500
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Contract check text is invalid")
        expected = (
            ContractCheckSeverity.INFORMATIONAL
            if self.state is ContractCheckState.PASSED
            else ContractCheckSeverity.ERROR
        )
        if self.severity is not expected:
            raise ValueError("Contract check severity is invalid")


@dataclass(frozen=True, slots=True)
class ContractCoverageSummary:
    manifest_count: int
    configuration_schema_count: int
    capability_count: int
    input_schema_count: int
    output_schema_count: int
    handler_count: int
    covered_capability_count: int
    contract_test_count: int
    synthetic_fixture_count: int
    orphan_artifact_count: int
    contract_set_digest: str

    def __post_init__(self) -> None:
        counts = (
            self.manifest_count,
            self.configuration_schema_count,
            self.capability_count,
            self.input_schema_count,
            self.output_schema_count,
            self.handler_count,
            self.covered_capability_count,
            self.contract_test_count,
            self.synthetic_fixture_count,
            self.orphan_artifact_count,
        )
        if any(not 0 <= value <= 10_000 for value in counts):
            raise ValueError("Contract coverage counts are invalid")
        if self.covered_capability_count > self.capability_count:
            raise ValueError("Contract capability coverage is invalid")
        if _DIGEST.fullmatch(self.contract_set_digest) is None:
            raise ValueError("Contract-set digest is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageContractValidation:
    validation_id: str
    schema_version: str
    version: int
    lifecycle: ContractLifecycle
    outcome: ContractOutcome
    source_license_analysis_id: str
    source_license_analysis_digest: str
    source_malware_analysis_id: str
    source_malware_analysis_digest: str
    source_vulnerability_analysis_id: str
    source_vulnerability_analysis_digest: str
    source_static_dependency_analysis_id: str
    source_static_dependency_analysis_digest: str
    source_authority_behavior_validation_id: str
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
    source_static_analyzed_by: str
    source_vulnerability_analyzed_by: str
    source_malware_analyzed_by: str
    source_license_analyzed_by: str
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
    dependency_set_digest: str
    coverage: ContractCoverageSummary
    findings: tuple[ContractFinding, ...]
    finding_set_digest: str
    validation_digest: str
    checks: tuple[ContractCheck, ...]
    limitations: tuple[str, ...]
    promotion_blocked: bool
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    validated_at: datetime
    secret_content_scan_completed: bool = True
    prohibited_content_scan_completed: bool = True
    schema_semantic_validation_completed: bool = True
    permission_behavior_validation_completed: bool = True
    static_code_validation_completed: bool = True
    vulnerability_scan_completed: bool = True
    malware_scan_completed: bool = True
    license_scan_completed: bool = True
    contract_validation_completed: bool = True
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
            self.source_license_analysis_id,
            self.source_malware_analysis_id,
            self.source_vulnerability_analysis_id,
            self.source_static_dependency_analysis_id,
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
            self.source_static_analyzed_by,
            self.source_vulnerability_analyzed_by,
            self.source_malware_analyzed_by,
            self.source_license_analyzed_by,
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
            validate_stable_identifier(value, "contract validation identifier")
        if self.version != 1 or self.lifecycle is not ContractLifecycle.VALIDATING:
            raise ValueError("Contract validation version or lifecycle is invalid")
        for digest in (
            self.source_license_analysis_digest,
            self.source_malware_analysis_digest,
            self.source_vulnerability_analysis_digest,
            self.source_static_dependency_analysis_digest,
            self.package_digest,
            self.inventory_digest,
            self.dependency_set_digest,
            self.finding_set_digest,
            self.validation_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(digest) is None:
                raise ValueError("Contract validation digest is invalid")
        if self.validated_by in self.source_actor_ids:
            raise ValueError("Contract validation violates separation of duties")
        if self.findings != tuple(
            sorted(
                self.findings,
                key=lambda item: (item.artifact_scope, item.subject_fingerprint, item.rule_id),
            )
        ):
            raise ValueError("Contract findings are not deterministic")
        if tuple(item.code for item in self.checks) != CONTRACT_CHECK_CODES:
            raise ValueError("Contract check set is invalid")
        passed = all(item.state is ContractCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is ContractOutcome.PASSED):
            raise ValueError("Contract validation outcome is inconsistent")
        if self.promotion_blocked != (self.outcome is ContractOutcome.FAILED):
            raise ValueError("Contract promotion state is inconsistent")
        if not self.limitations or len(self.limitations) != len(set(self.limitations)):
            raise ValueError("Contract limitations are invalid")
        if any(not item.strip() or len(item) > 500 for item in self.limitations):
            raise ValueError("Contract limitation text is invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000 or self.validated_at.tzinfo is None:
            raise ValueError("Contract package size or timestamp is invalid")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Contract idempotency key is invalid")
        if not all(
            (
                self.secret_content_scan_completed,
                self.prohibited_content_scan_completed,
                self.schema_semantic_validation_completed,
                self.permission_behavior_validation_completed,
                self.static_code_validation_completed,
                self.vulnerability_scan_completed,
                self.malware_scan_completed,
                self.license_scan_completed,
                self.contract_validation_completed,
            )
        ):
            raise ValueError("Contract completion flags are invalid")
        if any(
            (
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
            raise ValueError("Contract validation violates the no-authority boundary")

    @property
    def source_actor_ids(self) -> set[str]:
        return {
            self.source_acquired_by,
            self.source_manifest_validated_by,
            self.source_inventoried_by,
            self.source_content_scanned_by,
            self.source_schema_validated_by,
            self.source_authority_validated_by,
            self.source_static_analyzed_by,
            self.source_vulnerability_analyzed_by,
            self.source_malware_analyzed_by,
            self.source_license_analyzed_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
        }
