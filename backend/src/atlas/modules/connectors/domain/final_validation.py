from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")

FINAL_VALIDATION_STAGE_CODES = (
    "acquisition",
    "validation-intake",
    "supply-chain-inventory",
    "content-policy",
    "schema-semantics",
    "authority-behavior",
    "static-dependency",
    "vulnerability",
    "malware",
    "license",
    "contract",
    "runner",
    "lab",
)

FINAL_VALIDATION_CHECK_CODES = (
    "final.policy.accepted",
    "final.lineage.complete",
    *(f"final.stage.{stage}" for stage in FINAL_VALIDATION_STAGE_CODES),
    "final.coverage.complete",
    "final.risks.classified",
    "final.no-authority",
)


class FinalValidationOutcome(StrEnum):
    ELIGIBLE = "eligible_for_human_approval"
    BLOCKED = "blocked"


class FinalValidationCheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class FinalValidationSeverity(StrEnum):
    INFORMATIONAL = "informational"
    WARNING = "warning"
    ERROR = "error"


class FinalRiskClassification(StrEnum):
    DISCLOSED_LIMITATION = "disclosed_limitation"
    BLOCKING_POLICY = "blocking_policy"


@dataclass(frozen=True, slots=True)
class FinalValidationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_stage_codes: tuple[str, ...]
    maximum_evidence_age_days: int
    maximum_disclosed_limitations: int
    require_complete_capability_coverage: bool
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        for value in (
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.signed_by,
        ):
            validate_stable_identifier(value, "final validation policy identifier")
        if (
            self.version != 1
            or self.required_stage_codes != FINAL_VALIDATION_STAGE_CODES
            or not 1 <= self.maximum_evidence_age_days <= 3650
            or not 0 <= self.maximum_disclosed_limitations <= 500
            or not self.require_complete_capability_coverage
            or not self.signature_verified
        ):
            raise ValueError("Final validation policy contract is invalid")
        if (
            self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
        ):
            raise ValueError("Final validation policy evidence is invalid")


@dataclass(frozen=True, slots=True)
class FinalStageEvidence:
    stage_code: str
    evidence_id: str
    evidence_digest: str
    observed_at: datetime
    outcome: str
    promotion_blocked: bool
    finding_count: int
    limitation_count: int

    def __post_init__(self) -> None:
        if self.stage_code not in FINAL_VALIDATION_STAGE_CODES:
            raise ValueError("Final validation stage is invalid")
        validate_stable_identifier(self.evidence_id, "final validation evidence identifier")
        if _DIGEST.fullmatch(self.evidence_digest) is None:
            raise ValueError("Final validation evidence digest is invalid")
        if (
            self.observed_at.tzinfo is None
            or not self.outcome
            or len(self.outcome) > 64
            or min(self.finding_count, self.limitation_count) < 0
        ):
            raise ValueError("Final validation stage evidence is invalid")


@dataclass(frozen=True, slots=True)
class FinalRiskSummary:
    code: str
    source_stage: str
    source_evidence_id: str
    source_evidence_digest: str
    classification: FinalRiskClassification
    severity: FinalValidationSeverity
    blocking: bool
    occurrence_count: int
    next_step: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.code, "final validation risk code")
        validate_stable_identifier(
            self.source_evidence_id, "final validation risk source identifier"
        )
        if self.source_stage not in FINAL_VALIDATION_STAGE_CODES:
            raise ValueError("Final validation risk stage is invalid")
        if _DIGEST.fullmatch(self.source_evidence_digest) is None:
            raise ValueError("Final validation risk digest is invalid")
        if not 1 <= self.occurrence_count <= 500 or not 1 <= len(self.next_step) <= 500:
            raise ValueError("Final validation risk summary is invalid")


