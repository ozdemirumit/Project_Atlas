from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_PRODUCT_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class LabSelfTestOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class LabCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class LabCheckSeverity(StrEnum):
    INFORMATIONAL = "informational"
    ERROR = "error"


LAB_CHECK_CODES = (
    "lab.source.accepted",
    "lab.plan.approved",
    "lab.package.integrity",
    "lab.access.lease",
    "lab.egress.restricted",
    "lab.tls.identity",
    "lab.authentication",
    "lab.package.import",
    "lab.capabilities.readonly",
    "lab.response.bounded",
    "lab.mutation.absent",
    "lab.session.closed",
    "lab.access.revoked",
    "lab.workspace.cleaned",
)
LAB_RUNNER_CHECK_CODES = (*LAB_CHECK_CODES[3:12], LAB_CHECK_CODES[13])


@dataclass(frozen=True, slots=True)
class LabCheck:
    code: str
    state: LabCheckState
    severity: LabCheckSeverity
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in LAB_CHECK_CODES:
            raise ValueError("Lab check code is invalid")
        if not self.summary.strip() or len(self.summary) > 500:
            raise ValueError("Lab check summary is invalid")
        if not self.remediation.strip() or len(self.remediation) > 500:
            raise ValueError("Lab check remediation is invalid")
        expected = (
            LabCheckSeverity.INFORMATIONAL
            if self.state is LabCheckState.PASSED
            else LabCheckSeverity.ERROR
        )
        if self.severity is not expected:
            raise ValueError("Lab check severity is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorLabPlan:
    plan_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    target_alias: str
    product_family: str
    product_version: str
    validation_profile: str
    adapter_contract: str
    allowed_capability_classes: tuple[str, ...]
    capability_count: int
    destination_references: tuple[str, ...]
    tls_trust_reference: str
    secret_reference_ids: tuple[str, ...]
    max_requests: int
    max_request_bytes: int
    max_response_bytes: int
    timeout_seconds: int
    approved_by: str
    credential_custodied_by: str
    approved_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.plan_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.target_alias,
            self.product_family,
            self.validation_profile,
            self.adapter_contract,
            self.tls_trust_reference,
            self.approved_by,
            self.credential_custodied_by,
        ):
            validate_stable_identifier(value, "lab plan identifier")
        for value in (*self.destination_references, *self.secret_reference_ids):
            validate_stable_identifier(value, "lab plan reference")
        if self.version != 1 or _PRODUCT_VERSION.fullmatch(self.product_version) is None:
            raise ValueError("Lab plan contract is invalid")
        if (
            not self.allowed_capability_classes
            or tuple(sorted(set(self.allowed_capability_classes)))
            != self.allowed_capability_classes
            or any(item not in {"C0", "C1"} for item in self.allowed_capability_classes)
        ):
            raise ValueError("Lab plan capability classes are invalid")
        if (
            self.capability_count < 1
            or not self.destination_references
            or len(set(self.destination_references)) != len(self.destination_references)
            or not self.secret_reference_ids
            or len(set(self.secret_reference_ids)) != len(self.secret_reference_ids)
        ):
            raise ValueError("Lab plan bindings are invalid")
        if not (
            1 <= self.max_requests <= 1_000
            and 1 <= self.max_request_bytes <= 1_048_576
            and 1 <= self.max_response_bytes <= 4_194_304
            and 1 <= self.timeout_seconds <= 900
        ):
            raise ValueError("Lab plan execution bounds are invalid")
        if (
            self.approved_by == self.credential_custodied_by
            or self.approved_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.approved_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Lab plan approval evidence is invalid")


@dataclass(frozen=True, slots=True)
class LabExecutionLease:
    lease_id: str
    plan_id: str
    credential_handle: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        for value in (self.lease_id, self.plan_id, self.credential_handle):
            validate_stable_identifier(value, "lab lease identifier")
        if (
            self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("Lab lease timing is invalid")


@dataclass(frozen=True, slots=True)
class LabExecutionResult:
    adapter_contract: str
    runner_runtime: str
    observed_product_version: str
    checks: tuple[LabCheck, ...]
    capability_count: int
    tested_capability_count: int
    request_count: int
    request_bytes: int
    response_bytes: int
    duration_ms: int
    evidence_digest: str
    lease_issued: bool
    session_closed: bool
    workspace_removed: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.adapter_contract, "lab adapter contract")
        validate_stable_identifier(self.runner_runtime, "lab runner runtime")
        if _PRODUCT_VERSION.fullmatch(self.observed_product_version) is None:
            raise ValueError("Lab observed product version is invalid")
        if tuple(item.code for item in self.checks) != LAB_RUNNER_CHECK_CODES:
            raise ValueError("Lab runner check set is invalid")
        if (
            min(
                self.capability_count,
                self.tested_capability_count,
                self.request_count,
                self.request_bytes,
                self.response_bytes,
                self.duration_ms,
            )
            < 0
        ):
            raise ValueError("Lab execution metrics are invalid")
        if self.tested_capability_count > self.capability_count:
            raise ValueError("Lab execution coverage is invalid")
        if _DIGEST.fullmatch(self.evidence_digest) is None:
            raise ValueError("Lab execution digest is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageLabSelfTest:
    self_test_id: str
    schema_version: str
    version: int
    outcome: LabSelfTestOutcome
    source_runner_validation_id: str
    source_runner_validation_digest: str
    source_contract_validation_id: str
    source_contract_validation_digest: str
    source_inventory_id: str
    source_acquisition_id: str
    source_project_id: str
    source_runner_validated_by: str
    source_actor_set_digest: str
    lab_plan_id: str
    lab_plan_digest: str
    lab_plan_approved_by: str
    credential_custodied_by: str
    organization_id: str
    environment_id: str
    validated_by: str
    target_alias: str
    product_family: str
    observed_product_version: str
    validation_profile: str
    adapter_contract: str
    runner_runtime: str
    package_digest: str
    package_size_bytes: int
    inventory_digest: str
    capability_count: int
    tested_capability_count: int
    request_count: int
    request_bytes: int
    response_bytes: int
    checks: tuple[LabCheck, ...]
    duration_ms: int
    evidence_digest: str
    lease_issued: bool
    lease_released: bool
    credentials_revoked: bool
    session_closed: bool
    workspace_removed: bool
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
    runner_validation_completed: bool = True
    lab_validation_completed: bool = True
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
        for value in (
            self.self_test_id,
            self.schema_version,
            self.source_runner_validation_id,
            self.source_contract_validation_id,
            self.source_inventory_id,
            self.source_acquisition_id,
            self.source_project_id,
            self.source_runner_validated_by,
            self.lab_plan_id,
            self.lab_plan_approved_by,
            self.credential_custodied_by,
            self.organization_id,
            self.environment_id,
            self.validated_by,
            self.target_alias,
            self.product_family,
            self.validation_profile,
            self.adapter_contract,
            self.runner_runtime,
        ):
            validate_stable_identifier(value, "lab self-test identifier")
        if _PRODUCT_VERSION.fullmatch(self.observed_product_version) is None:
            raise ValueError("Lab self-test product version is invalid")
        for value in (
            self.source_runner_validation_digest,
            self.source_contract_validation_digest,
            self.source_actor_set_digest,
            self.lab_plan_digest,
            self.package_digest,
            self.inventory_digest,
            self.evidence_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Lab self-test digest is invalid")
        if self.version != 1 or tuple(item.code for item in self.checks) != LAB_CHECK_CODES:
            raise ValueError("Lab self-test contract is invalid")
        passed = all(item.state is LabCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is LabSelfTestOutcome.PASSED):
            raise ValueError("Lab self-test outcome is inconsistent")
        if self.promotion_blocked != (self.outcome is LabSelfTestOutcome.FAILED):
            raise ValueError("Lab self-test promotion state is inconsistent")
        if (
            min(
                self.package_size_bytes,
                self.capability_count,
                self.tested_capability_count,
                self.request_count,
                self.request_bytes,
                self.response_bytes,
                self.duration_ms,
            )
            < 0
            or self.package_size_bytes == 0
        ):
            raise ValueError("Lab self-test metrics are invalid")
        if self.tested_capability_count > self.capability_count:
            raise ValueError("Lab self-test coverage is invalid")
        if not 8 <= len(self.idempotency_key) <= 128:
            raise ValueError("Lab self-test idempotency key is invalid")
        if self.validated_at.tzinfo is None or not self.limitations:
            raise ValueError("Lab self-test evidence is incomplete")
        if len(self.limitations) != len(set(self.limitations)) or any(
            not item.strip() or len(item) > 500 for item in self.limitations
        ):
            raise ValueError("Lab self-test limitations are invalid")
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
                self.runner_validation_completed,
                self.lab_validation_completed,
            )
        ):
            raise ValueError("Lab self-test completion flags are invalid")
        if any(
            (
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
            raise ValueError("Lab self-test violates the no-authority boundary")
