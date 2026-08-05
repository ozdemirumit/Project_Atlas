from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")

AUTHORITY_BEHAVIOR_CHECK_CODES = (
    "authority-behavior.source.accepted",
    "authority-behavior.archive.contract",
    "authority-behavior.declarations.contract",
    "authority-behavior.capability.bindings",
    "authority-behavior.implementation.contract",
)


class AuthorityBehaviorLifecycle(StrEnum):
    VALIDATING = "validating"


class AuthorityBehaviorOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class AuthorityBehaviorCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class AuthorityBehaviorSeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


class BehaviorCategory(StrEnum):
    DECLARATION = "declaration"
    READ = "read"
    MUTATION = "mutation"
    NETWORK = "network"
    PROCESS = "process"
    FILESYSTEM = "filesystem"
    DYNAMIC_EXECUTION = "dynamic_execution"
    AMBIGUOUS = "ambiguous"


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
class AuthorityBehaviorFinding:
    rule_code: str
    category: BehaviorCategory
    severity: AuthorityBehaviorSeverity
    relative_path: str
    line_number: int
    evidence_fingerprint: str
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.rule_code, "authority behavior rule")
        if not _safe_path(self.relative_path) or not 0 <= self.line_number <= 1_000_000:
            raise ValueError("Authority behavior finding location is invalid")
        if _DIGEST.fullmatch(self.evidence_fingerprint) is None:
            raise ValueError("Authority behavior finding fingerprint is invalid")
        if self.severity is not AuthorityBehaviorSeverity.ERROR:
            raise ValueError("Authority behavior findings must block promotion")
        if (
            not self.summary.strip()
            or len(self.summary) > 300
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Authority behavior finding text is invalid")


@dataclass(frozen=True, slots=True)
class AuthorityBehaviorCheck:
    code: str
    state: AuthorityBehaviorCheckState
    severity: AuthorityBehaviorSeverity
    summary: str
    evidence_paths: tuple[str, ...]
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in AUTHORITY_BEHAVIOR_CHECK_CODES:
            raise ValueError("Authority behavior check code is invalid")
        if (
            not self.summary.strip()
            or len(self.summary) > 500
            or not self.remediation.strip()
            or len(self.remediation) > 500
        ):
            raise ValueError("Authority behavior check text is invalid")
        if (
            len(self.evidence_paths) > 500
            or len(self.evidence_paths) != len(set(self.evidence_paths))
            or any(not _safe_path(item) for item in self.evidence_paths)
        ):
            raise ValueError("Authority behavior check evidence is invalid")
        expected = (
            AuthorityBehaviorSeverity.INFORMATIONAL
            if self.state is AuthorityBehaviorCheckState.PASSED
            else AuthorityBehaviorSeverity.ERROR
        )
        if self.severity is not expected:
            raise ValueError("Authority behavior check severity is invalid")


@dataclass(frozen=True, slots=True)
class CapabilityBehaviorSummary:
    capability_id: str
    declared_class: str
    required_permission: str
    module_path: str
    source_digest: str
    observed_categories: tuple[BehaviorCategory, ...]
    network_call_count: int
    mutation_call_count: int
    declaration_matches: bool
    permission_matches: bool
    behavior_compatible: bool
    statically_resolved: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.capability_id, "behavior capability")
        validate_stable_identifier(self.required_permission, "behavior permission")
        if self.declared_class not in {f"C{value}" for value in range(6)}:
            raise ValueError("Capability behavior class is invalid")
        if not _safe_path(self.module_path) or _DIGEST.fullmatch(self.source_digest) is None:
            raise ValueError("Capability behavior source is invalid")
        if (
            not self.observed_categories
            or self.observed_categories != tuple(sorted(set(self.observed_categories)))
            or not 0 <= self.network_call_count <= 10_000
            or not 0 <= self.mutation_call_count <= 10_000
        ):
            raise ValueError("Capability behavior observations are invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageAuthorityBehaviorValidation:
    validation_id: str
    schema_version: str
    version: int
    lifecycle: AuthorityBehaviorLifecycle
    outcome: AuthorityBehaviorOutcome
    source_schema_semantics_validation_id: str
    source_schema_semantics_validation_digest: str
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
    source_custodied_by: str
    source_domain_reviewed_by: str
    source_security_reviewed_by: str
    source_lab_operated_by: str
    organization_id: str
    environment_id: str
    validated_by: str
    validation_profile: str
    analyzer_version: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    semantic_validation_digest: str
    capabilities: tuple[CapabilityBehaviorSummary, ...]
    capability_set_digest: str
    findings: tuple[AuthorityBehaviorFinding, ...]
    finding_set_digest: str
    behavior_validation_digest: str
    checks: tuple[AuthorityBehaviorCheck, ...]
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
    vulnerability_scan_completed: bool = False
    malware_scan_completed: bool = False
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
            self.validation_id,
            self.schema_version,
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
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
            self.organization_id,
            self.environment_id,
            self.validated_by,
            self.validation_profile,
            self.analyzer_version,
        )
        for value in identifiers:
            validate_stable_identifier(value, "authority behavior identifier")
        if self.version != 1 or self.lifecycle is not AuthorityBehaviorLifecycle.VALIDATING:
            raise ValueError("Authority behavior version or lifecycle is invalid")
        for digest in (
            self.source_schema_semantics_validation_digest,
            self.package_digest,
            self.inventory_digest,
            self.semantic_validation_digest,
            self.capability_set_digest,
            self.finding_set_digest,
            self.behavior_validation_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(digest) is None:
                raise ValueError("Authority behavior digest is invalid")
        source_actors = {
            self.source_acquired_by,
            self.source_manifest_validated_by,
            self.source_inventoried_by,
            self.source_content_scanned_by,
            self.source_schema_validated_by,
            self.source_custodied_by,
            self.source_domain_reviewed_by,
            self.source_security_reviewed_by,
            self.source_lab_operated_by,
        }
        if self.validated_by in source_actors:
            raise ValueError("Authority behavior validation violates separation of duties")
        if not self.capabilities or self.capabilities != tuple(
            sorted(self.capabilities, key=lambda item: item.capability_id)
        ):
            raise ValueError("Authority behavior capability summaries are invalid")
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
            raise ValueError("Authority behavior findings are invalid")
        if tuple(item.code for item in self.checks) != AUTHORITY_BEHAVIOR_CHECK_CODES:
            raise ValueError("Authority behavior check set is invalid")
        passed = all(item.state is AuthorityBehaviorCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is AuthorityBehaviorOutcome.PASSED):
            raise ValueError("Authority behavior outcome is inconsistent")
        if self.promotion_blocked != (self.outcome is AuthorityBehaviorOutcome.FAILED):
            raise ValueError("Authority behavior promotion state is inconsistent")
        if not self.limitations or len(self.limitations) != len(set(self.limitations)):
            raise ValueError("Authority behavior limitations are invalid")
        if any(not item.strip() or len(item) > 500 for item in self.limitations):
            raise ValueError("Authority behavior limitation text is invalid")
        if not 1 <= self.package_size_bytes <= 25_000_000 or self.validated_at.tzinfo is None:
            raise ValueError("Authority behavior package size or timestamp is invalid")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Authority behavior idempotency key is invalid")
        if not all(
            (
                self.secret_content_scan_completed,
                self.prohibited_content_scan_completed,
                self.schema_semantic_validation_completed,
                self.permission_behavior_validation_completed,
            )
        ):
            raise ValueError("Authority behavior completion flags are invalid")
        if any(
            (
                self.vulnerability_scan_completed,
                self.malware_scan_completed,
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
            raise ValueError("Authority behavior validation cannot grant later-stage authority")
