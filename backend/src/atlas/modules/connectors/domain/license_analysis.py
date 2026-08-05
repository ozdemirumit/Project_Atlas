from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_RULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_CATEGORY = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")
_OBLIGATION = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")

LICENSE_CHECK_CODES = (
    "license.source.accepted",
    "license.archive.contract",
    "license.metadata.contract",
    "license.policy.trusted",
    "license.policy.coverage",
    "license.subjects.permitted",
)


class LicenseLifecycle(StrEnum):
    VALIDATING = "validating"


class LicenseOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class LicenseCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class LicenseCheckSeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


class LicenseSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LicenseDisposition(StrEnum):
    PERMITTED = "permitted"
    REVIEW_REQUIRED = "review_required"
    PROHIBITED = "prohibited"


class LicenseSubjectScope(StrEnum):
    PACKAGE = "package"
    SOURCE = "source"
    RUNTIME = "runtime"
    TRANSITIVE = "transitive"
    BUILD = "build"
    DATASET = "dataset"


@dataclass(frozen=True, slots=True)
class LicensePolicyRecord:
    rule_id: str
    category: str
    subject_scope: LicenseSubjectScope
    subject_fingerprint: str
    disposition: LicenseDisposition
    obligations: tuple[str, ...] = ()
    active: bool = True

    def __post_init__(self) -> None:
        if _RULE_ID.fullmatch(self.rule_id) is None or _CATEGORY.fullmatch(self.category) is None:
            raise ValueError("License policy record identity is invalid")
        if _DIGEST.fullmatch(self.subject_fingerprint) is None:
            raise ValueError("License policy subject fingerprint is invalid")
        if (
            self.obligations != tuple(sorted(self.obligations))
            or len(self.obligations) > 20
            or len(self.obligations) != len(set(self.obligations))
            or any(_OBLIGATION.fullmatch(item) is None for item in self.obligations)
        ):
            raise ValueError("License policy obligations are invalid")