@dataclass(frozen=True, slots=True)
class FinalValidationCheck:
    code: str
    state: FinalValidationCheckState
    severity: FinalValidationSeverity
    summary: str
    remediation: str

    def __post_init__(self) -> None:
        if self.code not in FINAL_VALIDATION_CHECK_CODES:
            raise ValueError("Final validation check code is invalid")
        if not 1 <= len(self.summary) <= 500 or not 1 <= len(self.remediation) <= 500:
            raise ValueError("Final validation check text is invalid")


@dataclass(frozen=True, slots=True)
class ConnectorPackageFinalValidation:
    validation_id: str
    schema_version: str
    version: int
    outcome: FinalValidationOutcome
    source_lab_self_test_id: str
    source_lab_self_test_digest: str
    source_handoff_id: str
    source_handoff_digest: str
    source_project_id: str
    source_actor_set_digest: str
    organization_id: str
    environment_id: str
    validated_by: str
    policy_id: str
    policy_digest: str
    policy_version: str
    package_digest: str
    inventory_digest: str
    product_family: str
    observed_product_version: str
    capability_count: int
    tested_capability_count: int
    stage_evidence: tuple[FinalStageEvidence, ...]
    stage_count: int
    passed_stage_count: int
    finding_count: int
    limitation_count: int
    blocking_risk_count: int
    risks: tuple[FinalRiskSummary, ...]
    checks: tuple[FinalValidationCheck, ...]
    limitations: tuple[str, ...]
    eligible_for_human_approval: bool
    promotion_blocked: bool
    evidence_digest: str
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
    final_validation_completed: bool = True
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
            self.validation_id,
            self.schema_version,
            self.source_lab_self_test_id,
            self.source_handoff_id,
            self.source_project_id,
            self.organization_id,
            self.environment_id,
            self.validated_by,
            self.policy_id,
            self.policy_version,
            self.product_family,
        ):
            validate_stable_identifier(value, "final validation identifier")
        for value in (
            self.source_lab_self_test_digest,
            self.source_handoff_digest,
            self.source_actor_set_digest,
            self.policy_digest,
            self.package_digest,
            self.inventory_digest,
            self.evidence_digest,
            self.canonical_digest,
            self.request_fingerprint,
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError("Final validation digest is invalid")
        if (
            self.version != 1
            or tuple(item.stage_code for item in self.stage_evidence)
            != FINAL_VALIDATION_STAGE_CODES
            or tuple(item.code for item in self.checks) != FINAL_VALIDATION_CHECK_CODES
        ):
            raise ValueError("Final validation contract is invalid")
        passed = all(item.state is FinalValidationCheckState.PASSED for item in self.checks)
        if passed != (self.outcome is FinalValidationOutcome.ELIGIBLE):
            raise ValueError("Final validation outcome is inconsistent")
        if self.eligible_for_human_approval != passed or self.promotion_blocked == passed:
            raise ValueError("Final validation eligibility is inconsistent")
        if (
            self.stage_count != len(FINAL_VALIDATION_STAGE_CODES)
            or self.passed_stage_count
            != sum(not item.promotion_blocked for item in self.stage_evidence)
            or self.blocking_risk_count != sum(item.blocking for item in self.risks)
            or min(
                self.capability_count,
                self.tested_capability_count,
                self.finding_count,
                self.limitation_count,
            )
            < 0
            or self.tested_capability_count > self.capability_count
        ):
            raise ValueError("Final validation metrics are invalid")
        if not 8 <= len(self.idempotency_key) <= 128 or self.validated_at.tzinfo is None:
            raise ValueError("Final validation request evidence is invalid")
        if not self.limitations or len(self.limitations) != len(set(self.limitations)):
            raise ValueError("Final validation limitations are invalid")
        if any(not item.strip() or len(item) > 500 for item in self.limitations):
            raise ValueError("Final validation limitation text is invalid")
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
                self.final_validation_completed,
            )
        ):
            raise ValueError("Final validation completion flags are invalid")
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
            raise ValueError("Final validation violates the no-authority boundary")
