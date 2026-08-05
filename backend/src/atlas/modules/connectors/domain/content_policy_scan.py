from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")

CONTENT_POLICY_CHECK_CODES = (
    "content-policy.source.accepted",
    "content-policy.archive.contract",
    "content-policy.inventory.contract",
    "content-policy.secret-content",
    "content-policy.prohibited-content",
)


class ContentPolicyLifecycle(StrEnum):
    VALIDATING = "validating"


class ContentPolicyOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ContentPolicyCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class ContentPolicySeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


class ContentPolicyFindingKind(StrEnum):
    EMBEDDED_SECRET = "embedded_secret"
    PROHIBITED_CONTENT = "prohibited_content"


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
class ContentPolicyFinding:
    rule_code: str
    kind: ContentPolicyFindingKind
    severity: ContentPolicySeverity
    relative_path: str
    line_number: int | None
    evidence_fingerprint: str
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.rule_code, "content policy rule")
        if not _safe_path(self.relative_path):
            raise ValueError("Content policy finding path is invalid")
        if self.line_number is not None and not 1 <= self.line_number <= 100_000:
            raise ValueError("Content policy finding line is invalid")
        if _DIGEST.fullmatch(self.evidence_fingerprint) is None:
            raise ValueError("Content policy finding fingerprint is invalid")
        if self.severity is not ContentPolicySeverity.ERROR:
            raise ValueError("Content policy findings must block promotion")
        if (
            not self.summary.strip()
            or len(self.summary) > 300
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Content policy finding text is invalid")


@dataclass(frozen=True, slots=True)
class ContentPolicyCheck:
    code: str
    state: ContentPolicyCheckState
    severity: ContentPolicySeverity
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in CONTENT_POLICY_CHECK_CODES:
            raise ValueError("Content policy check code is invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 500
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Content policy check text is invalid")
        if (
            len(self.evidence_paths) > 500
            or len(self.evidence_paths) != len(set(self.evidence_paths))
            or any(not _safe_path(item) for item in self.evidence_paths)
        ):
            raise ValueError("Content policy check evidence is invalid")
        expected = (
            ContentPolicySeverity.INFORMATIONAL
            if self.state is ContentPolicyCheckState.PASSED
            else ContentPolicySeverity.ERROR
        )
        if self.severity is not expected:
            raise ValueError("Content policy check severity is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageContentPolicyScan:
    scan_id: str
    schema_version: str
    version: int
    lifecycle: ContentPolicyLifecycle
    outcome: ContentPolicyOutcome
    source_inventory_id: str
    source_inventory_digest: str
    source_validation_id: str
    source_validation_digest: str
    source_acquisition_id: str
    source_acquisition_digest: str
    source_handoff_id: str
    source_project_id: str
    source_acquired_by: str
    source_validated_by: str
    source_inventoried_by: str
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    scanned_by: str
    scan_profile: str
    scanner_version: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    dependency_set_digest: str
    scanned_file_count: int
    findings: tuple[ContentPolicyFinding, ...]
    finding_set_digest: str
    content_scan_digest: str
    checks: tuple[ContentPolicyCheck, ...]
    limitations: tuple[str, ...]
    promotion_blocked: bool
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    scanned_at: datetime
    secret_content_scan_completed: bool = True
    prohibited_content_scan_completed: bool = True
    vulnerability_scan_completed: bool = False
    malware_scan_completed: bool = False
    license_scan_completed: bool = False
    static_code_validation_completed: bool = False
    schema_semantic_validation_completed: bool = False
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
            self.scan_id,
            self.schema_version,
            self.source_inventory_id,
            self.source_validation_id,
            self.source_acquisition_id,
            self.source_handoff_id,
            self.source_project_id,
            self.source_acquired_by,
            self.source_validated_by,
            self.source_inventoried_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
            self.organization_id,
            self.environment_id,
            self.scanned_by,
            self.scan_profile,
            self.scanner_version,
        )
        for value in identifiers:
            validate_stable_identifier(value, "content policy identifier")
        if self.version != 1 or self.lifecycle is not ContentPolicyLifecycle.VALIDATING:
            raise ValueError("Content policy scan version or lifecycle is invalid")
        for digest in (
            self.source_inventory_digest,
            self.source_validation_digest,
            self.source_acquisition_digest,
            self.package_digest,
            self.inventory_digest,
            self.dependency_set_digest,
            self.finding_set_digest,
            self.content_scan_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(digest) is None:
                raise ValueError("Content policy scan digest is invalid")
        source_actors = {
            self.source_acquired_by,
            self.source_validated_by,
            self.source_inventoried_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
        }
        if self.scanned_by in source_actors:
            raise ValueError("Content policy scan violates separation of duties")
        if self.findings != tuple(
            sorted(
                self.findings,
                key=lambda item: (item.relative_path, item.line_number or 0, item.rule_code),
            )
        ):
            raise ValueError("Content policy findings order is invalid")
        if len(self.findings) > 500:
            raise ValueError("Content policy finding count is invalid")
        if tuple(item.code for item in self.checks) != CONTENT_POLICY_CHECK_CODES:
            raise ValueError("Content policy check set is invalid")
        passed = all(item.state is ContentPolicyCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is ContentPolicyOutcome.PASSED):
            raise ValueError("Content policy outcome is inconsistent")
        if self.promotion_blocked != (self.outcome is ContentPolicyOutcome.FAILED):
            raise ValueError("Content policy promotion state is inconsistent")
        if not self.limitations or len(self.limitations) != len(set(self.limitations)):
            raise ValueError("Content policy limitations are invalid")
        if any(not item.strip() or len(item) > 500 for item in self.limitations):
            raise ValueError("Content policy limitation text is invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000:
            raise ValueError("Content policy package size is invalid")
        if not 1 <= self.scanned_file_count <= 500 or self.scanned_at.tzinfo is None:
            raise ValueError("Content policy scan count or timestamp is invalid")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Content policy idempotency key is invalid")
        if not self.secret_content_scan_completed or not self.prohibited_content_scan_completed:
            raise ValueError("Content policy completion flags are invalid")
        if any(
            (
                self.vulnerability_scan_completed,
                self.malware_scan_completed,
                self.license_scan_completed,
                self.static_code_validation_completed,
                self.schema_semantic_validation_completed,
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
            raise ValueError("Content policy scan cannot grant later-stage authority")