@dataclass(frozen=True, slots=True)
class LicensePolicySnapshot:
    snapshot_id: str
    schema_version: str
    snapshot_version: str
    organization_id: str
    environment_id: str
    analysis_profile: str
    analyzer_version: str
    issued_at: datetime
    expires_at: datetime
    package_coverage_complete: bool
    source_coverage_complete: bool
    dependency_coverage_complete: bool
    obligation_coverage_complete: bool
    signing_key_id: str
    signature_verified: bool
    records: tuple[LicensePolicyRecord, ...]
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.snapshot_id,
            self.schema_version,
            self.snapshot_version,
            self.organization_id,
            self.environment_id,
            self.analysis_profile,
            self.analyzer_version,
            self.signing_key_id,
        ):
            validate_stable_identifier(value, "license policy snapshot identifier")
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("License policy snapshot time is invalid")
        if self.expires_at <= self.issued_at or _DIGEST.fullmatch(self.canonical_digest) is None:
            raise ValueError("License policy snapshot validity is invalid")
        if len(self.records) > 25_000 or self.records != tuple(
            sorted(
                self.records,
                key=lambda item: (item.subject_scope, item.subject_fingerprint, item.rule_id),
            )
        ):
            raise ValueError("License policy records are invalid")
        keys = [
            (item.subject_scope, item.subject_fingerprint, item.rule_id) for item in self.records
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("License policy records are duplicated")


@dataclass(frozen=True, slots=True)
class LicenseFinding:
    rule_id: str
    category: str
    severity: LicenseSeverity
    subject_scope: LicenseSubjectScope
    subject_fingerprint: str
    disposition: LicenseDisposition
    obligations: tuple[str, ...]
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        if _RULE_ID.fullmatch(self.rule_id) is None or _CATEGORY.fullmatch(self.category) is None:
            raise ValueError("License finding identity is invalid")
        if _DIGEST.fullmatch(self.subject_fingerprint) is None:
            raise ValueError("License finding fingerprint is invalid")
        if (
            self.obligations != tuple(sorted(self.obligations))
            or len(self.obligations) > 20
            or len(self.obligations) != len(set(self.obligations))
            or any(_OBLIGATION.fullmatch(item) is None for item in self.obligations)
        ):
            raise ValueError("License finding obligations are invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 300
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("License finding text is invalid")


@dataclass(frozen=True, slots=True)
class LicenseCheck:
    code: str
    state: LicenseCheckState
    severity: LicenseCheckSeverity
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in LICENSE_CHECK_CODES:
            raise ValueError("License check code is invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 500
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("License check text is invalid")
        expected = (
            LicenseCheckSeverity.INFORMATIONAL
            if self.state is LicenseCheckState.PASSED
            else LicenseCheckSeverity.ERROR
        )
        if self.severity is not expected:
            raise ValueError("License check severity is invalid")


@dataclass(frozen=True, slots=True)
class LicensePolicySnapshotSummary:
    snapshot_id: str
    snapshot_version: str
    snapshot_digest: str
    signing_key_id: str
    issued_at: datetime
    expires_at: datetime
    analysis_profile: str
    analyzer_version: str
    record_count: int
    package_coverage_complete: bool
    source_coverage_complete: bool
    dependency_coverage_complete: bool
    obligation_coverage_complete: bool
    fresh: bool

    def __post_init__(self) -> None:
        for value in (
            self.snapshot_id,
            self.snapshot_version,
            self.signing_key_id,
            self.analysis_profile,
            self.analyzer_version,
        ):
            validate_stable_identifier(value, "license policy summary identifier")
        if _DIGEST.fullmatch(self.snapshot_digest) is None:
            raise ValueError("License policy summary digest is invalid")
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("License policy summary time is invalid")
        if not 0 <= self.record_count <= 25_000:
            raise ValueError("License policy summary count is invalid")


@dataclass(frozen=True, slots=True)
class LicenseSubjectSummary:
    package_subject_count: int
    source_subject_count: int
    runtime_dependency_count: int
    transitive_dependency_count: int
    build_dependency_count: int
    scanned_subject_count: int
    permitted_count: int
    review_required_count: int
    prohibited_count: int
    unknown_count: int
    obligation_count: int
    unsatisfied_obligation_count: int
    subject_set_digest: str

    def __post_init__(self) -> None:
        counts = (
            self.package_subject_count,
            self.source_subject_count,
            self.runtime_dependency_count,
            self.transitive_dependency_count,
            self.build_dependency_count,
            self.scanned_subject_count,
            self.permitted_count,
            self.review_required_count,
            self.prohibited_count,
            self.unknown_count,
            self.obligation_count,
            self.unsatisfied_obligation_count,
        )
        if any(not 0 <= value <= 100_000 for value in counts):
            raise ValueError("License subject counts are invalid")
        expected_subjects = (
            self.package_subject_count
            + self.source_subject_count
            + self.runtime_dependency_count
            + self.transitive_dependency_count
            + self.build_dependency_count
        )
        if self.scanned_subject_count != expected_subjects:
            raise ValueError("License scanned subject count is inconsistent")
        dispositions = (
            self.permitted_count
            + self.review_required_count
            + self.prohibited_count
            + self.unknown_count
        )
        if dispositions != self.scanned_subject_count:
            raise ValueError("License disposition counts are inconsistent")
        if self.package_subject_count != 1 or self.source_subject_count != 1:
            raise ValueError("License package or source subject count is invalid")
        if self.unsatisfied_obligation_count > self.obligation_count:
            raise ValueError("License obligation counts are inconsistent")
        if _DIGEST.fullmatch(self.subject_set_digest) is None:
            raise ValueError("License subject-set digest is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageLicenseAnalysis:
    analysis_id: str
    schema_version: str
    version: int
    lifecycle: LicenseLifecycle
    outcome: LicenseOutcome
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
    dependency_set_digest: str
    policy_snapshot: LicensePolicySnapshotSummary
    subject_summary: LicenseSubjectSummary
    findings: tuple[LicenseFinding, ...]
    finding_set_digest: str
    analysis_digest: str
    checks: tuple[LicenseCheck, ...]
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
    vulnerability_scan_completed: bool = True
    malware_scan_completed: bool = True
    license_scan_completed: bool = True
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
            validate_stable_identifier(value, "license analysis identifier")
        if self.version != 1 or self.lifecycle is not LicenseLifecycle.VALIDATING:
            raise ValueError("License analysis version or lifecycle is invalid")
        for digest in (
            self.source_malware_analysis_digest,
            self.source_vulnerability_analysis_digest,
            self.source_static_dependency_analysis_digest,
            self.package_digest,
            self.inventory_digest,
            self.dependency_set_digest,
            self.finding_set_digest,
            self.analysis_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(digest) is None:
                raise ValueError("License analysis digest is invalid")
        prior_actors = {
            self.source_acquired_by,
            self.source_manifest_validated_by,
            self.source_inventoried_by,
            self.source_content_scanned_by,
            self.source_schema_validated_by,
            self.source_authority_validated_by,
            self.source_static_analyzed_by,
            self.source_vulnerability_analyzed_by,
            self.source_malware_analyzed_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
        }
        if self.analyzed_by in prior_actors:
            raise ValueError("License analysis violates separation of duties")
        if self.findings != tuple(
            sorted(
                self.findings,
                key=lambda item: (item.subject_scope, item.subject_fingerprint, item.rule_id),
            )
        ):
            raise ValueError("License findings are not deterministic")
        if tuple(item.code for item in self.checks) != LICENSE_CHECK_CODES:
            raise ValueError("License check set is invalid")
        passed = all(item.state is LicenseCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is LicenseOutcome.PASSED):
            raise ValueError("License analysis outcome is inconsistent")
        if self.promotion_blocked != (self.outcome is LicenseOutcome.FAILED):
            raise ValueError("License promotion state is inconsistent")
        if not self.limitations or len(self.limitations) != len(set(self.limitations)):
            raise ValueError("License limitations are invalid")
        if any(not item.strip() or len(item) > 500 for item in self.limitations):
            raise ValueError("License limitation text is invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000 or self.analyzed_at.tzinfo is None:
            raise ValueError("License package size or timestamp is invalid")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("License idempotency key is invalid")
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
            )
        ):
            raise ValueError("License completion flags are invalid")
        if any(
            (
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
            raise ValueError("License analysis violates the no-authority boundary")
